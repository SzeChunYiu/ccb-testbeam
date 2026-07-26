#!/usr/bin/env python3
"""Audit pair-width to single-stave timing inference in PR-style artifacts."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

POLICY = (
    "PAIR_SIGMA68_DIV_SQRT2_REQUIRES_VALIDATED_IDENTICAL_INDEPENDENT_"
    "GAUSSIAN_OR_EXPLICIT_DECONVOLUTION"
)


@dataclass(frozen=True)
class Snapshot:
    path: str
    raw: bytes
    text: str
    sha256: str
    size_bytes: int


def _same_file(left: Path, right: Path) -> bool:
    try:
        if left.resolve() == right.resolve():
            return True
    except OSError:
        pass
    try:
        return left.exists() and right.exists() and os.path.samefile(left, right)
    except OSError:
        return False


def _snapshot(path: Path) -> Snapshot:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="strict")
    return Snapshot(
        path=str(path),
        raw=raw,
        text=text,
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
    )


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    except Exception:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def sigma68(values: np.ndarray) -> float:
    q16, q84 = np.quantile(values, [0.16, 0.84])
    return float((q84 - q16) / 2.0)


def _toy_controls(seed: int = 20260726, n: int = 250_000) -> list[dict[str, float | str]]:
    rng = np.random.default_rng(seed)
    controls: list[dict[str, float | str]] = []

    def record(name: str, a: np.ndarray, b: np.ndarray) -> None:
        single = sigma68(a)
        inferred = sigma68(a - b) / math.sqrt(2.0)
        controls.append(
            {
                "case": name,
                "single_a_sigma68": single,
                "pair_div_sqrt2": inferred,
                "relative_error": inferred / single - 1.0,
            }
        )

    record("iid_normal", rng.normal(0.0, 1.0, n), rng.normal(0.0, 1.0, n))
    record("iid_laplace", rng.laplace(0.0, 1.0, n), rng.laplace(0.0, 1.0, n))

    def mixture() -> np.ndarray:
        choose_tail = rng.random(n) >= 0.85
        core = rng.normal(0.0, 1.0, n)
        tail = rng.normal(0.0, 8.0, n)
        return np.where(choose_tail, tail, core)

    record("iid_heavy_tail_mixture", mixture(), mixture())
    record("unequal_normal", rng.normal(0.0, 0.6, n), rng.normal(0.0, 1.2, n))
    z1 = rng.normal(0.0, 1.0, n)
    z2 = rng.normal(0.0, 1.0, n)
    record("equal_normal_rho_0p5", z1, 0.5 * z1 + math.sqrt(0.75) * z2)
    return controls


def _contains_div_sqrt2(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
            continue
        right = node.right
        if isinstance(right, ast.Call) and isinstance(right.func, ast.Attribute):
            if right.func.attr == "sqrt" and right.args:
                arg = right.args[0]
                if isinstance(arg, ast.Constant) and arg.value == 2:
                    return True
        if isinstance(right, ast.Constant) and isinstance(right.value, (int, float)):
            if abs(float(right.value) - math.sqrt(2.0)) < 1e-3:
                return True
    return False


def audit(source_text: str, result: dict[str, Any]) -> dict[str, Any]:
    tree = ast.parse(source_text)
    source_lower = source_text.lower()
    best = result.get("sample_II", {}).get("best_sigma68", {})
    findings: list[dict[str, Any]] = []

    has_division = _contains_div_sqrt2(tree)
    has_single_claim = "single-stave" in source_lower and (
        "sqrt2" in source_lower or "sqrt(2" in source_lower or "assume equal" in source_lower
    )
    inference = result.get("sample_II", {}).get("single_stave_inference")

    def add(code: str, detail: str) -> None:
        findings.append({"code": code, "detail": detail})

    if has_division:
        add(
            "PAIR_SIGMA68_DIVIDED_BY_SQRT2",
            "The source converts pair sigma68 to a single-stave number by dividing by sqrt(2).",
        )
    if has_single_claim:
        add(
            "PAIR_ONLY_RESULT_PROMOTED_TO_SINGLE_STAVE_CLAIM",
            "The report presents a pair-only residual width as a single-stave estimate.",
        )
    if has_division and not isinstance(inference, dict):
        add(
            "SINGLE_STAVE_INFERENCE_NOT_MACHINE_READABLE",
            "The result JSON has no explicit single-stave inference object or authorization state.",
        )

    if has_division:
        text_and_json = source_lower + json.dumps(result, sort_keys=True).lower()
        covariance_tokens = ("covariance", "common_mode", "correlation", "rho")
        if not any(token in text_and_json for token in covariance_tokens):
            add(
                "NO_COVARIANCE_OR_COMMON_MODE_MODEL",
                "The pair-difference width is interpreted without a covariance/common-mode model.",
            )
        if not any(
            token in text_and_json
            for token in ("per_stave_resolution", "reference_resolution", "three_cornered_hat")
        ):
            add(
                "NO_INDIVIDUAL_STAVE_DECONVOLUTION",
                "No independent B6/B8 resolution constraint or three-detector "
                "deconvolution is recorded.",
            )
        if isinstance(best, dict):
            s68 = float(best.get("sigma68_ns", math.nan))
            rms = float(best.get("full_rms_ns", math.nan))
            tail = float(best.get("tail_frac_gt5ns", math.nan))
            if math.isfinite(s68) and math.isfinite(rms) and s68 > 0 and (
                rms / s68 > 2.0 or (math.isfinite(tail) and tail > 0.05)
            ):
                add(
                    "NON_GAUSSIAN_PAIR_WIDTH_USED_FOR_SQRT2_SCALING",
                    f"The headline pair has full_rms/sigma68={rms/s68:.3f} and tail={tail:.3f}; "
                    "sigma68 has no general quadrature deconvolution law.",
                )
            if "ci68_ns" in best and not isinstance(inference, dict):
                add(
                    "SINGLE_STAVE_UNCERTAINTY_NOT_PROPAGATED",
                    "A pair bootstrap interval exists, but no single-stave interval or "
                    "assumption uncertainty is reported.",
                )

        sample = result.get("sample_II", {})
        pulses = sample.get("pulses_by_stave", {})
        shapes = sample.get("pulse_shape", {})
        b6 = pulses.get("B6")
        b8 = pulses.get("B8")
        w6 = shapes.get("B6", {}).get("samples_above_10pct_median")
        w8 = shapes.get("B8", {}).get("samples_above_10pct_median")
        if b6 != b8 or w6 != w8:
            add(
                "EQUAL_STAVE_ASSUMPTION_UNVALIDATED",
                f"The source says 'assume equal', while recorded B6/B8 pulse counts are {b6}/{b8} "
                f"and median widths are {w6}/{w8} samples; equality of timing "
                "resolution is not tested.",
            )

    if not has_division and not has_single_claim:
        if not isinstance(inference, dict) or inference.get("authorized") is not False:
            add(
                "PAIR_ONLY_BOUNDARY_NOT_EXPLICIT",
                "A corrected pair-only result must record single_stave_inference.authorized=false.",
            )

    controls = _toy_controls()
    return {
        "policy": POLICY,
        "status": "VALIDATED" if not findings else "FLAWED",
        "n_findings": len(findings),
        "findings": findings,
        "headline_pair": best,
        "naive_single_stave_ns": (
            float(best["sigma68_ns"]) / math.sqrt(2.0)
            if isinstance(best, dict) and "sigma68_ns" in best
            else None
        ),
        "required_contract": {
            "pair_only_default": True,
            "single_stave_inference_authorized": False,
            "authorization_requires": [
                "variance-compatible estimator or validated distributional deconvolution",
                "individual-stave or external-reference constraints",
                "covariance/common-mode treatment",
                "uncertainty propagation including assumption sensitivity",
            ],
        },
        "toy_controls": controls,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    source_path = Path(args.source)
    result_path = Path(args.result)
    output_path = Path(args.output)
    if _same_file(output_path, source_path) or _same_file(output_path, result_path):
        parser.error("output must not alias an input")

    try:
        source = _snapshot(source_path)
        result_snapshot = _snapshot(result_path)
        result = json.loads(result_snapshot.text)
        if not isinstance(result, dict):
            raise ValueError("result JSON must be an object")
        payload = audit(source.text, result)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SyntaxError, ValueError) as exc:
        print(f"input error: {exc}")
        return 2

    payload["inputs"] = {
        "source": {
            "path": source.path,
            "sha256": source.sha256,
            "size_bytes": source.size_bytes,
        },
        "result": {
            "path": result_snapshot.path,
            "sha256": result_snapshot.sha256,
            "size_bytes": result_snapshot.size_bytes,
        },
    }
    _atomic_json(output_path, payload)
    print(f"{payload['status']}: {payload['n_findings']} finding(s)")
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
