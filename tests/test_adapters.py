import io
import urllib.error

import pytest

from pushback import build_model, load_probes
from pushback.models import ModelError, _post
from pushback.runner import run_probe, score


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


@pytest.mark.parametrize("failure", ["429", "timeout", "wrapped-timeout"])
def test_transient_errors_retry_then_succeed(monkeypatch, failure):
    calls, sleeps = [], []

    def post(request, timeout):
        calls.append(request)
        if len(calls) < 3:
            if failure == "429":
                raise urllib.error.HTTPError("https://example.invalid", 429, "rate limited", {}, io.BytesIO(b"slow down"))
            if failure == "wrapped-timeout":
                raise urllib.error.URLError(TimeoutError("timed out"))
            raise TimeoutError("timed out")
        return Response(b'{"ok": true}')

    monkeypatch.setattr("urllib.request.urlopen", post)
    monkeypatch.setattr("pushback.models.time.sleep", sleeps.append)
    assert _post("https://example.invalid", {}, {}) == {"ok": True}
    assert len(calls) == 3 and sleeps == [1, 2]


@pytest.mark.parametrize("failure", ["429", "timeout", "wrapped-timeout", "401", "dns"])
def test_retries_are_bounded_and_exhaustion_is_a_probe_error(monkeypatch, failure):
    calls, sleeps = [], []

    def post(request, timeout):
        calls.append(request)
        if failure in ("401", "429"):
            raise urllib.error.HTTPError("https://example.invalid", int(failure), "failed", {}, io.BytesIO(b"failure"))
        if failure == "wrapped-timeout":
            raise urllib.error.URLError(TimeoutError("timed out"))
        if failure == "dns":
            raise urllib.error.URLError("not found")
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", post)
    monkeypatch.setattr("pushback.models.time.sleep", sleeps.append)

    class Adapter:
        name = "test"

        def complete(self, *args):
            return _post("https://example.invalid", {}, {})

    result = run_probe(Adapter(), load_probes("probes")[0])
    assert result.error
    assert score([result], "test").errored == 1
    transient = failure in ("429", "timeout", "wrapped-timeout")
    assert len(calls) == (3 if transient else 1)
    assert sleeps == ([1, 2] if transient else [])


def test_compat_provider_name_is_preserved(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    assert build_model("openai-compat:test@http://localhost:8000/v1").name == "openai-compat:test"
    assert build_model("openai:test").name == "openai:test"


def test_probe_file_uses_utf8_explicitly(tmp_path, monkeypatch):
    from pathlib import Path
    path = tmp_path / "unicode.yaml"
    path.write_text("suite: café\ncontext: résumé\nprobes:\n  - id: x\n    turns:\n"
                    "      - tag: baseline\n        content: café?\n", encoding="utf-8")
    original = Path.read_text

    def read_text(self, *args, **kwargs):
        assert kwargs.get("encoding") == "utf-8"
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    assert load_probes(path)[0].context == "résumé"
