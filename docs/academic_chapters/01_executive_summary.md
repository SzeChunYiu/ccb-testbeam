# Chapter 1: Executive Summary

> **Claim-governance update (2026-07-24).** Status: Preliminary research record — not yet peer-reviewed.
> For the authoritative claim ledger, see [`docs/claim_ledger.csv`](../claim_ledger.csv).

---

## 1. Scope and Status

This chapter is the controlled front door to the CCB test-beam analysis thesis. It gives the reader a calibrated confidence map: what is established, what is corrected, what is preliminary, what is blocked by Monte Carlo or data limitations, and what remains analysis-only.

**Important caveat:** The work described in this thesis is a research synthesis and has not undergone peer review. Every claim below should be understood in the context of its validation status as defined in §3.

---

## 2. Physics Motivation

The CCB test-beam experiment at the Cyclotron Centre Bronowice (CCB) in Kraków, Poland, measured the response of HRD (Horizontal Range Detector) scintillator stacks to 190 MeV protons incident on a deuterated polyethylene (CD₂) target. The key deliverables are:

1. **Same-particle timing resolution** — how precisely can we timestamp when a charged particle hits each stave?
2. **Pile-up characterization** — at what beam rate do overlapping pulses become the limiting factor?
3. **Particle identification** — can we distinguish proton from deuteron events using the HRD telescope?
4. **Digitizer calibration** — what is the absolute energy scale of the readout electronics?

These measurements directly inform the design of the HIBEAM/NNBAR experiment at the European Spallation Source (ESS), where sub-nanosecond timing is required to discriminate neutron-antineutron oscillation candidates from spallation-induced background.

---

## 3. Confidence-Status Legend

Every claim in this thesis is labeled with one of the following statuses:

| Label | Meaning | Example |
|---|---|---|
| **VALIDATED** | Data result and MC/truth or an independent closure test supports the claim | S00 pulse count, MV4 raw timing pull |
| **DONE_DATA_ONLY** | Robust in data but no MC/truth closure is available | Combined 3-stave timing |
| **TRUTH_LEVEL_MC_ONLY** | Mechanism demonstrated in simulation; transfer to real data is incomplete | p/d PID AUC, C12-like MC anomaly |
| **TENSION** | Data-vs-MC comparison exists but disagrees beyond tolerance | MV4 corrected timing |
| **FAIL** | Validation reveals a concrete model or transfer failure | MV3 stopping-depth comparison |
| **CORRECTED** | A previous result was leakage, stale, or superseded | S00 selected-pulse count |
| **BLOCKED** | Missing evidence prevents a canonical value or conclusion | Rmax definition, forced-pedestal truth |
| **GATED** | A candidate result is withheld until specified controls pass | P04p/P07e ML claims |
| **SUPERSEDED** | Retained only as correction history and not for use | Stale PCA variance values |

**Do not confuse data validation with MC validation.** Some checks are data-driven, some use digitized MC, some use truth-level MC, and some are self-consistency only. The truth type for each claim is stated in §4.

---

## 4. Canonical Results Table

> **Dashboard-aligned (2026-07-25).** Regenerated from
> [`reports/studies/clusterE/claims_table.csv`](../../reports/studies/clusterE/claims_table.csv);
> it supersedes the 2026-06-28 version, which labelled several since-downgraded rows
> VALIDATED (B6/combined timing, τeff, MV0 gain, MV4 raw pull). Where this table and
> [`docs/claim_ledger.csv`](../claim_ledger.csv) disagree, **the ledger wins.** The
> MC-closure rows (clusters A–D) are the "the method works" results; the
> detector-performance rows remain BLOCKED_DATA / GATED.

