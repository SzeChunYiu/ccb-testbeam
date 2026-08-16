# ARU-SIPM-RECOVERY-CORRELATED-NOISE-COUPLING-001

Status: PARTIAL / cross-atom model-form gap confirmed

Parents: #1066 `ARU-SIPM-RECOVERY-LAW-001`, #1071 `ARU-SIPM-CORRELATED-NOISE-001`

Exact repository state inspected:

- ccb-testbeam protected main at selection: `e25d59be37f59b8fddf7dd897295bcaa7bee14d0`.
- ccb-sipm-core exact merged main: `692857bde0c1c6c2ed59aac5a56c94740da31354`.
- core PR #13 exact head: `c2b79d83642852b458299b181d50dd94b733bdb7`.
- core PR-head CI: run `31533574607`, SUCCESS.
- core merged-main CI: run `31533753427`, SUCCESS.
- testbeam PR #1235 exact head: `4cb06465c2aaf30b4319e43f003578b18c953d8c`, base `e25d59be37f59b8fddf7dd897295bcaa7bee14d0`.
- testbeam PR CI: run `31534733706`, job `93923024769`, SUCCESS; ruff clean; pytest `1642 passed, 2 skipped, 8 xfailed, 1 xpassed, 7 warnings in 124.43 s`.
- PR #1235 subsequently merged onto protected main as `d9992a48d86a34f03f18a1e4f9426c97f6cf399b`; post-merge run `31535409449` was still in progress when this archive was written.

## 1. Atomic input/output contract

For a microcell that last fired at time zero and an accepted parent candidate at delay `dt`, the current core computes the raw recharge scalar

`r(dt) = 1 - exp(-dt / tau_recovery)`.

Core PR #13 made two previously conflated observables explicit:

- trigger recovery: `P_fire(dt) / P_fire(full) = F_trigger(r)`;
- conditional avalanche gain: `Q(dt) / Q(full) = F_gain(r)`.

The admitted implementation families are currently:

- `trigger_recovery_model = EXPONENTIAL`, hence `F_trigger(r)=r`;
- `gain_recovery_model = EXPONENTIAL_H1_SHARED`, hence `F_gain(r)=r`;
- `gain_recovery_model = FULL_RECOVERY`, hence `F_gain(r)=1`.

The newly exposed child contract is the probability/rate with which that accepted parent avalanche creates correlated-noise children. Denote the parent-generation recovery multiplier by `C_k(dt)` for mechanism `k` in {prompt crosstalk, delayed crosstalk, fast afterpulse, slow afterpulse}. In exact core `692857b...`, all four are still hard-wired to the raw scalar `r`:

- prompt crosstalk multiplicity: `N_prompt ~ Poisson(lambda_prompt * r)`, with `lambda_prompt=-ln(1-p_prompt)`;
- delayed crosstalk scheduling: Bernoulli(`p_delayed * r`);
- fast afterpulse scheduling: Bernoulli(`p_after_fast * r`);
- slow afterpulse scheduling: Bernoulli(`p_after_slow * r`).

A scheduled child candidate is later processed through its target/same-cell recovery gate, so parent-generation recovery and child-trigger recovery are distinct physical/software operations and must not be collapsed accidentally.

Units: `dt` and `tau_recovery` are ns; `r`, trigger/gain factors and probabilities are dimensionless; prompt `lambda` is a dimensionless Poisson mean.

Scientific meaning: this atom concerns microscopic model semantics for the number/probability of secondary avalanches emitted by a partially recovered accepted avalanche. It is not a measured CCB correlated-noise calibration.

## 2. Competing microscopic descriptions

### H1 — raw-recharge coupling (current implementation)

`C_k(dt)=r(dt)` for all correlated-noise mechanisms.

### H2 — parent-charge/gain coupling

`C_k(dt)=F_gain(r)` or another explicit function of parent avalanche charge. This is qualitatively motivated by the fact that optical crosstalk photons and trapped carriers arise from the parent avalanche carrier population, but no exact linear law is established here.

### H3 — mechanism-specific recovery surfaces

`C_prompt(dt,Vov,T)`, `C_delayed(dt,Vov,T)`, `C_after(dt,Vov,T)` are separately calibrated and need not equal trigger or gain recovery.

### H4 — no parent-recovery scaling negative-control family

