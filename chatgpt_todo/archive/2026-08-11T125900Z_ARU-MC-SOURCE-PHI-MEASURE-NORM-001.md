# ARU-MC-SOURCE-PHI-MEASURE-NORM-001 — exact azimuth source measure and full-2π reference gate

**Status:** `PARTIAL / IMPLEMENTED_ON_PR_1216 / EXACT_HEAD_CI_PENDING / POLARIZATION_CHILD_OPEN / DETECTOR_CLOSURE_BLOCKED`

**Protected base inspected:** `main@859903ada4a856c998b2bc79298cd4a26c2cb447`  
**Working PR:** #1216, branch `fix/issue-1057-source-phi-full-2pi`  
**Parent atom:** #1057 `ARU-MC-SOURCE-PHI-001`  
**Claim boundary:** CL-021 remains gated. No detector-performance claim is promoted.

## 1. Atomic contract

The atom is the event-level azimuth map from two source random variates to the distinguishable proton/deuteron momentum directions.

Inputs:

- `U_phi ~ Uniform[0,1)`;
- `U_branch ~ Uniform[0,1)`, reduced to `B = 1[U_branch < 1/2]`;
- legacy half-window `a = atan2((5 cm)/2, 1 m) = 0.02499479361892016 rad`;
- two-body polar kinematics already computed upstream.

Outputs:

- proton azimuth `phi_p` in radians;
- deuteron azimuth `phi_d` in radians;
- invariant coplanarity relation `phi_d - phi_p = pi (mod 2*pi)`.

Scientific meaning:

- the azimuth source measure is upstream of detector geometry and trigger acceptance;
- a source-level detector surrogate is either a physical conditioning statement or an importance-sampling proposal and cannot silently masquerade as the unconditional reaction measure.

## 2. Legacy measure

The historical source drew

`phi0 = 2*a*U_phi - a`

then assigned the `+pi` branch to either proton or deuteron with probability 1/2.

Modulo `2*pi`, the proton marginal is therefore

`q_p(phi) = 1/(4a)`

on the union of two intervals of width `2a` centered at `0` and `pi`, and zero elsewhere. The deuteron has the same marginal. The joint measure remains supported only on the back-to-back manifold.

For the spin-averaged H1 target

`p(phi) = 1/(2*pi)` on `[0,2*pi)`,

the exact normalized target/proposal ratio on legacy support is

`p/q = 2a/pi = 0.015912179824051628`.

The total legacy support fraction is also

`4a/(2*pi) = 2a/pi = 0.015912179824051628`.

Thus `0.9840878201759484` of the H1 full-circle support is absent from the legacy proposal and cannot be recovered by weights.

This corrects the factor-of-two shorthand in the original #1057 issue text. The 50/50 branch creates two opposite proton-support sectors and halves the density in each. A common normalization factor cancels in normalized shape-only comparisons, but it is material for absolute rates and efficiencies.

## 3. Competing mechanisms / models

1. **H1 — spin-averaged full physical azimuth.** `phi_p` is uniform on `[0,2*pi)` and `phi_d = phi_p + pi (mod 2*pi)`. Detector geometry and trigger establish acceptance downstream.
2. **H2 — narrow importance proposal.** Restrict source azimuth for efficiency, but require proposal support over every contributing target region and carry the exact proposal/target weight.
3. **H3 — explicitly conditional arm sample.** Treat the generated population as conditional on a declared geometric/trigger condition and never infer unconditional rates.
4. **H4 — polarization-dependent azimuth.** If the CCB beam/target initial state has a preferred spin axis, the physical source may contain azimuthal modulation and H1 is only a spin-averaged reference.
5. **H5 — historical 5 cm / 1 m detector surrogate as physical source law.** This survives only if independently shown equivalent to the actual versioned detector/trigger acceptance for every target observable.

The two full-circle parameterizations

