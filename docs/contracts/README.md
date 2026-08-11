# CCB data & geometry contracts

Explicit, versioned contracts that resolve the v2 re-audit P0 ambiguities. Each
is the single source of truth for its concern; downstream code and CI validate
against it.

| Contract | Resolves | What it fixes |
|---|---|---|
| [PULSE_TABLE_CONTRACT.md](PULSE_TABLE_CONTRACT.md) | P0 A-001 | amplitude is `peak_height_adc = max(waveform-baseline)`, already baseline-subtracted — forbids the MV0/MV3 double subtraction; deprecates ambiguous `amplitude_adc` |
| [GEOMETRY_READOUT_MAPPING_CONTRACT.md](GEOMETRY_READOUT_MAPPING_CONTRACT.md) | P0 A-004 | one canonical layer→stave map from deployed-ROOT coordinates, not fit-to-stopping; ships `geometry_contract.template.json` |
| [MC_WEIGHT_POLICY.md](MC_WEIGHT_POLICY.md) | P0 A-003 | MC readers must consume `PrimaryWeight` or explicitly declare it irrelevant; fail-fast + ESS reporting |
| [../adr/ADR-0002-geometry-kinematics-hypotheses.md](../adr/ADR-0002-geometry-kinematics-hypotheses.md) | #987/#989/#991/#992 | Versioned hypothesis registry; fail-closed when `geometry_profile_id` unset; no silent length/spacing/fibre/KE pick |
| [../adr/ADR-0003-beam-intersection-preflight.md](../adr/ADR-0003-beam-intersection-preflight.md) | #999 | Geometry-aware primary ray–stave preflight; rejects miss configs unless `allow_miss` |
| [`configs/geometry/registry_index.yaml`](../../configs/geometry/registry_index.yaml) | Wave A Lane 03 | Machine-readable geometry/mapping/kinematics hypothesis index |
| [../adr/ADR-0004-daq-digitizer-measured-transfer.md](../adr/ADR-0004-daq-digitizer-measured-transfer.md) | #1009 | Production DAQ digitizer BLOCKED without measured TF; no invented clocks |
| [../adr/ADR-0005-g4-step-convergence-neutron-timecut.md](../adr/ADR-0005-g4-step-convergence-neutron-timecut.md) | #1095 #1091 | Explicit step-policy + QGSP_BIC 10 µs neutron time-cut pins |
| [`configs/transport/`](../../configs/transport/) | Wave B Lane 06 | DAQ / step / neutron transport registries (fail-closed) |

## Enforcement (offline, live now)

- `tools/audit/validate_pulse_schema.py` → flags `AMBIGUOUS_AMPLITUDE_ADC`, `MISSING_REQUIRED_COLUMNS`, `DUPLICATE_PULSE_KEY`.
- `tools/audit/audit_repository.py` → flags `AMPLITUDE_SCHEMA_DOUBLE_SUBTRACTION`, `EVENTNO_ONLY_JOIN`, `MC_WEIGHT_NOT_DECLARED`, `INDEX_PARITY_SPLIT`.
- `tools/audit/validate_event_keys.py` → proves composite-key one-to-one join cardinality before any physics merge.
- `tools/audit/audit_mc_weight_usage.py` → reports weighted effective sample size.

## Mandated status corrections

The v2 re-audit's mandatory study-status changes (MV0–MV6, eventno-only ΔE–E)
are recorded machine-readably in
`reports/reaudit_20260720/status_corrections/` (schema-valid closure records).
These are the labels that must appear in any status document; the underlying
re-runs are `BLOCKED_COMPUTE`/`BLOCKED_EXTERNAL` on LUNARC.
