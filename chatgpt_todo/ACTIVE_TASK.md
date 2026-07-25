# Active Task

- **Task ID:** AUD-LEDGER-003
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T070705Z
- **Initial remote main SHA:** `53bf42c8d414c9d11bcc1f9d5ab2d088da5a7600`
- **Scope:** audit canonical `CL-011` effective-live-time provenance, estimand, count, uncertainty, and validation semantics against the tracked primary S10b artifacts and the later MV5 use.
- **Primary evidence:** S10b source commit `da9651c56ef6495ce9656d84b69b600daa6d8f86`; exact run-average live10 estimate `124.79018394263471 ns`; run-bootstrap 95% interval `[123.33094981246663, 126.35875117626817] ns`; 14 held-out runs and 252,266 selected pulses.
- **Confirmed defects:** current `CL-011` cites secondary MV5 files, includes a nonexistent `results.json` path, rounds the source estimate/CI, records unsupported `0.5/1.0/1.12 ns` uncertainty components, gives `n_data=213843`, obscures the run-average estimand, and overstates MV5 reuse as independent `VALIDATED` data+MC closure.
- **Audit gate:** `tools/audit/audit_tau_eff_claim_binding.py`, policy `TAU_EFF_CLAIM_MUST_BIND_TO_PRIMARY_S10B_MEASUREMENT`; current-like exact-width row returns `FLAWED` with 30 findings, while a corrected contract fixture returns `VALIDATED` with zero findings.
- **Validation:** `python -m py_compile` passed; `PYTHONPATH=. pytest -q tests/test_audit_tau_eff_claim_binding.py` returned `6 passed in 1.22s`; exact mean and RNG-dependent percentile interval were independently reconstructed; JSON and SVG parsed; local Git blob IDs match committed validator/test/evidence bytes.
- **Evidence:** `docs/validation/tau_eff_claim_binding_audit.md`, `tau_eff_claim_binding_validation.json`, `tau_eff_claim_binding.svg`, and immutable archive `chatgpt_todo/archive/2026-07-25T070705Z_AUD-LEDGER-003_TAU_EFF_BINDING.md`.
- **Scientific boundary:** tracked derived-artifact/provenance audit only; raw ROOT files were not reprocessed, no waveform fit was rerun, and no new detector measurement or systematic uncertainty was produced.
- **Status:** PARTIAL. The defect and fail-closed remediation contract are validated; canonical `CL-011` and dependent public text remain to be corrected under `BLK-S10B-001` after an explicit estimand/uncertainty acceptance decision.