- always set one named particle to `phi+pi`, or
- keep the existing 50/50 branch

are observationally equivalent for the full-azimuth joint distribution after a `pi` reparameterization. They are **not operationally equivalent for seeded reproducibility**, because removing the branch would consume one fewer RNG draw per event. PR #1216 therefore retains two phi-stage random draws so future paired-seed legacy/full-phi studies do not shift all subsequent events solely through RNG-call cardinality.

## 4. Eliminations

- **Legacy detector surrogate as unconditional physical law:** rejected; it removes 98.41% of the H1 azimuth support before geometry/trigger.
- **Recover zero-support regions by weighting:** impossible because `q=0` there.
- **Use `a/pi` as the normalized legacy target/proposal factor:** rejected for the distinguishable-particle/event-orientation measure; the 50/50 branch changes the normalized density by a factor two.
- **Treat a source-code comment as production provenance:** rejected. PR #1216 now also binds the measure in `scattering_source_model_v1.json`; runtime serialization remains a separate child.
- **Auto-close #1057 when the source line changes:** rejected. Compiled execution, accepted-observable closure, polarization state, and production provenance remain unresolved.

## 5. Deterministic falsifiers executed

A pure deterministic map audit used 4096 evenly spaced base-azimuth points and both branch states, for 8192 proton/deuteron pairs total. With 64 equal azimuth bins:

- every proton bin contained exactly 128 entries;
- every deuteron bin contained exactly 128 entries;
- maximum numerical error in `(phi_d - phi_p) mod 2*pi = pi` was `8.881784197001252e-16 rad`.

No RNG was used in this control. It is an analytical/software map check, not a Geant4 transport or detector validation.

PR #1216 was strengthened so repository tests now:

- require `source_phi_measure = uniform_full_2pi_v1` in the tracked source-model JSON;
- require full `[0,2*pi)` support and no detector-surrogate preselection in that model contract;
- bind the C++ phi block to the model ID and full-2pi expression;
- reject reintroduction of `det_size`, `det_distance`, or `phi_max`;
- require exactly two `G4UniformRand()` calls in the phi stage;
- reproduce the deterministic full-circle/back-to-back grid check.

The intended source-model JSON bytes written in this run were 2275 bytes, SHA-256 `308c9120a286a19295687d876886d5a616812470007fc92f9c4d6e0eecba6dfc`, Git blob `d5cabdb3bb9b01ffd76fe9dd2d3baed18fcdd6a7`.

The intended strengthened test bytes were 3460 bytes, SHA-256 `4c9ba2c0c5a2426716f9b763625f18957c961a3644b930617c66864932b43112`, Git blob `2d067b1ecabfac6f53377e40a0bee002c8332290`.

GitHub returned exactly those blob identities after publication.

## 6. External source facts

The source table is bound elsewhere in the repository to K. Ermisch et al., *Physical Review C* **71**, 064004 (2005), DOI `10.1103/PhysRevC.71.064004`.

That primary publication is explicitly about elastic scattering of **polarized protons** from deuterons and reports both the vector analyzing power and differential cross section at 190 MeV. Therefore the statement “full phi is the physical source law” requires a child contract establishing the actual CCB beam/target polarization state or an explicit decision to use the spin-averaged cross section as the source model. This does not invalidate H1 as a reference; it blocks promoting H1 to an unconditional production law without that provenance.

## 7. Four sequential AI review passes

### (a) Source / kinematics lead

Evidence inspected: historical source block, current PR #1216 source diff, #1057 contract, tracked source-model JSON, CL-021 source-model gate, primary-paper identity.

Strongest counter-hypothesis: the old 5 cm / 1 m window is merely an efficient but harmless detector-facing proposal.

Attempted falsifier: exact support calculation shows only 1.5912% of H1 proton azimuth is sampled; 98.4088% has zero proposal probability.

Residual uncertainty: actual CCB beam/target polarization; real geometry/trigger accepted support; compiled source behavior.

