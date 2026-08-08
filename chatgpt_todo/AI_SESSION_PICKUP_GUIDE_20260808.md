# AI session pickup guide — atomic audit queue

Use this guide when taking one issue from the audit. Work on **one independently testable leaf** at a time unless two leaves must be changed atomically to keep the repository valid.

## 0. Establish immutable state

Before modifying anything:

```bash
git status --short
git rev-parse HEAD
git submodule status --recursive
python --version
```

Record exact input paths, byte sizes and SHA-256 values for every real-data/MC artifact used. Do not infer that an artifact mentioned in a report is the one currently on disk.

## 1. Read the local contract first

Read:

- `chatgpt_todo/ATOMIC_RESEARCH_PROTOCOL.md`
- `chatgpt_todo/CURRENT_ATOMIC_FINDINGS_20260808.md`
- `chatgpt_todo/LITERATURE_AND_METHOD_MAP_20260808.md`
- the target GitHub issue and every linked predecessor/supervisor issue
- relevant `README.md`, `WIKI.md`, `docs/claim_ledger.csv`, study report, script and config

Do not resurrect a superseded claim merely because an older report contains a plausible number.

## 2. Declare the atomic question

Write one sentence specifying:

- input population;
- transformation/estimator;
- output measurand;
- nuisance variables;
- acceptance/falsification condition.

If that cannot be stated unambiguously, first fix the data/physics contract.

## 3. Four review passes before implementation

Produce short independent sections for:

- domain/physics lead;
- adversarial reviewer;
- validation/statistics reviewer;
- claims/provenance reviewer.

They are role-separated AI reviews, not human reviewers. Each must give its strongest alternative explanation and a test capable of falsifying the proposed fix.

## 4. Build negative controls before touching the production result

Examples:

### Waveform/data contract
- one ADC word changed;
- channel swap;
- sample rotation;
- event reorder;
- final channel zeroed;
- one event shortened/lengthened;
- polarity inverted;
- duplicate/missing event key.

A release validator must reject every scientifically material corruption that its name claims to detect.

### Statistical/ML
- group label shuffle within/among runs;
- run-held-out split;
- duplicate event rows crossing folds;
- large/small sampling weights;
- class-cap binding;
- degenerate bootstrap cluster count;
- calibration distribution shift.

### MC/data
- geometry thickness/material scans;
- readout parity 1/3/5/7 versus 2/4/6/8;
- missing-stave masks;
- Birks/quenching model alternatives;
- WLS attenuation/time-constant variations;
- SiPM PDE, saturation, recovery, crosstalk and afterpulse variations;
- electronics gain/noise/baseline/sampling-phase variations.

## 5. Implement fail closed

A tool named `validate_*`, `closure_*`, `compare_*`, or a production release gate must return nonzero when required evidence is missing or a declared invariant fails. Missing data must not be converted into copied reference values, zero-width intervals, empty-but-PASS outputs or skipped checks reported as success.

## 6. Validate at three levels

1. **Unit/synthetic** — exact fixture with positive and adversarial cases.
2. **Repository integration** — current config/script/report/claim surfaces remain internally consistent.
3. **Immutable real input** — execute on exact beam/MC bytes if the claim depends on them.

A synthetic pass alone is `VALIDATED_METHOD`, not a beam-data result.

## 7. Scientific result requirements

For any numerical result record:

- numerator/denominator or sufficient statistics;
- event/run counts;
- selection flow;
- weights and effective sample size when applicable;
- point estimator;
- uncertainty method and resampling unit;
- systematic/nuisance set;
- held-out/validation population;
- exact code/config/data hashes;
- negative-control outcomes.

For data/MC comparisons, reconstruct both through the same observable definition. Do not compare Geant4 truth energy to ADC amplitude without an explicitly validated response model and truth-type label.

## 8. Update claims after evidence, not before

Search for every affected value/wording:

```bash
git grep -n '<value-or-claim-fragment>' -- ':!reports/archive/**'
```

Update the claim ledger/status before public README/WIKI wording. Preserve correction history and label old results as superseded rather than silently deleting them.

## 9. Handoff

Close or update the issue only with:

- exact commit SHA;
- commands executed;
- test summary;
- real input hashes if used;
- output artifact hashes;
- remaining limitations;
- which child issue is now unlocked.

If blocked, state the smallest missing external dependency and move to another unrelated atomic issue rather than marking the parent complete.