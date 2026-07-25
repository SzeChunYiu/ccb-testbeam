# Active Task

- **Task ID:** AUD-DELTAE-003
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T050141Z
- **Initial remote main SHA:** `67a7cdd6ef0dc64f00a9ebb43077d2acc1a7418e`
- **Scope:** audit whether the canonical ΔE-E bridge rejects nonfinite net-amplitude rows before event/stave aggregation and missing-layer zero filling.
- **Repository evidence:** bridge blob `7f50ce667a6cde07e94717d0187831da4d8459ac`; direct net assignment at lines 183-184; aggregation/pivot at 200-215; zero fill at 218-221.
- **Confirmed defect:** a NaN B2 row can disappear during pivoting and become `amp_B2=0.0` when another stave is finite; positive infinity is retained. This can silently alter stopping-layer and ΔE classification.
- **Delivered:** fail-closed audit tool, five focused tests, reproducible renderer, Markdown/JSON/SVG evidence, immutable archive, and handoff.
- **Validation:** focused py_compile passed; pytest returned `5 passed in 0.12s`; JSON and SVG parsed; changed Python lines are at most 95 characters.
- **Scientific boundary:** synthetic software/provenance validation only; no A-002 data rerun or detector result.
- **Status:** PARTIAL — audit/evidence validated; canonical bridge remediation and exact production rerun remain blocked.
