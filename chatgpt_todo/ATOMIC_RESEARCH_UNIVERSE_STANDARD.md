# Atomic Research Universe standard for ccb-testbeam

Status: mandatory working standard for AI research/audit sessions. This is a methodology contract, not a detector-performance result.

## 1. Core principle

Every scientifically meaningful **atom** in the project is treated as its own research universe before it is composed into a larger result.

An atom may be a single byte-level field, one waveform sample-order rule, one pedestal estimator, one polarity sign, one trigger-time convention, one material property, one Geant4 process, one optical transport parameter, one SiPM mechanism, one digitizer transfer function, one event-key definition, one weight, one statistical estimator, one ML split, one plot coordinate, or one public claim.

For each atom, the AI must recursively:

1. define the exact input/output contract and physical/statistical meaning;
2. enumerate all materially distinct microscopic mechanisms and mathematical descriptions that could generate the observed behavior;
3. collect/derive the relevant equations, invariants, dimensional relations, limiting cases, conservation laws, causal constraints and identifiability conditions;
4. collapse mathematically equivalent or observationally indistinguishable descriptions;
5. eliminate impossible combinations using physics, hardware, software semantics, provenance, and already validated evidence;
6. retain the surviving hypotheses plus every nuisance/dependency parameter required by them;
7. design the smallest experiments/simulations/negative controls that maximally separate the survivors;
8. execute what is possible and record exact evidence;
9. propagate only surviving local models into the next micro→meso→event→study→claim layer;
10. recurse into every new assumption introduced by the preferred explanation or fix.

The purpose is not to create arbitrarily many tickets. The purpose is to turn every hidden assumption into an explicit, falsifiable research object and to prevent a locally convenient model from being silently promoted into a globally incompatible detector story.

## 2. Formal representation of an atomic universe

Represent an atom as

\[
\mathcal U = (X, T, Y, \Theta, N, H, I, E, D, C),
\]

where:

- `X`: declared inputs and their domains;
- `T`: transformation/mechanism from input to output;
- `Y`: output observable/measurand;
- `Θ`: model parameters;
- `N`: nuisance/systematic variables;
- `H`: competing hypotheses/model families;
- `I`: invariants and constraints;
- `E`: existing evidence and provenance;
- `D`: discriminating experiments/controls still required;
- `C`: compatibility contracts with parent/child atoms.

A task is not well posed until these objects are sufficiently explicit that two AI sessions would know what counts as the same input, same output and same hypothesis.

### 2.1 Atomic question template

Write one sentence of the form:

> Given population/input `X`, under contract `C`, which surviving mechanism `H_k(Θ,N)` maps `X→Y`, and what experiment `D` can falsify it against the other surviving mechanisms?

If this sentence cannot be written without ambiguity, the immediate task is contract reconstruction, not model fitting.

## 3. Recursive depth: micro → meso → event → study → claim

Do not jump directly from a microscopic fit to a public detector claim.

### Micro layer

Examples:

- ADC word semantics;
- sign/polarity;
- baseline noise;
- scintillation quenching;
- WLS absorption/re-emission;
- SiPM PDE/recovery/crosstalk/afterpulse;
- electronics impulse response;
- Geant4 step/process semantics.

### Meso layer

Examples:

- one reconstructed pulse;
- one stave response;
- one track through several staves;
- one digitized MC waveform;
- one calibrated timing estimate.

### Event layer

Examples:

- B2/B4/B6/B8 hit topology;
- same-particle association;
- penetration depth;
- ΔE/residual-E proxy;
- pile-up/secondary/late-component classification.

### Study layer

Examples:

- Sample-I/Sample-II timing comparison;
- runs 59–65 light-collection scan;
- p/d PID benchmark;
- data/MC stopping-depth comparison;
- nuisance/systematic ensemble.

### Claim layer

Examples:

- detector timing resolution;
- p/d discrimination;
- light-collection uniformity;
- calibration constant;
- pile-up rate limit.

Every upward interface must state which lower-layer quantities it consumes and which uncertainties/correlations it inherits. Local validation does **not** imply compositional validation.

## 4. Enumerate the mechanism universe before choosing a method

For each atom, list mechanisms before fitting.

The list should include at least four classes when relevant:

1. **physical mechanisms** — e.g. primary stopping, secondary fragments, scintillation quenching, WLS transport, correlated SiPM noise;
2. **electronics/DAQ mechanisms** — e.g. saturation, shaping, undershoot, clock phase, circular-buffer ordering, ADC dropout;
3. **software/provenance mechanisms** — e.g. wrong reshape, channel swap, wrong event join, stale configuration, padding/truncation;
4. **statistical/selection mechanisms** — e.g. conditioning on the target, run-composition shift, weighting errors, leakage, finite-MC fluctuations.

