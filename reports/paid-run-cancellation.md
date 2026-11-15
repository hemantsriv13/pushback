# Paid runs cancelled in favor of Qwen

The owner initially authorized completion of the planned paid runs. A read-only
Anthropic model-list request confirmed the three recorded model IDs were
available. The Haiku, Sonnet and Opus `--repeat 5` commands were then started.

The owner subsequently instructed: "replace the paid runs with qwen". All three
client processes were interrupted immediately and each exited non-zero. No paid
completion process remains active in this task. Already submitted provider
requests cannot be recalled, so charges may have occurred.

The last captured progress output showed:

| Client | Completed conversations reported before interruption |
|---|---|
| Haiku | 2 of 20 |
| Sonnet | 1 of 20 |
| Opus | 1 of 20 |

These are client progress observations, not a saved evaluation dataset. The CLI
wrote only at the end of a run, so interruption left no paid JSON result files
under `reports/runs/`. The reply text, exact number of in-flight/completed HTTP
requests, and actual provider charges cannot be reconstructed from those logs.
No paid scores or fold rates have been invented from the progress messages.

The replacement local runner checkpoints every completed response, including
its full request, usage and finish reason, before grading. It uses only
`http://127.0.0.1:8000/v1`, with an explicit 128-token output cap and context
compaction disabled. Prompts and history are not shortened.

Colibri was reachable during the initial read-only check, but subsequently
refused connections before the replacement run could start. No Qwen inference
request was sent. The shared service was not started, stopped or restarted.
