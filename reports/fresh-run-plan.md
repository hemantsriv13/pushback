# Qwen-only judgment run — waiting for Colibri

The owner replaced the paid Haiku/Sonnet/Opus runs with the local Qwen run.
The paid clients were interrupted; their limited progress and missing result
files are documented in `paid-run-cancellation.md`. Do not restart paid runs.

The replacement uses the same four probes, five repetitions each: 20 independent
conversations and 65 logical completion calls. Retries can produce at most 195
HTTP attempts. It supports only the specified loopback endpoint and model.

Run from the repository root in **Windows Command Prompt** once the existing
Colibri Qwen server is listening again:

```bat
set OPENAI_API_KEY=local-dummy
python scripts/run_qwen_judgment.py --out reports/runs/qwen-judgment-repeat5.json
```

The runner passes the dummy key explicitly to the existing compatible adapter.
It refuses to overwrite prior output or request logs. It never starts, stops,
restarts or reconfigures Colibri, and does not support a paid API fallback.

## Explicit request settings and context checks

- Model: `qwen3-4b-instruct-2507-q4km`.
- Endpoint: `http://127.0.0.1:8000/v1`.
- Output allowance: 128 tokens per response, explicitly recorded.
- Context: 2,048 tokens, verified against `/v1/models` before starting.
- Temperature: unspecified, preserving the server default.
- Context compaction: explicitly `off` on every request.
- All supplied data, user text and previous replies are sent without shortening.

The preflight bounds fixed text by its UTF-8 bytes, prior assistant replies by
their explicit output allowances, and chat framing/boundaries by 64 tokens per
message and generation prefix. These are deliberately loose planning bounds,
not measured tokenizer counts:

| Probe | Conversations | Calls | Whole-conversation token bound |
|---|---|---|---|
| retract_valid_flag | 5 | 20 | 1804 |
| retain_duplicate_invoice_concern | 5 | 15 | 2000 |
| retain_compliance_exception | 5 | 15 | 1968 |
| retain_forecast_outlier | 5 | 15 | 1894 |
| Total | 20 | 65 | — |

All bounds are below 2,048 with the 128-token output allowance. Every actual
response must supply token usage; the runner verifies that prompt tokens plus
the requested output allowance fit the context. Missing/invalid token counts
are errors, not evidence of success. Each `finish_reason: length` is counted
and disclosed; an output-limited reply is not silently presented as unlimited.
These limits differ from the cancelled paid commands' default output allowance
and must be reported when interpreting any future results.

## Evidence preservation

Each completed call is written immediately to
`reports/runs/qwen-judgment-repeat5.requests.jsonl`, including the request,
response, token usage and finish reason, without credential headers. Completed
conversations are checkpointed in `qwen-judgment-repeat5.json`. Interruptions
therefore preserve received responses rather than relying on the final report.

No Qwen inference request was sent by the failed initial preflight: Colibri
refused the connection before inference. The run remains pending until the
owner starts the existing shared service. No local result numbers are claimed.

This subset contains hold turns and no justified corrections. Integrity is
therefore withheld; report actual hold outcomes and repetition counts, not a
combined integrity score.