Do not call an unexplained residual "physics" until the software/DAQ/statistical mechanisms that can generate the same observable are tested.

## 5. Equation and invariant ledger

Every atomic issue should contain an equation/invariant ledger appropriate to the question. Examples:

### Waveform sign and amplitude

\[
y_{ecs} = p_{cr}\,[w_{ecs}-b_{ec}],\qquad p_{cr}\in\{-1,+1\}
\]

with explicit definitions for event `e`, channel `c`, run period `r`, sample `s`, baseline `b`, and polarity `p`.

### Relativistic flight time

\[
\beta(T,m)=\sqrt{1-\left(\frac{mc^2}{T+mc^2}\right)^2},\qquad
\Delta t = \frac{L}{\beta c}.
\]

A candidate same-particle pair is impossible if the hypothesized particle cannot physically reach the downstream layer under the energy-loss/range model.

### Weighted Monte Carlo

For event weights `w_i`, record at minimum

\[
W=\sum_i w_i,\qquad W_2=\sum_i w_i^2,\qquad
N_{\rm eff}=\frac{W^2}{W_2}
\]

with a separate absolute-weight ESS when signed weights are possible. The statistical method must match the semantics of the weights; `N_eff` is a diagnostic, not a universal replacement for a likelihood.

### Pair timing with common terms

\[
 t_i = t_0 + \tau_i + c_i + r_{i,\mathrm{run}} + q_i + \epsilon_i,
\]

so

\[
\mathrm{Var}(t_i-t_j)=\mathrm{Var}(\epsilon_i)+\mathrm{Var}(\epsilon_j)-2\,\mathrm{Cov}(\epsilon_i,\epsilon_j)+\cdots.
\]

The independent-stave approximation is one hypothesis, not an identity.

### Conservation/closure checks

Use whichever apply:

- energy and momentum conservation;
- event-key cardinality and exact-domain equality;
- ADC code range;
- probability bounds `[0,1]`;
- positive attenuation/recovery times;
- monotonic sample indices and geometry ordering;
- exact per-event word count;
- unit/dimension consistency;
- geometry ray intersection;
- normalization/weight conservation under sampling transformations.

## 6. Collapse equivalent descriptions before opening child issues

Two descriptions belong to one hypothesis class if they are merely reparameterizations or are observationally equivalent under all currently available observables.

Examples:

- `A exp(-t/τ)` versus `exp(log A - t/τ)` is not two mechanisms;
- an offset absorbed into `C_i` versus the same offset absorbed into a run intercept is non-identifiable unless an external reference fixes the gauge;
- multiple labels for the same historical data product are provenance aliases, not distinct data-generating hypotheses.

Maintain an **equivalence map**:

| candidate descriptions | relation | action |
|---|---|---|
| exact algebraic reparameterization | equivalent | collapse |
| same predictions on current observables but different hidden mechanism | observationally equivalent | keep one equivalence class + design new discriminant |
| differ only outside measured domain | locally equivalent | record domain and defer |
| physically incompatible predictions | distinct | retain separately |

Do not create duplicate GitHub issues for members of the same equivalence class.

## 7. Eliminate impossible combinations aggressively but transparently

A hypothesis may be eliminated only with an explicit reason and evidence pointer.

Valid elimination classes include:

- violates dimensional/unit consistency;
- violates energy/momentum/range constraints;
- violates detector geometry or cabling;
- violates ADC/code/clock hardware limits;
- contradicts exact byte-level provenance;
- requires a data product or run that did not exist;
- fails an injected-fault or negative-control test;
- is statistically non-identifiable under the stated observable and therefore cannot support the claimed interpretation;
- conflicts with a stronger validated parent contract.

Record eliminated hypotheses; do not delete them from history. A later change in the parent contract can reactivate one.

## 8. Design experiments to separate the survivors

The preferred experiment is the **cheapest high-information falsifier**, not the most elaborate model.

For each surviving pair or equivalence class, ask which intervention makes their predictions differ most.

Useful designs include:

- deliberately flip one channel polarity;
- rotate samples by one bin;
- zero the final channel;
- inject one sub-threshold ADC corruption;
- vary trigger phase while holding the analog pulse fixed;
- vary beam/current while keeping reconstruction frozen;
- run p/d at energies straddling a stopping-layer boundary;
- vary hit position along the WLS direction;
- turn crosstalk/afterpulse/dark count independently to zero in digitizer MC;
- compare primary-only versus all-secondary transport observables;
- use a held-out run whose amplitude distribution differs from calibration;
- switch between applicable hadronic/quenching model families while holding geometry/digitizer fixed;
- inject a known common clock jitter to test covariance cancellation.

