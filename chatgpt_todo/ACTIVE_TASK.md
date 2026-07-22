# Active Task

- **Task ID:** AUD-PULSE-001
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-22T08:06:55Z
- **Base main SHA:** `bcd5762ec8fc10a911e32e60a0b91b0d6fbd6d0c`
- **Primary scope:** make A-001 pulse-schema validation artifacts traceable to exact input bytes.
- **Files inspected:** `tools/audit/validate_pulse_schema.py`, `tests/test_audit_tools.py`, A-001 report and JSON artifacts, recent `main` history.
- **Observed fact:** the committed A-001 JSON used abbreviated table paths and omitted input hashes and byte sizes, so the exact validated compressed table could not be independently identified.
- **Implementation:** validator now emits input path, byte size, SHA-256, tool path, and tool version; compressed-CSV provenance regression test added.
- **Validation:** exact temporary copies passed `python -m pytest /tmp/exact_a001/tests/test_pulse_schema_provenance.py -q` with `1 passed in 0.07s`.
- **Evidence boundary:** no real pulse table, ROOT input, MV0 gain, or MV3 threshold was regenerated in this session.
- **Progress:** code, regression test, and immutable archive record are present on remote `main`.
- **Acceptance status:** PARTIAL — implementation validated; real A-001 artifact regeneration remains BLOCKED_COMPUTE.
