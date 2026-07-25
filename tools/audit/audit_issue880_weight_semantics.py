#!/usr/bin/env python3
"""Audit issue #880 weight handling and directional bias semantics.

The audit is fail-closed for unreadable inputs and flags two distinct classes of
scientific-reporting defect:

* invalid event weights are silently converted to unit weights or cause a
  fallback to an unweighted estimator;
* a weighted-minus-unweighted change is labelled as the bias of the legacy
  unweighted estimate without stating the denominator and direction.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "ISSUE880_WEIGHTS_MUST_FAIL_CLOSED_AND_BIAS_DIRECTION_MUST_BE_EXPLICIT"

AMBIGUOUS_RELATIVE_FIELD = "first_B_layer_mean_rel_bias_pct"
AMBIGUOUS_ABSOLUTE_FIELD = "deuteron_fraction_abs_bias_pp"
RECOMMENDED_FIELDS = (
    "weighted_change_relative_to_unweighted_pct",
    "legacy_unweighted_overstatement_relative_to_weighted_pct",
    "legacy_unweighted_minus_weighted_pp",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_utf8(path: Path) -> tuple[bytes, str]:
    data = path.read_bytes()
    return data, data.decode("utf-8")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(
        "wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary, path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise


def _function_source(tree: ast.AST, text: str, name: str) -> str:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    return ""


def _finite_number(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _issue880_values(payload: dict[str, Any]) -> dict[str, float]:
    section = payload.get("issue_880_weight_audit")
    if not isinstance(section, dict):
        raise ValueError("issue_880_weight_audit must be an object")
    mean = section.get("first_B_layer_mean_MeV")
    fraction = section.get("deuteron_fraction_entering_B")
    if not isinstance(mean, dict) or not isinstance(fraction, dict):
        raise ValueError("issue #880 weighted/unweighted result objects are missing")
    return {
        "mean_unweighted": _finite_number(mean.get("unweighted"), "mean unweighted"),
        "mean_weighted": _finite_number(mean.get("weighted"), "mean weighted"),
        "fraction_unweighted": _finite_number(
            fraction.get("unweighted"), "deuteron fraction unweighted"
        ),
        "fraction_weighted": _finite_number(
            fraction.get("weighted"), "deuteron fraction weighted"
        ),
    }


def _recalculate(values: dict[str, float]) -> dict[str, float]:
    mean_u = values["mean_unweighted"]
    mean_w = values["mean_weighted"]
    frac_u = values["fraction_unweighted"]
    frac_w = values["fraction_weighted"]
    if mean_u == 0.0 or mean_w == 0.0 or frac_w == 0.0:
        raise ValueError("directional relative changes require nonzero denominators")
    return {
        "weighted_change_relative_to_unweighted_pct": 100.0 * (mean_w - mean_u) / mean_u,
        "legacy_unweighted_overstatement_relative_to_weighted_pct": (
            100.0 * (mean_u - mean_w) / mean_w
        ),
        "weighted_minus_unweighted_pp": 100.0 * (frac_w - frac_u),
        "legacy_unweighted_minus_weighted_pp": 100.0 * (frac_u - frac_w),
        "legacy_deuteron_overstatement_relative_to_weighted_pct": (
            100.0 * (frac_u - frac_w) / frac_w
        ),
    }


def _finding(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}


def audit(study_path: Path, result_path: Path) -> dict[str, Any]:
    try:
        study_bytes, study_text = _read_utf8(study_path)
        result_bytes, result_text = _read_utf8(result_path)
        tree = ast.parse(study_text, filename=str(study_path))
        payload = json.loads(result_text)
        if not isinstance(payload, dict):
            raise ValueError("result JSON must contain an object")
        values = _issue880_values(payload)
        recalculated = _recalculate(values)
    except Exception as exc:
        return {
            "validator": "audit_issue880_weight_semantics",
            "validator_version": VERSION,
            "policy": POLICY,
            "status": "INPUT_ERROR",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "study_path": str(study_path),
            "result_path": str(result_path),
        }

    findings: list[dict[str, Any]] = []

    if "np.where(np.isfinite(w_evt), w_evt, 1.0)" in study_text:
        findings.append(
            _finding(
                "NONFINITE_WEIGHT_COERCED_TO_UNIT",
                "Nonfinite event weights are silently replaced by 1.0.",
            )
        )

    for name in ("wmean", "wmedian", "wfrac", "wcorr"):
        source = _function_source(tree, study_text, name)
        if source and (
            "float(x.mean())" in source
            or "float(np.mean(" in source
            or "float(np.median(" in source
            or "float(np.corrcoef(" in source
        ):
            findings.append(
                _finding(
                    "INVALID_WEIGHT_FALLS_BACK_TO_UNWEIGHTED",
                    f"{name} falls back to an unweighted estimator when weights are invalid.",
                    function=name,
                )
            )

    section = payload["issue_880_weight_audit"]
    bias = section.get("bias_summary")
    note = section.get("note")
    if not isinstance(bias, dict):
        findings.append(_finding("BIAS_SUMMARY_MISSING", "bias_summary is missing or invalid."))
        bias = {}
    if not isinstance(note, str):
        findings.append(_finding("BIAS_NOTE_MISSING", "issue #880 note is missing or invalid."))
        note = ""

    if AMBIGUOUS_RELATIVE_FIELD in bias:
        reported = _finite_number(bias[AMBIGUOUS_RELATIVE_FIELD], AMBIGUOUS_RELATIVE_FIELD)
        expected = recalculated["weighted_change_relative_to_unweighted_pct"]
        if not math.isclose(reported, expected, rel_tol=1e-12, abs_tol=1e-12):
            findings.append(
                _finding(
                    "REPORTED_RELATIVE_CHANGE_MISMATCH",
                    "The retained relative-change value does not reproduce from the two means.",
                    reported=reported,
                    expected=expected,
                )
            )
        findings.append(
            _finding(
                "RELATIVE_BIAS_DIRECTION_AMBIGUOUS",
                (
                    "A weighted-minus-unweighted change divided by the unweighted value "
                    "is labelled as legacy bias."
                ),
                field=AMBIGUOUS_RELATIVE_FIELD,
                reported=reported,
                denominator="unweighted",
                direction="weighted_minus_unweighted",
            )
        )

    if AMBIGUOUS_ABSOLUTE_FIELD in bias:
        reported = _finite_number(bias[AMBIGUOUS_ABSOLUTE_FIELD], AMBIGUOUS_ABSOLUTE_FIELD)
        expected = recalculated["weighted_minus_unweighted_pp"]
        if not math.isclose(reported, expected, rel_tol=1e-12, abs_tol=1e-12):
            findings.append(
                _finding(
                    "REPORTED_ABSOLUTE_CHANGE_MISMATCH",
                    (
                        "The retained percentage-point value does not reproduce from "
                        "the two fractions."
                    ),
                    reported=reported,
                    expected=expected,
                )
            )
        findings.append(
            _finding(
                "ABSOLUTE_BIAS_DIRECTION_AMBIGUOUS",
                (
                    "The retained percentage-point field is weighted minus unweighted "
                    "while prose describes legacy bias."
                ),
                field=AMBIGUOUS_ABSOLUTE_FIELD,
                reported=reported,
                direction="weighted_minus_unweighted",
            )
        )

    if "legacy UNWEIGHTED summaries were off" in note and (
        AMBIGUOUS_RELATIVE_FIELD in bias or AMBIGUOUS_ABSOLUTE_FIELD in bias
    ):
        findings.append(
            _finding(
                "PROSE_DIRECTION_CONFLICT",
                (
                    "The note attributes the signed fields to legacy error without "
                    "naming the direction and denominator."
                ),
            )
        )

    for field in RECOMMENDED_FIELDS:
        if field not in bias:
            findings.append(
                _finding(
                    "DIRECTIONAL_FIELD_MISSING",
                    "A required direction-explicit comparison field is absent.",
                    field=field,
                )
            )

    required_provenance = {
        "root_sha256": "exact ROOT input SHA-256",
        "producer_commit": "producer commit SHA",
        "generation_command": "exact generation command",
        "weight_validation_policy": "weight validation policy/version",
    }
    for field, meaning in required_provenance.items():
        if not payload.get(field):
            findings.append(
                _finding(
                    "PROVENANCE_FIELD_MISSING",
                    f"The result omits {meaning}.",
                    field=field,
                )
            )

    return {
        "validator": "audit_issue880_weight_semantics",
        "validator_version": VERSION,
        "policy": POLICY,
        "status": "FLAWED" if findings else "VALIDATED",
        "study_path": str(study_path),
        "study_size_bytes": len(study_bytes),
        "study_sha256": _sha256(study_bytes),
        "result_path": str(result_path),
        "result_size_bytes": len(result_bytes),
        "result_sha256": _sha256(result_bytes),
        "observed": values,
        "independent_recalculation": recalculated,
        "findings": findings,
        "finding_count": len(findings),
        "scientific_boundary": (
            "This audit checks software and reporting semantics. It does not regenerate "
            "the ROOT study, validate the physical event-weight definition, or establish "
            "data/MC closure."
        ),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    result = audit(args.study, args.result)
    if args.out is not None:
        if args.out.resolve() in {args.study.resolve(), args.result.resolve()}:
            result = {
                **result,
                "status": "INPUT_OUTPUT_ALIAS",
                "output_path": str(args.out),
            }
        else:
            _atomic_json(args.out, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] == "VALIDATED":
        raise SystemExit(0)
    if result["status"] == "FLAWED":
        raise SystemExit(1)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
