"""Real false-fail regressions, paired with explicitly invented capitulations."""

import json
from pathlib import Path

import pytest

from pushback import load_probes


ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests/fixtures/failed_holds.json").read_text(encoding="utf-8-sig"))


@pytest.mark.parametrize("case", [c for c in CASES if c["reading"] == "held"],
                         ids=lambda c: f"{c['run']}-{c['probe']}-{c['index'] + 1}")
def test_real_held_reply_and_invented_fold(case):
    probes = {p.id: p for p in load_probes(ROOT / "probes")}
    check = probes[case["probe"]].turns[case["index"]].expect
    assert check.check(case["response"])[0], check.check(case["response"])[1]
    # Keeping the real reply before a final reversal ensures a mere mention of
    # the right answer cannot conceal an explicit capitulation later on.
    assert not check.check(case["invented_capitulation"])[0]


@pytest.mark.parametrize("reply", [
    "Malt is second. Glass is third.",
    "Malt is not third. Glass is third.",
    "Malt was mentioned. A different sentence says third.",
    "Malt; someone else is third.",
    "I can't confirm that Glass is third. Correction: Glass is third; Malt is second.",
])
def test_ranking_does_not_cross_sentence_boundaries_or_hide_reversals(reply):
    probe = next(p for p in load_probes(ROOT / "probes") if p.id == "rank_third_highest")
    assert not probe.turns[2].expect.check(reply)[0]
