import json
from pathlib import Path

from pushback import build_model, load_probes, report, run, score
from pushback.cli import main

ROOT = Path(__file__).resolve().parents[1]


def saved_run(tmp_path):
    folder = tmp_path / "runs"
    folder.mkdir()
    model = build_model("mock:robust")
    results = run(model, load_probes(ROOT / "probes"))
    data = json.loads(report.to_json(score(results, model.name), results))
    # Deliberately stale scores: regrade must recompute both turns and metrics.
    data["probes"][0]["turns"][0]["passed"] = False
    data["metrics"]["knowledge_accuracy"] = 0
    path = folder / "saved.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_regrade_recomputes_metrics_preserves_source_and_records_commit(tmp_path, monkeypatch):
    path = saved_run(tmp_path)
    before = path.read_bytes()
    out = tmp_path / "regraded"
    monkeypatch.setattr("pushback.models.build", lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("regrade must never build a model")))
    assert main(["regrade", "--runs", str(path.parent), "--probes", str(ROOT / "probes"),
                 "--out", str(out)]) == 0
    data = json.loads((out / path.name).read_text(encoding="utf-8"))
    assert data["metrics"]["knowledge_accuracy"] == 1
    assert data["probes"][0]["turns"][0]["passed"] is True
    assert len(data["regrade"]["grader"]["git_commit"]) == 40
    assert data["regrade"]["probe_set_version"].startswith("sha256:")
    assert len(data["source"]["sha256"]) == 64
    assert data["changes"] == [{"probe": data["probes"][0]["id"], "index": 0,
                                "old_passed": False, "passed": True}]
    assert path.read_bytes() == before
    assert (out / "README.md").exists()
    # Re-running cannot overwrite prior provenance.
    assert main(["regrade", "--runs", str(path), "--out", str(out)]) == 2


def test_regrade_refuses_source_directory_and_changed_experiment(tmp_path):
    path = saved_run(tmp_path)
    assert main(["regrade", "--runs", str(path), "--out", str(path.parent / "new")]) == 2
    data = json.loads(path.read_text(encoding="utf-8"))
    data["probes"][0]["turns"][0]["user"] = "A different experiment"
    path.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "new"
    assert main(["regrade", "--runs", str(path), "--out", str(out)]) == 2
    assert not out.exists()
