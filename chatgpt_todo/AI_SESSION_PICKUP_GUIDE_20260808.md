# AI session pickup guide — atomic research universe queue

Use this guide when taking one issue from the audit. Work on **one independently testable leaf** at a time unless two leaves must be changed atomically to keep the repository valid.

The mandatory method is defined in:

- `chatgpt_todo/ATOMIC_RESEARCH_PROTOCOL.md`
- `chatgpt_todo/ATOMIC_RESEARCH_UNIVERSE_STANDARD.md`

Do not start by coding the first plausible fix. First map the atom's research universe.

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
- `chatgpt_todo/ATOMIC_RESEARCH_UNIVERSE_STANDARD.md`
- `chatgpt_todo/CURRENT_ATOMIC_FINDINGS_20260808.md`
- current addenda under `chatgpt_todo/`
- `chatgpt_todo/LITERATURE_AND_METHOD_MAP_20260808.md`
- the target GitHub issue and every linked predecessor/supervisor issue
- relevant `README.md`, `WIKI.md`, `docs/claim_ledger.csv`, study report, script and config

Search **open and closed** GitHub issues, current PRs and source paths before creating any new child atom. Collapse equivalent descriptions and use one canonical issue. Do not resurrect a superseded claim merely because an older report contains a plausible number.

## 2. Declare the atomic research universe

Before implementation, write a compact contract card:

- **atom ID**;
- **input `X`** and domain/population;
- **transformation/mechanism `T`**;
- **output/measurand `Y`** and unit/truth type;
- **parameters `Θ`**;
- **nuisance variables `N`**;
- **parent/child atoms**;
- **authorising scope**;
- **falsification condition**.

Write one sentence:

> Given `X`, under contract `C`, which surviving mechanism `H_k(Θ,N)` maps `X→Y`, and what experiment can falsify it against the other surviving mechanisms?

If that sentence is ambiguous, fix the data/physics contract first.

## 3. Enumerate mechanisms before choosing a fix

Create the hypothesis ledger. Consider, where applicable:

- physical mechanisms;
- electronics/DAQ mechanisms;
- software/provenance mechanisms;
- statistical/selection mechanisms.

For each candidate record:

- mathematical form or causal mechanism;
- parameters/nuisances;
- evidence for/against;
- predictions/limiting cases;
- state: `SURVIVING`, `EQUIVALENT`, `ELIMINATED`, `BLOCKED_EXTERNAL`, or `NOT_IDENTIFIABLE`.

### 3.1 Collapse equivalent descriptions

Do not create separate issues for algebraic reparameterizations or aliases. If two mechanisms are observationally indistinguishable under current measurements, keep one equivalence class and design a new discriminant rather than claiming one microscopic explanation.

### 3.2 Eliminate impossible combinations

Use explicit constraints only: units, conservation laws, geometry, hardware limits, ADC range, exact byte provenance, causal ordering, validated parent contracts, and negative-control failures. Preserve the eliminated hypothesis and reason in the issue/history.

## 4. Build the equation/invariant ledger

Write the equations actually needed for this atom and define every symbol/unit/domain. Include relevant limiting cases and invariants.

Examples:

- signed waveform: `y = polarity * (raw - baseline)`;
- relativistic `β(T,m)` and `Δt=L/(βc)`;
- MC `sum(w)`, `sum(w²)` and ESS diagnostics;
- covariance terms in pair timing;
- exact event-key-domain/cardinality rules;
- energy/momentum conservation;
- positive attenuation/recovery times and probability bounds;
- detector ray-intersection/path-length constraints.

If the method relies on an approximation, state the regime in which it is supposed to hold and design a test outside/near that regime.

## 5. Four review passes before implementation

Produce short sections for:

- domain/physics lead;
- adversarial mechanism reviewer;
- validation/statistics reviewer;
- claims/provenance reviewer.

They are role-separated AI reviews, not human reviewers. Each must give its strongest surviving alternative explanation and a test capable of falsifying the proposed fix.

Each role records evidence inspected, strongest counter-hypothesis, attempted/proposed falsifier, residual uncertainty and vote (`ACCEPT`, `REVISE`, `BLOCK`, `REJECT`).

## 6. Design the discriminating experiment matrix

Before touching the production result, write a table:

| discriminant | survivor H1 prediction | survivor H2 prediction | held fixed | required data/MC | decision rule |
|---|---|---|---|---|---|

Prefer the cheapest high-information falsifier. Do not build a complicated fit if one injected fault or dedicated run can separate the hypotheses.

### Waveform/data-contract examples

