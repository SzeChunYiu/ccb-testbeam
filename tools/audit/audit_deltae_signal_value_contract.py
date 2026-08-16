#!/usr/bin/env python3
"""Audit the canonical DeltaE present-signal value contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

POLICY = "DELTAE_PRESENT_SIGNAL_CELLS_MUST_BE_FINITE_NUMERIC"
REQUIRED_TOKENS = (
    f'SIGNAL_VALUE_POLICY = "{POLICY}"',
    'MISSING_LAYER_POLICY = "ZERO_ONLY_WHEN_SUPPORTED_COLUMN_IS_ABSENT"',
    "class SignalValueError(ValueError):",
    "def _coerce_present_finite_signals(",
    'pd.to_numeric(out[column], errors="coerce")',
    "invalid = ~np.isfinite(values)",
    "signal_columns = (\"amp_B2\", *FILLABLE_DATA_LAYERS)",
    "mc_layer_columns(raw)",
    "_core.fill_missing_layers = fill_missing_layers",
    "_core.prepare_data_side = prepare_data_side",
    "_core.prepare_mc_side = prepare_mc_side",
    "except SignalValueError as exc:",
)


def _snapshot(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    try:
        raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path} is not strict UTF-8: {exc}") from exc
    return raw, hashlib.sha256(raw).hexdigest()


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def audit_source(source_path: Path) -> dict:
    raw, digest = _snapshot(source_path)
    text = raw.decode("utf-8")
    findings = []
    for token in REQUIRED_TOKENS:
        if token not in text:
            findings.append(
                {
                    "code": "MISSING_CONTRACT_TOKEN",
                    "token": token,
                }
            )

    malformed = pd.Series(["bad", "4.5"])
    former_malformed = pd.to_numeric(malformed, errors="coerce").fillna(0.0)
    infinity = pd.Series([np.inf])
    former_infinity = pd.to_numeric(infinity, errors="coerce").fillna(0.0)
    corrected_malformed = pd.to_numeric(malformed, errors="coerce").to_numpy(
        dtype=float,
        na_value=np.nan,
    )
    corrected_infinity = pd.to_numeric(infinity, errors="coerce").to_numpy(
        dtype=float,
        na_value=np.nan,
    )
    controls = {
        "former_malformed_cell_became_zero": bool(former_malformed.iloc[0] == 0.0),
        "former_infinity_remained_infinite": bool(np.isinf(former_infinity.iloc[0])),
        "corrected_malformed_finite_mask": np.isfinite(corrected_malformed).tolist(),
        "corrected_infinity_finite_mask": np.isfinite(corrected_infinity).tolist(),
        "absent_column_fill_authorized": True,
    }
    if not controls["former_malformed_cell_became_zero"]:
        findings.append({"code": "FORMER_MALFORMED_CONTROL_NOT_REPRODUCED"})
    if not controls["former_infinity_remained_infinite"]:
        findings.append({"code": "FORMER_INFINITY_CONTROL_NOT_REPRODUCED"})
    if controls["corrected_malformed_finite_mask"][0]:
        findings.append({"code": "CORRECTED_MALFORMED_MASK_FAILED"})
    if controls["corrected_infinity_finite_mask"][0]:
        findings.append({"code": "CORRECTED_INFINITY_MASK_FAILED"})

    return {
        "schema": "ccb-deltae-signal-value-audit/1",
        "policy": POLICY,
        "status": "VALIDATED" if not findings else "FLAWED",
        "source": {
            "path": str(source_path),
            "bytes": len(raw),
            "sha256": digest,
            "snapshot_policy": "SINGLE_READ_STRICT_UTF8",
        },
        "findings": findings,
        "finding_count": len(findings),
        "synthetic_controls": controls,
        "interpretation": (
            "Only a wholly absent supported downstream layer may be filled with zero. "
            "Every present data amp_B* or MC edep_B* cell used by the canonical analysis "
            "must coerce to a finite number before derived quantities or stopping logic."
        ),
        "scientific_boundary": (
            "Software input validation only; no A-002 amplitude convention, polarity, "
            "stopping fraction, PID, calibration, or detector-performance claim."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    if args.output is not None and args.output.resolve() == source:
        print("output must not alias source")
        return 2
    try:
        payload = audit_source(source)
    except (OSError, ValueError) as exc:
        print(f"input error: {exc}")
        return 2
    if args.output is not None:
        _atomic_json(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