`C_k=1` while child-cell recovery still acts downstream. This is a useful falsifier/reduced-model control, not a preferred detector law.

## 3. Equivalences, invariants and limiting cases

Under the legacy H1 default, `F_gain(r)=r`, so H1 raw-recharge coupling and H2 gain-coupled generation are observationally identical for this variable. Existing tests confined to the default H1 model therefore cannot validate which microscopic coupling is intended.

They become distinguishable as soon as `F_gain(r) != r`, including the newly admitted `FULL_RECOVERY` gain hypothesis.

Long-delay invariant: `dt >> tau -> r -> 1`, so all physically sensible normalized recovery descriptions should approach their fully recovered limit.

At `dt=tau`,

`r = 1 - exp(-1) = 0.6321205588285577`.

With `gain_recovery_model=FULL_RECOVERY`, the accepted parent amplitude uses gain multiplier 1 while the current correlated-noise generation still uses 0.6321205588. The two model families differ by 36.78794411714423% at this point.

For the representative uncalibrated profile:

- `p_prompt=0.03`, so `lambda_prompt=-ln(0.97)=0.030459207484708546`;
- at `dt=tau`, current prompt mean is `lambda_prompt*r=0.01925389125670895`;
- `p_after_fast=0.01` becomes scheduling probability `0.006321205588285576`;
- `p_after_slow=0.005` becomes `0.003160602794142788`.

These values are deterministic consequences of the current simulator law, not measured detector probabilities.

## 4. Elimination and surviving hypotheses

Eliminated: the claim that core PR #13 makes every recovery-dependent process independently model-selectable. Exact source inspection falsifies it because correlated-noise generation still consumes raw `r` directly.

Eliminated: treating green H1 tests as discrimination between raw-recharge and gain-coupled secondary generation. Under H1, `g=r`, making those parameterizations identical for the tested observable.

Surviving: H1/H2/H3/H4 above. Physical selection among them requires independent correlated-noise delay/amplitude data at the relevant device operating point and a response model that separately exposes the generation law.

Nuisance/dependency variables: overvoltage, temperature, device identity, gain/trigger recovery law, recovery time constants, secondary-pulse threshold/definition, prompt-neighbour topology, trap/diffusion components, dark background, parent amplitude, child target-cell state and acquisition history.

## 5. Discriminating experiments / controls

1. Add explicit per-mechanism correlated-noise recovery selectors while preserving current `C=r` as a named legacy hypothesis.
2. Fixed-seed paired simulation where only `gain_recovery_model` / correlated-generation law is changed. At `dt=tau`, H1 and charge-coupled alternatives must diverge under `FULL_RECOVERY` but agree under `EXPONENTIAL_H1_SHARED`.
3. Long-delay control: all admitted normalized laws converge to the fully recovered correlated-noise probability/multiplicity.
4. Same-cell afterpulse control versus neighbouring-cell crosstalk control to separate parent-generation probability from child recovery.
5. Bench/low-light data: infer joint secondary-pulse delay and amplitude distributions on calibration data, then predict held-out delays, thresholds, overvoltages and temperatures.
6. Propagate the surviving model envelope into saturation/pile-up/B2 late-component studies only after the microscopic calibration gates are defined.

No toy or production Monte Carlo was promoted to detector validation in this atom. The exact-source calculation above is the strongest currently available discriminator; existing C++ CI verifies implementation consistency, not detector truth.

## 6. External evidence mapping

Authoritative Hamamatsu MPPC guidance treats optical crosstalk as secondary photons emitted during avalanche multiplication and documents dependence of gain/correlated-noise observables on operating point. The same guidance characterizes recovery/afterpulse/delayed-crosstalk with secondary-pulse delay and amplitude and warns that reported afterpulse probabilities depend on measurement/discriminator definition. Rosado & Hidalgo's Hamamatsu SiPM study similarly distinguishes prompt/delayed crosstalk and afterpulsing through secondary-pulse amplitude×delay information. These sources motivate explicit model separation; they do not validate `C=r`, `C=g`, or numerical coefficients for the CCB device.

## 7. Cross-scale propagation

Micro: parent avalanche recharge, trigger, gain and secondary generation are distinct state transitions.

Meso: correlated-noise multiplicity and ancestry alter finite-cell occupancy/recovery and history.

Event: waveform late components, baseline/timing structure and saturation can change.

