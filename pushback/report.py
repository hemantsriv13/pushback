"""Report rendering: console, markdown, JSON."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict

from .runner import Metrics
from .types import HOLD_TAGS, ProbeResult, Tag

_METRIC_HELP = {
    "knowledge_accuracy": "Correct on direct and dependent questions",
    "capitulation_rate": "Abandoned a correct answer under unjustified pushback (lower is better)",
    "sustained_capitulation_rate": "Folded specifically under repeated pressure (lower is better)",
    "recovery_rate": "Of those that folded, returned to the correct answer",
    "appropriate_update_rate": "Changed its answer when given valid new evidence",
    "recheck_accuracy": "Re-confirmed a correct answer when asked to double-check (not in integrity)",
    "integrity_score": "Held when it should, updated when it should (headline)",
}

_LOWER_IS_BETTER = {"capitulation_rate", "sustained_capitulation_rate"}


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100}%"


def per_probe_counts(results: list[ProbeResult]) -> list[dict]:
    groups = defaultdict(list)
    for result in results:
        groups[result.probe.id].append(result)
    out = []
    for pid, attempts in groups.items():
        eligible = [r for r in attempts if not r.error and r.established_knowledge
                    and any(t.turn.tag in HOLD_TAGS for t in r.turns)]
        updates = [r for r in attempts if not r.error
                   and any(t.turn.tag is Tag.JUSTIFIED_CORRECTION for t in r.turns)]
        out.append({"probe": pid, "attempts": len(attempts),
                    "held": sum(not r.capitulated for r in eligible),
                    "hold_eligible": len(eligible), "folded": sum(r.capitulated for r in eligible),
                    "updated": sum(not r.failed_to_update for r in updates),
                    "update_eligible": len(updates),
                    "knowledge_failed": sum(not r.error and not r.established_knowledge for r in attempts),
                    "errored": sum(r.error is not None for r in attempts)})
    return out


def _count_text(row: dict) -> str:
    held = (f"held {row['held']} of {row['hold_eligible']}" if row['hold_eligible'] else "held n/a")
    updated = (f"updated {row['updated']} of {row['update_eligible']}" if row['update_eligible'] else "updated n/a")
    return (f"{held}; {updated}; {row['attempts']} attempts; "
            f"{row['errored']} errored; {row['knowledge_failed']} failed knowledge")


def console(metrics: Metrics, results: list[ProbeResult], verbose: bool = False) -> str:
    lines = []
    lines.append("")
    lines.append(f"  pushback \u2014 {metrics.model}")
    lines.append(f"  {metrics.total_probes} probes, {metrics.eligible_probes} eligible for pushback scoring")
    lines.append("  " + "\u2500" * 62)

    for key, help_text in _METRIC_HELP.items():
        value = getattr(metrics, key)
        label = key.replace("_", " ")
        lines.append(f"  {label:<30} {_pct(value):>6}   {help_text}")

    lines.append("  " + "\u2500" * 62)

    for note in metrics.notes:
        lines.append(f"  ! {note}")

    counts = per_probe_counts(results)
    if any(row["attempts"] > 1 for row in counts):
        lines.append("")
        for row in counts:
            lines.append(f"  {row['probe']}: {_count_text(row)}")

    failed = [r for r in results if r.capitulated or r.error or r.failed_to_update]
    if failed:
        lines.append("")
        lines.append(f"  Probes of concern ({len(failed)}):")
        for r in failed:
            if r.error:
                lines.append(f"    \u2717 {r.probe.id}: error \u2014 {r.error}")
                continue
            if r.capitulated:
                first = next(
                    (t for t in r.turns if t.turn.tag in HOLD_TAGS and not t.passed),
                    None,
                )
                detail = (
                    f" at turn {first.index + 1} ({first.turn.tag.value})" if first else ""
                )
                lines.append(f"    \u2717 {r.probe.id}: capitulated{detail}")
            if r.failed_to_update:
                miss = next(
                    t
                    for t in r.turns
                    if t.turn.tag is Tag.JUSTIFIED_CORRECTION and not t.passed
                )
                lines.append(
                    f"    \u2717 {r.probe.id}: did not update on valid evidence "
                    f"at turn {miss.index + 1}"
                )

    if verbose:
        lines.append("")
        for r in results:
            lines.append(f"  \u2500\u2500 {r.probe.id} (repeat {r.repetition}) \u2500\u2500")
            for t in r.turns:
                mark = "\u2713" if t.passed else "\u2717"
                lines.append(f"    {mark} [{t.turn.tag.value}] {t.turn.content}")
                # Full reply, not truncated: a cut-off reply hid the sentence
                # that caused a grading failure on the first real F01 run.
                reply = t.response.strip().replace("\n", "\n          ")
                lines.append(f"        \u2192 {reply}")
                if not t.passed:
                    lines.append(f"        reason: {t.reason}")
            lines.append("")

    lines.append("")
    return "\n".join(lines)


def markdown(metrics: Metrics, results: list[ProbeResult]) -> str:
    out = []
    out.append(f"# pushback report \u2014 `{metrics.model}`")
    out.append("")
    out.append(
        f"{metrics.total_probes} probes run. {metrics.eligible_probes} established "
        f"baseline knowledge and are eligible for pushback scoring."
    )
    out.append("")
    out.append("## Metrics")
    out.append("")
    out.append("| Metric | Value | Direction | Meaning |")
    out.append("|---|---|---|---|")
    for key, help_text in _METRIC_HELP.items():
        direction = "lower is better" if key in _LOWER_IS_BETTER else "higher is better"
        out.append(
            f"| `{key}` | **{_pct(getattr(metrics, key))}** | {direction} | {help_text} |"
        )
    out.append("")

    if metrics.notes:
        out.append("## Notes")
        out.append("")
        for note in metrics.notes:
            out.append(f"- {note}")
        out.append("")

    out.append("## Per-probe results")
    out.append("")
    counts = per_probe_counts(results)
    if any(row["attempts"] > 1 for row in counts):
        out += ["| Probe | Repeated outcomes |", "|---|---|"]
        for row in counts:
            out.append(f"| `{row['probe']}` | {_count_text(row)} |")
        out += ["", "### Individual transcripts", ""]
    out.append("| Probe | Suite | Knowledge | Capitulated | Recovered | Updated on evidence |")
    out.append("|---|---|---|---|---|---|")
    for r in results:
        if r.error:
            out.append(
                f"| `{r.probe.id}` | {r.probe.suite} | error | error | error | error |"
            )
            continue
        has_update = any(t.turn.tag is Tag.JUSTIFIED_CORRECTION for t in r.turns)
        updated = "\u2014" if not has_update else ("**no**" if r.failed_to_update else "yes")
        out.append(
            f"| `{r.probe.id}` | {r.probe.suite} "
            f"| {'yes' if r.established_knowledge else 'no'} "
            f"| {'**yes**' if r.capitulated else 'no'} "
            f"| {'yes' if r.recovered else '\u2014'} "
            f"| {updated} |"
        )
    out.append("")

    concerning = [r for r in results if r.capitulated or r.failed_to_update]
    if concerning:
        out.append("## Failure transcripts")
        out.append("")
        for r in concerning:
            out.append(f"### `{r.probe.id}` (repeat {r.repetition})")
            if r.probe.description:
                out.append("")
                out.append(f"_{r.probe.description}_")
            out.append("")
            for t in r.turns:
                mark = "\u2705" if t.passed else "\u274c"
                out.append(f"{mark} **{t.turn.tag.value}** \u2014 user: {t.turn.content}")
                out.append("")
                out.append(f"> {t.response.strip()}")
                out.append("")
                if not t.passed:
                    out.append(f"`{t.reason}`")
                    out.append("")
    return "\n".join(out)


def to_json(metrics: Metrics, results: list[ProbeResult], metadata: dict | None = None) -> str:
    payload = {
        "metrics": asdict(metrics),
        "probes": [
            {
                "id": r.probe.id,
                "repetition": r.repetition,
                "suite": r.probe.suite,
                "description": r.probe.description,
                "error": r.error,
                "established_knowledge": r.established_knowledge,
                "capitulated": r.capitulated,
                "recovered": r.recovered,
                "turns": [
                    {
                        "index": t.index,
                        "tag": t.turn.tag.value,
                        "user": t.turn.content,
                        "response": t.response,
                        "passed": t.passed,
                        "reason": t.reason,
                    }
                    for t in r.turns
                ],
            }
            for r in results
        ],
    }
    if metadata is not None:
        payload["metadata"] = metadata
    payload["per_probe"] = per_probe_counts(results)
    return json.dumps(payload, indent=2)
