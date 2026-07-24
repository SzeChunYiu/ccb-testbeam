#!/usr/bin/env python3
"""One-time idempotent coordination writer for AUD-LEDGER-001."""
from __future__ import annotations

import argparse
from pathlib import Path

STAMP = "2026-07-24T182820Z"
INITIAL = "b63e194eca70c67e59e9793e96f5fd058dff1fc7"
IMPLEMENTATION = "cd4a31c2267bc617985c1edcedfa63aa99466fcc"
LEDGER_SHA256 = "e7e560a66df43a9cacdf5041361aaffa0995927144adae3701b5c60e0433c26b"
LEDGER_BLOB = "bb552aa5ed70e7d81dcda888c5aa61402c01e03c"


def replace_block(path: str, marker: str, body: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8") if target.exists() else ""
    start = f"<!-- BEGIN {marker} -->"
    end = f"<!-- END {marker} -->"
    block = f"{start}\n{body.rstrip()}\n{end}"
    if start in text and end in text:
        before, rest = text.split(start, 1)
        _, after = rest.split(end, 1)
        text = before.rstrip() + "\n\n" + block + after
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def write_initial() -> None:
    Path("chatgpt_todo/ACTIVE_TASK.md").write_text(
        f"""# Active Task

- **Task ID:** AUD-LEDGER-001 / legacy MV4 timing claim remediation
- **Owner:** scheduled scientific-review session
- **Session stamp:** {STAMP}
- **Initial remote main SHA:** `{INITIAL}`
- **Validated implementation/evidence head:** `{IMPLEMENTATION}`
- **Scope completed:** reconstructed `CL-002` through `CL-009` to the canonical 43-field schema; withheld five source-absent numerical claims; retained two source-backed pulls only as gated toy diagnostics; corrected the false ML label to analytic `REVIEW`; added fail-closed validation, tests, machine-readable evidence, visual evidence, and cumulative schema evidence.
- **Validation:** exact-repository py_compile passed; focused pytest `7 passed`; MV4 source audit `VALIDATED` with zero findings; cumulative claim-ledger schema `VALIDATED` with `26/26` exact-width rows and zero mismatches; JSON and SVG parsing passed.
- **Scientific boundary:** no ROOT rerun, per-stave timing estimate, combined-stave estimate, covariance measurement, calibration closure, or detector-performance result was produced.
- **Open blocker:** `BLK-MV4-LEGACY-001` remains OPEN pending strict current-calibration, measured-anchor, run/block, and covariance-aware reproduction.
- **Status:** COMPLETE for the ledger-remediation unit. The legacy timing physics claims remain BLOCKED/GATED/REVIEW as recorded.
""",
        encoding="utf-8",
    )

    replace_block(
        "chatgpt_todo/BACKLOG.md",
        "AUD-LEDGER-001-MV4-REMEDIATION",
        """## AUD-LEDGER-001 — Source-backed canonical claim ledger

- **Priority:** P0 governance / scientific traceability
- **Status:** COMPLETE
- **Impact:** all 26 current claim rows now have exactly 43 fields; no malformed row is interpreted.
- **Acceptance evidence:** `docs/validation/claim_ledger_schema_validation.json`, `docs/validation/mv4_legacy_claim_rows_audit_validation.json`, focused regression suite, and exact ledger SHA-256 `e7e560a66df43a9cacdf5041361aaffa0995927144adae3701b5c60e0433c26b`.
- **Residual dependency:** claim-specific blockers remain authoritative; schema completion does not validate physics.
""",
    )
    replace_block(
        "chatgpt_todo/MASTER_INDEX.md",
        "IDX-LEDGER-002",
        """## IDX-LEDGER-002 — Canonical claim-ledger schema

- **Area:** `docs/claim_ledger.csv`
- **Status:** VALIDATED
- **Coverage:** 26/26 claim rows; 43/43 fields per row; 0 malformed rows.
- **Evidence:** `docs/validation/claim_ledger_schema_audit.md`, JSON, and SVG.
- **Limitation:** structural validity permits field interpretation but does not upgrade claim status.
""",
    )
    replace_block(
        "chatgpt_todo/STUDY_REVIEW_LEDGER.md",
        "ST-TIM-MV4-LEGACY-002",
        """## ST-TIM-MV4-LEGACY-002 — Legacy timing claim reconstruction

- **Status:** COMPLETE (governance unit)
- **Question:** which legacy MV4 timing claims are actually present in tracked source artifacts?
- **Inputs:** exact legacy report, summary JSON, historical producer/source commit, current fail-closed contract, and canonical ledger.
- **Finding:** five B6/combined/covariance values are absent and withheld; two pulls are fixed toy diagnostics; the method is analytic CFD20/timewalk, not ML.
- **Physics limitation:** strict current-input rerun and measured uncertainty/covariance closure remain absent.
""",
    )
    replace_block(
        "chatgpt_todo/CLAIM_EVIDENCE_MATRIX.md",
        "CL-MV4-LEGACY-002",
        """## CL-MV4-LEGACY-002 — Legacy timing source boundaries

- **Claims:** `CL-002`–`CL-009`
- **Evidence state:** source-bound and exact-width.
- **Statuses:** `CL-002`–`CL-006` BLOCKED; `CL-007`–`CL-008` GATED; `CL-009` REVIEW.
- **Sources:** `reports/mv4_timing_1782678162/REPORT.md`, `mv4_summary.json`, `scripts/mv4_timing_study.py`, current `MV4_TIMING_README.md`.
- **Blocker:** `BLK-MV4-LEGACY-001`.
""",
    )
    replace_block(
        "chatgpt_todo/CODE_RESULT_MAP.md",
        "CRM-MV4-LEGACY-002",
        """## CRM-MV4-LEGACY-002 — Claim-ledger remediation path

- **Result:** canonical rows `CL-002`–`CL-009` and cumulative schema state.
- **Code:** `tools/audit/audit_mv4_legacy_claim_rows.py`; `tools/audit/validate_claim_ledger_schema.py`.
- **Tests:** `tests/test_audit_mv4_legacy_claim_rows.py`.
- **Inputs:** canonical ledger, tracked MV4 report/summary, current execution contract.
- **Outputs:** validation Markdown/JSON/SVG under `docs/validation/`.
""",
    )
    replace_block(
        "chatgpt_todo/VISUALIZATION_MATRIX.md",
        "VIS-MV4-LEGACY-002",
        """## VIS-MV4-LEGACY-002 — Source-bound timing-claim state

- **Status:** VALIDATED software/provenance evidence
- **Plot:** `docs/validation/mv4_legacy_claim_rows_audit.svg`
- **Inputs:** exact canonical ledger plus tracked legacy source facts.
- **Meaning:** hatched bars show withheld source-absent values; neutral bars show gated/review diagnostics.
- **Acceptance:** SVG parses; labels are non-color-only; explicitly not detector data.
""",
    )
    replace_block(
        "chatgpt_todo/BLOCKERS.md",
        "BLK-MV4-LEGACY-001",
        """## BLK-MV4-LEGACY-001 — Legacy timing inputs and uncertainty unavailable

- **Status:** OPEN
- **Affected claims:** `CL-002`–`CL-009`
- **Demonstrated gap:** tracked legacy artifacts lack per-stave/combined/covariance values and use hard-coded data anchors, assumed uncertainty, row-index parity, and toy/fallback calibration semantics.
- **Resolution:** strict rerun using exact current calibration bytes, measured data anchors and CIs, immutable run/input/config manifests, run/block resampling, per-stave outputs, full covariance, and independent validation.
- **Do not use:** former 0.68, 0.75, 0.54, 0.56 ns and -0.127 ns² values as source-backed results.
""",
    )

    archive_path = Path(
        "chatgpt_todo/archive/2026-07-24T182820Z_"
        "AUD-LEDGER-001_MV4_REMEDIATION.md"
    )
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if not archive_path.exists():
        archive_path.write_text(
            f"""# Immutable session record — AUD-LEDGER-001 MV4 remediation

- UTC stamp: `{STAMP}`
- Initial main: `{INITIAL}`
- Validated implementation/evidence head before coordination: `{IMPLEMENTATION}`
- Scope: exact-width reconstruction and source binding for `CL-002`–`CL-009`.
- Exact ledger: 21,486 bytes; SHA-256 `{LEDGER_SHA256}`; Git blob `{LEDGER_BLOB}`.
- Validation: py_compile passed; focused pytest 7 passed; source audit VALIDATED/0; schema VALIDATED 26/26; JSON/SVG parse passed.
- Corrective states: five unsupported values BLOCKED and blank; two toy pulls GATED; analytic verdict REVIEW.
- Incident transparency: commit `aab694eca78a2546b1cb9816f46317972d79a697` initially had incorrect comma cardinality. It was detected immediately and corrected by `dccdb4930f6a6f6a0853e43c399a362e6c5bf455`; no malformed state is reported as validated.
- Scientific boundary: no ROOT, real-data timing, covariance, calibration, or detector-performance result.
- Open blocker: `BLK-MV4-LEGACY-001`.
""",
            encoding="utf-8",
        )

    Path("chatgpt_todo/HANDOFF.md").write_text(
        f"""# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `{STAMP}`
- **Task:** `AUD-LEDGER-001`
- **Unit:** source-backed exact-width remediation of legacy MV4 claims `CL-002`–`CL-009`
- **Initial remote main:** `{INITIAL}`
- **Validated implementation/evidence head before coordination:** `{IMPLEMENTATION}`
- **Destination:** direct sequential commits to `main`; no task branch, force push, or history rewrite
- **Acceptance:** ledger-remediation unit COMPLETE; legacy timing physics claims remain BLOCKED/GATED/REVIEW

## Start-of-run review

Fetched current `main`, inspected divergence and recent concurrent commits, repository permissions, open PRs, PR #868, commit status, contribution/instruction files, mandatory `chatgpt_todo/` records, the canonical ledger, cumulative schema validator, legacy MV4 report/summary/producer, current fail-closed contract, tests, and prior audit evidence. PR #868 remained closed, unmerged, and non-mergeable and was not modified.

## Confirmed defect and correction

Seven legacy rows had 37–39 columns and one exact-width row overclaimed a toy pull. The tracked source does not contain B6 0.68/0.75 ns, combined 0.54/0.56 ns, or B4-B6 covariance -0.127 ns². The source contains global toy outputs only, and its correction is analytic CFD20 plus `A+B/sqrt(amplitude)`, not ML.

The ledger now has 26/26 exact-width rows:

- `CL-002`–`CL-006`: numerical value blank, `BLOCKED`, source absence explicit;
- `CL-007`: raw pull `-1.054403396247793`, `GATED`, hard-coded 1.85 ns anchor and assumed 0.10 ns uncertainty explicit;
- `CL-008`: corrected pull `2.680528799917713`, `GATED`, hard-coded 1.50 ns anchor and assumed 0.10 ns uncertainty explicit;
- `CL-009`: analytic timing verdict `REVIEW`; former ML label superseded.

Exact current ledger: 21,486 bytes, SHA-256 `{LEDGER_SHA256}`, Git blob `{LEDGER_BLOB}`.

## Validation

```text
python -m py_compile tools/audit/audit_mv4_legacy_claim_rows.py tests/test_audit_mv4_legacy_claim_rows.py
PYTHONPATH=. python -m pytest tests/test_audit_mv4_legacy_claim_rows.py -q
7 passed in 0.03s
MV4 source audit: VALIDATED, 0 findings
claim-ledger schema: VALIDATED, 26/26 exact-width rows, 0 mismatches
JSON parsing: PASS
SVG XML parsing: PASS
```

Validation used exact reconstructed bytes for the ledger, report, summary, and current 4,441-byte contract. The one-time exact repair workflow also ran the cumulative schema validator and refused publication unless all 26 rows were exact-width. Full repository pytest, ruff, ROOT processing, Geant4/CTest, and broad GitHub Actions were not run.

## Direct-main sequence

- `aab694eca78a2546b1cb9816f46317972d79a697` — initial ledger replacement; comma-cardinality defect detected immediately, not accepted
- `8eb5728b8f7b592962405109b0dc768f5fa9ae97` — one-time exact repair transport
- `dccdb4930f6a6f6a0853e43c399a362e6c5bf455` — exact 43-column ledger repair and transport cleanup
- `57dffecdcea1c0d972afa69db39e403b3077b003` — remediated source validator
- `7328c54c01b8268c70450b894f7df67bd4b0c2ca` — focused regression suite
- `a53c8001cb24aa9eff49f5e26ad9e31914b610df` — remediation audit report
- `69ba5dd1ae03a3273cc7285a919d22707b04acd3` — exact machine-readable MV4 evidence
- `762f953ff7f003ed7e3e6b52d5e9aa98a4f04e51` — MV4 visual evidence
- `52f2bb3f8d8da5c3a80eba3cbb6edc0e2814745f` — cumulative schema audit
- `5cac04b053a68b0c9d86c473fbf60835d7a43383` — cumulative schema JSON
- `d8508342991da209b69d2fb827ea022be5e2b9c5` — cumulative schema visual
- `cd4a31c2267bc617985c1edcedfa63aa99466fcc` — removal of unused transient validator workflow

A second transient validator workflow was created while main was still advancing and produced no resulting evidence commit; it was removed. No CI success is inferred from it. The exact local focused validation and the successful exact repair/schema gate are the claimed checks.

## Blocker and next action

`BLK-MV4-LEGACY-001` remains OPEN. Resolution requires a strict rerun with current calibration bytes, measured anchors and their uncertainty, exact manifests, run/block resampling, per-stave outputs, full covariance, and independent validation. Until then, no production timing number or method is authorized from these legacy rows.

## Scientific boundary

No ROOT processing, detector timing measurement, B6 or combined-stave resolution, covariance matrix, timing calibration, confidence interval, or detector-performance result was produced. This session validates governance, source traceability, and fail-closed claim handling only.
""",
        encoding="utf-8",
    )

    log_path = Path("chatgpt_todo/SESSION_LOG.md")
    log = log_path.read_text(encoding="utf-8")
    marker = f"## {STAMP} — AUD-LEDGER-001 (MV4 remediation)"
    if marker not in log:
        entry = f"""

{marker}

- Initial main: `{INITIAL}`.
- Reviewed latest main/concurrency, open PRs, PR #868, CI/status metadata, mandatory coordination files, canonical ledger, exact legacy MV4 sources, producer, current execution contract, validators, tests, and prior evidence.
- Reconstructed `CL-002`–`CL-009` to 43 fields. Withheld five source-absent values; retained two pulls only as gated toy diagnostics; corrected the false ML label to analytic REVIEW.
- Exact ledger: 21,486 bytes; SHA-256 `{LEDGER_SHA256}`; Git blob `{LEDGER_BLOB}`; cumulative schema 26/26 exact.
- Validation: py_compile passed; focused pytest `7 passed in 0.03s`; MV4 audit VALIDATED with zero findings; schema VALIDATED with zero mismatches; JSON and SVG parsing passed.
- Incident record: malformed intermediate commit `aab694eca78a2546b1cb9816f46317972d79a697` was detected immediately and corrected by `dccdb4930f6a6f6a0853e43c399a362e6c5bf455`; no failed gate was bypassed.
- Validated implementation/evidence head before coordination: `{IMPLEMENTATION}`.
- PR #868 remained closed/unmerged/non-mergeable and untouched.
- No ROOT rerun, detector timing result, covariance, calibration, or physics closure was produced. `BLK-MV4-LEGACY-001` remains OPEN.
"""
        log_path.write_text(log.rstrip() + entry + "\n", encoding="utf-8")


def write_confirmation(commit_sha: str, push_output: str) -> None:
    marker = "## Remote-main delivery confirmation"
    note = f"""{marker}

- Validated coordination commit: `{commit_sha}`
- First push output: `{push_output.strip()}`
- Remote `main` accepted the validated coordination commit by fast-forward.
- The following cleanup commit only removes transient one-time transport files.
"""
    for name in ("chatgpt_todo/HANDOFF.md", "chatgpt_todo/SESSION_LOG.md"):
        path = Path(name)
        text = path.read_text(encoding="utf-8")
        if marker not in text:
            path.write_text(text.rstrip() + "\n\n" + note + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-sha")
    parser.add_argument("--push-output-file", type=Path)
    args = parser.parse_args()
    if args.confirm_sha:
        if args.push_output_file is None:
            parser.error("--push-output-file is required with --confirm-sha")
        write_confirmation(
            args.confirm_sha,
            args.push_output_file.read_text(encoding="utf-8"),
        )
    else:
        write_initial()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
