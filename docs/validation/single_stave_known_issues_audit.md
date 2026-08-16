# Single-stave known-issues status audit

## Scope

This audit checks whether `geant4/single_stave/KNOWN_ISSUES.md` matches the
canonical repository-recorded runtime evidence in
`docs/validation/G4_VALIDATION_RESULTS.md`. It also maps the validated technical
content of closed PR #868 to current `main` without merging the stale branch.

## Confirmed documentation defect

The pre-correction file contradicted itself. Its opening update said photon
collection and the authoritative overlap test were resolved, but lower sections
still labelled both items as open and ended with
`photon-collection readout IN_PROGRESS`. It also omitted the later exact
1-thread/48-thread and multiseed validation results.

The fail-closed validator reproduced the defect on the exact pre-correction text:

- exit status: `1`;
- status: `FLAWED`;
- findings: `19`;
- finding classes: 12 missing current-status tokens, 4 missing seed means, and
  3 stale resolved-issue narratives.

## Canonical runtime evidence

The tracked validation record states:

- Geant4 11.2.2, GCC 12.3.0, LUNARC node `hpua40`;
- 100 MeV protons and 500 events per run;
- 27/27 event branches exactly equal for same-seed 1T versus 48T;
- 1,170,091 photon records with all six stored fields exactly equal;
- four independent seed means of 177.1, 178.0, 179.5, and 178.5 PE/event;
- cross-seed mean 178.3 PE/event with RSE 0.48%.

The correction reports these results while preserving the scientific boundary:
this fixed-configuration simulation is not a detector calibration, stopping-power
closure, data/MC transfer result, or peer-reviewed performance measurement.

## PR #868 integration map

PR #868 is closed and unmerged. A file-level review showed that its validated
implementation is already represented on current `main`:

| Area | Current-main state |
|---|---|
| multiseed RNG analyzer | exact Git blob match |
| event-tree comparator | exact Git blob match |
| photon-tree comparator | exact Git blob match |
| three focused test modules | exact Git blob matches |
| thread configuration fields and CLI | semantic superset with stricter numeric parsing |
| master-owned RNG and no worker reseeding | present |
| requested/effective/forced thread provenance | present in run metadata |
| MC validation workflow | covers all six exact-matched scripts/tests and runs the broader unit suite |

The stale PR branch therefore must not be merged merely for transport. Its old
`chatgpt_todo/` coordination files are superseded by current-main coordination.
The current-main implementation remains subject to the scientific limits recorded
here and under `BLK-G4-SP-001`.

## Validator

`tools/audit/validate_single_stave_known_issues.py` uses policy
`KNOWN_ISSUES_MUST_MATCH_REPOSITORY_RECORDED_G4_VALIDATION`. It reads both files
as exact UTF-8 bytes, records size and SHA-256, parses the canonical result
quantities, requires matching status/boundary tokens, and rejects stale open-issue
phrases. Malformed input returns controlled status 2.

## Validation

```text
python -m py_compile \
  tools/audit/validate_single_stave_known_issues.py \
  tests/test_validate_single_stave_known_issues.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_single_stave_known_issues.py -q

5 passed in 0.05s
```

Direct validation of the corrected files returned `VALIDATED` with zero issues.
JSON parsing and SVG XML parsing passed. Maximum changed Python line lengths were
97 characters in the validator and 93 in the tests.

## Acceptance boundary

This unit validates repository documentation and implementation integration. It
does not independently access the LUNARC ROOT files, rerun Geant4, reproduce the
reported PE distribution, validate stopping power, calibrate PE/MeV, or establish
beam-data agreement. The runtime facts are repository-recorded evidence, and the
unresolved scientific limitations remain explicit.
