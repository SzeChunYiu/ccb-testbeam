# AUD-MC-003 — strict issue #880 producer remediation

## Session identity

- UTC stamp: `2026-07-25T040311Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `2868b1a7aaa15cd6a03970c2385c2b7ab53c5598`
- Validated implementation/evidence head: `7506eecfc54f550f2583bad24d0c85de383bbbde`
- Active-task completion: `d7ef92fc1320b3e44fb8de1e802f34cf1f71d8c9`
- Acceptance: **PARTIAL** — strict code/evidence validated; exact production rerun blocked

## Start-of-run review

Authenticated GitHub reads inspected repository permissions, the latest `main` history, open pull
requests, issue #880, repository-local coordination records, the historical issue #879/#880/#887
producer, and its retained result. Direct pushes to `main` were available. No task branch, force
push, history rewrite, or PR transport was used.

The exact historical producer was:

- `scripts/single_stave/issues879_880_887_mc_study.py`;
- Git blob `bc1220fdfe1010989fd8ab273f8c1b1fcf708b2c`.

The retained result was:

- `reports/issues879_880_887_mc_analysis/issues879_880_887_result.json`;
- Git blob `37d69e2c697a7ce7c9e1eff9aeff48539551d922`.

Issue #880 remains open and requests correct use of MC event weights.

## Confirmed defects

The retained producer:

1. replaces a nonfinite `PrimaryWeight` with `1.0`;
2. allows weighted mean, median, fraction, and correlation helpers to return unweighted values;
3. substitutes an epsilon denominator for a relative comparison;
4. labels signed bias fields without unambiguous direction and denominator semantics;
5. records no exact ROOT digest, producer commit, command/environment, or weight-policy version.

These behaviors allow an invalid weight vector to produce plausible numerical output rather than a
controlled failure.

## Correction delivered

### Reusable numerical contract

Added `scripts/single_stave/strict_event_weights.py` with policy
`MC_WEIGHT_VECTOR_MUST_BE_UNAMBIGUOUS_FINITE_NONNEGATIVE_AND_EVENT_ALIGNED`.

It requires a one-dimensional, finite, nonnegative, event-aligned vector with at least one positive
weight; uses `math.fsum` for weighted sums and ESS components; supplies fail-closed weighted mean,
median, fraction, and correlation; represents zero relative denominators as JSON `null`; emits both
weighted-minus-unweighted and legacy-minus-weighted comparisons; hashes exact files; and publishes
JSON atomically with protected-input alias rejection.

### Strict study entry point

Added `scripts/single_stave/issues879_880_887_mc_study_strict.py` with policy
`ISSUE880_STRICT_CONTENT_ADDRESSED_WEIGHTED_RERUN`.

It:

- requires exactly one `PrimaryWeight` and `PrimaryPDG` per loaded event;
- checks loaded count against ROOT metadata and `--entry-stop`;
- rejects nonfinite or negative scintillator deposits;
- measures ROOT size/SHA-256 before and after the ROOT read and requires identity;
- refuses a tracked-dirty checkout;
- installs strict estimators into the retained #879/#887 study logic;
- generates direction-explicit #880 results and a corrected visual;
- records git commit, exact argv/shell command, runtime versions, and script hashes;
- refuses to replace prior outputs without `--overwrite`;
- publishes the result JSON atomically and protects ROOT/code inputs from aliasing.

The historical producer remains in place only for provenance and shared non-weight-specific study
logic; it is not an accepted entry point for a new scientific run.

## Independent calculation

Tracked retained values were independently reconstructed:

- first-B mean: unweighted `6.674567424757 MeV`, weighted `2.134364334727324 MeV`;
- weighted-minus-unweighted relative to `|unweighted|`: `-68.02243203341332%`;
- legacy unweighted overstatement relative to `|weighted|`: `+212.7192164972955%`;
- entering-B deuteron fraction: unweighted `0.5719111928400914`, weighted
  `0.16606032425392264`;
- legacy-minus-weighted: `+40.585086858616876 percentage points`;
- legacy overstatement relative to `|weighted|`: `+244.39966043037631%`.

No arithmetic discrepancy was found in those retained endpoints. The correction addresses invalid
weight handling, direction/denominator clarity, and provenance.

## Files added or updated

Added:

- `scripts/single_stave/strict_event_weights.py`;
- `scripts/single_stave/issues879_880_887_mc_study_strict.py`;
- `scripts/single_stave/ISSUE880_STRICT_RERUN.md`;
- `tests/test_strict_event_weights.py`;
- `tests/test_issues879_880_887_strict_producer.py`;
- `tools/audit/render_issue880_strict_producer_evidence.py`;
- `docs/validation/issue880_strict_producer_audit.md`;
- `docs/validation/issue880_strict_producer_validation.json`;
- `docs/validation/issue880_strict_producer.svg`;
- this immutable archive.

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`;
- `chatgpt_todo/BACKLOG.md`;
- `chatgpt_todo/HANDOFF.md` after this archive.

