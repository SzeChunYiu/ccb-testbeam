#!/usr/bin/env python3
"""Audit MV3 Pearson chi-square support and normalization semantics."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

POLICY = "PEARSON_CHI2_MUST_REJECT_OUT_OF_SUPPORT_DATA_AND_NONUNIT_PROFILES"
STAVES = ("B2", "B4", "B6", "B8")


class AuditInputError(RuntimeError):
    """Controlled malformed-input or publication-contract failure."""


def _snapshot(path: Path) -> tuple[bytes, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AuditInputError(f"SOURCE_READ_FAILED:{exc}") from exc
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditInputError(
            f"INVALID_UTF8:byte={exc.start}:reason={exc.reason}"
        ) from exc
    return raw, text


def _load_chi2(source: str, source_path: Path) -> tuple[Callable[..., Any], type[Exception]]:
    namespace: dict[str, Any] = {
        "__file__": str(source_path),
        "__name__": "mv3_chi2_audit_target",
    }
    try:
        exec(compile(source, str(source_path), "exec"), namespace)
    except Exception as exc:
        raise AuditInputError(f"SOURCE_IMPORT_FAILED:{type(exc).__name__}:{exc}") from exc
    chi2 = namespace.get("_chi2")
    contract_error = namespace.get("ContractError")
    if not callable(chi2):
        raise AuditInputError("MISSING_CHI2_FUNCTION")
    if not isinstance(contract_error, type) or not issubclass(contract_error, Exception):
        raise AuditInputError("MISSING_CONTRACT_ERROR")
    return chi2, contract_error


def _call(chi2: Callable[..., Any], mc: dict[str, float], data: dict[str, float]) -> dict[str, Any]:
    try:
        result = chi2(mc, data)
    except Exception as exc:
        return {
            "outcome": "RAISED",
            "exception_type": type(exc).__name__,
            "message": str(exc),
        }
    try:
        chi2_value, ndf, per_ndf = result
        return {
            "outcome": "RETURNED",
            "chi2": float(chi2_value),
            "ndf": int(ndf),
            "chi2_per_ndf": float(per_ndf),
        }
    except Exception as exc:
        return {
            "outcome": "MALFORMED_RETURN",
            "exception_type": type(exc).__name__,
            "message": str(exc),
        }


def _rejected_with(control: dict[str, Any], token: str) -> bool:
    return control.get("outcome") == "RAISED" and token in control.get("message", "")


def audit(source_path: Path) -> dict[str, Any]:
    raw, source = _snapshot(source_path)
    chi2, _ = _load_chi2(source, source_path)
    controls = {
        "valid_four_bin": _call(
            chi2,
            dict(B2=0.50, B4=0.30, B6=0.15, B8=0.05),
            dict(B2=50, B4=30, B6=15, B8=5),
        ),
        "zero_expected_zero_observed": _call(
            chi2,
            dict(B2=0.50, B4=0.50, B6=0.0, B8=0.0),
            dict(B2=50, B4=50, B6=0, B8=0),
        ),
        "positive_observed_zero_expected": _call(
            chi2,
            dict(B2=0.50, B4=0.50, B6=0.0, B8=0.0),
            dict(B2=45, B4=45, B6=10, B8=0),
        ),
        "nonunit_model_profile": _call(
            chi2,
            dict(B2=0.45, B4=0.45, B6=0.05, B8=0.0),
            dict(B2=45, B4=45, B6=10, B8=0),
        ),
    }
    findings: list[dict[str, str]] = []
    valid = controls["valid_four_bin"]
    if not (
        valid.get("outcome") == "RETURNED"
        and valid.get("chi2") == 0.0
        and valid.get("ndf") == 3
    ):
        findings.append({
            "code": "VALID_PROFILE_NOT_ACCEPTED",
            "detail": "A normalized four-bin exact-match profile must return chi2=0 and ndf=3.",
        })
    zero_zero = controls["zero_expected_zero_observed"]
    if not (
        zero_zero.get("outcome") == "RETURNED"
        and zero_zero.get("chi2") == 0.0
        and zero_zero.get("ndf") == 1
    ):
        findings.append({
            "code": "ZERO_SUPPORT_EMPTY_BIN_NOT_HANDLED",
            "detail": (
                "A category with expected=observed=0 may be omitted while retaining "
                "supported-bin ndf."
            ),
        })
    outside = controls["positive_observed_zero_expected"]
    if not _rejected_with(outside, "CHI2_OBSERVED_OUTSIDE_MODEL_SUPPORT"):
        findings.append({
            "code": "OBSERVED_MASS_OUTSIDE_MODEL_SUPPORT_NOT_REJECTED",
            "detail": (
                "The B6 control has observed=10 and expected=0. Pearson chi-square is not finite "
                "under that model and must fail closed instead of dropping the bin."
            ),
        })
    nonunit = controls["nonunit_model_profile"]
    if not _rejected_with(nonunit, "CHI2_PROFILE_NOT_NORMALIZED"):
        findings.append({
            "code": "NONUNIT_MODEL_PROFILE_NOT_REJECTED",
            "detail": "The model fractions sum to 0.95 and must not be used as probabilities.",
        })
    return {
        "schema": "ccb-mv3-chi2-support-audit/1",
        "policy": POLICY,
        "status": "VALIDATED" if not findings else "FLAWED",
        "source": {
            "path": str(source_path),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "controls": controls,
        "finding_count": len(findings),
        "findings": findings,
        "scientific_boundary": (
            "Synthetic software/statistical validation only; no production ROOT or beam-data "
            "profile, covariance, closure, calibration, PID, or detector result is established."
        ),
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.source.resolve(strict=False) == args.output.resolve(strict=False):
        print("INPUT_ERROR:OUTPUT_ALIASES_SOURCE")
        return 2
    try:
        payload = audit(args.source)
        _atomic_json(args.output, payload)
    except AuditInputError as exc:
        payload = {
            "schema": "ccb-mv3-chi2-support-audit/1",
            "policy": POLICY,
            "status": "INPUT_ERROR",
            "finding_count": 1,
            "findings": [{"code": "INPUT_ERROR", "detail": str(exc)}],
        }
        _atomic_json(args.output, payload)
        print(f"INPUT_ERROR:{exc}")
        return 2
    print(f"{payload['status']}: findings={payload['finding_count']}")
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
