# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-25T040311Z`
- **Task:** `AUD-MC-003`
- **Unit:** strict fail-closed, content-addressed issue #880 producer remediation
- **Initial remote `main`:** `2868b1a7aaa15cd6a03970c2385c2b7ab53c5598`
- **Validated implementation/evidence head:** `7506eecfc54f550f2583bad24d0c85de383bbbde`
- **Complete delivery handoff / recorded after-SHA:** `21bfbea26af83ad8787d121f96f4b5e698a9b0e2`
- **Immutable archive:** `chatgpt_todo/archive/2026-07-25T040311Z_AUD-MC-003_STRICT_PRODUCER.md`
- **Destination:** direct sequential commits to remote `main`; no force-push, branch transport, PR, or history rewrite
- **Push result:** GitHub contents writes returned successful direct-main commit SHAs; post-write history confirmed the delivery handoff on remote `main`
- **Acceptance:** **PARTIAL** — strict code and synthetic evidence validated; exact production rerun remains blocked

This confirmation-only update records that `21bfbea26af83ad8787d121f96f4b5e698a9b0e2` was present on
remote `main`. It does not change the scientific implementation or validation state.

## Exact repository evidence and defect

The historical producer is
`scripts/single_stave/issues879_880_887_mc_study.py`, Git blob
`bc1220fdfe1010989fd8ab273f8c1b1fcf708b2c`. The retained result is
`reports/issues879_880_887_mc_analysis/issues879_880_887_result.json`, Git blob
`37d69e2c697a7ce7c9e1eff9aeff48539551d922`.

The historical producer converts nonfinite event weights to `1.0`, permits weighted mean, median,
fraction, and correlation to fall back to unweighted estimators, uses an epsilon relative
denominator, leaves signed comparison direction ambiguous, and omits exact ROOT/producer/command
provenance. The retained one-million-event output remains a flagged diagnostic.

## Correction delivered

Added `scripts/single_stave/strict_event_weights.py` under policy:

`MC_WEIGHT_VECTOR_MUST_BE_UNAMBIGUOUS_FINITE_NONNEGATIVE_AND_EVENT_ALIGNED`

It requires a one-dimensional, finite, nonnegative, event-aligned weight vector with at least one
positive weight; uses `math.fsum` weighted primitives; fails closed for mean, median, fraction,
correlation, and ESS; emits both comparison directions with explicit denominators; represents zero
relative denominators as JSON `null`; hashes exact files; and publishes protected JSON atomically.

Added `scripts/single_stave/issues879_880_887_mc_study_strict.py` under policy:

`ISSUE880_STRICT_CONTENT_ADDRESSED_WEIGHTED_RERUN`

It requires exactly one `PrimaryWeight` and `PrimaryPDG` per loaded event, verifies event count,
rejects invalid energy deposits, requires identical ROOT SHA-256 before/after reading, requires a
clean tracked checkout, installs strict estimators into the retained #879/#887 logic, emits
direction-explicit #880 fields, records commit/command/runtime/script hashes, requires explicit
overwrite, and atomically publishes the result JSON.

Also added focused tests, rerun instructions, a deterministic renderer, validation JSON, Markdown
audit, SVG evidence, backlog state, active-task completion, and immutable archive.

## Independent retained arithmetic

- first-B unweighted mean: `6.674567424757 MeV`;
- first-B weighted mean: `2.134364334727324 MeV`;
- weighted-minus-unweighted relative to `|unweighted|`: `-68.02243203341332%`;
- legacy overstatement relative to `|weighted|`: `+212.7192164972955%`;
- deuteron unweighted fraction: `0.5719111928400914`;
- deuteron weighted fraction: `0.16606032425392264`;
- legacy-minus-weighted: `+40.585086858616876 percentage points`;
- legacy overstatement relative to `|weighted|`: `+244.39966043037631%`.

The endpoints are arithmetically consistent. The correction addresses invalid weight handling,
semantic ambiguity, and missing provenance.

## Validation

```text
python -m py_compile \
  scripts/single_stave/strict_event_weights.py \
  scripts/single_stave/issues879_880_887_mc_study_strict.py \
  tests/test_strict_event_weights.py \
  tests/test_issues879_880_887_strict_producer.py \
  tools/audit/render_issue880_strict_producer_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_strict_event_weights.py \
  tests/test_issues879_880_887_strict_producer.py

17 passed in 0.04s
```

JSON and SVG XML parsing passed. Changed Python lines were at most 100 characters. Remote `main`
re-reads identified strict module blob `1e87372f0db109b9428cd2c56576a46cbd45a259` and wrapper blob
`5c0138904db3ce2ea743dd0d75cb1cd0751bcf1d`.

The exact historical source was inspected through GitHub. Because connector-returned repository
bytes were not materialized locally, the local wrapper harness used a minimal API-compatible
historical fixture; the committed test imports the actual sibling producer in a full checkout. No
repository-wide pytest, production ROOT execution, or GitHub Actions success is claimed. No status
checks were attached to implementation head `7506eecfc54f550f2583bad24d0c85de383bbbde`.

## Direct-main commit sequence

- `4b0116d127fe1e2c80287644812eac3944f81afb` — task claim;
- `5365c4a000e7df5e7c9fc1a30d3bed0070203b62` — strict weighted statistics;
- `b86ab5880e0e6d88933620c7cbc3aa187b173ac4` — strict rerun entry point;
- `371d56ec7d17678a0ddd55b336f86033ed8c6466` — strict primitive tests;
- `3804df82b0cd01881efa615151881a12103cdfe7` — strict producer tests;
- `f669c62ad586d4b9a7fe277d601f7e7951e982f2` — evidence renderer;
- `8fff914f8c98d28f9e0b9bc495270fc9c92eb62b` — validation JSON;
- `3c18646f6f77237573a522813e99d251dd74af27` — SVG evidence;
- `a3808ecf348953e125b1e4d361106981fcc0f1bb` — audit report;
- `2caff6a499a1f26d2677eba52335b19cfb4d1a8f` — rerun instructions;
- `7506eecfc54f550f2583bad24d0c85de383bbbde` — backlog registration;
- `d7ef92fc1320b3e44fb8de1e802f34cf1f71d8c9` — active-task completion;
- `0a1de05bc16352fa2406cf85decf55f3ce59ad97` — immutable archive;
- `21bfbea26af83ad8787d121f96f4b5e698a9b0e2` — complete delivery handoff, confirmed on remote `main`.

## Scientific boundary and next action

The exact one-million-event ROOT bytes were unavailable. No production rerun, first-primary weight
definition proof, weighted uncertainty, high-weight-tail stability, regenerated production bundle,
selection transfer, calibration, empirical species identification, or data/MC closure is claimed.
The retained result remains `FLAWED`; `AUD-MC-003` remains `PARTIAL`.

Run the command in `scripts/single_stave/ISSUE880_STRICT_RERUN.md` from a clean checkout on the exact
ROOT input. Retain all hashes and environment details, quantify weighted uncertainty and tail/
selection stability, regenerate all plots, and require data/MC closure before resolving issue #880.

`SESSION_LOG.md` was not replaced because a complete byte-safe append was unavailable and whole-file
replacement of an incomplete append-only snapshot could destroy unrelated provenance. The immutable
archive and this handoff preserve the append-equivalent record.