Study: B2 late-component and pile-up interpretations (#968/#1116), SiPM systematic envelopes (#985), and correlated-noise calibration (#1071) inherit this uncertainty.

Claim: no detector-performance, pile-up-efficiency, saturation-closure or late-component-mechanism claim is authorized by the software refactor alone.

## 8. Four sequential AI reviews

### A. SiPM/device physics lead

Evidence inspected: exact `ResponseSimulator` recovery/correlated-noise code, representative profile, #1066/#1071 contracts, core/testbeam CI.

Strongest counter-hypothesis: raw recharge is the correct common microscopic state variable for all parent-generation mechanisms.

Attempted falsifier: select `FULL_RECOVERY`; parent modeled charge becomes fully recovered while correlated-noise generation remains suppressed by raw `r`. The code therefore represents an additional independent physical assumption not covered by gain-model selection.

Residual uncertainty: actual CCB secondary-pulse delay/amplitude measurements and operating point are unavailable in this execution.

Vote: **REVISE** — accept the bounded trigger/gain refactor, do not accept the correlated-noise recovery law as detector truth.

### B. Adversarial mechanism reviewer

Evidence inspected: exact source path and model equivalence under H1.

Strongest counter-hypothesis: `C=r` and `C=g` are effectively the same model.

Attempted falsifier: they are exactly equivalent only when `g=r`; `FULL_RECOVERY` gives `g=1` while `r=0.6321` at one time constant.

Residual uncertainty: which alternative family is physically preferred.

Vote: **BLOCK implicit coupling** until the generation law is explicit and testable.

### C. Independent statistics/validation reviewer

Evidence inspected: exact PR-head and merged-main C++ CI plus testbeam PR CI; current test structure.

Strongest counter-hypothesis: green #13 tests are sufficient validation.

Attempted falsifier: H1 collapses the competing raw-r and gain-coupled descriptions; those tests cannot identify a parameter that is observationally identical in their configured model.

Residual uncertainty: no held-out two-pulse/secondary-pulse detector calibration participates.

Vote: **ACCEPT software/source-level diagnosis / BLOCK physical model selection**.

### D. Claims/provenance reviewer

Evidence inspected: #1066 acceptance criteria, #1071 mechanism-neutral requirements, representative profile status.

Strongest counter-hypothesis: integration of separate trigger/gain fields is enough to close #1066.

Attempted falsifier: #1066 still requires two-pulse validation, model-form uncertainty, operating-point provenance and source/calibration closure; the new correlated-noise child adds a cross-atom compatibility gate.

Residual uncertainty: historical outputs and downstream claims have not been reprocessed under model alternatives.

Vote: **BLOCK #1066/#1071 completion and public/detector claim promotion**.

## 9. Repository actions

- Added stable concern `CCB-1071-RECOVERY-COUPLING-001` to existing #1071 instead of opening a duplicate issue.
- Added cross-atom partial-completion evidence to #1066; issue remains OPEN.
- Reframed testbeam PR #1235 as a bounded partial integration rather than issue closure and recorded exact CI and scientific limits.
- PR #1235 merged on protected main as `d9992a48d86a34f03f18a1e4f9426c97f6cf399b`; post-merge CI was in progress when archived.

## 10. Child atoms

- `ARU-SIPM-CORRELATED-NOISE-GENERATION-MODEL-001`: explicit prompt/delayed/afterpulse parent-generation recovery selectors and metadata; legacy raw-r retained as named hypothesis.
- `ARU-SIPM-CORRELATED-NOISE-TWO-PULSE-CALIBRATION-001`: actual device/operating-point delay×amplitude calibration and held-out model discrimination.
- `ARU-SIPM-RECOVERY-DISTINCT-TAU-001`: trigger and gain currently remain functions of one shared raw `r` and therefore one `recovery_time_ns`; distinct time scales/nonlinear surfaces are still unrepresented.
- #1072 operating-point response-surface dependency.
- #1096 physical history-horizon convergence dependency.

## Next highest-value atom

`ARU-SIPM-CORRELATED-NOISE-GENERATION-MODEL-001`: make the currently hidden `C=r` assumption explicit, serializable and independently switchable without pretending to select detector truth. This enables a future paired software falsifier and provides the configuration surface required for real delay×amplitude calibration. If code changes would force an unvalidated physical preference, preserve all surviving hypotheses and stop at the explicit model interface.