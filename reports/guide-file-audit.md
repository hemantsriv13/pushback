# Guide-file audit

Commit `459947e` is titled "Add a local Qwen guide", but its tree contains the
grader/repeats/regrade work, not a guide implementation.

Git's untracked and ignored file listings in the `pushback` working folder
contained no guide, Qwen or Colibri source file. No guide was created or copied
as part of this repair.

There is an existing, separate sibling worktree at
`C:\Users\Hemant\Documents\GitHub\pushback-local-guide`, checked out on
`feature/local-guide` at `b5a349f`. It tracks:

- `pushback/guide.py`
- `pushback/guide_budget.py`
- `pushback/guide_checks.py`
- `pushback/guide_docs.py`
- `pushback/guide_explain.py`
- `pushback/guide_protocol.py`

These are tracked files on that separate branch, not untracked or ignored files
in the reviewed checkout. That branch has not been merged or copied here.
