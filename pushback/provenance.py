"""Identify the exact local grader and probe definitions behind a report."""

import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from .types import Probe

ROOT = Path(__file__).resolve().parents[1]


def probe_version(probes: list[Probe]) -> str:
    body = json.dumps([asdict(p) for p in probes], sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def grader_version() -> dict:
    """A commit plus a source digest, so dirty checkouts cannot impersonate HEAD."""
    commit = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain", "--", "pushback", "probes"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    digest = hashlib.sha256()
    for path in sorted((ROOT / "pushback").glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return {"git_commit": commit, "dirty": bool(dirty), "source_sha256": digest.hexdigest()}
