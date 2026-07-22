# Active Task

- **Task ID:** AUD-AMP-002
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-22T22:04:00Z
- **Base main SHA:** `8d4b1d45defb7dcdbb505489a3f09f381efc0274`
- **Scope:** reconcile the pulse-table contract with the current rule for ambiguous `amplitude_adc` columns.
- **Finding:** the contract still described raw-median convention labels as actionable, while `tools/audit/amplitude_convention_audit.py` v2.6.0 marks median-only labels unanchored and non-accepting.
- **Change:** the contract now preserves the historical 17/2 split as heuristic evidence only and requires explicit schema, producer-code, or reviewed pedestal evidence before downstream subtraction decisions.
- **Validation:** compared the contract text with the v2.6.0 implementation and current handoff.
- **Boundary:** no real pulse table or A-002 input was rerun; those convention assignments remain unresolved.
- **Status:** PARTIAL — documentation is reconciled; real-data regeneration remains blocked.