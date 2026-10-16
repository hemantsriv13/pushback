"""Loading probe suites from YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from .types import Expectation, Probe, Tag, Turn


class ProbeError(ValueError):
    """Raised when a probe file is malformed."""


def _build_turn(raw: dict, probe_id: str, idx: int) -> Turn:
    try:
        tag = Tag(raw["tag"])
    except KeyError as exc:
        raise ProbeError(f"{probe_id} turn {idx}: missing 'tag'") from exc
    except ValueError as exc:
        valid = ", ".join(t.value for t in Tag)
        raise ProbeError(
            f"{probe_id} turn {idx}: unknown tag {raw['tag']!r}. Valid: {valid}"
        ) from exc

    content = raw.get("content")
    if not content:
        raise ProbeError(f"{probe_id} turn {idx}: missing 'content'")

    return Turn(
        content=content,
        tag=tag,
        expect=Expectation.from_dict(raw.get("expect")),
        note=raw.get("note", ""),
    )


def load_file(path: Path) -> list[Probe]:
    """Load every probe defined in one YAML file."""
    doc = yaml.safe_load(path.read_text()) or {}
    suite = doc.get("suite", path.stem)
    shared_context = doc.get("context", "")

    probes = []
    for raw in doc.get("probes", []):
        probe_id = raw.get("id")
        if not probe_id:
            raise ProbeError(f"{path}: a probe is missing 'id'")

        turns = [
            _build_turn(t, probe_id, i)
            for i, t in enumerate(raw.get("turns", []))
        ]
        if not turns:
            raise ProbeError(f"{probe_id}: has no turns")

        probes.append(
            Probe(
                id=probe_id,
                description=raw.get("description", ""),
                turns=turns,
                context=raw.get("context", shared_context),
                suite=suite,
            )
        )
    return probes


def load(path: str | Path) -> list[Probe]:
    """Load a probe file, or every ``*.yaml`` in a directory."""
    p = Path(path)
    if p.is_dir():
        files = sorted(p.glob("*.yaml")) + sorted(p.glob("*.yml"))
        if not files:
            raise ProbeError(f"no probe files found in {p}")
        return [probe for f in files for probe in load_file(f)]
    if not p.exists():
        raise ProbeError(f"probe path does not exist: {p}")
    return load_file(p)
