# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-25T040311Z`
- **Task:** `AUD-MC-003`
- **Unit:** strict fail-closed, content-addressed issue #880 producer remediation
- **Initial remote `main`:** `2868b1a7aaa15cd6a03970c2385c2b7ab53c5598`
- **Validated implementation/evidence head:** `7506eecfc54f550f2583bad24d0c85de383bbbde`
- **Active-task completion:** `d7ef92fc1320b3e44fb8de1e802f34cf1f71d8c9`
- **Immutable archive:** `chatgpt_todo/archive/2026-07-25T040311Z_AUD-MC-003_STRICT_PRODUCER.md`
- **Archive commit:** `0a1de05bc16352fa2406cf85decf55f3ce59ad97`
- **Destination:** direct sequential commits to remote `main`; no force-push, history rewrite, task branch, or PR transport
- **Acceptance:** **PARTIAL** — code and synthetic evidence validated; exact production rerun remains blocked

## Start-of-run review

Authenticated GitHub reads inspected repository metadata and permissions, current `main`, recent
history, open pull requests, issue #880, `chatgpt_todo` coordination, the historical issue
#879/#880/#887 producer, and its retained result. The exact initial remote head was
`2868b1a7aaa15cd6a03970c2385c2b7ab53c5598`. No concurrent commit was interleaved through the
validated implementation/evidence sequence.

Issue #880 remains open and asks that MC event weights be used correctly. PR #868 was not reopened,
extended, or merged.

## Exact repository evidence

Historical producer:

- path: `scripts/single_stave/issues879_880_887_mc_study.py`;
- Git blob: `bc1220fdfe1010989fd8ab273f8c1b1fcf708b2c`.

Retained result:

- path: `reports/issues879_880_887_mc_analysis/issues879_880_887_result.json`;
- Git blob: `37d69e2c697a7ce7c9e1eff9aeff48539551d922`;
- nominal event count: `1,000,000`;
- retained ESS: `347261.8375452912` (`0.34726183754529116` of nominal).

## Confirmed defects

The historical producer can silently create plausible output from an invalid weight state:

1. nonfinite `PrimaryWeight` values are replaced by `1.0`;
2. weighted mean, median, fraction, and correlation helpers can return unweighted estimates;
3. a relative comparison uses an epsilon denominator rather than declaring an undefined relative
   quantity;
4. signed bias fields do not unambiguously name comparison direction and denominator;
5. the result omits exact ROOT SHA-256, producer commit, command/environment, and policy version.

## Correction delivered

Added `scripts/single_stave/strict_event_weights.py` under policy:

`MC_WEIGHT_VECTOR_MUST_BE_UNAMBIGUOUS_FINITE_NONNEGATIVE_AND_EVENT_ALIGNED`

It provides strict one-dimensional/event-aligned weight validation, rejection of nonfinite,
negative, empty, and all-zero vectors, `math.fsum` weighted primitives, fail-closed median/fraction/
correlation, direction-explicit comparisons with zero denominators represented by JSON `null`, file
hashing, and protected atomic JSON publication.

Added `scripts/single_stave/issues879_880_887_mc_study_strict.py` under policy:

`ISSUE880_STRICT_CONTENT_ADDRESSED_WEIGHTED_RERUN`

The strict entry point:

- requires exactly one `PrimaryWeight` and `PrimaryPDG` per loaded event;
- checks the event count against ROOT metadata and `--entry-stop`;
- rejects nonfinite or negative scintillator energy deposits;
- requires identical ROOT byte count/SHA-256 before and after the ROOT read;
- refuses a tracked-dirty checkout;
- installs strict estimators into the retained #879/#887 logic;
- publishes explicit weighted-minus-unweighted and legacy-minus-weighted #880 fields;
- records git commit, exact argv/shell command, runtime versions, and all producer hashes;
- requires explicit `--overwrite` before replacing a prior artifact set;
- publishes the result JSON atomically and protects ROOT/code paths from aliasing.

The historical entry point remains only for provenance and shared non-weight-specific study/plot
logic; it is not accepted for a new scientific rerun.

## Independent arithmetic reconstruction

Tracked endpoint values were independently reconstructed:

