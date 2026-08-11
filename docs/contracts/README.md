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

## Lane 10 Wave B fail-closed contracts

| Contract | Issue | Policy |
|---|---|---|
| [TRIGGER_HARDWARE_RESPONSE.json](TRIGGER_HARDWARE_RESPONSE.json) | #1045 | Hardware trigger `UNKNOWN_EXTERNAL` / `BLOCKED`; MC uses `MC_TRIGGER_PROXY` only ([mc_validation ADR-0002](../mc_validation/ADR-0002-trigger-hardware-proxy-blocked.md)). No invented hardware parameters. |
| [I885_ANGULAR_PHASE_SPACE.json](I885_ANGULAR_PHASE_SPACE.json) | #1093 | I885 campaign is `NORMAL_INCIDENCE_ONLY`; angular/azimuth closure claims blocked. |

Scientific PRs must not auto-close research-universe issues without ledgered
completion/successor-transfer evidence (#1218 / Wave A `fix/lane10-waveA`). Prefer `Refs`.