**Vote: ACCEPT exact measure correction and H1 reference implementation / REVISE physical-source wording.**

### (b) Adversarial mechanism reviewer

Evidence inspected: distinguishable proton/deuteron branch, normalized proposal density, RNG-call sequence, PR auto-close semantics.

Strongest counter-hypothesis: the issue-body `a/pi` factor is equivalent up to an irrelevant constant.

Attempted falsifier: derive the normalized marginal including the Bernoulli branch. The correct density is `1/(4a)` on two sectors, giving `2a/pi`; the factor matters for absolute rate/efficiency semantics.

Residual uncertainty: a future importance proposal may use a different parameterization and must define its own Radon–Nikodym factor.

**Vote: REJECT factor-of-two shorthand for absolute normalization / ACCEPT corrected event measure / BLOCK zero-support recovery.**

### (c) Independent statistics / validation reviewer

Evidence inspected: deterministic 4096x2 map, 64-bin exact counts, coplanarity residual, CI history.

Strongest counter-hypothesis: static/string tests prove the Geant4 generator is validated.

Attempted falsifier: no Geant4 executable or event population is exercised; the deterministic test checks only the mathematical/source contract.

Residual uncertainty: exact-head repository CI after the new commits; compiled seeded generator closure; accepted-observable statistics and ESS.

**Vote: ACCEPT deterministic source-contract oracle / REVISE until exact-head CI / BLOCK detector inference.**

### (d) Claims / provenance reviewer

Evidence inspected: PR title/body, #1057 acceptance criteria, CL-021 gate, source-model JSON, primary paper.

Strongest counter-hypothesis: changing the source line is enough to close #1057.

Attempted falsifier: unresolved compilation, runtime provenance, polarization, accepted-observable closure, and detector-response chain are explicit parent dependencies.

Residual uncertainty: production serialization of `source_phi_measure`; downstream campaign regeneration impact.

**Vote: ACCEPT bounded implementation / BLOCK #1057 closure and CL-021 promotion.**

## 8. Cross-scale propagation

Micro: two uniform variates define the event azimuth pair.

Meso: the source measure determines which reaction planes can reach the detector geometry.

Event: full-phi generation can create accepted events that the legacy source made impossible; paired-seed RNG-call conservation allows eventwise comparison of the source-measure change where all preceding random draws are otherwise identical.

Study: rates, Sample-I/II mixture, angular spectra, and trigger-selected distributions must be regenerated or compared under the new source law.

Claim: no rate, efficiency, PID, B2/B8, penetration, or detector-performance result is promoted until source variants propagate through the validated detector-response chain.

## 9. Child atoms

- `ARU-MC-SOURCE-PHI-POLARIZATION-001`: establish CCB beam/target polarization state and spin-axis provenance; decide whether a spin-averaged full-phi source is physically complete.
- `ARU-MC-SOURCE-PHI-COMPILED-CLOSURE-001`: compile the exact source and verify seeded generator-level phi support, marginals, coplanarity, event count, seed/thread/run-manager provenance.
- `ARU-MC-SOURCE-PHI-ACCEPTANCE-CLOSURE-001`: full-phi versus any importance/conditional proposal through the exact geometry/trigger; compare accepted truth distributions, rates, support, weights, and ESS.
- `ARU-MC-SOURCE-PHI-PROVENANCE-SERIALIZATION-001`: carry source phi measure/model IDs and exact source/input hashes into production run/output provenance.

## 10. Repository actions in this session

- strengthened PR #1216 source-model contract and tests;
- removed `Fixes #1057` auto-close semantics from PR #1216 and converted it to draft pending fresh exact-head CI;
- recorded the exact normalized legacy proposal correction on #1057;
- kept CL-021 explicitly gated.

No production Geant4 campaign was run, no beam or production-MC ROOT bytes were opened, and no detector-performance quantity was regenerated.
