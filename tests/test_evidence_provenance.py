"""Evidence identity checks; these do not inspect labels to tune the grader."""

import hashlib
import json
from pathlib import Path

from pushback import labels

ROOT = Path(__file__).resolve().parents[1]


def test_preserved_sonnet_runs_match_recorded_source_hashes():
    manifest = json.loads((ROOT / "reports/run-provenance.json").read_text(encoding="utf-8"))
    for source in manifest["sources"]:
        data = (ROOT / source["path"]).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(data).hexdigest() == source["normalized_sha256"]


def test_every_regression_fixture_points_to_its_exact_real_reply():
    fixtures = json.loads((ROOT / "tests/fixtures/failed_holds.json").read_text(encoding="utf-8-sig"))
    for case in fixtures:
        run = json.loads((ROOT / "runs" / case["run"]).read_bytes())
        probe = next(p for p in run["probes"] if p["id"] == case["probe"])
        turn = next(t for t in probe["turns"] if t["index"] == case["index"])
        assert turn["response"] == case["response"], (case["run"], case["probe"], case["index"])


def test_label_references_match_saved_replies_without_changing_labels():
    # This is a provenance comparison only, not a held-out grader evaluation.
    items = {item.item_id: item for item in labels.load_items(ROOT / "runs")}
    manifest = json.loads((ROOT / "reports/run-provenance.json").read_text(encoding="utf-8"))
    for name, digest in manifest["label_csv_normalized_sha256"].items():
        path = ROOT / name
        assert hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == digest
        for row in labels._read_sheet(path):
            item = items[row["item_id"]]
            assert item.response.strip() == row["model_reply"], row["item_id"]
            assert item.user.strip() == row["user_message"], row["item_id"]
