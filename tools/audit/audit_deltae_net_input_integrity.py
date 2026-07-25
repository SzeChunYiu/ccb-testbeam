#!/usr/bin/env python3
"""Audit whether the ΔE-E bridge rejects non-finite net amplitudes before aggregation."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence

import pandas as pd

POLICY = "DELTAE_NET_AMPLITUDE_ROWS_MUST_BE_FINITE_NUMERIC_BEFORE_AGGREGATION"
VERSION = "1.0.0"


class AuditError(RuntimeError):
    """Raised when the audit cannot execute its controlled synthetic checks."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_source(path: Path) -> tuple[bytes, str]:
    resolved = path.expanduser().resolve(strict=True)
    data = resolved.read_bytes()
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditError(f"source is not valid UTF-8: {exc}") from exc
    return data, text


def _load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"ccb_deltae_net_input_audit_{os.getpid()}", path
    )
    if spec is None or spec.loader is None:
        raise AuditError(f"cannot import source module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "build_event_table", None)):
        raise AuditError("source module does not define callable build_event_table")
    return module


def _fixture(amplitude: object) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "run": [1, 1],
            "evt": [10, 10],
            "eventno": [100, 100],
            "stave": ["B2", "B4"],
            "median_amp_adc": [amplitude, 300.0],
        }
    )


def _run_case(module: ModuleType, label: str, amplitude: object) -> dict[str, Any]:
    try:
        wide, result = module.build_event_table(
            _fixture(amplitude),
            source_file_id="synthetic_nonfinite_control",
            threshold_adc=200.0,
            amplitude_column="median_amp_adc",
            amplitude_convention="net",
        )
    except Exception as exc:
        return {
            "label": label,
            "rejected": True,
            "exception_type": type(exc).__name__,
            "exception": str(exc),
        }

    b2_values = []
    if "amp_B2" in wide.columns:
        b2_values = [str(value) for value in wide["amp_B2"].tolist()]
    return {
        "label": label,
        "rejected": False,
        "rows": int(len(wide)),
        "amp_B2": b2_values,
        "stopping_distribution": result.get("stopping_distribution"),
    }


def audit_source(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve(strict=True)
    data, text = _read_source(resolved)
    module = _load_module(resolved)

    finite = _run_case(module, "finite_control", 250.0)
    nan_case = _run_case(module, "nan_net_amplitude", float("nan"))
    inf_case = _run_case(module, "positive_infinity_net_amplitude", float("inf"))

    issues: list[dict[str, str]] = []
    if finite.get("rejected"):
        issues.append(
            {
                "code": "FINITE_CONTROL_REJECTED",
                "message": "The bridge rejected the valid finite control input.",
            }
        )
    if not nan_case.get("rejected"):
        issues.append(
            {
                "code": "NONFINITE_NET_ROW_NOT_REJECTED",
                "message": "A NaN net-amplitude row was accepted before event aggregation.",
            }
        )
        if nan_case.get("amp_B2") == ["0.0"]:
            issues.append(
                {
                    "code": "NONFINITE_NET_ROW_BECAME_ZERO",
                    "message": (
                        "The NaN B2 row disappeared during pivoting and was indistinguishable "
                        "from an absent stave after zero filling."
                    ),
                }
            )
    if not inf_case.get("rejected"):
        issues.append(
            {
                "code": "INFINITE_NET_ROW_NOT_REJECTED",
                "message": "An infinite net-amplitude row was accepted before aggregation.",
            }
        )

    has_direct_net_assignment = "df[signal_column] = df[ampcol]" in text
    has_finite_message = "finite numeric" in text and "net" in text.lower()
    return {
        "status": "VALIDATED" if not issues else "FLAWED",
        "policy": POLICY,
        "validator_version": VERSION,
        "source": {
            "path": str(resolved),
            "bytes": len(data),
            "sha256": _sha256(data),
        },
        "source_indicators": {
            "direct_net_assignment_present": has_direct_net_assignment,
            "net_finite_validation_language_present": has_finite_message,
        },
        "synthetic_controls": {
            "finite": finite,
            "nan": nan_case,
            "positive_infinity": inf_case,
        },
        "issues": issues,
        "issue_count": len(issues),
        "scientific_boundary": (
            "Synthetic software-integrity validation only; no detector data, calibration, "
            "stopping profile, or particle-identification result is established."
        ),
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=resolved.parent, delete=False
    ) as handle:
        tmp = Path(handle.name)
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(tmp, resolved)
    finally:
        if tmp.exists():
            tmp.unlink()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = audit_source(args.source)
        if args.out is not None:
            if args.out.expanduser().resolve() == args.source.expanduser().resolve():
                raise AuditError("output path must not alias the audited source")
            _atomic_json(args.out, payload)
    except Exception as exc:
        error = {
            "status": "ERROR",
            "policy": POLICY,
            "validator_version": VERSION,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        print(json.dumps(error, sort_keys=True))
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