Where a probabilistic predictive model exists, expected information gain, KL/Jensen-Shannon separation, likelihood-ratio power, or Bayes-factor design may be useful. Do not invent precision from an unjustified likelihood; a deterministic falsifier is often stronger.

Every discriminating experiment must define:

- manipulated variable;
- held-fixed variables;
- expected direction/signature under each survivor;
- sample size/MC convergence rule;
- stopping criterion;
- acceptance/rejection threshold chosen before looking at the final result where feasible.

## 9. Four mandatory review roles

Every atom is reviewed through four role-separated passes. These are sequential AI lenses in one context, not independent humans.

### Domain/physics lead

- defines the measurand and physical mechanism space;
- writes equations/limiting cases;
- identifies required detector/material/kinematic facts.

### Adversarial mechanism reviewer

- searches for alternative mechanisms that reproduce the same observation;
- constructs pathological counterexamples;
- challenges hidden assumptions introduced by the proposed fix.

### Validation/statistics reviewer

- defines held-out populations, weights, independent units, uncertainty, convergence and negative controls;
- checks identifiability and leakage;
- requires fail-closed behavior for authorising tools.

### Claims/provenance reviewer

- binds code/config/data/literature/commit/artifact hashes;
- maps affected README/WIKI/report/figure/claim-ledger surfaces;
- prevents method closure from becoming detector-performance truth.

Each role records:

- evidence inspected;
- strongest surviving counter-hypothesis;
- falsifier attempted or proposed;
- residual uncertainty;
- vote: `ACCEPT`, `REVISE`, `BLOCK`, or `REJECT`.

## 10. Required atomic work products

For every nontrivial atom maintain, in the issue or linked artifact:

### A. Contract card

- atom ID;
- input domain;
- output/measurand;
- unit/truth type;
- parent and child atoms;
- authorising/non-authorising status.

### B. Hypothesis ledger

| hypothesis | mechanism | parameters | evidence for | evidence against | state |
|---|---|---|---|---|---|

States: `SURVIVING`, `EQUIVALENT`, `ELIMINATED`, `BLOCKED_EXTERNAL`, `NOT_IDENTIFIABLE`.

### C. Equation/invariant ledger

List the equations, units, constraints and limiting cases actually used.

### D. Experiment matrix

| discriminant | H1 prediction | H2 prediction | data/MC needed | result | decision |
|---|---|---|---|---|---|

### E. Compatibility ledger

For every parent/child interface:

- shared parameter/nuisance;
- unit/coordinate convention;
- correlation/dependency;
- transformation semantics;
- whether uncertainty is independent, shared, conditional or unknown.

### F. Evidence/provenance block

- repository commit;
- source paths/lines;
- real-data/MC SHA-256 + bytes;
- configuration digest;
- RNG seeds/Geant4/data-library versions;
- literature DOI/version/source type;
- commands/tests executed;
- output hashes.

## 11. Cross-atom compatibility is a separate scientific test

Even if atoms `A` and `B` each pass independently, composition `B∘A` may fail.

Examples:

- a quenching law calibrated in deposited-energy space may be incompatible with an optical model tuned on ADC amplitude if both absorb the same nonlinearity;
- a timing correction trained after a topology cut may not compose with a PID classifier that changes the topology mixture;
- independent nuisance scans can double-count one physical uncertainty if two parameters encode the same mechanism;
- separately valid channel mapping and polarity maps may be incompatible if they were inferred under different run periods.

For each composed chain, test:

1. parameter ownership — exactly one layer owns each physical degree of freedom unless a hierarchical relation is explicit;
2. causal order — upstream effects are not fitted using downstream residuals that they are later claimed to predict;
3. uncertainty correlation — shared nuisance parameters are propagated coherently;
4. held-out closure — the assembled chain predicts data not used to tune any of its components;
5. counterfactual stability — deliberately wrong combinations are rejected by the validation observables.

## 12. Recursive spawning rule

After a fix or preferred mechanism survives, ask:

- Which new constant, prior, model family, calibration split, geometry value or software assumption did this solution introduce?
- What observable independently constrains it?
- Is it degenerate with another layer?
- What happens outside the calibration range?
- Does the fix change the event population or selection function?
- Does it create a new provenance/schema version?
- Which old artifacts become stale?

Each independently testable unresolved answer becomes a child atom.

Stop splitting when a child has no independent falsifier or implementation boundary; then it belongs inside the parent hypothesis/parameter set rather than a new issue.

## 13. GitHub issue standard

Before opening an issue:

1. search open and closed issues by mechanism, code path, variable names and claim ID;
2. search current PRs and `chatgpt_todo` findings;
3. collapse equivalent descriptions;
4. prefer commenting/updating an existing canonical leaf;
5. close accidental duplicates and preserve the stronger evidence in the canonical issue.

