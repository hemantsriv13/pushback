import importlib.util
import json
from pathlib import Path

import pytest

from pushback import models, probes

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_judgment", ROOT / "scripts/run_qwen_judgment.py")
local = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local)


def test_whole_probe_bounds_fit_without_shortening_inputs():
    suite = [p for p in probes.load(ROOT / "probes") if p.id in local.IDS]
    bounds = local.preflight(suite)
    assert len(bounds) == 4
    assert max(bounds.values()) == 2000
    assert all(n <= 2048 for n in bounds.values())


def test_local_requests_preserve_full_history_and_capture_usage(monkeypatch, tmp_path):
    probe = next(p for p in probes.load(ROOT / "probes") if p.id == "retract_valid_flag")
    messages = [{"role": "user", "content": "full original question"},
                {"role": "assistant", "content": "full original reply"},
                {"role": "user", "content": "full original pushback"}]
    def post(url, payload, headers):
        assert url == local.URL + "/chat/completions"
        assert payload["messages"][1:] == messages
        assert payload["max_tokens"] == 128 and payload["context_compaction"] == "off"
        return {"model": local.MODEL, "usage": {"prompt_tokens": 50, "completion_tokens": 10},
                "choices": [{"finish_reason": "stop", "message": {"content": "Week 5 remains an anomaly."}}]}
    monkeypatch.setattr(models, "_post", post)
    path = tmp_path / "requests.jsonl"
    client = local.BudgetedQwen(path)
    assert client.complete("data", messages, probe, probe.turns[2]) == "Week 5 remains an anomaly."
    event = json.loads(path.read_text())
    assert event["response"]["usage"]["prompt_tokens"] == 50
    assert "authorization" not in event


def test_oversized_prompt_is_rejected_before_request(monkeypatch, tmp_path):
    monkeypatch.setattr(models, "_post", lambda *a, **k: pytest.fail("oversized request sent"))
    with pytest.raises(models.ModelError, match="no prompt or history was truncated"):
        local.BudgetedQwen(tmp_path / "requests.jsonl").complete("x" * 3000, [], None, None)


def test_output_cap_is_disclosed_in_counter_and_raw_log(monkeypatch, tmp_path):
    probe = probes.load(ROOT / "probes")[0]
    monkeypatch.setattr(models, "_post", lambda *a, **k: {"model": local.MODEL,
        "usage": {"prompt_tokens": 20, "completion_tokens": 128},
        "choices": [{"finish_reason": "length", "message": {"content": "partial"}}]})
    client = local.BudgetedQwen(tmp_path / "requests.jsonl")
    client.complete("data", [], probe, probe.turns[0])
    assert client.capped == 1
