# P10f: Automatic conditional-template claim linter

- **Ticket:** `1781025208.1030.73ae38c0`
- **Worker:** `testbeam-laptop-4`
- **Input:** existing `reports/*/{result.json,REPORT.md}` artifacts only; no Monte Carlo and no raw ROOT reread for this infrastructure ticket.

## Reproduction First

The linter reproduces the P10e registry anchor from the committed P10e result before scanning the wider report corpus.

| quantity | expected | observed | pass |
| --- | --- | --- | --- |
| P10e selected B-stave pulses | 640737 | 640737 | True |
| P10e analysis selected rows | 377362 | 377362 | True |
| P10e required registry controls | 5 | 5 | True |
| P10e registry status | pass | pass | True |
| P10e family-heldout folds | 2 | 2 | True |
| holdout_sample_i conditional-minus-empirical delta | positive no q-space win | 0.013014769388423343 | True |
| holdout_sample_ii conditional-minus-empirical delta | positive no q-space win | 0.029225251206238367 | True |

## Traditional Gate

The production method is a schema-aware deterministic linter. It marks a report as failing only when a promoted q-space conditional/template ML win is present and at least one required P10e control is missing or dirty: mean-template, shuffled-target, train/eval run overlap, train/eval key overlap, and no run/event feature use.

| scanned_result_json | in_scope_p10_or_template | promoted_claims | control_complete | linter_failures |
| --- | --- | --- | --- | --- |
| 229 | 9 | 0 | 2 | 0 |

Current failures:

No current committed P10/P-template result fails the promoted-claim gate.

## ML Triage

The ML method is deliberately advisory: a leave-one-report-out multinomial Naive Bayes text model predicts whether a result schema is control-complete. It is not allowed to override the deterministic gate.

| method | split | n_reports | positive | accuracy | accuracy_ci95 | roc_auc | used_in_gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| multinomial_naive_bayes_text_triage | leave-one-report-out; report-bootstrap confidence interval | 9 | 2 | 0.889 | [0.6666666666666666, 1.0] | 0.929 | False |

## Leakage Check

The linter treats suspiciously good ML/template claims as unsafe unless the control names and clean overlap/feature checks are present in the report artifact. Reports that say the result is diagnostic or not promoted are not failed as promoted claims, but their missing controls remain visible in `linter_decisions.csv`.

## Verdict

The P10e control schema is reproducible from committed artifacts, and the deterministic linter finds no current promoted q-space conditional/template claim that lacks the required clean controls.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/p10f_1781025208_1030_73ae38c0_claim_linter.py --config configs/p10f_1781025208_1030_73ae38c0_claim_linter.json
```
