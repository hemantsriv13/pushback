# Pushback handoff — paused by owner, 15 November 2026

The owner explicitly asked to stop and remember this conversation. Do not resume
evaluations or other work until the owner asks to continue.

## Where to resume

- Repository: `C:\Users\Hemant\Documents\GitHub\pushback`.
- Branch: `fix/evidence-and-readme`; last committed HEAD: `cfb2275`.
- Current chat title: **Continue archived chat**.
- Chat ID: `01a1d91e-580d-74c3-b800-f13443bcd99f`.
- This handoff and `reports/runs/` are saved locally and uncommitted.
- Last full suite: **134 passed**. The mock CI gate passed before each commit.
- README still says 129 tests and needs a later documentation update.

## Completed evidence repair

Six initial commits repaired Sonnet provenance, corrected fixture/document
references, fixed the hard-sheet caution, applied two owner-approved dev-only
probe rules, saved offline regrades/agreement reports, and rewrote the README.

- `127c56d`: restore original `sonnet-1.json`; preserve replacement as `sonnet-3.json`.
- `d73a059`: avoid asking hard-sheet reviewers to label the same sheet again.
- `7bef214`: document dev-only rule proposal, run plan and guide-file audit.
- `593c3e1`: apply the two approved dev rules and paired regressions.
- `6c43357`: save clean-grader regrades, agreement reports and executed audit.
- `91aa96b`: replace stale README claims with measured repository evidence.

Both human CSVs remain unchanged. Only the explicitly authorized provenance
repair changed files in historical `runs/`. Seven saved files regrade to four
integrity scores of 100%, two of 95%, and one of 75% under grader `593c3e1`.

Agreement, excluding unclear labels:

| Sheet | Dev | Test | Unclear dev/test | Remaining false passes |
|---|---|---|---|---|
| sheet.csv | 22/22 | 18/18 | 0/0 | 0 |
| hard.csv | 9/9 | 8/9 | 1/1 | 1, held-out Opus |

The owner-unclear `opus-1` reply remains unresolved. The separate held-out
`r5fdbc158e7` false pass was measured, not used to tune rules. Preserve the
separation: no new rule design from held-out replies.

## Paid runs are CANCELLED

The owner first authorized the three planned paid runs, then explicitly said
**replace the paid runs with Qwen**. All three paid client processes were
stopped. Already submitted requests may have incurred charges. No paid result
JSON was written before interruption, so exact usage/cost cannot be recovered.
See `reports/paid-run-cancellation.md`. Do not resume paid models.

## Qwen-only run: partial evidence preserved

The owner manually started Colibri after this session was denied access to the
model files on `D:\LocalAI`. Do not assume the model is missing; it is outside
this session's readable workspace. Do not restart or reconfigure the shared
service without a new request.

Runner: `scripts/run_qwen_judgment.py`.

- Only `qwen3-4b-instruct-2507-q4km` at `http://127.0.0.1:8000/v1`.
- Same four probes, five repetitions: 20 conversations / 65 completion calls.
- Output cap 128 tokens; full prompt/history retained; compaction explicitly off.
- Client evaluation budget stays 2,048 tokens; larger advertised server capacity
  is accepted, smaller capacity is rejected. The service advertised 4,096 and
  later 2,048 during readiness checks.
- Per-response JSONL captures full requests/replies, usage and finish reasons.
- Output-cap hits are counted and must be disclosed in any eventual report.
- Context bounds are conservative planning allowances, not tokenizer measurements;
  actual provider usage is checked on every received response.

Run artifacts — do not overwrite or delete them:

1. `reports/runs/qwen-judgment-repeat5.json` and matching `.requests.jsonl`:
   first attempt suffered engine HTTP 500, refused connections and a connection
   reset. The JSON checkpoint contains 13 attempted conversations: 12 errored
   and one completed. There are five received-response journal entries. Its older
   `completed_conversations` metadata is misleading because it counted attempted
   conversations; use the actual probe error fields. The runner was subsequently
   fixed at `cfb2275` to distinguish attempted and successful conversations.
2. `reports/runs/qwen-judgment-repeat5-attempt2.json` and matching `.requests.jsonl`:
   service recovered. The owner stopped the task after three completed anomaly
   conversations. The checkpoint records 12 received responses, no conversation
   errors, and three output-cap hits. The JSONL has 13 entries and may include
   an additional received response from the next, incomplete conversation. Treat
   the JSONL as the detailed evidence; do not infer a full completed evaluation.

The second evaluation client was interrupted at the owner's stop request and
exited non-zero. No evaluation client remains active in this task. Colibri
itself was left alone. These partial attempts are not a completed repeat-5
dataset and must not be presented as the planned full result.

Additional commits after the evidence repair:

- `413dffc`: bounded local runner and response checkpoints.
- `e17c420`: paid cancellation audit and clear offline errors.
- `7300231`: Qwen-only plan and README status.
- `6487ae9`: allow larger server contexts while retaining the fixed budget.
- `cfb2275`: checkpoint local connection failures; distinguish incomplete conversations.

## GitHub push remains blocked

The owner authorized pushing this branch, not opening/merging a PR. This session
cannot retrieve GitHub credentials: VS Code askpass is inaccessible; shell helper
startup is restricted; direct noninteractive Git Credential Manager found no
usable cached credential. No secrets were printed or saved. No new commits from
the latest work have been pushed to `fix/evidence-and-readme`.

The owner can push from their own authenticated terminal:

```powershell
cd C:\Users\Hemant\Documents\GitHub\pushback
git push -u origin fix/evidence-and-readme
```

## Next time, only after the owner asks to continue

1. Check branch/status and existing journals; preserve all partial attempts.
2. Decide whether to continue the missing repetitions or run a clearly separate
   complete dataset. Never silently replace partial evidence or pool retries
   into a claimed repeat-5 sample. Inspect service health before inference.
3. Complete only the local Qwen evaluation. No paid API fallback.
4. Produce results solely from saved complete transcripts, disclose output caps,
   errors and incomplete samples. This subset has no justified corrections, so
   integrity is undefined and must remain withheld.
5. Update README test count and Qwen status, commit partial/evaluation evidence
   with accurate descriptions, run full tests and the mock gate before commits.
6. Push if authentication is available; otherwise give the owner the exact
   terminal command. Do not open or merge a PR.

Hard constraints remain: no human CSV edits, no additional historical `runs/`
edits, no invented or rounded results, no judge model, no new dependencies
without approval, and no commits to main. The separate guide implementation
already exists on `feature/local-guide` in sibling `pushback-local-guide`;
do not recreate or merge it as part of this repair.