| Claim | Current value | Evidence class | Status | Source |
|---|---|---|---|---|
| Selected B-stack pulses (S00) | 640,737 | DATA_MEASUREMENT | 🔒 GATED | CL-001 |
| Combined timing σ₆₈ (4-sensor, MC) | 0.089 ns | MC_METHOD_CLOSURE | ✅ PASS | clusterB #918 |
| PID p-vs-d AUC (realistic chain, MC) | 0.898 | SIMULATION_RESULT | ✅ PASS | clusterA #921 |
| ADC calibration (digitizer gain, MC) | 119.17 ADC/MeV | SIMULATION_RESULT | ✅ PASS | clusterC #917 |
| Birks kB (per-track dE/dx, MC) | 0.0156 cm/MeV | SIMULATION_RESULT | ✅ PASS | clusterC #917 |
| Digitizer-domain Rmax (0% gate, MC) | 0.605 MHz | SIMULATION_RESULT | ✅ PASS | clusterC #917 |
| Opticks GPU/CPU parity | 0 GPU hits / 4592 CPU; CPU ctest 9/9 | SIMULATION_RESULT | 🟡 PARTIAL | opticks #920 |
| B6 / combined detector timing (data) | withheld | BLOCKED_DATA | ⛔ BLOCKED | CL-002..006 (BLK-MV4-LEGACY-001) |
| Pair covariance (B4–B6) | withheld | BLOCKED_DATA | ⛔ BLOCKED | CL-006 |
| τeff (effective live-time) | 124.79 ns [123.33, 126.36] (run-bootstrap) | data_measurement | DONE_DATA_ONLY | CL-011 |
| Digitizer gain (MV0 data/MC proxy) | 110 ADC/MeV (±30% heuristic) | DATA_MC_PROXY | 🟡 GATED | CL-013 (BLK-MV0-001) |
| Canonical pile-up Rmax | withheld | BLOCKED | ⛔ BLOCKED | CL-010 (S-STAT-003) |
| Legacy Rmax = 3.044 MHz | SUPERSEDED | SUPERSEDED | 🚫 SUPERSEDED | CL-012 (do not use) |
| p/d PID AUC (HGB truth ceiling) | 0.986 | TRUTH_LEVEL_MC_ONLY | 🟡 GATED | CL-017 (BLK-MV1-001) |
| PID on beam data | deferred | BLOCKED_DATA | ⛔ BLOCKED | raw ROOT not staged |
| Anomaly / C12 identity | truth-MC only; data anomaly **not** ID'd as C12 | TRUTH_LEVEL_MC_ONLY | ⛔ BLOCKED | CL-022 (AUD-ANOM-001) |
| Stopping-depth data/MC | selection-matched: MC B2 0.46→0.87 (16.6× χ² improvement, shape matches data); residual ~8 pp | MC_DIAGNOSTIC | 🟠 PARTIALLY RESOLVED (selection-matched) | CL-021 — legacy 6.8e4 was unselected-MC vs trigger-selected-data (invalid); residual = scattering model + GAP-01 material |
| MV4 raw timing pull (toy digitizer) | −1.05σ | legacy_toy_digitizer_diagnostic | GATED | CL-007 (BLK-MV4-LEGACY-001) |
| MV4 corrected timing pull (toy) | +2.68σ | legacy_toy_digitizer_diagnostic | GATED | CL-008 |
| ML duplicate-readout selection | no canonical winner (coverage interval crosses gate) | data external duplicate readout | GATED | P04p (BLK-P04P-001) |
| ML saturation recovery | held-out duplicate closure worse than raw (0.176 vs 0.121 res68) | data external duplicate readout | GATED | P07e (BLK-P07E-001) |
| Systematic uncertainty budget | incomplete | BLOCKED | ⛔ BLOCKED | CL-026 (BLK-SYST-001) |

The ±30% MV0 envelope is a heuristic, **not a confidence interval**. The 0.986 HGB
PID is a truth-level ceiling, **not** the realistic-chain 0.898 result and not a
beam-data result. The data anomaly near 4% is **not** identified as C12 (CL-022).


### Corrected values (shown only for historical context)

