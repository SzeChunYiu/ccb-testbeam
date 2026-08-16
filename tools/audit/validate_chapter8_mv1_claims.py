#!/usr/bin/env python3
"""Fail-closed source binding for Chapter 8 MV1 PID claims."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

POLICY = "CHAPTER8_MV1_MUST_MATCH_TRACKED_TRUTH_MC_SOURCE_AND_LIMITATIONS"
VERSION = "1.0.0"
EXPECTED_FIELDS = 43
EXPECTED_SOURCE_COMMIT = "3539ae3aad222284bd7be100802a2651c0e064de"
EXPECTED_SCRIPT = "scripts/mv1_mv2_truth_pid_energy.py"
EXPECTED_SUMMARY = "reports/mv1_mv2_truth_pid_energy_1782220258/mv1_mv2_truth_summary.json"

EXPECTED = {
    "n_tracks": 400369,
    "n_proton": 150130,
    "n_deuteron": 146842,
    "n_pd": 296972,
    "logreg_auc": 0.9628868703282414,
    "logreg_purity_at_90eff": 0.9488978818667125,
    "hgb_auc": 0.9859658513538254,
    "hgb_purity_at_90eff": 0.9644090769970706,
    "cut_edep_l0_thr_MeV": 13.287866011130776,
    "cut_purity": 0.8909863556160177,
    "cut_efficiency": 0.900961577750235,
}


@dataclass(frozen=True)
class Snapshot:
    path: str
    data: bytes
    text: str

    @property
    def size_bytes(self) -> int:
        return len(self.data)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def read_utf8(path: Path) -> Snapshot:
    data = path.read_bytes()
    text = data.decode("utf-8")
    return Snapshot(str(path), data, text)


def issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"code": code, "message": message}
    if details:
        row["details"] = details
    return row


def parse_ledger(snapshot: Snapshot, issues: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    rows = list(csv.reader(io.StringIO(snapshot.text)))
    if not rows:
        issues.append(issue("LEDGER_EMPTY", "claim ledger is empty"))
        return {}
    header = rows[0]
    if len(header) != EXPECTED_FIELDS:
        issues.append(
            issue(
                "LEDGER_HEADER_WIDTH",
                f"ledger header has {len(header)} fields; expected {EXPECTED_FIELDS}",
            )
        )
        return {}
    parsed: dict[str, dict[str, str]] = {}
    for line_no, row in enumerate(rows[1:], start=2):
        if not row:
            continue
        claim_id = row[0]
        if claim_id not in {"CL-017", "CL-018"}:
            continue
        if len(row) != EXPECTED_FIELDS:
            issues.append(
                issue(
                    "LEDGER_ROW_WIDTH",
                    f"{claim_id} has {len(row)} fields; expected {EXPECTED_FIELDS}",
                    line=line_no,
                )
            )
            continue
        if claim_id in parsed:
            issues.append(issue("LEDGER_DUPLICATE", f"duplicate {claim_id} row"))
            continue
        parsed[claim_id] = dict(zip(header, row, strict=True))
    for claim_id in ("CL-017", "CL-018"):
        if claim_id not in parsed:
            issues.append(issue("LEDGER_ROW_MISSING", f"missing {claim_id}"))
    return parsed


def same_float(actual: Any, expected: float) -> bool:
    try:
        return float(actual) == expected
    except (TypeError, ValueError):
        return False


def validate_summary(summary: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    for key in ("n_tracks", "n_proton", "n_deuteron"):
        if summary.get(key) != EXPECTED[key]:
            issues.append(
                issue(
                    "SUMMARY_COUNT_MISMATCH",
                    f"{key}={summary.get(key)!r}; expected {EXPECTED[key]!r}",
                )
            )
    n_pd = summary.get("n_proton", 0) + summary.get("n_deuteron", 0)
    if n_pd != EXPECTED["n_pd"]:
        issues.append(
            issue(
                "SUMMARY_PD_COUNT_MISMATCH",
                f"n_proton+n_deuteron={n_pd}; expected {EXPECTED['n_pd']}",
            )
        )
    mv1 = summary.get("MV1_pid")
    if not isinstance(mv1, dict):
        issues.append(issue("SUMMARY_MV1_MISSING", "MV1_pid object is missing"))
        return
    for key in (
        "logreg_auc",
        "logreg_purity_at_90eff",
        "hgb_auc",
        "hgb_purity_at_90eff",
        "cut_edep_l0_thr_MeV",
        "cut_purity",
        "cut_efficiency",
    ):
        if not same_float(mv1.get(key), EXPECTED[key]):
            issues.append(
                issue(
                    "SUMMARY_METRIC_MISMATCH",
                    f"MV1_pid.{key}={mv1.get(key)!r}; expected {EXPECTED[key]!r}",
                )
            )


def validate_script(text: str, issues: list[dict[str, Any]]) -> None:
    required = {
        "MASK_CONTRACT": "mask=isp|isd",
        "ROW_PARITY_SPLIT": "tr=idx%2==0; te=~tr",
        "DEFAULT_HGB": "HistGradientBoostingClassifier().fit",
        "FOUR_FEATURES": "rec[\"edep_tot\"][mask],rec[\"stop_layer\"][mask]",
    }
    compact = "".join(text.split())
    for code, token in required.items():
        if "".join(token.split()) not in compact:
            issues.append(issue(code, f"source script is missing required token: {token}"))
    if 'rec = {"event_id"' in text or 'rec={"event_id"' in compact:
        issues.append(
            issue(
                "SOURCE_CONTRACT_CHANGED",
                "source unexpectedly records event_id; update the audit contract",
            )
        )
    if "HistGradientBoostingClassifier(random_state=" in compact:
        issues.append(
            issue(
                "SOURCE_CONTRACT_CHANGED",
                "source now sets HGB random_state; update the audit contract",
            )
        )


def validate_ledger(rows: dict[str, dict[str, str]], issues: list[dict[str, Any]]) -> None:
    expected_values = {
        "CL-017": EXPECTED["hgb_auc"],
        "CL-018": EXPECTED["hgb_purity_at_90eff"],
    }
    for claim_id, expected_value in expected_values.items():
        row = rows.get(claim_id)
        if not row:
            continue
        checks = {
            "current_value": str(expected_value),
            "n_mc": str(EXPECTED["n_pd"]),
            "truth_type": "mc_truth_only",
            "status": "GATED",
            "allowed_status_validated": "NO",
            "source_script": EXPECTED_SCRIPT,
            "source_data": EXPECTED_SUMMARY,
            "source_commit": EXPECTED_SOURCE_COMMIT,
            "blocked_by": "BLK-MV1-001",
        }
        for field, expected in checks.items():
            if row.get(field) != expected:
                issues.append(
                    issue(
                        "LEDGER_FIELD_MISMATCH",
                        f"{claim_id}.{field}={row.get(field)!r}; expected {expected!r}",
                    )
                )
        if row.get("stat_unc") or row.get("syst_unc") or row.get("total_unc"):
            issues.append(
                issue(
                    "LEDGER_UNSUPPORTED_UNCERTAINTY",
                    f"{claim_id} publishes an unsupported uncertainty component",
                )
            )
        if row.get("ci_low") or row.get("ci_high") or row.get("ci_level"):
            issues.append(
                issue(
                    "LEDGER_UNSUPPORTED_CI",
                    f"{claim_id} publishes an unsupported confidence interval",
                )
            )


def validate_chapter(text: str, issues: list[dict[str, Any]]) -> None:
    required = [
        "truth-labelled Monte Carlo",
        "296,972",
        "400,369",
        "150,130",
        "146,842",
        str(EXPECTED["logreg_auc"]),
        str(EXPECTED["logreg_purity_at_90eff"]),
        str(EXPECTED["hgb_auc"]),
        str(EXPECTED["hgb_purity_at_90eff"]),
        str(EXPECTED["cut_edep_l0_thr_MeV"]),
        str(EXPECTED["cut_purity"]),
        str(EXPECTED["cut_efficiency"]),
        "row-index parity",
        "No beam-data PID performance metric is established",
        "BLK-MV1-001",
        "GATED",
        "the producer does not report a traditional-cut AUC",
        "mean_ekin_MeV",
        "unit convention",
        "event-group-disjoint",
        "confidence intervals",
    ]
    for token in required:
        if token not in text:
            issues.append(issue("CHAPTER_REQUIRED_TEXT_MISSING", f"missing required text: {token}"))

    forbidden = [
        "ACCEPTED by nature-reviewer",
        "AUC = 0.891",
        "leave-one-run-out",
        "LORO",
        "Monte Carlo truth ceiling",
        "maximum achievable separation",
        "irreducible confusion",
        "irreducible information loss",
        "data-only logistic regression",
        "combined strategy achieves",
        "245.6 plus or minus 73.7",
        "total systematic uncertainty on the deuteron fraction",
        "Sample I (coincidence trigger",
        "Sample II (single-B trigger",
    ]
    lowered = text.lower()
    for token in forbidden:
        if token.lower() in lowered:
            issues.append(issue("CHAPTER_STALE_OR_UNSUPPORTED_TEXT", f"forbidden text: {token}"))


def atomic_write_json(path: Path, payload: dict[str, Any], protected: set[Path]) -> None:
    resolved = path.resolve()
    if resolved in protected:
        raise ValueError("output JSON path aliases an input path")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{resolved.name}.", dir=resolved.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, resolved)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def run(
    chapter_path: Path,
    ledger_path: Path,
    script_path: Path,
    summary_path: Path,
    output_json: Path | None,
) -> tuple[int, dict[str, Any]]:
    paths = [chapter_path, ledger_path, script_path, summary_path]
    protected = {path.resolve() for path in paths}
    if output_json is not None and output_json.resolve() in protected:
        payload = {
            "policy": POLICY,
            "validator_version": VERSION,
            "status": "INPUT_ERROR",
            "issues": [issue("OUTPUT_ALIAS_INPUT", "output JSON path aliases an input path")],
        }
        return 2, payload

    try:
        chapter = read_utf8(chapter_path)
        ledger = read_utf8(ledger_path)
        script = read_utf8(script_path)
        summary_snapshot = read_utf8(summary_path)
        summary = json.loads(summary_snapshot.text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        payload = {
            "policy": POLICY,
            "validator_version": VERSION,
            "status": "INPUT_ERROR",
            "issues": [issue("INPUT_ERROR", str(exc))],
        }
        if output_json is not None:
            atomic_write_json(output_json, payload, protected)
        return 2, payload

    issues: list[dict[str, Any]] = []
    rows = parse_ledger(ledger, issues)
    validate_summary(summary, issues)
    validate_script(script.text, issues)
    validate_ledger(rows, issues)
    validate_chapter(chapter.text, issues)

    payload = {
        "policy": POLICY,
        "validator_version": VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "issues": issues,
        "inputs": {
            "chapter": {
                "path": chapter.path,
                "size_bytes": chapter.size_bytes,
                "sha256": chapter.sha256,
            },
            "ledger": {
                "path": ledger.path,
                "size_bytes": ledger.size_bytes,
                "sha256": ledger.sha256,
            },
            "script": {
                "path": script.path,
                "size_bytes": script.size_bytes,
                "sha256": script.sha256,
            },
            "summary": {
                "path": summary_snapshot.path,
                "size_bytes": summary_snapshot.size_bytes,
                "sha256": summary_snapshot.sha256,
            },
        },
        "source_contract": EXPECTED,
        "interpretation": (
            "Fixed truth-labelled MC point estimates only; no beam-data PID performance, "
            "performance ceiling, uncertainty, or production authorization."
        ),
    }
    if output_json is not None:
        atomic_write_json(output_json, payload, protected)
    return (0 if not issues else 1), payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    status, payload = run(
        args.chapter,
        args.ledger,
        args.script,
        args.summary,
        args.output_json,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
