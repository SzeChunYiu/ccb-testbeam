#!/usr/bin/env python3
"""Validate source-backed governance for the legacy MV1 PID claim rows."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "LEGACY_MV1_PID_OUTPUTS_REQUIRE_GROUP_DISJOINT_RERUN_AND_UNCERTAINTY"
EXPECTED_COLUMNS = 43
CLAIM_IDS = ("CL-017", "CL-018")
SOURCE_COMMIT = "3539ae3aad222284bd7be100802a2651c0e064de"
SOURCE_SCRIPT = "scripts/mv1_mv2_truth_pid_energy.py"
SOURCE_DATA = "reports/mv1_mv2_truth_pid_energy_1782220258/mv1_mv2_truth_summary.json"
BLOCKER = "BLK-MV1-001"
AUC = 0.9859658513538254
PURITY = 0.9644090769970706
N_TRACKS = 400369
N_PROTON = 150130
N_DEUTERON = 146842
N_BINARY = N_PROTON + N_DEUTERON


class Mv1ClaimError(ValueError):
    """Controlled input or schema error."""


def _snapshot(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise Mv1ClaimError(f"cannot read {path}: {exc}") from exc
    return raw, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def _decode(raw: bytes, path: Path) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Mv1ClaimError(f"{path} is not valid UTF-8") from exc


def _load_ledger(text: str) -> tuple[list[str], dict[str, list[str]]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise Mv1ClaimError(f"invalid claim-ledger CSV: {exc}") from exc
    if not rows:
        raise Mv1ClaimError("claim ledger is empty")
    header = rows[0]
    selected: dict[str, list[str]] = {}
    for row in rows[1:]:
        if row and row[0] in CLAIM_IDS:
            if row[0] in selected:
                raise Mv1ClaimError(f"duplicate claim row {row[0]}")
            selected[row[0]] = row
    missing = [claim_id for claim_id in CLAIM_IDS if claim_id not in selected]
    if missing:
        raise Mv1ClaimError(f"missing required claim rows: {', '.join(missing)}")
    return header, selected


def _load_json(text: str, path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise Mv1ClaimError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise Mv1ClaimError(f"{path} must contain a JSON object")
    return payload


def _legacy_contract(source: str) -> dict[str, bool]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise Mv1ClaimError(f"legacy producer is not valid Python: {exc}") from exc

    compact = "".join(source.split())
    parity_split = "idx%2==0" in compact
    complement_test = "te=~tr" in compact
    event_id_recorded = False
    hgb_has_random_state = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [key.value for key in node.keys if isinstance(key, ast.Constant)]
            if "pdg" in keys and "edep_l0" in keys and "event_id" in keys:
                event_id_recorded = True
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else ""
            if name == "HistGradientBoostingClassifier":
                hgb_has_random_state = any(
                    keyword.arg == "random_state" for keyword in node.keywords
                )
    return {
        "row_index_parity_split": parity_split and complement_test,
        "event_id_recorded": event_id_recorded,
        "hgb_random_state_explicit": hgb_has_random_state,
    }


def _expect(
    issues: list[dict[str, Any]],
    condition: bool,
    code: str,
    detail: str,
    claim_id: str | None = None,
) -> None:
    if not condition:
        issue: dict[str, Any] = {"code": code, "detail": detail}
        if claim_id is not None:
            issue["claim_id"] = claim_id
        issues.append(issue)


def validate(
    ledger_path: Path,
    summary_path: Path,
    producer_path: Path,
) -> dict[str, Any]:
    ledger_raw, ledger_prov = _snapshot(ledger_path)
    summary_raw, summary_prov = _snapshot(summary_path)
    producer_raw, producer_prov = _snapshot(producer_path)
    ledger_text = _decode(ledger_raw, ledger_path)
    summary = _load_json(_decode(summary_raw, summary_path), summary_path)
    producer_text = _decode(producer_raw, producer_path)

    header, rows = _load_ledger(ledger_text)
    contract = _legacy_contract(producer_text)
    issues: list[dict[str, Any]] = []

    _expect(
        issues,
        len(header) == EXPECTED_COLUMNS,
        "HEADER_WIDTH",
        "header must have 43 fields",
    )
    _expect(
        issues,
        contract["row_index_parity_split"],
        "LEGACY_SPLIT_NOT_DETECTED",
        "source must retain the audited row-index parity split",
    )
    _expect(
        issues,
        not contract["event_id_recorded"],
        "EVENT_GROUP_KEY_PRESENT",
        "legacy source unexpectedly records event_id; reassess the audit",
    )
    _expect(
        issues,
        not contract["hgb_random_state_explicit"],
        "RANDOM_STATE_PRESENT",
        "legacy HGB unexpectedly has random_state; reassess the audit",
    )

    mv1 = summary.get("MV1_pid", {})
    _expect(
        issues,
        summary.get("n_tracks") == N_TRACKS,
        "N_TRACKS",
        "source n_tracks changed",
    )
    _expect(
        issues,
        summary.get("n_proton") == N_PROTON,
        "N_PROTON",
        "source proton count changed",
    )
    _expect(
        issues,
        summary.get("n_deuteron") == N_DEUTERON,
        "N_DEUTERON",
        "source deuteron count changed",
    )
    _expect(issues, mv1.get("hgb_auc") == AUC, "AUC_SOURCE", "source HGB AUC changed")
    _expect(
        issues,
        mv1.get("hgb_purity_at_90eff") == PURITY,
        "PURITY_SOURCE",
        "source HGB purity changed",
    )

    index = {name: i for i, name in enumerate(header)}
    expected = {
        "CL-017": {
            "current_value": repr(AUC),
            "claim_text": "Legacy truth-MC HGB p/d ROC AUC (row-index split)",
        },
        "CL-018": {
            "current_value": repr(PURITY),
            "claim_text": (
                "Legacy truth-MC HGB p/d purity at nominal 90% efficiency "
                "(row-index split)"
            ),
        },
    }
    required_note_fragments = (
        "fixed legacy output",
        "296972 proton/deuteron tracks",
        "row-index parity",
        "event-group leakage risk",
        "no uncertainty",
        "group-disjoint",
        "no beam-data pid performance",
    )

    for claim_id, row in rows.items():
        _expect(
            issues,
            len(row) == EXPECTED_COLUMNS,
            "ROW_WIDTH",
            f"row has {len(row)} columns rather than 43",
            claim_id,
        )
        if len(row) != EXPECTED_COLUMNS:
            continue
        values = {name: row[pos] for name, pos in index.items()}
        _expect(
            issues,
            values["claim_text"] == expected[claim_id]["claim_text"],
            "CLAIM_TEXT",
            "claim text must label the legacy row-index split",
            claim_id,
        )
        _expect(
            issues,
            values["current_value"] == expected[claim_id]["current_value"],
            "VALUE",
            "claim value must match the exact fixed source output",
            claim_id,
        )
        for field in (
            "stat_unc",
            "syst_unc",
            "total_unc",
            "ci_low",
            "ci_high",
            "p_value",
        ):
            _expect(
                issues,
                values[field] == "",
                "UNSUPPORTED_QUANTITATIVE_FIELD",
                f"{field} must remain empty",
                claim_id,
            )
        _expect(
            issues,
            values["n_mc"] == str(N_BINARY),
            "N_MC",
            "n_mc must be binary tracks",
            claim_id,
        )
        _expect(
            issues,
            values["truth_type"] == "mc_truth_only",
            "TRUTH_TYPE",
            "truth type mismatch",
            claim_id,
        )
        _expect(
            issues,
            values["status"] == "GATED",
            "STATUS",
            "legacy output must be GATED",
            claim_id,
        )
        _expect(
            issues,
            values["allowed_status_validated"] == "NO",
            "ALLOWED",
            "claim must not be authorized",
            claim_id,
        )
        _expect(
            issues,
            values["source_report"] == "",
            "SOURCE_REPORT",
            "no tracked report exists",
            claim_id,
        )
        _expect(
            issues,
            values["source_script"] == SOURCE_SCRIPT,
            "SOURCE_SCRIPT",
            "source script mismatch",
            claim_id,
        )
        _expect(
            issues,
            values["source_data"] == SOURCE_DATA,
            "SOURCE_DATA",
            "source data mismatch",
            claim_id,
        )
        _expect(
            issues,
            values["source_commit"] == SOURCE_COMMIT,
            "SOURCE_COMMIT",
            "source commit mismatch",
            claim_id,
        )
        _expect(
            issues,
            values["link_validated"] == "YES",
            "LINK",
            "source links must be validated",
            claim_id,
        )
        _expect(
            issues,
            values["ci_status"] == "NOT_EVALUATED_LEGACY_ROW_INDEX_SPLIT",
            "CI_STATUS",
            "CI state must identify the legacy split",
            claim_id,
        )
        _expect(
            issues,
            values["blocked_by"] == BLOCKER,
            "BLOCKER",
            "blocker mismatch",
            claim_id,
        )
        note = values["notes"].lower()
        for fragment in required_note_fragments:
            _expect(
                issues,
                fragment in note,
                "NOTE_CAVEAT",
                f"notes must include '{fragment}'",
                claim_id,
            )

    return {
        "validator": "validate_mv1_legacy_claim_rows.py",
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not issues else "FLAWED",
        "legacy_source_contract": contract,
        "source_values": {
            "n_tracks": N_TRACKS,
            "n_proton": N_PROTON,
            "n_deuteron": N_DEUTERON,
            "n_binary_pid": N_BINARY,
            "hgb_auc": AUC,
            "hgb_purity_at_90eff": PURITY,
        },
        "claims": list(CLAIM_IDS),
        "inputs": {
            "claim_ledger": ledger_prov,
            "summary": summary_prov,
            "producer": producer_prov,
            "producer_git_blob": "4f3632e59ede59bcf27e053265908ddca77b4386",
            "producer_source_commit": SOURCE_COMMIT,
        },
        "issues": issues,
        "n_issues": len(issues),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("summary", type=Path)
    parser.add_argument("producer", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate(args.claim_ledger, args.summary, args.producer)
    except Mv1ClaimError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
