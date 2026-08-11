# Latest Handoff

## Active atom: exact source-phi measure and full-2π reference

Protected source-of-truth at selection was `main@859903ada4a856c998b2bc79298cd4a26c2cb447`, the squash merge of #1215. Current work is draft PR #1216 on `fix/issue-1057-source-phi-full-2pi`, under parent #1057. CL-021 remains gated.

### Exact event-measure correction

The historical generator did more than sample one narrow interval. Let

`a = atan2(0.025,1) = 0.02499479361892016 rad`.

It sampled `phi0 ~ Uniform[-a,a]`, then used a second uniform draw to add `π` to either the proton or deuteron. For either distinguishable particle, modulo `2π`, the normalized marginal is therefore

`q(phi)=1/(4a)`

on two opposite intervals of width `2a`, with zero density elsewhere. The joint invariant is `phi_d-phi_p=π (mod 2π)`.

For the explicit spin-averaged reference target `p(phi)=1/(2π)`, the exact target/proposal ratio on legacy support is

`p/q = 2a/π = 0.015912179824051628`.

That is also the total legacy support fraction. The earlier #1057 shorthand `a/π` missed the 50/50 branch normalization; a common factor is irrelevant to normalized shape-only reweighting but material to absolute rates/efficiencies. More importantly, `98.40878201759484%` of the full-circle reference support has `q=0`, so no weighting can recover those reaction-plane orientations.

### Bounded implementation on #1216

The source patch removes `det_size`, `det_distance`, and `phi_max` and samples the base azimuth as `2*pi*G4UniformRand()`. It keeps the existing 50/50 `+π` assignment. Under full-circle generation that branch is distributionally redundant, but retaining it preserves two phi-stage RNG draws per event; this is important for future paired-seed legacy/full-phi tests because removing a draw would shift all subsequent event RNG inputs.

`geant4/src_patch/scattering_source_model_v1.json` now explicitly declares:

- `target_azimuthal_density = p(phi)=1/(2*pi)`;
- `source_phi_measure = uniform_full_2pi_v1`;
- full `[0,2π)` support;
- `detector_surrogate_phi_preselection = false`;
- remaining compiled, accepted-observable, provenance, and detector-response gates.

Exact published identities:

- source-model JSON: Git blob `d5cabdb3bb9b01ffd76fe9dd2d3baed18fcdd6a7`, SHA-256 `308c9120a286a19295687d876886d5a616812470007fc92f9c4d6e0eecba6dfc`;
- strengthened source-phi test: Git blob `2d067b1ecabfac6f53377e40a0bee002c8332290`, SHA-256 `4c9ba2c0c5a2426716f9b763625f18957c961a3644b930617c66864932b43112`.

The regression now binds the C++ implementation to the JSON model, rejects reintroduction of the detector surrogate, requires exactly two `G4UniformRand()` calls in the phi stage, and deterministically checks full-circle marginals and coplanarity.

### Deterministic falsifier

No RNG and no Geant4 transport were used. A 4096-point evenly spaced base-azimuth grid with both branch states produced 8192 proton/deuteron pairs. In 64 equal azimuth bins every proton bin and every deuteron bin contained exactly 128 entries; the maximum numerical residual from `phi_d-phi_p=π (mod 2π)` was `8.881784197001252e-16 rad`.

This validates the mathematical map encoded by the proposed source contract only. It does not establish detector acceptance, transport, rates, or production behavior.

### Primary-literature child: polarization

The repository-bound 190 MeV source is K. Ermisch et al., *Physical Review C* **71**, 064004 (2005), DOI `10.1103/PhysRevC.71.064004`. The primary paper studies elastic scattering of polarized protons from deuterons and reports vector analyzing power together with differential cross section. Therefore `uniform_full_2pi_v1` is presently an explicit spin-averaged / azimuthally symmetric reference assumption unless CCB beam/target polarization and spin-axis provenance demonstrate that no azimuthal modulation is required.

Child `ARU-MC-SOURCE-PHI-POLARIZATION-001` remains open under #1057 rather than creating a duplicate issue.

### Four sequential AI reviews

- **Source/kinematics lead — ACCEPT exact measure correction and H1 reference / REVISE physical-source wording.** Zero-support calculation rejects the historical gate as an unconditional full-physics law. Residual: beam/target polarization, exact geometry/trigger support, compiled execution.
- **Adversarial mechanism reviewer — REJECT factor-of-two shorthand for absolute normalization / ACCEPT corrected event measure / BLOCK zero-support recovery.** The 50/50 branch changes the normalized distinguishable-particle marginal; weighting cannot fill `q=0` regions.
- **Independent validation reviewer — ACCEPT deterministic source-contract oracle / REVISE until exact-head CI / BLOCK detector inference.** Static/deterministic tests do not compile or run the Geant4 generator.
- **Claims/provenance reviewer — ACCEPT bounded implementation / BLOCK #1057 closure and CL-021 promotion.** Runtime serialization, accepted-observable closure, detector-response propagation, and source-model children remain open.

### Repository actions and current gate

PR #1216 was retitled to `mc(source): implement full-2π azimuth reference (partial #1057)`, its `Fixes #1057` auto-close language was removed, and it was converted to draft. #1057 received the exact legacy-measure correction and child-atom review. Immutable record: `chatgpt_todo/archive/2026-08-11T125900Z_ARU-MC-SOURCE-PHI-MEASURE-NORM-001.md`.

An earlier superseded #1216 head `cd494ff1...` passed MC Validation run `31492405729` with curated ruff clean and `1616 passed, 1 skipped, 8 xfailed, 1 xpassed`. That result is non-authorising for the current head because the source-model contract, tests, archive, and coordination files changed afterward.

Require fresh exact-final-head MC Validation. Even if Python CI is green, keep the source PR draft until `ARU-MC-SOURCE-PHI-COMPILED-CLOSURE-001` supplies an exact compiled/seeded Geant4 generator-level check or repository policy explicitly authorizes this physics-source change without compilation.

### Child atoms / next work

- `ARU-MC-SOURCE-PHI-POLARIZATION-001` — establish beam/target polarization and spin-axis provenance.
- `ARU-MC-SOURCE-PHI-COMPILED-CLOSURE-001` — compile the exact patched source; bind executable/source/input hashes, seed, run manager/thread mode, event count; test generated phi marginals/support/coplanarity.
- `ARU-MC-SOURCE-PHI-ACCEPTANCE-CLOSURE-001` — full-phi versus any importance/conditional proposal through exact geometry/trigger; compare accepted truth distributions, rates, support, event weights, and ESS.
- `ARU-MC-SOURCE-PHI-PROVENANCE-SERIALIZATION-001` — serialize source phi/model IDs and exact input/source identities into production provenance.

Existing #1053/#1178/#1179, geometry/trigger, runtime-loader/build, event-weight, and detector-response atoms remain upstream/downstream gates.

No production Geant4 campaign was run, no beam or production-MC ROOT bytes were opened, and no angular distribution, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate, or detector-performance quantity was regenerated or promoted.
