"""Run the approved four-probe sample locally with full history and an explicit cap.

No paid endpoint is supported. Request/response JSONL checkpoints preserve each
completed call, including usage and finish_reason, before grading happens.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pushback import models, probes, provenance, report, runner

ROOT = Path(__file__).resolve().parents[1]
MODEL = "qwen3-4b-instruct-2507-q4km"
URL = "http://127.0.0.1:8000/v1"
OUTPUT_TOKENS = 128
CONTEXT = 2048
IDS = {"retract_valid_flag", "retain_duplicate_invoice_concern",
       "retain_compliance_exception", "retain_forecast_outlier"}


def context_bound(system, turns, assistant_count):
    # Text-only byte-level tokenizer: one token per fixed UTF-8 byte is a loose
    # input bound. Prior outputs are capped at 128 tokens each. Reserve another
    # 64 tokens per chat message and generation prefix for framing/boundaries.
    fixed = len((system + "".join(turns)).encode("utf-8"))
    messages = 1 + len(turns) + assistant_count
    return fixed + OUTPUT_TOKENS * (assistant_count + 1) + 64 * (messages + 1)


def preflight(suite):
    bounds = {p.id: context_bound(runner.SYSTEM_PREAMBLE + p.context,
              [t.content for t in p.turns], len(p.turns) - 1) for p in suite}
    if any(n > CONTEXT for n in bounds.values()):
        raise models.ModelError("full probe history does not fit the conservative local context budget")
    return bounds


def check_server():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(URL + "/models", timeout=10) as response:
            data = json.load(response)
    except (OSError, ValueError) as exc:
        raise models.ModelError("Colibri is unreachable at " + URL + "; no model run started") from exc
    served = next((row for row in data["data"] if row["id"] == MODEL), None)
    capacity = served.get("context_length", served.get("max_model_len")) if served else None
    if type(capacity) is not int or capacity < CONTEXT:
        raise models.ModelError("Colibri must serve the expected Qwen model with at least a 2,048-token context")
    return data


class BudgetedQwen(models.OpenAICompatibleModel):
    def __init__(self, log_path):
        super().__init__(MODEL, base_url=URL, api_key="local-dummy", max_tokens=OUTPUT_TOKENS,
                         provider="openai-compat")
        self.log_path = log_path
        self.calls = 0
        self.attempts = 0
        self.capped = 0

    def complete(self, system, messages, probe, turn):
        bound = context_bound(system, [m["content"] for m in messages if m["role"] == "user"],
                              sum(m["role"] == "assistant" for m in messages))
        if bound > CONTEXT:
            raise models.ModelError("local context bound exceeded; no prompt or history was truncated")
        payload = {"model": MODEL, "max_tokens": OUTPUT_TOKENS, "context_compaction": "off",
                   "messages": [{"role": "system", "content": system}, *messages]}
        self.attempts += 1
        try:
            data = models._post(URL + "/chat/completions", payload,
                                {"content-type": "application/json", "authorization": "Bearer local-dummy"})
        except (OSError, models.ModelError) as exc:
            with self.log_path.open("a", encoding="utf-8", newline="\n") as log:
                log.write(json.dumps({"attempt": self.attempts, "probe": probe.id,
                    "turn": probe.turns.index(turn) + 1, "request": payload,
                    "error": str(exc)}, ensure_ascii=False) + "\n")
            raise models.ModelError("local request failed: " + str(exc)) from exc
        self.calls += 1
        # Persist the real response before checking or grading it. No credentials
        # or HTTP headers are written; the dummy local key is never needed here.
        with self.log_path.open("a", encoding="utf-8", newline="\n") as log:
            log.write(json.dumps({"call": self.calls, "probe": probe.id,
                "turn": probe.turns.index(turn) + 1, "input_and_output_bound": bound,
                "request": payload, "response": data}, ensure_ascii=False) + "\n")
        if data.get("model") != MODEL:
            raise models.ModelError("Colibri returned a different model")
        usage = data.get("usage", {})
        used = usage.get("prompt_tokens")
        generated = usage.get("completion_tokens")
        if type(used) is not int or type(generated) is not int:
            raise models.ModelError("Colibri response omitted token counts; context fit cannot be verified")
        if used + OUTPUT_TOKENS > CONTEXT or generated > OUTPUT_TOKENS:
            raise models.ModelError("Colibri token usage violates the explicit local context/output budget")
        choice = data["choices"][0]
        self.capped += choice.get("finish_reason") == "length"
        return choice["message"]["content"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="reports/runs/qwen-judgment-repeat5.json")
    args = parser.parse_args(argv)
    out = Path(args.out).resolve()
    allowed = (ROOT / "reports/runs").resolve()
    if allowed not in out.parents:
        parser.error("output must be inside reports/runs/")
    log_path = out.with_suffix(".requests.jsonl")
    if out.exists() or log_path.exists():
        parser.error("refusing to overwrite an existing result or request log")
    suite = [p for p in probes.load(ROOT / "probes") if p.id in IDS]
    if {p.id for p in suite} != IDS:
        parser.error("the approved four probes were not found")
    bounds = preflight(suite)
    print("Conservative whole-conversation token bounds:", bounds, flush=True)
    server = check_server()
    out.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=False)
    model = BudgetedQwen(log_path)
    completed = []
    metadata = {"created_at": datetime.now(timezone.utc).isoformat(), "model": model.name,
        "model_spec": "openai-compat:" + MODEL + "@" + URL, "temperature": None,
        "repeat": 5, "max_tokens": OUTPUT_TOKENS, "context_limit": CONTEXT,
        "context_compaction": "off", "probe_set_version": provenance.probe_version(suite),
        "harness_version": provenance.grader_version(), "context_bounds": bounds,
        "server_models": server, "request_log": log_path.name}

    def save():
        metrics = runner.score(completed, model.name)
        successful = sum(not r.error for r in completed)
        metadata.update(attempted_calls=model.attempts, completed_calls=model.calls,
                        output_cap_reached=model.capped, attempted_conversations=len(completed),
                        completed_conversations=successful,
                        complete=len(completed) == successful == 20)
        out.write_text(report.to_json(metrics, completed, metadata=metadata), encoding="utf-8")

    def progress(i, total, result):
        completed.append(result)
        save()
        print(f"[{i}/{total}] {result.probe.id}: " + ("error" if result.error else "saved"), flush=True)

    try:
        runner.run(model, suite, on_progress=progress, repeat=5)
    except KeyboardInterrupt:
        save()
        print("Interrupted; completed conversations and individual responses are checkpointed.")
        return 130
    save()
    print(report.console(runner.score(completed, model.name), completed))
    print(f"Output cap reached on {model.capped} of {model.calls} responses; see recorded finish reasons.")
    return int(any(r.error for r in completed))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except models.ModelError as exc:
        print("local run: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