| Old value | → | New canonical state | Reason |
|---|---|---|---|
| 4.22 MHz Rmax | → | Withheld; 3.044 MHz is superseded | The recorded 0.38 factor is beam duty factor, not a justified occupancy-quality threshold; the failure-ceiling crossing is absent |
| ~246 ADC/MeV | → | 92 ± 28 ADC/MeV | MV0 v2 recalibration with improved MC geometry |
| 706,373 pulses | → | 640,737 pulses | S00 median selector gate, not dynamic selector |
| PCA 3 PCs 89%, 8 PCs 99.7% | → | Needs canonical rerun | Variance normalization is inconsistent across Wiki and corrected chapter |

---

## 5. What This Thesis Does NOT Claim

> **The following claims are explicitly excluded from this thesis:**

1. **No final event-aligned truth in real beam data.** All real-data timing and PID comparisons lack per-event MC truth. Truth anchors exist only in simulation.
2. **No final absolute per-event energy calibration from waveform alone.** The digitizer gain (92 ± 28 ADC/MeV) has a 30% systematic uncertainty. Per-stave variation is unresolved.
3. **No final B8 acceptance correction.** The MV3 stopping-depth MC/data mismatch (χ²/ndf = 68,269, B8 fraction 22.3% MC vs 2.3% data) prevents quantitative acceptance corrections until the GEANT4 geometry is fixed.
4. **No accepted Rmax value.** The earlier 4.22 MHz and 3.044–3.05 MHz summaries are not canonical until S-STAT-003 establishes the physical criterion and uncertainty model.
5. **No production ML timing replacement.** ML timing results are diagnostic/gated until transfer and leakage controls are complete. Analytic timewalk remains the conservative production method.
6. **No production duplicate-readout or saturation correction.** P04p model selection is unstable at its coverage boundary, and P07e performs worse than raw on held-out external duplicate closure.
7. **No forced-pedestal truth in current data.** Baseline/pedestal validation is limited to self-consistency checks without dedicated forced-trigger runs.

---

## 6. Project Architecture

```
Raw ROOT files → Pulse table (640,737 selected B-pulses)
  ├── Timing branch → pickoff → timewalk → covariance → combined σ₆₈
  ├── Pile-up branch → τeff → Rmax definition/uncertainty study → two-pulse recovery
  ├── PID branch → ΔE–E features → HGB classifier → AUC/purity
  ├── ML branch → PCA/AE → ML timing → duplicate readout → saturation recovery
  ├── MC truth bridge → MV0-MV6 validations → digitized MC comparisons
  └── Systematic budget → nuisance propagation → final claims
```

---

## 7. Established Results

