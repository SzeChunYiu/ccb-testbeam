# CCB test-beam — v2 scientific re-audit response (LUNARC-independent)

**Branch:** `ai/scientific-reaudit-20260720`
**Base:** merged main after PR #858
**Audited HEAD:** `d3b2beb…` (== the v2 handoff's audited HEAD)
**Scope:** implement everything from the v2 re-audit that runs **without LUNARC**,
verified locally. Data/compute re-runs are staged and marked `BLOCKED_*`.

## Delivered

### 1. Executable repository-wide audit harness — `tools/audit/`
The four v2 audit tools integrated, hardened, unit-tested (9 pytest green), and
**run over the whole repo**. Real, evidenced findings
(`reports/reaudit_20260720/audit_harness/findings.{csv,json}` + `summary.json`):

- **1024 files inventoried; 111 P0, 567 P1.** P0 codes (all spot-checked genuine):
  - `CLAIM_SOURCE_MISSING` ×50 — claim-ledger `source_*` paths not on disk
  - `MC_WEIGHT_NOT_DECLARED` ×36 — uproot MC readers with no `PrimaryWeight`/justification
  - `EVENTNO_ONLY_JOIN` ×13 — e.g. `scripts/data01_sample_split_staves.py:116`
  - `INDEX_PARITY_SPLIT` ×10 — e.g. `scripts/mc01_trigger_split_truth.py`
  - `AMPLITUDE_SCHEMA_DOUBLE_SUBTRACTION` ×2 — e.g. `scripts/mv3_stopping_v2.py:103`

These findings are candidates for triage, not verdicts; each becomes actionable
against the contracts below. The per-script physics fixes require data on LUNARC
to validate (re-running would change results), so they are `BLOCKED_*`, while the
harness, contracts, and canonical replacements are done now.

### 2. Data & geometry contracts — `docs/contracts/`
Explicit versioned contracts resolving the P0 ambiguities:
- `PULSE_TABLE_CONTRACT.md` (A-001) — amplitude already baseline-subtracted; forbids double subtraction; deprecates ambiguous `amplitude_adc`.
- `GEOMETRY_READOUT_MAPPING_CONTRACT.md` (A-004) — one canonical layer→stave map from deployed-ROOT coordinates; `geometry_contract.template.json`.
- `MC_WEIGHT_POLICY.md` (A-003) — consume `PrimaryWeight` or declare irrelevance; ESS reporting.

### 3. Mandatory status corrections — `reports/reaudit_20260720/status_corrections/`
The v2 mandated study-status changes as 7 schema-valid closure records:
MV0→CORRECTED/BLOCKED, MV1→MC_TRUTH_ONLY_REAUDIT, MV3→FAIL_DIAGNOSTIC,
MV4→TOY_DIAGNOSTIC, MV5→SELF_CONSISTENCY_ONLY, MV6→MC_HYPOTHESIS_TENSION,
eventno-only ΔE–E→INVALID_PENDING_RERUN.

### 4. Canonical ΔE–E module — `scripts/single_stave/deltaE_E.py`  *(see closure matrix)*
Composite-key `(source_file_id, run_id, event_id)` join, explicit Sample I/II,
applied thresholds, threshold-defined stopping layer, deterministic seed,
hexbin+conditional-quantile plots, event tables — the correct replacement for the
unsafe/absent `supervisor_deltaE_E.py` (A-002). ADC and MeV kept distinct.

### 5. Publication-figure result registry — `tools/figure_registry/`  *(see closure matrix)*
Registry-driven figure builder that FAILS on missing result / missing
uncertainty / source-hash mismatch / disallowed status, and keeps ILLUSTRATIVE
schematics separate from quantitative figures (governance finding #10).

## Not done (LUNARC-required, staged)
Pulse-table regeneration + MV0 gain re-derivation, weighted MC re-runs (MV1/MV3),
material-budget/stopping (#844), timing re-run (MV4), independent pile-up (MV5),
C12 tension quantification (MV6), and the real-data ΔE–E rerun — all
`BLOCKED_COMPUTE`/`BLOCKED_EXTERNAL`. See `status_corrections/` and
`audit_harness/summary.json`.

## Honesty
No physics result was re-run or relabeled as passing. The audit findings are
reported at face value; per-script edits that would change results are left
blocked pending data, not applied blind.
