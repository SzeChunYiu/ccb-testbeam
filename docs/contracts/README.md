# CCB data & geometry contracts

Explicit, versioned contracts that resolve the v2 re-audit P0 ambiguities. Each
is the single source of truth for its concern; downstream code and CI validate
against it.

| Contract | Resolves | What it fixes |
|---|---|---|
| [PULSE_TABLE_CONTRACT.md](PULSE_TABLE_CONTRACT.md) | P0 A-001 | amplitude is `peak_height_adc = max(waveform-baseline)`, already baseline-subtracted — forbids the MV0/MV3 double subtraction; deprecates ambiguous `amplitude_adc` |
| [GEOMETRY_READOUT_MAPPING_CONTRACT.md](GEOMETRY_READOUT_MAPPING_CONTRACT.md) | P0 A-004 | one canonical layer→stave map from deployed-ROOT coordinates, not fit-to-stopping; ships `geometry_contract.template.json` |
| [MC_WEIGHT_POLICY.md](MC_WEIGHT_POLICY.md) | P0 A-003 | MC readers must consume `PrimaryWeight` or explicitly declare it irrelevant; fail-fast + ESS reporting |

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
