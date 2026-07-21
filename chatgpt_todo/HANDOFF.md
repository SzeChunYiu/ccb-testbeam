# Latest Handoff

## Session

- **UTC:** 2026-07-21T13:00Z
- **Task:** `AUD-G4-001` with implementation progress on `AUD-G4-004`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Base:** `0005ed0cb2c06617abd36b3bb1e615497e15832a`
- **Branch:** `chatgpt/AUD-G4-001-mt-rng-seeding`
- **PR:** `#868` (draft)
- **Status:** PARTIAL — RNG ownership, thread provenance, event-tree validation, photon-tree validation, and multiseed ensemble validation are implemented and pushed. Python execution, Geant4 compilation, real ROOT validation, multiseed results, and optical-yield regeneration remain mandatory.

## Area reviewed

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/HANDOFF.md`
- `chatgpt_todo/SESSION_LOG.md`
- `chatgpt_todo/VISUALIZATION_MATRIX.md`
- `scripts/compare_single_stave_mt_reproducibility.py`
- `tests/test_compare_single_stave_mt_reproducibility.py`
- `scripts/compare_single_stave_photon_trees.py`
- `tests/test_compare_single_stave_photon_trees.py`
- PR `#868`

## New scientific/reproducibility gap

Exact equality for the same seed across one and multiple thread counts is necessary but not sufficient. It cannot by itself reveal:

- accidental reuse of an identical random stream for different configured seeds;
- repeated seeds within one effective-thread group;
- seed-specific anomalous means;
- event-indexed cross-seed dependence;
- a systematic shift between effective-thread groups;
- inadequate seed coverage for uncertainty estimation.

A multiseed ensemble validator was therefore required before the approximately 178 PE/event claim can be treated as stable after the seeding correction.

## New implementation

### `scripts/analyze_single_stave_multiseed_rng.py`

The manifest-driven validator requires each run's ROOT file and metadata sidecar. It:

1. Validates a nonempty manifest and unique run labels.
2. Reads declared numeric observables from the `events` tree.
3. Requires complete, unique integer event IDs exactly in `[0, n_events)`.
4. Sorts every run by event ID before all event-indexed diagnostics.
5. Requires comparable physics provenance across the ensemble, while reporting thread provenance separately.
6. Requires unique seeds within each effective-thread group; the same seed may intentionally appear in different thread groups for paired thread-count validation.
7. Hashes the complete selected event stream, including branch names, dtypes, shapes, event IDs, and values.
8. Detects exact stream duplication across different configured seeds.
9. Reports per-run mean, sample standard deviation, standard error, minimum, and maximum for each observable.
10. Computes robust median/MAD seed-mean z scores, with standard-deviation fallback when MAD is zero.
11. Computes event-indexed Pearson correlation for each different-seed run pair and transforms it to a Fisher-z significance diagnostic.
12. Compares effective-thread groups using run-mean differences and combined seed-level standard errors.
13. Requires a configurable minimum number of unique seeds per effective-thread group.
14. Writes a machine-readable JSON summary with every gate and threshold.
15. Writes a PDF summary plus per-observable seed-mean/SEM and robust-outlier plots.
16. Returns nonzero status when any acceptance gate fails.

Default diagnostic thresholds are:

- at least four unique seeds per effective-thread group;
- maximum absolute thread-group mean z score: 3;
- maximum absolute robust seed-outlier z score: 4;
- maximum absolute event-indexed cross-seed Fisher-z score: 4.

These are preregistration defaults for the audit, not universal proofs of RNG independence. Threshold changes must be justified before final output inspection.

### `tests/test_analyze_single_stave_multiseed_rng.py`

Synthetic uproot tests cover:

- a passing ensemble with the same two seeds represented in one-thread and four-thread groups;
- exact duplicate event streams under different seeds;
- duplicate seed reuse within one effective-thread group;
- insufficient unique-seed coverage;
- JSON output;
- nonempty PDF output;
- thread-group and cross-seed diagnostic fields.

## Important methodological correction made during implementation

An initial design considered enforcing globally unique seeds across all runs. That would have prevented using the same seed in one-thread and four-thread configurations, which is exactly the paired design needed for thread-count reproducibility. The final implementation enforces uniqueness only within each effective-thread group and permits the same seed across different thread groups.

## Evidence classification

- **Observed repository fact:** the prior handoff had no implemented multiseed ensemble validator.
- **Static implementation evidence:** the new script and synthetic tests are committed on the PR branch.
- **Methodological inference:** exact duplicate hashes under different seeds are strong evidence of stream reuse; event-indexed correlations and seed/thread mean diagnostics can reveal additional dependence or instability.
- **Explicit limitation:** absence of duplicate hashes or significant correlations is not proof of complete RNG independence.
- **Still unverified:** actual Geant4 outputs, real correlations, thread effects, uncertainty coverage, and the approximately 178 PE/event claim.

## Commits added in this session

