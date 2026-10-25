# #1628 follow-on: canonical MV1–MV3 ROOT truth unit/row-contract audit

**SCIENTIFIC RELEASE NOT_AUTHORIZED; 2026-10-19.** Base main `a61427813344e29047ca9eb9b764182eb29e4c83`; review parent `bf9215bba7259f9d9d57b0a55a9377558306f63c`. This is a **different canonical producer** from the preceding `track_builder.py` audit. No production code or result was modified.

## New executed defects

**RT-01 — raw GeV/c components used with MeV/c² masses.** The full bytes of main `src/ccb_mc_validation/io/root_truth.py` (Git blob `a9b3f8ad064db4031521110e78ac741d2a61a7c6`) were independently copied into a bounded local fixture and verified byte-identical. Its real conversion function uses sqrt(px²+py²+pz²+m²)−m without converting raw momentum. But the canonical `truth/pdg.py` (blob `8c484b131ec07f3af2e2bd4726b83cd64601190c`) explicitly declares Krakow Sci_bar momentum in **GeV/c**, with MeV masses. A proton with synthetic p=0.4 GeV/c produces **0.0000852631 MeV** rather than **81.7056203 MeV**. A deuteron with p=0.6 GeV/c produces **0.0000959686 MeV** rather than **93.6315571 MeV**. An independent 60-digit decimal Lorentz oracle found incompatible unit results in **202/202** bounded p/d momentum cases. This is **not** a simple factor-of-1000 energy correction: energy is nonlinear in momentum. The result is conditional on the verified repository GeV/c source-world contract; actual historic ROOT impact is not yet measured. CLI MV2 uses this Ekin as a range-energy regression target; do not transfer the finding automatically to MV1's AUC.

**RT-02 — silently drops misaligned deposits.** Original code computes `usable=min(lay.size,e.size)` and sums only the prefix of `Sci_bar_EDep`. With 2 layers and 1 deposit, it returns ordinary 2 MeV and 1 occupied layer instead of rejecting unequal per-hit branches. With 2 layers and 0 deposits it reports zero deposited energy. The called trigger validator checks layer/arm/PDG/time shapes, **not EDep**. Whether real input is corrupted is unknown.

**RT-03 — first hit masquerades as event species and kinematics.** Original code assigns the event PDG and momentum from the first row. Two permutations of the same p+d hit multiset both deposit 5 MeV, but receive different species labels and kinetic energies. This is not an identified generator primary, entering track, or exclusive species event. It is separate from the known PR1544 first-recognized-charged-hit defect and the preceding track-builder endpoint failure.

Related observed risks: first `Sci_bar_TrackLength` value varies with row order (branch accumulation semantics unresolved); empty momentum arrays default to 0 KE, NaN inputs can propagate; empty events carry numeric stop_layer=0 even without stopping. Current `tests/test_root_truth_records.py` only asserts Ekin>0 after feeding momentum numbers 100/200; it never checks the physical unit. In `ccb_mc_validation.cli` the production MV1/MV2/MV3 runner normally reads a bounded first **100,000** events unless overridden and may still label its study PRODUCTION; this is a separate static population/provenance gate, not evidence that a historical result was biased.

## Executed tests and honest boundaries

- 28 local unittest methods passed normally and when run with `python -O`; the optimized repetition is **not 28 more independent validations**.
- Original entire `root_truth.py` Git blob imported/executed. Test doubles were injected for **mass_of** (declared exact p/d values only) and **process_chunk** (inert flag vectors) to isolate conversion. Not a full production import with authentic dependencies.
- `checkout_probe.py` provided here reproduces all three central defects from a complete checkout matching the pinned blob. Its exit **1** means defects reproduced; exit **2** means missing/changed source or test failure. Local result JSON replayed byte-for-byte in optimized mode.
- No ROOT archive, actual C++ Sci_bar writer, complete Geant4, actual MV1/MV2/MV3 report, installed hardware or independent human review was executed. The source writer `SD_Det::ProcessHits` is not present in checked `geant4/src_patch` and `geant4/single_stave/src`; single-stave code is not a substitute for the Krakow producer.

## Four perspective challenges — one assistant, not an independent panel

Detector/DAQ: reject unequal jagged branches and get ROOT source/DAQ bytes and exact writer. Transport: convert GeV/c→MeV/c once before relativistic KE; label per-hit, per-track and generator primaries distinctly. Statistical reviewer: wrong Ekin targets and arbitrary first-hit species can change calibration/PID estimands; rerun only with source-bound event/weight and run-level independence. Adversarial provenance reviewer: fail source drift, invalid data, synthetic-as-physical claims, default-prefix population ambiguity and false publication promotion.

Next: owner integrate strict alignment, finite/count validation, explicit campaign momentum units and physical species/track identity into canonical module; then **run exact full-checkout tests**, replay immutable ROOT with declared N_total/valid/tracks/weights/ESS and rerun affected MV1–MV3 figures/claims through #1595 ledgers. Preserve historical failures. No numerical headline repairs or closure before authentic source/physics evidence.

Primary method sources: https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Fundamentals/unitSystem.html ; https://geant4.web.cern.ch/documentation/dev/faq_html/FAQ/tracksAndSteps.html . Both explain unit and step conventions, **not the experiment-specific ROOT writer**.