## Validation

Executed locally on the strict module/wrapper, focused tests, and renderer prepared for publication:

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

JSON parsing and SVG XML parsing passed. Changed Python files were no longer than 100 characters per
line. The strict module and wrapper were re-read from remote `main`; Git blobs are
`1e87372f0db109b9428cd2c56576a46cbd45a259` and
`5c0138904db3ce2ea743dd0d75cb1cd0751bcf1d`, respectively.

The exact historical source was inspected through its GitHub blob. Connector-returned repository
bytes were not materialized into the local runtime, so the local wrapper harness used a minimal
API-compatible historical module fixture. The committed test imports the actual sibling producer in
a complete checkout. No repository-wide test or production ROOT execution is claimed.

No status checks were attached to implementation head `7506eecfc54f550f2583bad24d0c85de383bbbde`.

## Direct-main commit sequence

- `4b0116d127fe1e2c80287644812eac3944f81afb` — task claim;
- `5365c4a000e7df5e7c9fc1a30d3bed0070203b62` — strict weighted statistics;
- `b86ab5880e0e6d88933620c7cbc3aa187b173ac4` — strict rerun entry point;
- `371d56ec7d17678a0ddd55b336f86033ed8c6466` — strict primitive tests;
- `3804df82b0cd01881efa615151881a12103cdfe7` — producer tests;
- `f669c62ad586d4b9a7fe277d601f7e7951e982f2` — evidence renderer;
- `8fff914f8c98d28f9e0b9bc495270fc9c92eb62b` — validation JSON;
- `3c18646f6f77237573a522813e99d251dd74af27` — SVG evidence;
- `a3808ecf348953e125b1e4d361106981fcc0f1bb` — validation audit;
- `2caff6a499a1f26d2677eba52335b19cfb4d1a8f` — rerun instructions;
- `7506eecfc54f550f2583bad24d0c85de383bbbde` — backlog registration;
- `d7ef92fc1320b3e44fb8de1e802f34cf1f71d8c9` — active-task completion.

The connector returned successful direct-main commit SHAs rather than conventional textual
`git push` stdout. Remote history showed the sequence without an interleaved commit through the
active-task completion.

## Scientific boundary and blockers

The exact one-million-event ROOT bytes were unavailable. This run therefore did not:

- rerun the retained production study;
- prove that the first primary is the correct event-weight carrier;
- estimate weighted statistical or systematic uncertainty;
- evaluate sensitivity to high-weight tails under selections;
- regenerate production plots from exact input bytes;
- establish selection transfer, detector calibration, species identification, or data/MC closure.

The retained result remains `FLAWED`. `AUD-MC-003` remains `PARTIAL` until the strict producer is
run from a clean content-addressed checkout on the exact ROOT input, uncertainty and tail stability
are quantified, all artifacts are regenerated, and scientific closure passes.

## Coordination limitation

`SESSION_LOG.md` is append-only and substantially longer than the safely available connector
snapshot. The connector exposes whole-file replacement rather than a byte-safe append operation;
reconstructing and replacing a partial log could destroy unrelated provenance. It was therefore not
replaced. This immutable archive and the latest `HANDOFF.md` preserve the complete append-equivalent
record. No claim is made that the aggregate matrices or master index were fully synchronized in this
focused unit.

## Next action

Run the documented strict command on the exact one-million-event ROOT file from a clean checkout.
Retain ROOT and output hashes, exact command/environment, strict producer commit, weighted
uncertainty, weight-tail and selection stability, all regenerated plots, and a data/MC closure review
before resolving issue #880 or restoring affected scientific claims.
