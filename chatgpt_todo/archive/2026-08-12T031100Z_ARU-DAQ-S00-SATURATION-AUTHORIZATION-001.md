# ARU-DAQ-S00-SATURATION-AUTHORIZATION-001

Status: `PARTIAL`  
Parent atoms: #1073, #1014; polarity/rail dependency #954; S00 producer integration child remains open.  
Branch base: `ccb-testbeam main@896c6c0bca2fa0d5fdf50a5d33840e4b8ab75b60`.

## Selected atomic universe

Field-level scientific authority of the S00 pulse-table `saturation` boolean.
The repository already has a fail-closed ADC-world registry, but the live S00
producer still computes `waveforms.max(axis=-1) >= 16383`, serializes it under
the plain name `saturation`, and does not carry a saturation field-authorization
gate in the canonical manifest.

The bounded question is not which ADC hardware CCB used. It is whether presence
of this field in an otherwise canonical S00 artifact can authorize a physical
clipping/censoring statement while the native-to-stored transfer is unresolved.

## Input/output contract and scientific meaning

Input to the legacy diagnostic is `peak_code_adc`, the maximum **stored HRDv
sample code** in a waveform. It is not baseline-subtracted amplitude and it is
not proven to be a native ADC code.

The historical World-A numerical map is

`D_A(x) = 1{x >= 16383}`.

The new machine contract `ccb-s00-saturation-field/1` returns this only as a
named diagnostic with:

- `semantic_class = DIAGNOSTIC_ONLY_ADC_WORLD_UNRESOLVED`,
- `diagnostic_world_id = A`,
- `authorising = false`,
- `hardware_censoring_claim = false`,
- parent registry status `BLOCKED_HARDWARE_EVIDENCE`.

A physical saturation/censoring consumer must instead request an authorising
contract and fail closed.

Field-level authority is intentionally distinct from an S00 count/selection
contract: the selector uses pedestal/polarity-corrected amplitude, not the
`saturation` boolean. Therefore a valid count reproduction does not logically
prove or require a physical saturation threshold.

## Competing mechanisms / descriptions

1. `16383` is the real upper rail of the stored product after a true 14-bit path.
2. Native 12-bit V1742 values are transformed/rescaled/repacked before `HRDv`.
3. The actual CCB board is a 14-bit 100-MS/s family and the legacy V1742 name is wrong.
4. `7000` marks an analog/front-end nonlinearity rather than digital full scale.
5. `7000` is only an analysis diagnostic boundary.
6. `16383` is merely an int14/schema convenience rather than measured censoring.
7. A stored integer domain or baseline-subtracted amplitude has been mistaken for native ADC range.

Descriptions differing only by an unknown monotone transform from native code to
stored `HRDv` are observationally indistinguishable from stored extrema alone and
are collapsed until the transform is recovered.

## Equations / invariants / limiting cases

For an ideal unsigned `b`-bit native ADC,

`N_codes = 2^b`, `code_native in [0, 2^b - 1]`.

Stored-code peak and baseline-subtracted amplitude are different measurands:

`P = max_s code_stored(s)`,

`A = max_s polarity * (code_stored(s) - baseline)`.

A physical censoring state requires a known transfer-domain exit or explicit
clipping transform. A plain comparison `P >= T` is only physical if `T` and the
stored/native mapping are source bound.

Authorization invariant:

`AUTHORISE(saturation physical censoring)`
`=> transfer_resolved AND rails_resolved AND polarity_resolved`
`AND overrange_semantics_resolved AND source_bound_hardware_firmware`.

Limiting case: if future evidence proves World A exactly, the current numerical
flags may remain unchanged while their authority state changes only through an
explicit schema transition. Numerical identity is not provenance identity.

## Evidence inspected

- `src/ccb_mc_validation/daq/adc_saturation_registry.py`: registry status is
  `BLOCKED_HARDWARE_EVIDENCE`; no authorising threshold; diagnostics carry
  `authorising=false`.
- `docs/contracts/ADC_SATURATION_WORLD_REGISTRY.md`: same fail-closed policy.
- `tests/test_lane08_daq_contracts.py`: tests registry failure/diagnostic World A.
- `scripts/01_build_pulse_table_from_root.py` on exact base main: still labels
  16383 as 14-bit V1742 hardware saturation, serializes plain `saturation`, and
  omits a saturation field-authority record from canonical manifest gating.
- `tests/test_s00_implementation_consistency.py`: fixtures still construct
  `saturation = peak_code_adc >= 16383` as a v1 schema column.
- `src/ccb_mc_validation/selector.py`: separate child gap; `_is_saturated` still
  hard-codes 16383 and an asymmetric lower-rail heuristic.
- #1073 / #1014 bodies and comments; both had been administratively closed even
  though their physical acceptance criteria remained open. Both were reopened.
- Official CAEN product documentation: V1742 is a 12-bit DRS4 switched-capacitor
  digitizer with GHz-rate modes; V1724 is a 14-bit 100-MS/s flash-ADC family.
  This eliminates the literal identity `V1742 == 14-bit 100-MS/s`, but does not
  identify the actual CCB board.

## Discriminating experiments / controls

Executed in this branch as deterministic software contracts, no RNG:

1. values `[0,4095,6999,7000,16382,16383,20000]` under explicit World A must
   map to `[0,0,0,0,0,1,1]` while retaining `authorising=false`;
2. boundaries 4095 and 7000 must not silently select Worlds B/C when World A is named;
3. requesting physical saturation authority must raise while #1073 registry is blocked;
4. a future registry transition cannot silently promote this legacy helper: the
   schema deliberately requires an explicit implementation review.

Not executed because required immutable inputs are unavailable here:

- run/channel `HRDv` code histograms and exact boundary occupancy;
- native-word -> unpacker/sorter -> `HRDv` reproduction;
- pulser/bench transfer and over-range scans.

## Implemented repository changes

- `src/ccb_mc_validation/daq/s00_saturation_field.py`: typed field-level contract,
  exact legacy World-A diagnostic wrapper, and fail-closed physical-authority API.
- `tests/test_s00_saturation_field_contract.py`: four deterministic controls.
- `docs/contracts/ADC_SATURATION_WORLD_REGISTRY.md`: records field-level
  authorization and the live producer integration gap.
- #1073 reopened and stable concern `CCB-1073-S00-FIELD-AUTHORIZATION-001` added.
- #1014 reopened as hardware-evidence BLOCKED; ADR remains valid as fail-closed
  governance rather than hardware-identification completion.
- #1059 reopened because #1277 explicitly retained it OPEN/PARTIAL but merge state
  drifted to completed; this side repair does not change the selected DAQ atom.

## Four sequential AI review passes

### 1. DAQ/hardware lead
Background: waveform digitizer transfer chains, ADC/SCA code domains, firmware
repacking and acquisition provenance.

Evidence: live S00 source/registry, #1014/#1073, official CAEN V1742/V1724 specs.
Strongest counter-hypothesis: 16383 may still be the true transformed `HRDv` rail.
Attempted falsifier: searched for source-bound transform/firmware identity; none is
present in inspected repository evidence, while literal V1742 14-bit/100-MS/s
semantics contradict official specifications.
Residual uncertainty: actual CCB module, firmware, native words and transform.
Vote: `ACCEPT` field-level diagnostic boundary; `BLOCK` hardware identity.

### 2. Adversarial mechanism reviewer
Background: data-contract fault injection, provenance state machines and
measurement-chain ambiguity.

Evidence: canonical S00 gate logic and independent registry semantics.
Strongest counter-hypothesis: canonical artifact authority should transitively
authorize every serialized field.
Falsifier: count selection does not consume `saturation`; field authority is
therefore logically separable. Conversely downstream saturation consumers can
still be unsafe until migrated.
Residual uncertainty: consumer audit/migration completeness.
Vote: `ACCEPT` field separation; `REVISE` production integration.

### 3. Independent statistics/validation reviewer
Background: measurement validation, negative controls and estimator identifiability.

Evidence: exact deterministic boundary controls; no random sampling.
Strongest counter-hypothesis: threshold fixtures validate detector saturation.
Falsifier: fixtures contain no measured transfer, raw rail occupancy, pulser
response or immutable CCB waveform population.
Residual uncertainty: run/channel rail behavior and nonlinearity distribution.
Vote: `ACCEPT` software oracle; `BLOCK` detector inference.

### 4. Claims/provenance reviewer
Background: source-to-claim ledgers, field-level evidence authority and public-claim gates.

Evidence: #1244 description, registry, live producer, #1073 acceptance criteria.
Strongest counter-hypothesis: fail-closed registry/ADR was sufficient to close #1073.
Falsifier: live producer still emits unresolved plain `saturation`; parent issue
requires source-bound transfer and downstream regeneration.
Residual uncertainty: full downstream saturation-consumer inventory.
Vote: `ACCEPT` bounded child; `REOPEN/BLOCK` #1073 parent completion.

## Cross-scale propagation

Micro: numerical threshold map is stable only as a named diagnostic.
Meso waveform: rail/clipping state is unresolved without transfer/polarity.
Event/study: any saturation-conditioned population remains non-authorising unless
its consumer checks the field contract.
Claim: energy/PID/pile-up/saturation performance cannot be promoted from this
software boundary.

## Child atoms

- `ARU-DAQ-S00-SATURATION-PRODUCER-INTEGRATION-001`: migrate producer/manifest/schema
  so plain field cannot be mistaken for physical censoring; audit consumers.
- `ARU-DAQ-SELECTOR-ADC-RANGE-UNKNOWN-001`: remove/replace hard-coded 16383 and
  asymmetric lower-rail heuristic in candidate pedestal validity.
- `ARU-DAQ-ADC-RAW-RAIL-OCCUPANCY-001`: immutable `HRDv` extrema/boundary pile-up
  by run/channel with event counts and hashes.
- #1014 hardware/firmware/unpacker transfer reconstruction.
- downstream saturation-conditioned report/figure/claim regeneration.

## Claim boundary / blockers

No beam bytes, native acquisition words, production MC, saturation fraction,
energy/PID tail, pile-up rate/mechanism, timing resolution, ESS, p-value or
detector-performance quantity was generated. The complete parent remains
`OPEN/PARTIAL` because immutable raw/native data and hardware/firmware evidence
are unavailable in this execution environment.
