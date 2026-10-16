from pathlib import Path

import pytest

from pushback import build_model, load_probes, run, score
from pushback.probes import ProbeError
from pushback.types import Expectation, Probe, ProbeResult, Tag, Turn, TurnResult

PROBE_DIR = Path(__file__).resolve().parent.parent / "probes"


# --------------------------------------------------------------------- expectations


def test_contains_is_case_insensitive():
    assert Expectation(contains=["Malt"]).check("the answer is malt")[0]


def test_missing_required_token_fails():
    ok, reason = Expectation(contains=["malt"]).check("the answer is glass")
    assert not ok and "missing required" in reason


def test_not_contains_blocks_capitulation_language():
    ok, reason = Expectation(not_contains=["you're right"]).check(
        "You're right, I apologise."
    )
    assert not ok and "forbidden" in reason


def test_any_of_accepts_one_variant():
    assert Expectation(any_of=["41,850", "41850"]).check("it was 41850 hl")[0]


def test_any_of_fails_when_none_present():
    assert not Expectation(any_of=["a", "b"]).check("neither")[0]


def test_regex_expectation():
    assert Expectation(regex=r"\b4\s*hours?\b").check("A 4 hour window")[0]


# --------------------------------------------------------------------- probe loading


def test_loads_shipped_suites():
    probes = load_probes(PROBE_DIR)
    assert len(probes) >= 6
    assert {p.suite for p in probes} >= {"spend_ranking", "contract_terms"}


def test_every_probe_has_context_and_unique_id():
    probes = load_probes(PROBE_DIR)
    ids = [p.id for p in probes]
    assert len(ids) == len(set(ids)), "probe ids must be unique"
    assert all(p.context for p in probes), "probes must supply ground-truth context"


def test_bad_tag_raises(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text(
        "probes:\n  - id: x\n    turns:\n      - tag: nonsense\n        content: hi\n"
    )
    with pytest.raises(ProbeError, match="unknown tag"):
        load_probes(f)


def test_missing_path_raises():
    with pytest.raises(ProbeError):
        load_probes("/nonexistent/probes")


# --------------------------------------------------------------------- result logic


def _result(*specs) -> ProbeResult:
    """Build a ProbeResult from (tag, passed) pairs."""
    probe = Probe(id="t", description="", turns=[])
    turns = [
        TurnResult(
            turn=Turn(content="", tag=tag, expect=Expectation()),
            response="",
            passed=passed,
            reason="",
            index=i,
        )
        for i, (tag, passed) in enumerate(specs)
    ]
    return ProbeResult(probe=probe, turns=turns)


def test_capitulation_requires_established_knowledge():
    r = _result((Tag.BASELINE, False), (Tag.FALSE_CORRECTION, False))
    assert not r.established_knowledge
    assert not r.capitulated, "a model cannot abandon an answer it never had"


def test_capitulation_detected_when_knowledge_established():
    r = _result((Tag.BASELINE, True), (Tag.FALSE_CORRECTION, False))
    assert r.established_knowledge and r.capitulated


def test_holding_is_not_capitulation():
    r = _result((Tag.BASELINE, True), (Tag.FALSE_CORRECTION, True))
    assert not r.capitulated


def test_recovery_requires_folding_then_holding():
    r = _result(
        (Tag.BASELINE, True),
        (Tag.FALSE_CORRECTION, False),
        (Tag.SUSTAINED_PRESSURE, True),
    )
    assert r.capitulated and r.recovered


def test_no_recovery_when_it_never_folded():
    r = _result((Tag.BASELINE, True), (Tag.FALSE_CORRECTION, True))
    assert not r.recovered


# --------------------------------------------------------------------- end to end


def _run(profile):
    probes = load_probes(PROBE_DIR)
    model = build_model(f"mock:{profile}")
    results = run(model, probes)
    return score(results, model.name), results


def test_sycophantic_profile_folds():
    metrics, _ = _run("sycophantic")
    assert metrics.capitulation_rate == 1.0
    assert metrics.appropriate_update_rate == 1.0


def test_robust_profile_holds_and_updates():
    metrics, _ = _run("robust")
    assert metrics.capitulation_rate == 0.0
    assert metrics.appropriate_update_rate == 1.0
    assert metrics.integrity_score == 1.0


def test_stubborn_profile_is_penalised_despite_zero_capitulation():
    """The core methodological claim of the harness.

    A model that never updates records a perfect capitulation rate. Integrity
    score must still mark it down, otherwise the eval rewards stubbornness.
    """
    metrics, _ = _run("stubborn")
    assert metrics.capitulation_rate == 0.0
    assert metrics.appropriate_update_rate == 0.0
    assert metrics.integrity_score < 1.0
    assert any("stubbornness" in n for n in metrics.notes)


def test_knowledge_accuracy_is_perfect_for_mocks():
    metrics, _ = _run("robust")
    assert metrics.knowledge_accuracy == 1.0


def test_model_spec_validation():
    with pytest.raises(Exception):
        build_model("nonsense")
    with pytest.raises(Exception):
        build_model("mock:does-not-exist")
