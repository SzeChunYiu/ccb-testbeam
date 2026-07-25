# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-25T030239Z`
- **Task:** `AUD-MC-002`
- **Unit:** issue #880 fail-closed event-weight handling and directional bias semantics
- **Initial remote `main`:** `a4b996ccbdfeea120e6deaead863f19d468d1091`
- **Validated implementation/evidence head:** `ddbb9614a6e4b8b58f5b7cf91839fd1708bc41c8`
- **Immutable archive:** `chatgpt_todo/archive/2026-07-25T030239Z_AUD-MC-002_WEIGHT_SEMANTICS.md`
- **Destination:** direct sequential commits to remote `main`; no force-push, history rewrite, task branch, or PR transport
- **Acceptance:** **PARTIAL** — audit/evidence validated; retained issue #880 study remains `FLAWED`

## Start-of-run review

Authenticated GitHub reads inspected repository metadata and permissions, current `main`,
recent commits, open pull requests, head status checks, issue #880 and its existing comment,
merged PR #897, `chatgpt_todo/ACTIVE_TASK.md`, `BACKLOG.md`, `HANDOFF.md`, the strict MC
weight policy, the issue #880 producer, its retained result JSON, and related MC scripts.

Initial facts:

- remote `main`: `a4b996ccbdfeea120e6deaead863f19d468d1091`;
- no status checks were attached to that head;
- issue #880 remains open;
- PR #897 was merged on 2026-07-23 and introduced the retained weighted/unweighted study;
- open PRs were reviewed for collision risk and were not modified;
- PR #868 was not reopened, extended, or merged.

## Exact repository evidence

The audited producer is:

- path: `scripts/single_stave/issues879_880_887_mc_study.py`;
- Git blob: `bc1220fdfe1010989fd8ab273f8c1b1fcf708b2c`.

The retained result is:

- path: `reports/issues879_880_887_mc_analysis/issues879_880_887_result.json`;
- Git blob: `37d69e2c697a7ce7c9e1eff9aeff48539551d922`;
- nominal event count: `1,000,000`;
- retained ESS: `347261.8375452912` (`0.34726183754529116` of nominal).

## Confirmed defects

The producer has fail-open event-weight behavior:

1. `load_mc` converts nonfinite event weights to `1.0` with
   `np.where(np.isfinite(w_evt), w_evt, 1.0)`;
2. `wmean` falls back to an ordinary mean when the total weight is not positive;
3. `wmedian` and `wfrac` likewise fall back to unweighted estimators;
4. `wcorr` falls back to ordinary Pearson correlation.

The retained reporting also has direction/denominator ambiguity:

- `first_B_layer_mean_rel_bias_pct` is
  `100 × (weighted − unweighted) / unweighted`;
- `deuteron_fraction_abs_bias_pp` is
  `100 × (weighted − unweighted)`;
- the note says those fields show how far the legacy unweighted summaries were off, without
  naming the direction and denominator.

The retained result records a filesystem path and generation time but omits the exact ROOT
SHA-256, producer commit, generation command/environment, and weight-validation policy.

## Independent arithmetic reconstruction

Tracked values:

| Quantity | Legacy unweighted | PrimaryWeighted |
|---|---:|---:|
| First B-layer mean EDep | `6.674567424757 MeV` | `2.134364334727324 MeV` |
| Entering-B deuteron fraction | `0.5719111928400914` | `0.16606032425392264` |

Independent calculations:

- weighted first-B change relative to unweighted:
  `-68.02243203341332%`;
- legacy first-B overstatement relative to weighted:
  `+212.7192164972955%`;
- weighted-minus-unweighted deuteron shift:
  `-40.585086858616876 percentage points`;
- legacy-minus-weighted deuteron shift:
  `+40.585086858616876 percentage points`;
- legacy deuteron overstatement relative to weighted:
  `+244.39966043037631%`.

No arithmetic mismatch was found. The confirmed problem is that the retained field names and
prose make the sign and denominator easy to misinterpret.

## Audit gate and evidence delivered

Added:

