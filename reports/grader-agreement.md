# Grader agreement with human labels

Sheet: `sheet.csv`. Among labelled replies, the human marked 1 as fail and the grader 1.

Each labelled reply was re-graded with the current rules and compared with the human label. `dev` items may be used to improve the rules; `test` items are held out and only measured, so the `test` row is the honest estimate of how often the grader matches human judgment.

| Split | Labelled | Unclear | Agreement | Grader passed a human fail | Grader failed a human pass | Kappa |
|---|---|---|---|---|---|---|
| **test (held out)** | 18 | 0 | **18 / 18** | 0 | 0 | n/a |
| dev | 22 | 0 | **22 / 22** | 0 | 0 | 1.0 |

Kappa measures agreement beyond what chance alone would give: 1 is perfect, 0 is no better than chance. Unclear items are excluded.

**Caution:** only 1 labelled failure(s). High agreement here shows the grader does not fail good answers; it says little about whether it catches bad ones. Label a hard-case sheet (`pushback labels make --focus hard`) to test that.