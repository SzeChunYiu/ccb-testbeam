# Pulse-schema validation on real tables (A-001, CCB-PULSE)

Checked real pulse tables against `docs/contracts/PULSE_TABLE_CONTRACT.md` using the
`tools/audit/validate_pulse_schema.py` rules.

## Confirmed: the ambiguous amplitude is present in real data
- `reports/1781012359.../timing_pulse_table.csv.gz` — has **`amplitude_adc`** but
  **no** `peak_height_adc` / `peak_code_adc` / `net_adc`, and no baseline column →
  **`AMBIGUOUS_AMPLITUDE_ADC` = true**. A consumer cannot tell whether this column
  is net (baseline-subtracted) or absolute ADC code — exactly the ambiguity that
  produced the MV0/MV3 double subtraction (A-001).
- `reports/1781033578.../matched_pulse_table.csv.gz` — no `amplitude_adc` (uses
  `median_amp_adc`/`dynamic_amp_adc`) and carries explicit `baseline_*` columns →
  not flagged.

## Consequence
The producer (`scripts/01_build_pulse_table_from_root.py`) must emit
`peak_height_adc` (net) and `peak_code_adc` (absolute) per the contract; consumers
must stop treating `amplitude_adc` as absolute and re-subtracting `baseline_adc`.
Regenerating the tables under schema v1 and re-deriving the MV0 gain / MV3
thresholds remains BLOCKED_COMPUTE (needs the raw ROOT + the producer re-run).
Wiring `validate_pulse_schema.py` into CI as a gate is READY.