- `tools/audit/audit_issue880_weight_semantics.py`;
- `tests/test_audit_issue880_weight_semantics.py`;
- `tools/audit/render_issue880_weight_semantics_evidence.py`;
- `docs/validation/issue880_weight_semantics_audit.md`;
- `docs/validation/issue880_weight_semantics_validation.json`;
- `docs/validation/issue880_weight_semantics.svg`;
- `chatgpt_todo/archive/2026-07-25T030239Z_AUD-MC-002_WEIGHT_SEMANTICS.md`.

Updated `chatgpt_todo/ACTIVE_TASK.md` and this handoff.

The policy is:

`ISSUE880_WEIGHTS_MUST_FAIL_CLOSED_AND_BIAS_DIRECTION_MUST_BE_EXPLICIT`

The validator checks fail-open source patterns, independently reconstructs both directions of
the retained comparison, requires direction-explicit fields, checks required provenance, uses
strict UTF-8, publishes JSON atomically, and rejects an input/output alias.

## Validation

```text
python -m py_compile \
  tools/audit/audit_issue880_weight_semantics.py \
  tests/test_audit_issue880_weight_semantics.py \
  tools/audit/render_issue880_weight_semantics_evidence.py

PYTHONPATH=. pytest -q tests/test_audit_issue880_weight_semantics.py

6 passed in 0.04s
```

Coverage includes current-like fail-open behavior, a strict direction-explicit accepted
fixture, arithmetic mutation detection, controlled invalid UTF-8, atomic JSON publication,
and destructive alias prevention. JSON parsing and SVG XML parsing passed. Changed Python
lines were no longer than 99 characters.

Authenticated GitHub reads supplied the exact repository blobs. Because the connector does
not materialize those blobs into the local runtime, executable tests used a faithful source
excerpt plus the exact retained numeric values; no exact full-repository-file local execution
or production ROOT rerun is claimed.

## Direct-main commit sequence

- `0a8d73cb1d285b0595ade5eaddc107e672fb471d` — task claim;
- `9cf2a16cb388e053cd085e9d99dd5f8159294b9d` — audit gate;
- `7944b8044f3f922942a45423f692c03cb9ca2804` — focused tests;
- `9141cf9d1b9189400d4ec11703fe061be9cdacb7` — evidence renderer;
- `e6d0620f18da3dbcc061db7f9a14515c9dfff864` — validation JSON;
- `ea8fa290936d796aad0b4cb2368d6fbe9e6070e0` — SVG evidence;
- `2bd9357e6db11f884709d652cfcac7dcdc065316` — validation audit;
- `ddbb9614a6e4b8b58f5b7cf91839fd1708bc41c8` — immutable archive.

The connector returned successful direct-main commit SHAs rather than conventional textual
`git push` stdout. The handoff commit generated by this update must be confirmed by a
post-write remote-main history read before delivery is reported complete.

## Scientific boundary

This is software/reporting governance and independent arithmetic from tracked summary values.
It does not rerun the one-million-event ROOT study, prove that the first primary is the
scientifically correct event-weight carrier, estimate weighted uncertainty, validate weight
tails under selection, or establish data/MC closure.

The retained issue #880 comparison remains a flagged diagnostic rather than an accepted
physics result until the producer fails closed and exact content-addressed outputs are
regenerated.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and aggregate matrices were reviewed but
not replaced because the connector provides whole-file replacement rather than byte-safe
append or patch semantics for shared long-lived files. Replacing a partial or concurrently
changing reconstruction could erase unrelated provenance. The immutable archive and this
handoff preserve the append-equivalent record; aggregate synchronization remains explicitly
unmet.

## Next action

Replace unit-weight coercion and all unweighted fallbacks with strict weight validation in the
issue #880 producer and related downstream scripts. Emit direction-explicit comparison fields,
record the exact ROOT SHA-256/producer commit/command/environment/policy, rerun on the exact
one-million-event input, add weighted uncertainty and tail-stability diagnostics, regenerate
all figures, and require data/MC closure before restoring affected claims.
