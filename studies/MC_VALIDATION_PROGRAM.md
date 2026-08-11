# MC-Validation Program — CCB DATA↔MC validation roadmap

**Status:** `GATED / HISTORICAL_MC_PRODUCTS_NONAUTHORISING / CURRENT_GENERATOR_PROVENANCE_OPEN`.

This file is a roadmap, not evidence that the historical Krakow MC has validated the data studies. Earlier versions stated that the 1M-event HIBEAM sample was “validated” and treated truth-level comparisons as ready for immediate physics closure. Subsequent audits have superseded that interpretation: the historical p+d source used the old scattering mechanism, the current Table-VI source correction has not yet passed the required pinned compiled-runtime provenance chain, stopping-power semantics remain open, and detector-response/digitizer closure is incomplete. See #1182, #1178, #1179, #1058 and `docs/validation/CL-021_scattering_model.md`.

Historical MC may still be used for **diagnostic development, schema inspection, algorithm exercises, and falsifiers** when its exact provenance is stated. It must not be used to promote detector performance, PID efficiency/purity, stopping/penetration closure, absolute energy calibration, or DATA↔MC goodness-of-fit.

---

## Statistical-unit and measurand boundary

The historical `hibeam` tree is truth-level simulation: primary particles plus per-detector hit/step information such as `Sci_bar` layer, PDG, deposited energy, time, position, and momentum. The beam data are sampled ADC waveforms without truth labels. Those are **different statistical units and different measurands**.

A truth quantity becomes comparable to a reconstructed DATA quantity only after the relevant aggregation and response chain is defined and validated. Depending on the claim, the required chain includes:

`Geant4 steps/hits → event/stave deposited energy → quenching/visible energy → optical/WLS transport → SiPM → electronics/digitizer → data-like waveform schema → identical reconstruction/selection → event weights → held-out DATA↔MC comparison → nuisance/systematic envelope`.

Truth-only studies can test mechanisms and reconstruction logic, but they do not by themselves validate a data inference.

### Backbone: a validated detector-response/digitizer chain

The original MV0 idea remains useful, but its contract is stronger than “make a pulse that looks like data.” A production-capable digitizer must carry explicit material/optical/SiPM/electronics/sampling nuisance parameters and provenance, preserve source event identity and weights, emit the exact data-like waveform contract, and be validated on held-out observables rather than tuned and judged on the same comparison.

---

## Study lines and present authority boundary

| ID | Research direction | MC role | Current authority state |
|---|---|---|---|
| **MV1** | Particle ID p vs d | Truth-labelled mechanism study; test whether proposed DATA PID observables are identifiable after a matched detector/reconstruction chain | **GATED** — no detector-performance promotion from historical truth |
| **MV2** | Energy / range calibration | Study event/stave energy and stopping/range mechanisms; compare only after stopping/material/response semantics are validated | **GATED** |
| **MV3** | Stopping-depth / stave profile | Diagnose truth depth populations and mapping hypotheses; require source, geometry, selection and detector-response closure for DATA comparison | **GATED** |
| **MV4** | Timing resolution & timewalk | Requires time-response/digitizer chain and identical timing estimator on DATA and MC | **BLOCKED on response chain** |
| **MV5** | Pile-up & two-pulse recovery | Requires event-overlay/rate model plus detector/electronics response and true event identity | **BLOCKED on rate/response chain** |
| **MV6** | Pulse shape & representation | Requires waveform generation and held-out shape validation; truth labels may diagnose mechanisms only after domain closure | **BLOCKED on response chain** |
| **MV7** | Pedestal / baseline | Requires electronics/baseline model and comparison to real pedestal observables | **BLOCKED on response chain** |
| **MV8** | Saturation recovery | Requires SiPM/electronics/digitizer saturation model and held-out real duplicate/saturation closure | **BLOCKED on response chain** |
| **MV9** | Synthesis | Add an MC verdict only when the upstream atom chain is traceable and its validation class is explicit | **GATED** |

No row above should be interpreted as validated merely because a truth branch exists.

---

## Required execution order

1. **Source and executable provenance first.** Pin the external generator commit/tree; verify the reviewed installed source pair immediately before build; bind compiler/Geant4/VGM/build/run-manager/thread/seeds/event count and immutable run inputs; execute compiled hostile-source controls. This is the active #1182 lane.
2. **Beam/source physics.** Close or explicitly envelope cross-section support/UQ (#1178/#1179), stopping table/source/units/material (#1058), geometry/material and reaction-kinematic dependencies.
3. **Event-level truth product.** Convert hit/step rows to source-event/stave products with immutable event identity, trigger/sample membership and exactly one validated event-measure weight.
4. **Detector-response chain.** Add quenching, optical/WLS transport, SiPM, electronics and sampling with versioned nuisance parameters and negative controls.
5. **Identical reconstruction.** Emit the exact DATA-like waveform schema and run the same selection/reconstruction code on DATA and MC.
6. **Held-out validation and uncertainty.** Keep tuning and validation samples separate; use the correct event/cluster statistical unit; retain weight-aware estimators, ESS, covariance and nuisance/systematic envelopes.
7. **Only then synthesize claims.** Public statements must point to immutable inputs/configs/results and the claim-evidence ledger.

---

## Historical infrastructure notes

Earlier work used LUNARC/fs10 locations such as `geant4/data/output_krakow_1M.root` and `ssh cosmos2`. Those locations are **historical execution notes**, not repository-resident immutable evidence. A future run must not rely on an opaque path alone: record content hashes, tree/schema identity, exact generator/build/config provenance, seeds, event counts and output hashes in a content-bound manifest.

The legacy `geant4/setup_and_run.sh` demonstrates the old environment recipe but is not an authorising reproduction front door: it can reuse an unpinned external checkout and stage mutable absolute-path inputs. See `geant4/REPRODUCTION_STATUS.md` for the current gate.

---

## Program acceptance

A research direction receives a validated MC verdict only when its claim-specific dependency chain is closed. At minimum the result must identify the source/executable/input state, statistical unit, event identity, weighting measure, detector-response level, reconstruction/selection, uncertainty/covariance treatment, held-out validation policy, serialized artifact identities, and claim-ledger consequence.

Allowed terminal states include `VALIDATED`, `FLAWED`, `BLOCKED`, `GATED`, `TENSION`, or `SUPERSEDED`; “truth exists” is not an acceptance state.