- `7dfecc43731e00f1ce0333ed7fb2924349f9e111` — `feat(g4): add multiseed RNG ensemble validator`
- `a311a676b1b701bf297edf1512f6a73cbe4468cf` — `test(g4): cover multiseed RNG ensemble validator`
- `82a6d0235680af4290ff49c1b5eba503750fbcca` — `feat(g4): add cross-seed correlation diagnostics`
- `fbfa1af5a97fcf0056070ff5c537e0f8513b83a9` — `test(g4): cover cross-seed correlation diagnostics`
- Coordination-file commits follow on the same branch.

## Static checks performed

- Parsed Python syntax before upload.
- Reviewed manifest normalization and failure paths.
- Confirmed event IDs are sorted before correlation and hashing.
- Confirmed stream hashes include dtype, shape, branch name, and values.
- Confirmed same-seed runs across thread groups are allowed.
- Confirmed duplicate seeds within one thread group fail.
- Confirmed exact duplicate streams under different seeds fail.
- Confirmed provenance mismatch, coverage, outlier, correlation, and thread-effect gates contribute to overall status.
- Confirmed JSON and PDF parent directories are created and exit status reflects pass/fail.
- Confirmed no raw data, generated ROOT files, or large binaries were committed.

## Checks not executed

This connector session did not expose a checked-out Python/ROOT/Geant4 environment or generated ROOT files. It therefore does **not** claim:

- pytest passed;
- ruff passed;
- the new validator executed successfully;
- Geant4 compilation succeeded;
- real same-seed one-thread/four-thread outputs match;
- real different-seed streams are independent;
- real seed coverage or thread-effect acceptance passed;
- approximately 178 PE/event was reproduced.

## Required runtime commands

```bash
python -m pytest \
  tests/test_compare_single_stave_mt_reproducibility.py \
  tests/test_compare_single_stave_photon_trees.py \
  tests/test_analyze_single_stave_multiseed_rng.py -q

ruff check \
  scripts/compare_single_stave_mt_reproducibility.py \
  scripts/compare_single_stave_photon_trees.py \
  scripts/analyze_single_stave_multiseed_rng.py \
  tests/test_compare_single_stave_mt_reproducibility.py \
  tests/test_compare_single_stave_photon_trees.py \
  tests/test_analyze_single_stave_multiseed_rng.py
```

Generate at least four unique seeds for each effective-thread group. Use the same seed set for one-thread and four-thread runs when practical. Create a manifest such as:

```json
{
  "runs": [
    {"root": "seed101_t1.root", "meta": "seed101_t1.root.meta.json", "label": "seed101-t1"},
    {"root": "seed102_t1.root", "meta": "seed102_t1.root.meta.json", "label": "seed102-t1"},
    {"root": "seed103_t1.root", "meta": "seed103_t1.root.meta.json", "label": "seed103-t1"},
    {"root": "seed104_t1.root", "meta": "seed104_t1.root.meta.json", "label": "seed104-t1"},
    {"root": "seed101_t4.root", "meta": "seed101_t4.root.meta.json", "label": "seed101-t4"},
    {"root": "seed102_t4.root", "meta": "seed102_t4.root.meta.json", "label": "seed102-t4"},
    {"root": "seed103_t4.root", "meta": "seed103_t4.root.meta.json", "label": "seed103-t4"},
    {"root": "seed104_t4.root", "meta": "seed104_t4.root.meta.json", "label": "seed104-t4"}
  ]
}
```

Then run:

```bash
python scripts/analyze_single_stave_multiseed_rng.py \
  --manifest configs/g4_multiseed_manifest.json \
  --output-json results/g4_multiseed_rng.json \
  --output-pdf docs/figures/g4_multiseed_rng.pdf \
  --minimum-seeds-per-thread 4 \
  --max-thread-effect-z 3 \
  --max-seed-outlier-z 4 \
  --max-cross-seed-correlation-z 4
```

## Acceptance criteria

- All selected runs share declared physics provenance.
- Every event tree contains exactly one row per event ID in `[0, n_events)`.
- At least four unique seeds exist in every effective-thread group.
- No seed is duplicated within one effective-thread group.
- No complete selected event stream is identical under different seeds.
- No event-indexed cross-seed correlation exceeds the preregistered Fisher-z threshold without investigation.
- No seed mean is an unexplained robust outlier.
- No thread-group mean effect exceeds the preregistered threshold without investigation.
- JSON and PDF artifacts identify inputs, thresholds, results, and pass/fail gates.
- Same-seed one-thread/four-thread event and photon validators pass separately.
- Approximately 178 PE/event is regenerated from the corrected code with event count, seed ensemble, uncertainty, geometry hash, optical-table hashes, and thread provenance.

## Next task

1. Execute all validator tests and lint.
2. Build supported Geant4 11.2.2.
3. Generate one-thread/four-thread/forced-thread and multiseed outputs.
4. Run event, photon, and multiseed validators.
5. Inspect failing diagnostics before changing thresholds.
6. Locate and regenerate the approximately 178 PE/event result with uncertainty.
7. Update headline claims and affected study/wiki text only after runtime evidence exists.

## Acceptance decision

Keep PR #868 in draft. Do not merge until Python checks pass, supported Geant4 compilation succeeds, real event/photon reproducibility passes, forced-thread provenance is verified, the multiseed ensemble is evaluated, and the optical-yield claim is regenerated with uncertainty.
