"""Re-score saved transcripts offline, without altering their source files."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import probes, provenance, report, runner
from .types import ProbeResult, TurnResult


class RegradeError(ValueError):
    pass


def _normal(text: str) -> str:
    return " ".join(text.split())


def regrade_file(path: Path, definitions: dict) -> tuple[dict, str]:
    raw = path.read_bytes()
    saved = json.loads(raw.decode("utf-8-sig"))
    results = []
    changes = []
    for old in saved["probes"]:
        probe = definitions.get(old["id"])
        if probe is None:
            raise RegradeError(f"{path.name}: unknown probe {old['id']!r}")
        turns = []
        for expected_index, old_turn in enumerate(old["turns"]):
            idx = old_turn["index"]
            if idx != expected_index or idx >= len(probe.turns):
                raise RegradeError(f"{path.name}: invalid turn index in {probe.id}")
            turn = probe.turns[idx]
            if (turn.tag.value != old_turn["tag"]
                    or _normal(turn.content) != _normal(old_turn["user"])):
                raise RegradeError(
                    f"{path.name}: {probe.id} turn {idx + 1} differs from current prompts/tags; "
                    "use matching probe definitions, not a new experiment"
                )
            passed, reason = turn.expect.check(old_turn["response"])
            turns.append(TurnResult(turn, old_turn["response"], passed, reason, idx))
            if passed != old_turn["passed"]:
                changes.append({"probe": probe.id, "index": idx,
                                "old_passed": old_turn["passed"], "passed": passed})
        if not old.get("error") and len(turns) != len(probe.turns):
            raise RegradeError(f"{path.name}: incomplete transcript for {probe.id}")
        results.append(ProbeResult(probe, turns, old.get("error"), old.get("repetition", 1)))
    if not results:
        raise RegradeError(f"{path.name}: no probe transcripts")
    model = saved["metrics"]["model"]
    metrics = runner.score(results, model)
    payload = json.loads(report.to_json(metrics, results))
    payload["source"] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                         "metadata": saved.get("metadata"), "metrics": saved["metrics"]}
    payload["changes"] = changes
    return payload, report.markdown(metrics, results)


def regrade(runs_path: str | Path, probes_path: str | Path, out: str | Path) -> Path:
    source = Path(runs_path).resolve()
    target = Path(out).resolve()
    # Never write beneath the source or the repository's historical runs/.
    for protected in (source if source.is_dir() else source.parent, provenance.ROOT / "runs"):
        if target == protected or protected in target.parents:
            raise RegradeError("regraded reports must be written outside runs/")
    if target.exists():
        raise RegradeError(f"{target} already exists; choose a new output location")
    paths = sorted(source.glob("*.json")) if source.is_dir() else [source]
    if not paths:
        raise RegradeError(f"no saved runs (*.json) found in {source}")
    suite = probes.load(probes_path)
    definitions = {p.id: p for p in suite}
    version = provenance.grader_version()
    metadata = {"regraded_at": datetime.now(timezone.utc).isoformat(),
                "grader": version, "probe_set_version": provenance.probe_version(suite),
                "kind": "offline regrade; no model calls"}
    # Validate every source before writing any report.
    graded = [(path, *regrade_file(path, definitions)) for path in paths]
    target.mkdir(parents=True)
    index = ["# v0.2 regraded saved transcripts", "",
             "These are current-grader scores of saved replies, not fresh model runs.",
             "The unresolved Opus Week 5 case still fails the unchanged rule; see ../failed-hold-review.md.",
             "", f"Grader commit: `{version['git_commit']}`. Dirty sources: `{version['dirty']}`.",
             "", "Exact metric values and source hashes are recorded in each JSON report.", "",
             "| Source | Metrics and transcripts | Review |", "|---|---|---|"]
    for path, payload, markdown in graded:
        payload["regrade"] = metadata
        (target / path.name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        (target / f"{path.stem}.md").write_text(markdown, encoding="utf-8")
        index.append(f"| {path.name} | [{path.name}]({path.name}) | [{path.stem}.md]({path.stem}.md) |")
    (target / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return target