- one ADC word changed;
- channel swap;
- sample rotation;
- event reorder;
- final channel zeroed;
- one event shortened/lengthened;
- polarity inverted;
- duplicate/missing event key;
- trigger phase shifted while analog pulse is fixed.

### Statistical/ML examples

- group label shuffle within/among runs;
- run-held-out split;
- duplicate event rows crossing folds;
- large/small/signed sampling or MC weights;
- class-cap binding;
- degenerate bootstrap cluster count;
- calibration distribution shift;
- target-conditioned selection.

### MC/data examples

- geometry thickness/material scans;
- readout parity 1/3/5/7 versus 2/4/6/8;
- missing-stave masks;
- applicable hadronic-model alternatives;
- Birks/quenching model-form alternatives;
- WLS attenuation/time-constant variations;
- SiPM PDE, saturation, recovery, crosstalk and afterpulse variations;
- electronics gain/noise/baseline/impulse/sampling-phase variations;
- primary-only vs all-secondary transport observables.

## 7. Implement fail closed

A tool named `validate_*`, `closure_*`, `compare_*`, or a production release gate must return nonzero when required evidence is missing or a declared invariant fails. Missing data must not be converted into copied reference values, zero-width intervals, empty-but-PASS outputs or skipped checks reported as success.

A permissive/exploratory mode may continue only if output is explicitly non-authorising and records the missing gate.

## 8. Validate at four levels

1. **Unit/synthetic** — exact fixture with positive and adversarial cases.
2. **Repository integration** — current config/script/report/claim surfaces remain internally consistent.
3. **Immutable real input** — execute on exact beam/MC bytes if the claim depends on them.
4. **Cross-atom composition** — verify the locally valid component is compatible with upstream/downstream assumptions and does not double-count/tune away another mechanism.

A synthetic pass alone is `VALIDATED_METHOD`, not a beam-data result. A local pass alone is not `COMPOSITION_VALIDATED`.

## 9. Scientific result requirements

For any numerical result record:

- numerator/denominator or sufficient statistics;
- event/run counts;
- selection-flow node;
- weights and effective sample size when applicable;
- point estimator;
- uncertainty method and resampling unit;
- systematic/nuisance set and correlations;
- held-out/validation population;
- exact code/config/data hashes;
- negative-control outcomes;
- parent/child model compatibility state.

For data/MC comparisons, reconstruct both through the same observable definition. Do not compare Geant4 truth energy to ADC amplitude without an explicitly validated response model and truth-type label.

## 10. Cross-scale compatibility review

Before promoting the result upward, check the entire local interface chain:

`micro → meso → event → study → claim`.

Ask:

- Which layer owns each parameter?
- Are two fitted parameters absorbing the same physical effect?
- Is an upstream parameter tuned using the downstream observable it later claims to predict?
- Are shared nuisance variables propagated as correlated?
- Does the assembled model predict held-out data that no component used for tuning?
- Can a deliberately wrong combination of locally plausible components also match the final plot?

If compensating errors remain possible, spawn a discriminating child atom rather than declaring global closure.

## 11. Update claims after evidence, not before

Search for every affected value/wording:

```bash
git grep -n '<value-or-claim-fragment>' -- ':!reports/archive/**'
```

Update the claim ledger/status before public README/WIKI wording. Preserve correction history and label old results as superseded rather than silently deleting them.

## 12. Recursive child-atom pass after every fix

After the preferred mechanism/fix survives, ask:

- What new constant/prior/model family did the fix introduce?
- What independent observable constrains it?
- Is it degenerate with another layer?
- What happens outside the calibration range?
- Did the fix change the event population/selection function?
- Does it require a new schema/provenance version?
- Which cached reports/plots are now stale?
- Which counterfactual wrong model would still pass the current checks?

Create a child issue only if it has an independent implementation or falsification boundary. Otherwise keep it as a parameter/hypothesis within the parent.

## 13. GitHub handoff

Close or update the issue only with:

- exact commit SHA;
- commands executed;
- test summary;
- hypothesis ledger state changes;
- discriminating experiments executed and outcomes;
- real input hashes if used;
- output artifact hashes;
- uncertainty/weight treatment;
- cross-atom compatibility result;
- remaining limitations;
- which child issue is now unlocked/spawned.

If blocked, state the smallest missing external dependency and move to another unrelated atomic issue rather than marking the parent complete.

## 14. Required completion state

Do not close a broad scientific topic merely because a code path passes tests. A material leaf must end in one of:

- `COMPOSITION_VALIDATED`;
- `CLAIM_AUTHORIZED`;
- `NEGATIVE_RESULT`;
- `BLOCKED_EXTERNAL` with the exact missing dependency.

If a material alternative mechanism has never been enumerated or tested, the research universe is not closed.