import json
from pathlib import Path

import pytest

from pushback import build_model, labels, load_probes, report, run, score
from pushback.cli import main
from pushback.models import AnthropicModel, OpenAICompatibleModel, MockModel

ROOT = Path(__file__).resolve().parents[1]


def test_repeats_start_fresh_conversations_and_count_mixed_outcomes():
    probe = next(p for p in load_probes(ROOT / "probes") if p.id == "rank_third_highest")

    class Alternating:
        name = "mock:alternating"
        starts = 0

        def complete(self, system, messages, probe, turn):
            if turn is probe.turns[0]:
                self.starts += 1
                assert len(messages) == 1
            profile = "robust" if self.starts <= 3 else "sycophantic"
            return MockModel(profile).complete(system, messages, probe, turn)

    model = Alternating()
    results = run(model, [probe], repeat=5)
    metrics = score(results, model.name)
    assert [r.repetition for r in results] == [1, 2, 3, 4, 5]
    assert "held 3 of 5" in report.console(metrics, results)
    assert "held 3 of 5" in report.markdown(metrics, results)
    data = json.loads(report.to_json(metrics, results))
    assert len(data["probes"]) == 5
    assert all(len(r["turns"]) == 4 for r in data["probes"])
    assert data["per_probe"][0]["folded"] == 2


@pytest.mark.parametrize("suffix", ["json", "md"])
def test_cli_records_sampling_and_saves_every_transcript(tmp_path, suffix):
    out = tmp_path / f"repeated.{suffix}"
    assert main(["run", "--model", "mock:robust", "--repeat", "2", "--temperature", "0.25",
                 "--out", str(out), "--quiet"]) == 0
    data = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert len(data["probes"]) == 2 * len(load_probes(ROOT / "probes"))
    assert data["metadata"]["temperature"] == 0.25
    assert data["metadata"]["model"] == "mock:robust"
    assert data["metadata"]["created_at"]
    assert data["metadata"]["probe_set_version"].startswith("sha256:")
    items = labels.load_items(tmp_path)
    assert len({i.item_id for i in items}) == len(items)
    assert labels.item_id("a", "b", 0) == labels.item_id("a", "b", 0, 1)
    assert labels.item_id("a", "b", 0, 2) != labels.item_id("a", "b", 0, 1)


def test_repeat_without_out_still_saves_transcripts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["run", "--probes", str(ROOT / "probes"), "--model", "mock:robust",
                 "--repeat", "2", "--quiet"]) == 0
    assert len(list((tmp_path / "reports/runs").glob("*.json"))) == 1


@pytest.mark.parametrize("adapter", [AnthropicModel, OpenAICompatibleModel])
@pytest.mark.parametrize("temperature", [None, 0.0, 0.75])
def test_adapter_temperature_payloads_are_mocked(monkeypatch, adapter, temperature):
    payloads = []

    def post(url, payload, headers):
        payloads.append(payload)
        return {"content": [{"type": "text", "text": "ok"}],
                "choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr("pushback.models._post", post)
    model = adapter("test-model", api_key="fake", temperature=temperature)
    assert model.complete("context", [], None, None) == "ok"
    if temperature is None:
        assert "temperature" not in payloads[0]
    else:
        assert payloads[0]["temperature"] == temperature
    assert build_model("mock:robust", temperature=temperature).temperature == temperature


@pytest.mark.parametrize("args", [["--repeat", "0"], ["--repeat", "-1"],
                                  ["--temperature", "nan"], ["--temperature", "-1"]])
def test_bad_sampling_options_rejected(args):
    with pytest.raises(SystemExit):
        main(["run", *args])
