# Chapter 8 MV1 source-binding audit

## Scope

This audit reviews the public particle-identification chapter against the tracked
MV1 producer, its machine-readable summary, and canonical claim rows `CL-017`
and `CL-018`. It is a documentation and software-contract review. It does not
rerun ROOT processing or establish beam-data PID performance.

## Inspected repository state

- initial remote `main`: `8cb0516e80f641d9f00d01d968ed0389ca48cac3`;
- former Chapter 8 Git blob:
  `5ad66ea8e7bfb22ca0cf4c1baf1e0b2cb759e527`;
- claim-ledger Git blob:
  `254dc5b64945260193d6b1bd4146bd6400ad28cf`;
- MV1/MV2 producer Git blob:
  `4f3632e59ede59bcf27e053265908ddca77b4386`;
- MV1/MV2 summary Git blob:
  `9e49af48025b9699d957e932d06901dd47a45321`;
- PR #868: closed, unmerged, non-mergeable; not modified;
- no tracked `reports/mv1_mv2_truth_pid_energy_1782220258/REPORT.md` was found.

## Confirmed defects

### 1. Traditional-cut purity was mislabeled as AUC

The producer computes a pooled-median first-layer threshold and records:

- threshold `13.287866011130776 MeV`;
- purity `0.8909863556160177`;
- efficiency `0.900961577750235`.

It does not compute a traditional-cut ROC AUC. The former chapter's “AUC = 0.891”
was the rounded purity, not a source-backed AUC.

### 2. Truth-MC logistic regression was described as beam-data LORO

The tracked producer restricts to proton and deuteron truth labels and splits the
track rows by index parity: even rows train, odd rows test. It does not use
leave-one-run-out evaluation, run-level weak labels, or beam data. The fixed
truth-MC outputs are:

- logistic-regression AUC `0.9628868703282414`;
- purity at nominal 90% deuteron efficiency `0.9488978818667125`.

### 3. HGB point estimates were promoted as a performance ceiling

The fixed HGB outputs are:

- AUC `0.9859658513538254`;
- purity at nominal 90% deuteron efficiency `0.9644090769970706`.

The producer retains no event identifier in the classification table. Multiple
tracks from one event can therefore cross the row-parity split, and event-group
independence cannot be demonstrated. The HGB constructor has no explicit
`random_state`, and no confidence interval, repeated split, or systematic study
is recorded. Calling this a truth ceiling, maximum achievable performance, or an
irreducible detector limit was unsupported.

### 4. Sample-split stopping-depth and combined-strategy results were unbound

The tracked summary contains no Sample-I/Sample-II stopping-depth table, no
combined decision-tree operating point, and no plus/minus 4% PID systematic
propagation. Those claims were removed rather than inferred from unbound or
unrelated artifacts.

### 5. MV2 kinetic-energy interpretation is blocked by units

The tracked summary stores `mean_ekin_MeV` values of order `1e-4 MeV`, which is
not compatible with a 190 MeV beam-scale interpretation. The producer combines a
rest-mass table labelled in MeV with momentum branches but does not bind an
explicit branch-unit conversion or immutable input manifest. MV2 range-energy
interpretation is therefore quarantined until exact units and conversion are
validated.

### 6. The former theoretical narrative contained internal inconsistencies

The former chapter mixed a 2 cm stave assumption with the repository's 1 cm
setup summary, gave an inconsistent numerical denominator in the maximum
energy-transfer expression, and stated a range scaling that contradicted its own
“deuterons stop in half the depth” conclusion. The replacement retains only the
qualitative physical motivation needed to interpret the tracked producer and
requires authoritative, unit-checked closure before new numerical theory claims.

## Source-backed replacement

The replacement chapter distinguishes fixed source output from inference. It
records:

- 400,369 charged B-arm tracks;
- 150,130 protons and 146,842 deuterons;
- 296,972 proton/deuteron classification tracks;
- exact cut, logistic-regression, and HGB point estimates;
- row-index parity split and missing event-group proof;
- absence of statistical/systematic uncertainty, CI, report, and manifest;
- `truth_type=mc_truth_only`, `status=GATED`, blocker `BLK-MV1-001`;
- no beam-data PID performance or production classifier authorization.

## Fail-closed validator

`tools/audit/validate_chapter8_mv1_claims.py` implements policy:

`CHAPTER8_MV1_MUST_MATCH_TRACKED_TRUTH_MC_SOURCE_AND_LIMITATIONS`

The validator checks:

- strict UTF-8 single-snapshot inputs and SHA-256 provenance;
- exact 43-column `CL-017` and `CL-018` interpretation;
- exact tracked counts and metrics;
- canonical truth type, status, source paths, source commit, and blocker;
- row-index parity and default-HGB source contract;
- required chapter caveats and exact point estimates;
- removal of stale data-LORO, cut-AUC, ceiling, irreducible-limit, combined-rule,
  and unsupported-systematics wording;
- atomic JSON publication and destructive input/output alias rejection.

## Validation

Executed on the reconstructed exact contract and focused fixtures:

```text
python -m py_compile \
  tools/audit/validate_chapter8_mv1_claims.py \
  tests/test_validate_chapter8_mv1_claims.py \
  tools/audit/render_chapter8_mv1_claims_evidence.py

pytest -q tests/test_validate_chapter8_mv1_claims.py

7 passed in 0.04s
```

Additional checks:

- accepted chapter fixture: `VALIDATED`, zero issues;
- stale former-claim fixture: `FLAWED`, eight explicit findings;
- mutated ledger status: rejected;
- mutated summary AUC: rejected;
- missing row-parity source contract: rejected;
- invalid UTF-8: controlled status 2;
- output/input alias: controlled status 2;
- validation JSON parsed;
- SVG parsed as XML;
- changed Python files are at most 100 characters per line.

## Better-method comparison

The source-bound next study should compare a transparent two-dimensional binned
likelihood, a monotonic generalized additive model, and calibrated gradient
boosting under event- and run-group-disjoint validation. The comparison must
include uncertainty, calibration, transfer, failure slices, data requirements,
interpretability, and compute cost. A larger point AUC alone is insufficient.

## Required visual evidence

Before production use, the repository needs data/MC feature overlays, group-safe
ROC and purity-efficiency curves with uncertainty bands, calibration plots,
confusion matrices, run/energy/layer stability, repeated-seed distributions,
feature ablations, and explicit event-group overlap diagnostics. Every output
must retain command, config, seed, source path, hash, units, selection,
normalization, uncertainty meaning, and success/failure interpretation.

## Acceptance boundary

This focused chapter correction and validation gate are `VALIDATED`. The
underlying MV1 scientific claim remains `GATED` under `BLK-MV1-001`. No ROOT
file was opened, no classifier was retrained, and no beam-data PID efficiency,
purity, AUC, calibration, uncertainty, stopping-depth closure, or detector
performance was established.
