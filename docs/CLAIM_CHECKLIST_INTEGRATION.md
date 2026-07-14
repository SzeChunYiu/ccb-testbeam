# Claim Ledger & Figure Registry — Integration Guide

> **Status:** Operational (2026-07-14)
> **Purpose:** How every thesis chapter connects to the claim ledger and figure registry.

## Quick reference

| If you are... | Read this first |
|---|---|
| **Writing a chapter** | [Writer's checklist](#writers-checklist) |
| **Reviewing a chapter** | [Reviewer's checklist](#reviewers-checklist) |
| **Running CI/lint** | [Automated checks](#automated-checks) |

---

## Canonical vocabulary

Use these labels consistently in all chapters:

| Label | Meaning | When to use |
|---|---|---|
| **VALIDATED** | Supported by data AND MC/truth/independent closure | Both data and independent test agree |
| **DONE_DATA_ONLY** | Robust in data, MC/truth pending or impossible | No MC truth available but data result is solid |
| **TRUTH_LEVEL_MC_ONLY** | Mechanism shown in simulation, detector transfer incomplete | MC shows mechanism but not yet validated with real data |
| **GATED** | Promising result, not adopted until controls pass | ML or novel method with pending transfer/leakage tests |
| **CORRECTED** | Previous result was leakage, convention error, or stale value | Old value was wrong; new value is canonical |
| **TENSION** | Data and MC disagree beyond tolerance | Comparison exists but shows significant discrepancy |
| **FAIL** | MC or validation reveals concrete model failure | MC is structurally wrong for this observable |
| **BLOCKED** | Cannot finalize until missing data/simulation/geometry exists | External dependency prevents closure |
| **SUPERSEDED** | Old value retained only for history | Never present as current result |

---

## Writer's checklist

Before marking a chapter as complete, verify:

1. **Every quantitative claim** in the chapter text has a corresponding row in `docs/claim_ledger.csv`.
   - If not, add it. Use `claim_id = CL-XXX` where XXX is the next available number.
2. **Every figure** in the chapter has a corresponding row in `docs/figure_registry.csv`.
   - If not, add it. Use `figure_id = FIG-XXX-YYY` (XXX=chapter code, YYY=sequential).
3. **No superseded value** appears without a correction marker (e.g., "corrected from 4.22 MHz → 3.05 MHz").
   - Run: `python scripts/audit_claim_superseded.py`
4. **Plot requirements** are met:
   - Vector export (PDF or SVG) exists
   - Source CSV/JSON data exists
   - DPI ≥ 300 for PNG, ≥ 600 for final print
   - Axes have units, caption states conclusion, sample size shown
5. **The chapter ends with three boxes:**
   - ✅ **Established results**
   - ⚠️ **Remaining open issues**
   - 🔬 **Next studies needed to close them**

---

## Reviewer's checklist

When cross-checking a chapter against the ledger:

1. Pick any quantitative claim in the chapter. Search `docs/claim_ledger.csv` for it.
   - If missing → flag as incomplete
2. Check the claim's status in the ledger matches the chapter text.
   - If chapter says "validated" but ledger says "GATED" → flag
3. Check all figures appear in `docs/figure_registry.csv` with non-"needs_redraw" status.
4. Run `python scripts/audit_claim_superseded.py` — must exit 0.

---

## Automated checks

### claim_ledger.csv schema
```
claim_id, chapter, claim_text, value, uncertainty_stat, uncertainty_syst, unit,
source_report, source_script, source_data, truth_type, status,
supersedes, blocked_by, figure_ids, table_ids, last_verified_commit
```

### figure_registry.csv schema
```
figure_id, chapter, caption_conclusion, source_script, source_csv_json,
output_pdf, output_png, status, dpi, vector_available, needs_redraw, reason
```

### CI linters (run on every push)
```bash
python scripts/audit_claim_superseded.py        # superseded-value scan
python scripts/check_claim_ledger_complete.py   # claim coverage check (Iteration 7)
python scripts/check_figure_source_data.py       # source data presence (Iteration 7)
```

---

## Chapter → claim_id mapping

| Chapter | claim_id range | Figure prefix |
|---|---|---|
| Executive Summary | CL-001 | FIG-EX-* |
| Experimental Setup | (TBD) | FIG-SET-* |
| Data Pipeline | (TBD) | FIG-DP-* |
| Timing Analysis | CL-002–CL-009 | FIG-TIM-* |
| Pile-up Analysis | CL-010–CL-012 | FIG-PU-* |
| Pulse Shape / ML | CL-023–CL-024 | FIG-PS-* |
| Energy Calibration | CL-013–CL-016 | FIG-EN-* |
| Particle ID | CL-017–CL-021 | FIG-PID-* |
| Anomaly ID | CL-022 | FIG-AN-* |
| MC Validation | CL-007–CL-008 | FIG-MC-* |
| Pedestal/Baseline | CL-025 | (TBD) |
| Systematics | CL-026 | FIG-SYS-* |

---

## Related files

- `docs/claim_ledger.csv` — canonical claims database
- `docs/figure_registry.csv` — canonical figure inventory
- `scripts/audit_claim_superseded.py` — stale-value linter
- `17_canonical_numbers_and_correction_ledger.md` — master correction ledger in upgrade pack
- `18_declared_figure_inventory.csv` — source figure inventory in upgrade pack
