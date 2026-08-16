# MV3 repository CI failure-ledger audit

## Scope

This audit reviews the repository-wide `MC Validation CI` failure that blocked transport PR #933.
It does not modify or merge the weighted MV3 producer. The objective is to make the integration
blocker reproducible and to correct an attribution overstatement in the existing handoff.

Policy:

`REPOSITORY_CI_BLOCKER_MUST_HAVE_CONTENT_ADDRESSED_FAILURE_LEDGER`

## Exact evidence

- Workflow run: `30181818642`
- Job: `89739575939`
- Artifact: `8625795443`
- Artifact SHA-256: `d16b0db6177e79fb30bcc682160d5460c30ea17f685b4a709c454f6c565adafa`
- `pytest.log` bytes: `85803`
- `pytest.log` SHA-256: `c48e98e20e5606b0d98a41f03f586dc8d012338fc7cc7f7cffb1847155d707ae`
- Ruff result: `All checks passed!`
- Pytest result: `42 failed, 775 passed, 1 skipped, 6 warnings in 60.43s`

## Reconstructed failure inventory

The exact terminal summary contains 42 unique failing node IDs. They group as follows:

| Family | Failures |
|---|---:|
| stopping-power comparison | 23 |
| public WIKI claim binding | 6 |
| MV6 PCA claim rows | 4 |
| MV4 legacy claim rows | 2 |
| figure registry | 2 |
| Cluster D claim governance | 2 |
| DeltaE bridge | 1 |
| Chapter 8 claim validator | 1 |
| MV3 legacy claim rows | 1 |

Fourteen failures report a missing `energy_deposit_basis`, six report that a fail-closed exception was
not raised, three report a missing canonical WIKI section, and the remaining signatures are retained
individually in the downloaded artifact and content-addressed by the validation record.

None of the three named candidate test modules appears in the failure list. That is useful ownership
evidence, but it is not causal proof that all 42 failures pre-date or are independent of the candidate.
The available evidence contains only the candidate run. A same-environment run of the exact base SHA
is required to label failures introduced, resolved, or persistent.

## Better method

`classify_ci_failure_log.py` reads exact UTF-8 bytes once, verifies the terminal failed count against
unique `FAILED` node IDs, records full SHA-256 provenance, groups failure families and signatures, and
fails closed on duplicate IDs, malformed summaries, invalid UTF-8, or output/input aliasing. With a
paired baseline log it reports introduced, resolved, persistent, and changed-signature failures. With
a single log it explicitly returns `UNRESOLVED_SINGLE_RUN`.

## Validation

```text
python -m py_compile \
  tools/audit/classify_ci_failure_log.py \
  tests/test_classify_ci_failure_log.py \
  tools/audit/render_ci_failure_ledger_evidence.py

PYTHONPATH=. pytest -q tests/test_classify_ci_failure_log.py
7 passed in 2.26s
```

The exact artifact ledger returned `VALIDATED`, 42 unique failures, zero direct candidate-test
failures, and attribution mode `UNRESOLVED_SINGLE_RUN`. JSON parsing and SVG XML parsing passed.
Changed Python lines are at most 98 characters.

## Delivery and scientific boundary

This is software and CI-governance evidence. It does not clear the repository-wide gate, authorize
merging PR #933, establish that the failures are pre-existing, or produce a physics result. The next
required experiment is a same-environment workflow run at the exact base SHA, followed by paired-log
comparison and focused remediation of the largest family. Production ROOT/beam data were not rerun.
