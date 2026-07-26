# Active Task

- **Task ID:** `AUD-FIG-002`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T073041Z`
- **Initial remote main SHA:** `67e019d5359d76cc82fa0634a8ae2161dd2a464c`
- **Scope:** remediate the paper figure registry and builder so the shipped scientific evidence vocabulary is structurally valid while non-authorizing states cannot become paper figures merely because artifacts exist.
- **Policy:** `FIGURE_REGISTRY_STATUS_MUST_MAP_EXPLICITLY_TO_BUILD_DISPOSITION`.
- **Implementation:** the registry now accepts eleven controlled statuses and three kinds, maps every status explicitly to `BUILD`, `CONDITIONAL`, `BLOCKED`, `QUARANTINED`, or `ILLUSTRATIVE`, and applies path requirements by kind and authorization. The builder records scientific/runtime disposition, never reads numerical files for quarantined or blocked states, copies source-only/illustrative artifacts with byte/hash provenance, supports nested result keys, rejects nonfinite scalars, and publishes its report atomically.
- **Validation:** `python -m py_compile ...` passed; `pytest -q tests/test_figure_registry.py` returned `11 passed in 0.52s`; validation JSON and SVG parsed; changed Python lines are at most 97 characters. The local shipped-registry fixture is explicitly a connector-inspected structural-field copy because the execution container could not resolve `github.com`; an exact shipped-file regression is committed for a complete checkout.
- **Evidence:**
  - `docs/validation/figure_registry_schema_remediation_validation.json`
  - `docs/validation/figure_registry_schema_remediation.svg`
  - `docs/validation/figure_registry_schema_remediation_audit.md`
  - `chatgpt_todo/archive/2026-07-26T073041Z_AUD-FIG-002_SCHEMA_REMEDIATION.md`
- **Core delivery through:** `ce9a647f93126aeb55545627ce98c86da16f9c8c`.
- **Focused acceptance:** registry/builder remediation `VALIDATED / COMPLETE`.
- **Repository acceptance:** cumulative paper-figure scientific review remains `PARTIAL`; production inputs and figures were not regenerated or scientifically revalidated.
- **Scientific boundary:** no figure value, uncertainty, source result, calibration, PID, timing, stopping, pile-up, or detector-performance claim is validated by this task.
- **Status:** `COMPLETE`
