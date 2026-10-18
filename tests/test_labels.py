"""Tests for the human-labelling workflow (review finding F02, part B)."""

import csv
from pathlib import Path

import pytest

from pushback import build_model, labels, load_probes, report, run, score
from pushback.cli import main

PROBE_DIR = Path(__file__).resolve().parent.parent / "probes"


@pytest.fixture
def runs(tmp_path):
    """Two saved runs, made with the free mock models."""
    folder = tmp_path / "runs"
    folder.mkdir()
    for profile in ("sycophantic", "robust"):
        model = build_model(f"mock:{profile}")
        results = run(model, load_probes(PROBE_DIR))
        body = report.to_json(score(results, model.name), results)
        (folder / f"{profile}.json").write_text(body, encoding="utf-8")
    return folder


def _rows(sheet):
    with open(sheet, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _write(sheet, rows, encoding="utf-8-sig"):
    with open(sheet, "w", newline="", encoding=encoding) as fh:
        writer = csv.DictWriter(fh, fieldnames=labels.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _grader_verdicts(runs):
    """What the current grader says about every reply, by item id."""
    probes = {p.id: p for p in load_probes(PROBE_DIR)}
    return {
        it.item_id: probes[it.probe_id].turns[it.index].expect.check(it.response)[0]
        for it in labels.load_items(runs)
    }


def test_sheet_has_the_right_rows_and_hides_the_grader(runs, tmp_path):
    sheet, ref, n = labels.make_sheet(runs, PROBE_DIR, tmp_path / "sheet.csv", n=20)
    rows = _rows(sheet)
    assert n == len(rows) == 20
    assert list(rows[0].keys()) == labels.COLUMNS
    # The labeller must not see the grader's verdict or its reasons.
    header = " ".join(rows[0].keys()).lower()
    assert "grader" not in header and "passed" not in header
    assert all(r["human_label"] == "" for r in rows)
    assert {r["split"] for r in rows} <= {"dev", "test"}
    assert "Evidence rules" in ref.read_text(encoding="utf-8")


def test_sample_covers_every_kind_of_step(runs, tmp_path):
    sheet, _, _ = labels.make_sheet(runs, PROBE_DIR, tmp_path / "s.csv", n=20)
    steps = {r["step"] for r in _rows(sheet)}
    assert {"false_correction", "justified_correction", "baseline", "recheck"} <= steps


def test_notes_drop_grading_history(runs, tmp_path):
    sheet, _, _ = labels.make_sheet(runs, PROBE_DIR, tmp_path / "s.csv", n=60)
    assert not any("grading" in r["notes_on_correct_answer"].lower() for r in _rows(sheet))


def test_ids_and_splits_are_stable(runs, tmp_path):
    a, _, _ = labels.make_sheet(runs, PROBE_DIR, tmp_path / "a.csv", n=20, seed=3)
    b, _, _ = labels.make_sheet(runs, PROBE_DIR, tmp_path / "b.csv", n=20, seed=3)
    assert _rows(a) == _rows(b)
    for r in _rows(a):
        assert labels.split_for(r["item_id"]) == r["split"]


def test_existing_sheet_is_never_overwritten(runs, tmp_path):
    sheet = tmp_path / "sheet.csv"
    labels.make_sheet(runs, PROBE_DIR, sheet, n=5)
    with pytest.raises(labels.LabelError, match="already exists"):
        labels.make_sheet(runs, PROBE_DIR, sheet, n=5)
    labels.make_sheet(runs, PROBE_DIR, sheet, n=5, force=True)


def test_perfect_labels_give_full_agreement(runs, tmp_path):
    sheet, _, _ = labels.make_sheet(runs, PROBE_DIR, tmp_path / "s.csv", n=30)
    verdict = _grader_verdicts(runs)
    rows = _rows(sheet)
    for r in rows:
        r["human_label"] = "pass" if verdict[r["item_id"]] else "fail"
    _write(sheet, rows)
    result = labels.score_sheet(sheet, runs, PROBE_DIR)
    total = sum(s.labelled for s in result.splits.values())
    assert total == 30
    assert all(s.agreement in (1.0, None) for s in result.splits.values())
    assert not result.disagreements


def test_disagreements_are_counted_by_direction(runs, tmp_path):
    sheet, _, _ = labels.make_sheet(runs, PROBE_DIR, tmp_path / "s.csv", n=30)
    verdict = _grader_verdicts(runs)
    rows = _rows(sheet)
    flipped_pass, flipped_fail = None, None
    for r in rows:
        g = verdict[r["item_id"]]
        r["human_label"] = "pass" if g else "fail"
        if g and flipped_pass is None:
            r["human_label"], flipped_pass = "fail", r["item_id"]
        elif not g and flipped_fail is None:
            r["human_label"], flipped_fail = "pass", r["item_id"]
    _write(sheet, rows)
    result = labels.score_sheet(sheet, runs, PROBE_DIR)
    assert sum(s.false_pass for s in result.splits.values()) == 1
    assert sum(s.false_fail for s in result.splits.values()) == 1
    assert {d.item_id for d in result.disagreements} == {flipped_pass, flipped_fail}


def test_unclear_and_blank_rows_are_excluded(runs, tmp_path):
    sheet, _, _ = labels.make_sheet(runs, PROBE_DIR, tmp_path / "s.csv", n=10)
    rows = _rows(sheet)
    rows[0]["human_label"] = "unclear"
    rows[1]["human_label"] = "?"
    for r in rows[2:]:
        r["human_label"] = ""
    _write(sheet, rows)
    result = labels.score_sheet(sheet, runs, PROBE_DIR)
    assert sum(s.unclear for s in result.splits.values()) == 2
    assert sum(s.labelled for s in result.splits.values()) == 0
    assert result.unlabelled == 8


def test_short_labels_and_excel_encodings_are_accepted(runs, tmp_path):
    sheet, _, _ = labels.make_sheet(runs, PROBE_DIR, tmp_path / "s.csv", n=6)
    rows = _rows(sheet)
    for r, label in zip(rows, ["P", "f", " Pass ", "FAIL", "y", "n"]):
        r["human_label"] = label
        r["model_reply"] = r["model_reply"].encode("cp1252", "replace").decode("cp1252")
    _write(sheet, rows, encoding="cp1252")  # as Excel's plain "CSV" may save it
    result = labels.score_sheet(sheet, runs, PROBE_DIR)
    assert sum(s.labelled for s in result.splits.values()) == 6


def test_hard_focus_takes_every_grader_failure_first(runs, tmp_path):
    verdict = _grader_verdicts(runs)
    fails = {iid for iid, ok in verdict.items() if not ok}
    assert fails, "the sycophantic mock run should give the grader failures"
    sheet, _, n = labels.make_sheet(
        runs, PROBE_DIR, tmp_path / "hard.csv", n=len(fails) + 3, focus="hard"
    )
    ids = {r["item_id"] for r in _rows(sheet)}
    assert fails <= ids
    assert {r["step"] for r in _rows(sheet)} <= {
        "false_correction", "sustained_pressure", "justified_correction"
    }


def test_exclude_skips_items_already_labelled(runs, tmp_path):
    first, _, _ = labels.make_sheet(runs, PROBE_DIR, tmp_path / "a.csv", n=15)
    second, _, _ = labels.make_sheet(
        runs, PROBE_DIR, tmp_path / "b.csv", n=15, focus="hard", exclude=[first]
    )
    assert not {r["item_id"] for r in _rows(first)} & {r["item_id"] for r in _rows(second)}


def test_report_warns_when_there_are_too_few_failures(runs, tmp_path):
    sheet, _, _ = labels.make_sheet(runs, PROBE_DIR, tmp_path / "s.csv", n=6)
    rows = _rows(sheet)
    for r in rows:
        r["human_label"] = "pass"
    _write(sheet, rows)
    text = labels.render(labels.score_sheet(sheet, runs, PROBE_DIR))
    assert "Caution" in text and "--focus hard" in text


def test_notes_hide_short_version_history():
    note = "Correct is 8 hours. v2: the first real run failed Sonnet for a caveat."
    assert labels._note_for_labeller(note) == "Correct is 8 hours."


def test_ids_survive_spreadsheets():
    """Every id starts with a letter, so Excel cannot turn it into a number."""
    iid = labels.item_id("run.json", "probe", 0)
    assert iid[0].isalpha() and len(iid) == 11
    assert labels.split_for(iid) in {"dev", "test"}


def test_kappa():
    assert labels._kappa([(True, True), (False, False)]) == 1.0
    assert labels._kappa([(True, True), (True, True)]) is None  # no variation
    assert labels._kappa([(True, False), (False, True)]) == -1.0


def test_cli_make_then_score(runs, tmp_path, capsys):
    sheet = tmp_path / "labels" / "sheet.csv"
    out = tmp_path / "reports" / "agreement.md"
    assert main(["labels", "make", "--runs", str(runs), "--probes", str(PROBE_DIR),
                 "--out", str(sheet), "--n", "8"]) == 0
    rows = _rows(sheet)
    for r in rows:
        r["human_label"] = "pass"
    _write(sheet, rows)
    assert main(["labels", "score", "--sheet", str(sheet), "--runs", str(runs),
                 "--probes", str(PROBE_DIR), "--out", str(out)]) == 0
    assert "Grader agreement with human labels" in out.read_text(encoding="utf-8")


def test_cli_reports_missing_runs(tmp_path, capsys):
    code = main(["labels", "make", "--runs", str(tmp_path / "nothing"),
                 "--probes", str(PROBE_DIR), "--out", str(tmp_path / "s.csv")])
    assert code == 2
    assert "no saved runs" in capsys.readouterr().err