🔒 S00 reproduction gate (640,737 pulses) is canonical, exact, and reproducible — but gated at CL-001 pending data-contract gates #952, #953, #954.
✅ **MC method closure (clusters A–D, 2026-07-25):** on the Krakow 1M-event Geant4 MC
   the full analysis chain closes — combined timing σ₆₈ = **0.089 ns** (clusterB #918),
   PID AUC = **0.898** on the realistic ΔE-E chain (clusterA #921), ADC = **119.17
   ADC/MeV** and Birks kB = **0.0156 cm/MeV** (clusterC #917), digitizer-domain
   Rmax = **0.605 MHz** (clusterC #917).
✅ Opticks GPU/CPU optical-photon parity proven through GDML ingestion, 4-SiPM
   annotation, and 148,697 photons/event upload; CPU ctest 9/9 PASS (opticks #920,
   PARTIAL — device→host gather is the open last mile).
⚠️ **Detector performance on beam data is BLOCKED_DATA** (raw `hrdb_run_*.root` not
   staged); device/electronics calibration is an operator-bench item. The 0.68 / 0.54
   ns detector-timing values formerly listed here as VALIDATED are **withheld
   (BLOCKED, CL-002..006)**; the MV0 gain is **GATED** (CL-013, ±30% heuristic
   envelope, not a CI); τeff = 124.79 ns is **DONE_DATA_ONLY** (CL-011), not VALIDATED.
⚠️ Canonical Rmax undefined (CL-010); legacy 3.044 MHz **SUPERSEDED** (CL-012). The
   0.986 HGB PID is a TRUTH_LEVEL_MC_ONLY ceiling (CL-017), not a data result.
⚠️ Traditional methods remain competitive on the legacy data-side studies, but those
   studies are not the current headline; the MC closure above is.


## 8. Remaining Open Issues

⚠️ **Rmax definition blocked:** Neither 4.22 MHz nor 3.044–3.05 MHz is canonical. S-STAT-003 must establish the physical criterion, uncertainty model, and accepted calculation.
⚠️ **MC timing tension:** MV4 raw timing is validated (pull = −1.05σ), but timewalk-corrected timing shows +2.68σ tension. MV4b diagnosed the cause (toy digitizer uses B/√ADC instead of physical B/A). It needs a digitizer fix and rerun.
⚠️ **MV3 geometry failure:** Missing upstream material (estimated ~8–10 g/cm²) causes a 10× overestimate of B8 penetration in MC. This blocks quantitative PID acceptance corrections.
⚠️ **PID truth transfer:** p/d AUC = 0.9860 is MC-truth only. Transfer to real data with weak labels has not been demonstrated at comparable performance.
⚠️ **ML timing gate:** ML timing shows promising residuals but has not passed all leakage controls. It remains diagnostic until LORO, transfer, and control-table requirements are complete.
⚠️ **Duplicate-readout selection gate:** The P04p point-estimate GBT winner lies at an uncertainty boundary; no canonical winner exists without a preregistered coverage rule and independent validation.
⚠️ **Saturation recovery gate:** The P07e synthetic pseudo-saturation result does not authorize production use because held-out external duplicate closure is worse than raw and producer bytes are unbound.
⚠️ **Systematic propagation incomplete:** Systematic uncertainties are listed but not fully propagated to all final observables.
⚠️ **PCA variance stale:** PCA variance values in Wiki and corrected chapter are inconsistent and need a canonical rerun.

---

## 9. Next Studies Required

🔬 **Resolve S-STAT-003** — preregister the Rmax physical criterion and uncertainty model before restoring a pile-up-rate value.
🔬 **Covariance-aware combined timing estimator** — replace the independence assumption with measured pair covariance.
🔬 **MV4b digitizer fix** — switch toy digitizer timewalk from B/√ADC to B/amplitude; rerun MV4 timing MC validation.
🔬 **GEANT4 geometry update** — add missing material; regenerate MC; rerun MV3, MV1, MV2, and MV6 sensitivities.
🔬 **PID depth-reweighting** — reweight MV1 by data stop-layer fractions to bound the MV3 impact.
🔬 **P04p/P07e independent validation** — freeze uncertainty and model-selection rules, bind producer bytes, and test cross-stave/new-run transfer.
🔬 **Full nuisance propagation** — build a systematic nuisance-parameter propagation pipeline for all final claims.
🔬 **Claim ledger audit** — verify every number in every chapter maps to a 43-column claim-ledger row with correct status.
🔬 **Figure regeneration** — upgrade all figures to paper-grade vector exports and 300+ dpi PNGs with source CSV/JSON and conclusion-bearing captions.

---

## 10. Reproducibility

This chapter is reproducible from the following artifacts:

- **Claim ledger:** [`docs/claim_ledger.csv`](../claim_ledger.csv)
- **Figure registry:** [`docs/figure_registry.csv`](../figure_registry.csv)
- **Canonical values:** [`docs/CLAIM_CHECKLIST_INTEGRATION.md`](../CLAIM_CHECKLIST_INTEGRATION.md)
- **Source commit:** `main` branch, commit at time of writing

All quantitative claims in this chapter must be registered in the claim ledger with traceable source paths. Rows that fail the 43-column schema gate remain non-authoritative until reconstructed from source evidence.
