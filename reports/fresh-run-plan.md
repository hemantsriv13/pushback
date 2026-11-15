# Fresh judgment runs — not started

These commands are a reviewable plan, not authorization to spend money. Do not
execute the Anthropic commands until the owner explicitly says yes. The local
command is also on hold pending the context-budget decision below. No API call,
including to Colibri, was made while preparing this plan.

Run from the repository root in **Windows Command Prompt**, not PowerShell.
The model IDs below are the IDs already recorded in this repository; service
availability has not been checked. No temperature override is proposed: the
run metadata will record the existing provider-default setting.

```bat
set ANTHROPIC_API_KEY=YOUR_ANTHROPIC_KEY
pushback run --model anthropic:claude-haiku-5-5 --probe retract_valid_flag --probe retain_duplicate_invoice_concern --probe retain_compliance_exception --probe retain_forecast_outlier --repeat 5 --out reports/runs/haiku-judgment-repeat5.json
pushback run --model anthropic:claude-sonnet-5-5 --probe retract_valid_flag --probe retain_duplicate_invoice_concern --probe retain_compliance_exception --probe retain_forecast_outlier --repeat 5 --out reports/runs/sonnet-judgment-repeat5.json
pushback run --model anthropic:claude-opus-5-5 --probe retract_valid_flag --probe retain_duplicate_invoice_concern --probe retain_compliance_exception --probe retain_forecast_outlier --repeat 5 --out reports/runs/opus-judgment-repeat5.json
```

Intended local command, **not cleared to execute**:

```bat
set OPENAI_API_KEY=local-dummy
pushback run --model openai-compat:qwen3-4b-instruct-2507-q4km@http://127.0.0.1:8000/v1 --probe retract_valid_flag --probe retain_duplicate_invoice_concern --probe retain_compliance_exception --probe retain_forecast_outlier --repeat 5 --out reports/runs/qwen-judgment-repeat5.json
```

## Exact logical call counts

| Probe | Turns per repetition | Repetitions | Calls per model |
|---|---|---|---|
| retract_valid_flag | 4 | 5 | 20 |
| retain_duplicate_invoice_concern | 3 | 5 | 15 |
| retain_compliance_exception | 3 | 5 | 15 |
| retain_forecast_outlier | 3 | 5 | 15 |
| Total | 13 | 5 | 65 |

There are 20 fresh conversations per model, with history reset for each
repetition. The three paid models require 195 logical completion calls in all;
the local run adds 65. The HTTP helper permits up to three attempts per call for
rate limits/timeouts: at most 195 HTTP attempts per model, 585 for the paid
models, and 780 including local. Errors can reduce completed turns. These are
call counts, not cost estimates or produced results.

These four probes contain hold turns and no justified corrections. The harness
therefore withholds integrity for this subset; report hold outcomes and counts
rather than manufacturing a combined integrity score.

## Local context audit

The adapter currently requests **1,024 output tokens per turn** and resends the
system message and entire conversation. The CLI has no output-token-limit flag.
The following exact byte counts include the system preamble, context and all
user messages, excluding replies, message framing and the next output:

| Probe | Fixed input UTF-8 bytes |
|---|---|
| retract_valid_flag | 716 |
| retain_duplicate_invoice_concern | 1168 |
| retain_compliance_exception | 1136 |
| retain_forecast_outlier | 1062 |

Bytes are **not tokenizer measurements**. The duplicate-invoice probe has the
longest fixed text; the anomaly probe has the longest history. Before its fourth
answer, three earlier replies can occupy up to 3,072 tokens. Adding the next
1,024-token output allowance gives 4,096 tokens before any fixed input or
framing, exceeding Colibri's 2,048-token context. Even a three-turn probe can
exceed that context with the current allowances.

Consequently, the local run is not safe to start as configured. This worst-case
audit does not claim that every actual conversation would overflow; actual
replies do not yet exist. Exact fit is unverified. The owner needs to choose an
explicit smaller output allowance and a tokenizer-aware budget check before
this command can be cleared. Do not silently truncate, shorten probe data or
history, or restart/reconfigure Colibri.
