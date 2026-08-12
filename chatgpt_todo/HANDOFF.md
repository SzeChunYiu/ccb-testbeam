# Latest Handoff

## S00 saturation is now explicitly a field-level diagnostic contract; hardware transfer remains blocked

Selected atom: `ARU-DAQ-S00-SATURATION-AUTHORIZATION-001`.

Protected root base was `main@896c6c0bca2fa0d5fdf50a5d33840e4b8ab75b60`. The live DAQ saturation registry already fails closed: it records incompatible ADC Worlds A/B/C, reports `BLOCKED_HARDWARE_EVIDENCE`, and exposes no authorising threshold. The production S00 producer nevertheless still bypasses that state by computing `waveforms.max(axis=-1) >= 16383`, serializing a plain `saturation` boolean, calling it 14-bit CAEN V1742 hardware saturation, and omitting saturation-field authority from the canonical manifest.

This run separated artifact-level and field-level authority. S00 selection/count closure is not logically identical to physical clipping closure because the selector uses pedestal/polarity-corrected amplitude rather than the `saturation` boolean. The exact physical-claim invariant is:

`AUTHORISE(saturation physical censoring) => native_to_stored_transfer_resolved && rails_resolved && polarity_resolved && overrange_semantics_resolved && hardware_firmware_source_bound`.

Draft PR #1279 on branch `audit/s00-saturation-field-authorization-v1` adds `src/ccb_mc_validation/daq/s00_saturation_field.py`, schema `ccb-s00-saturation-field/1`. `legacy_world_a_diagnostic()` reproduces the historical 16383 threshold map only under explicit World-A identity with `authorising=false`, `hardware_censoring_claim=false`, and `BLOCKED_HARDWARE_EVIDENCE`. `require_authorising_saturation_contract()` fails closed. `tests/test_s00_saturation_field_contract.py` has four deterministic controls covering exact boundaries at 4095/7000/16383 and the physical-authority failure state. No RNG, DATA or MC participates.

`docs/contracts/ADC_SATURATION_WORLD_REGISTRY.md` now states the known P0 producer integration gap and explicitly says #1073 is OPEN/PARTIAL. #1073 and #1014 were reopened: their ADR/registry fixes are valid fail-closed governance, but their issue bodies require source-bound hardware/firmware/native→stored reconstruction that is not present. #1059 was also reopened as a side governance repair because #1277 explicitly retained it OPEN/PARTIAL while its state drifted to completed.

A downstream claims audit found that `reports/P07_saturation_recovery/REPORT.md` still treated B2 >7000 ADC as likely hardware saturation and said its synthetic hard-clip benchmark directly enabled recovery of real B2 pulses. That interpretation has been demoted on this branch to `GATED / SYNTHETIC-CLIPPING ONLY`. The historical numerical benchmark table is retained without regeneration, but 7000 is no longer called a proven hardware rail, pre-injection amplitude is explicitly pseudo-truth, real B2 correction is not authorized, and the prior quenching/nonlinearity mechanism explanation is labeled a hypothesis. Claim-propagation provenance is archived in `chatgpt_todo/archive/2026-08-12T032300Z_ARU-DAQ-S00-SATURATION-AUTHORIZATION-001_CLAIM_PROPAGATION.md` and cross-linked on #1073.

Official CAEN documentation remains only an elimination tool: V1742 is a 12-bit DRS4 switched-capacitor digitizer with GHz-rate settings, whereas V1724 is a 14-bit 100-MS/s flash-ADC family. That rejects the literal repository phrase `14-bit V1742 @ 100 MS/s`; it does not prove which board the CCB run used or whether `HRDv` is transformed/repacked.

### Four sequential AI votes

**DAQ/hardware lead — ACCEPT field-level diagnostic boundary / BLOCK hardware identity.** Strongest counter-hypothesis is that 16383 is the real transformed stored rail; no source-bound transfer in the inspected repository falsifies or validates that yet.

**Adversarial mechanism/provenance reviewer — ACCEPT field separation / REVISE producer integration.** A canonical table can be valid for counts while one field remains non-authorising, but downstream consumers can still ignore metadata until the producer/schema migration lands.

**Independent statistics/validation reviewer — ACCEPT deterministic software oracle / BLOCK detector inference.** Exact threshold fixtures validate software semantics only; no rail-occupancy distribution, pulser scan, native-word replay or immutable beam sample was executed.

**Claims/provenance reviewer — ACCEPT bounded child and P07 demotion / REOPEN-BLOCK #1073 completion.** The fail-closed registry is necessary but insufficient while the live producer emits unresolved plain `saturation`; saturation-conditioned reports require explicit claim review and eventual regeneration after the transfer contract is known.

Archives: `chatgpt_todo/archive/2026-08-12T031100Z_ARU-DAQ-S00-SATURATION-AUTHORIZATION-001.md` and the P07 claim-propagation addendum above.

Immediate gate: protected exact-final-head CI on #1279; merge only if every required context on the same final head succeeds. The highest-value next scientific child is `ARU-DAQ-S00-SATURATION-PRODUCER-INTEGRATION-001`: migrate the S00 producer/manifest/schema so every emitted diagnostic is explicitly World-bound/non-authorising, audit downstream `saturation` consumers, and retain count authority without inventing hardware truth. After that, `ARU-DAQ-ADC-RAW-RAIL-OCCUPANCY-001` requires immutable run/channel `HRDv` bytes and #1014 requires native acquisition/firmware evidence.

No saturation fraction, beam-data result, production Geant4 result, energy/PID tail, pile-up mechanism, timing resolution, rate, ESS, p-value or detector-performance quantity was generated or promoted.