- first-B mean unweighted: `6.674567424757 MeV`;
- first-B mean weighted: `2.134364334727324 MeV`;
- weighted change relative to `|unweighted|`: `-68.02243203341332%`;
- legacy unweighted overstatement relative to `|weighted|`: `+212.7192164972955%`;
- deuteron fraction unweighted: `0.5719111928400914`;
- deuteron fraction weighted: `0.16606032425392264`;
- legacy-minus-weighted: `+40.585086858616876 percentage points`;
- legacy overstatement relative to `|weighted|`: `+244.39966043037631%`.

No arithmetic mismatch was found in these retained endpoints. The correction addresses invalid
weight handling, semantic ambiguity, and missing provenance.

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
- `chatgpt_todo/archive/2026-07-25T040311Z_AUD-MC-003_STRICT_PRODUCER.md`.

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`;
- `chatgpt_todo/BACKLOG.md`;
- this handoff.

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

JSON parsing and SVG XML parsing passed. Changed Python files were no longer than 100 characters per
line. The committed strict module and wrapper were re-read from remote `main` as Git blobs
`1e87372f0db109b9428cd2c56576a46cbd45a259` and
`5c0138904db3ce2ea743dd0d75cb1cd0751bcf1d`.

The exact historical source was inspected through its GitHub blob. Connector-returned repository
bytes were not materialized into the local runtime, so local wrapper tests used a minimal
API-compatible historical fixture. The committed test imports the actual sibling producer in a
complete checkout. No repository-wide pytest, ROOT execution, or GitHub Actions success is claimed.
No status checks were attached to implementation head `7506eecfc54f550f2583bad24d0c85de383bbbde`.

## Direct-main commit sequence

- `4b0116d127fe1e2c80287644812eac3944f81afb` — task claim;
- `5365c4a000e7df5e7c9fc1a30d3bed0070203b62` — strict weighted statistics;
- `b86ab5880e0e6d88933620c7cbc3aa187b173ac4` — strict rerun entry point;
- `371d56ec7d17678a0ddd55b336f86033ed8c6466` — strict primitive tests;
- `3804df82b0cd01881efa615151881a12103cdfe7` — strict producer tests;
- `f669c62ad586d4b9a7fe277d601f7e7951e982f2` — evidence renderer;
- `8fff914f8c98d28f9e0b9bc495270fc9c92eb62b` — validation JSON;
- `3c18646f6f77237573a522813e99d251dd74af27` — SVG evidence;
- `a3808ecf348953e125b1e4d361106981fcc0f1bb` — validation audit;
- `2caff6a499a1f26d2677eba52335b19cfb4d1a8f` — rerun instructions;
- `7506eecfc54f550f2583bad24d0c85de383bbbde` — backlog registration;
- `d7ef92fc1320b3e44fb8de1e802f34cf1f71d8c9` — active-task completion;
- `0a1de05bc16352fa2406cf85decf55f3ce59ad97` — immutable archive.

The connector returned successful direct-main commit SHAs rather than conventional textual
`git push` stdout. A following confirmation-only handoff update records the complete delivery SHA
and verifies that remote `main` contains it.

## Scientific boundary

This is validated software/provenance remediation plus independent arithmetic from tracked summary
values. It does not rerun the exact one-million-event ROOT study, prove the first-primary weight
definition, estimate weighted uncertainty, evaluate high-weight-tail stability, regenerate the
production artifact bundle, validate selection transfer, or establish calibration, species
identification, or data/MC closure.

The retained result remains `FLAWED`; `AUD-MC-003` remains `PARTIAL`. Closing issue #880 requires a
clean content-addressed run of the strict producer on the exact ROOT input, uncertainty and tail
stability, regenerated plots, and scientific closure.

## Coordination limitation

`SESSION_LOG.md` is append-only and its complete current bytes were not safely available for a
byte-preserving append. The connector exposes whole-file replacement rather than append semantics;
replacing a partial reconstruction could erase unrelated provenance. It was not replaced. The
immutable archive and this handoff preserve the complete append-equivalent record. No claim is made
that `MASTER_INDEX.md` or every aggregate matrix was synchronized in this focused unit.

## Next action

Execute the command in `scripts/single_stave/ISSUE880_STRICT_RERUN.md` from a clean checkout on the
exact one-million-event ROOT file. Retain input/output hashes, command/environment, strict producer
commit, weighted uncertainty, weight-tail and selection-stability diagnostics, all plots, and a
data/MC closure review before resolving issue #880 or restoring affected claims.