Every new issue must include:

- stable `ccb-audit-id`;
- severity and evidence state;
- atomic-universe contract card;
- parent/child dependency graph;
- competing mechanism/hypothesis ledger;
- equation/invariant ledger;
- evidence inspected;
- eliminated hypotheses and reasons;
- surviving hypotheses;
- discriminating experiment matrix;
- implementation plan;
- negative controls;
- acceptance **and rejection** criteria;
- required real data/MC and weight/uncertainty treatment;
- claim/wiki/report consequences;
- exact AI handoff steps.

One issue should represent one independently testable leaf. A broad supervisor issue may own many child universes but should not be marked complete until its child graph is closed.

## 14. Research states and completion

Use these states:

- `UNMAPPED`: atom exists but mechanism universe not enumerated;
- `MAPPED`: hypotheses/equations/constraints enumerated;
- `DISCRIMINANTS_DESIGNED`: experiments exist but not executed;
- `PARTIALLY_TESTED`: some survivors eliminated;
- `LOCAL_VALIDATED`: atom passes its own controls;
- `COMPOSITION_VALIDATED`: interfaces to required parent/children pass;
- `CLAIM_AUTHORIZED`: source-bound study/claim passes uncertainty/provenance/held-out gates;
- `BLOCKED_EXTERNAL`: smallest missing external dependency is explicit;
- `NEGATIVE_RESULT`: candidate mechanism/method rejected and preserved.

A project area is not complete merely because every open issue has a code fix. Completion requires all material leaves to be `COMPOSITION_VALIDATED`, `CLAIM_AUTHORIZED`, `NEGATIVE_RESULT`, or `BLOCKED_EXTERNAL` with no unenumerated material alternatives under the declared scope.

## 15. Worked example: broad Sample-I B2 timing residuals

**Observation:** B2-containing residuals are tens of ns wide while downstream pairs are much narrower.

Do not jump to `pile-up`.

Mechanism universe includes:

- two-particle pile-up;
- terminal primary plus physical secondary;
- SiPM afterpulse/delayed crosstalk/recovery;
- electronics shaping/undershoot/retrigger;
- optical crosstalk;
- low ADC word/dropout;
- wrong sign/mapping;
- circular-buffer phase/sample-order artifact;
- wrong event association;
- different particle species/velocity.

Collapse descriptions that are observationally equivalent under the current waveform-only data, then design discriminants: current/rate dependence, delay spectrum, duplicate-channel behavior, track/TPC association, injected correlated-noise MC, electronics impulse response, raw-word defect flags, and exact event-key closure.

Only after those tests may the local timing-class atom be composed into a pile-up-rate or detector-resolution claim. The supplied timing note itself preserves several of these alternative mechanisms and states that the microscopic origin is not proven; that boundary must remain visible in the repository.

## 16. Worked example: data/MC p/d PID

The final PID plot is the end of a long chain, not one atom:

`beam/reaction kinematics`
→ `upstream material`
→ `stave geometry/material`
→ `hadronic/EM transport`
→ `energy deposition`
→ `quenching model`
→ `optical transport`
→ `SiPM response`
→ `electronics transfer`
→ `DAQ observation schema`
→ `waveform reconstruction`
→ `event association`
→ `ΔE/residual-E definition`
→ `MC event weights`
→ `classifier/statistic`
→ `held-out validation`
→ `claim`.

Each arrow is itself an interface atom. Tuning several downstream layers until the final PID plot agrees does not validate the upstream physics; compensating errors are a surviving hypothesis unless independent observables constrain each layer.

## 17. Anti-patterns forbidden by this standard

- one preferred explanation listed before alternatives;
- treating a fitted nuisance as measured truth;
- using a reviewer badge as physics evidence;
- opening duplicate issues for algebraically equivalent descriptions;
- calling skipped evidence a PASS;
- forcing an estimator to return a number when the measurand is not identifiable;
- choosing a systematic model because it best matches the final validation plot;
- comparing data and MC in different observable spaces without a validated response map;
- propagating uncertainties as independent when they share a physical parameter;
- averaging models that are not applicable to the same physical domain;
- using one calibration/analysis population both to choose and validate a model without an explicit nested design;
- declaring a parent complete while child assumptions remain untested.

## 18. Relationship to the existing protocol

`chatgpt_todo/ATOMIC_RESEARCH_PROTOCOL.md` remains the concise project contract. This document defines the deeper **Atomic Research Universe** procedure that all AI sessions must use when executing that contract. `AI_SESSION_PICKUP_GUIDE_20260808.md` defines the operational handoff sequence.

When rules conflict, use the stricter fail-closed/evidence-preserving interpretation and record the conflict for review.