#!/usr/bin/env python3
"""Audit residual-histogram coverage in the real-data CFD timing study."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "REAL_DATA_CFD_RESIDUAL_PLOTS_MUST_COVER_THE_REPORTED_DISTRIBUTION"
DEFAULT_PLOT_RANGE_NS = (-10.0, 10.0)
PLOTTED_METHODS = ("t_cfd10", "t_cfd20")
REQUIRED_TAGS = ("sample_II", "task_runs")


class AuditInputError(RuntimeError):
    """Controlled input or publication failure."""


def _read_text_snapshot(path: Path, label: str) -> tuple[bytes, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AuditInputError(f"cannot read {label}: {exc}") from exc
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditInputError(f"{label} is not strict UTF-8: {exc}") from exc
    return raw, text


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


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except Exception:
        try:
            temp.unlink(missing_ok=True)
        finally:
            raise
    return {
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "publication": "SAME_DIRECTORY_TEMP_FLUSH_FSYNC_OS_REPLACE",
    }


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (TypeError, ValueError):
        return None


def _name_is_v(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "v"


def _uses_centered_residual(node: ast.AST) -> bool:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
        return _name_is_v(node.left)
    if isinstance(node, ast.Name):
        return node.id in {"centered", "centered_v", "residual_deviation"}
    return False


def inspect_histogram_contract(source_text: str) -> dict[str, Any]:
    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        raise AuditInputError(f"source is not valid Python: {exc}") from exc

    histograms: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "hist":
            continue
        if not node.args:
            continue
        plot_range = None
        for keyword in node.keywords:
            if keyword.arg == "range":
                plot_range = _literal(keyword.value)
        if plot_range is None:
            continue
        first_arg = node.args[0]
        histograms.append(
            {
                "line": node.lineno,
                "range": list(plot_range) if isinstance(plot_range, tuple) else plot_range,
                "raw_residual_argument": _name_is_v(first_arg),
                "centered_residual_argument": _uses_centered_residual(first_arg),
            }
        )

    fixed_raw = [
        item
        for item in histograms
        if item["range"] == list(DEFAULT_PLOT_RANGE_NS)
        and item["raw_residual_argument"]
    ]
    centered = any(item["centered_residual_argument"] for item in histograms)
    return {
        "histograms": histograms,
        "fixed_raw_residual_histograms": fixed_raw,
        "residuals_centered_before_plotting": centered,
        "dynamic_or_centered_contract": not fixed_raw,
    }


def _method_record(payload: dict[str, Any], tag: str, method: str) -> dict[str, Any]:
    section = payload.get(tag)
    if not isinstance(section, dict):
        raise AuditInputError(f"result JSON missing object {tag!r}")
    evaluation = section.get("evaluation")
    if not isinstance(evaluation, list):
        raise AuditInputError(f"result JSON missing {tag}.evaluation list")
    matches = [item for item in evaluation if item.get("method") == method]
    if len(matches) != 1:
        raise AuditInputError(
            f"expected exactly one {tag}/{method} record, found {len(matches)}"
        )
    return matches[0]


def coverage_bound(record: dict[str, Any], plot_low: float, plot_high: float) -> dict[str, Any]:
    try:
        median = float(record["median_ns"])
        sigma68 = float(record["sigma68_ns"])
        count = int(record["n"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuditInputError(f"invalid residual summary record: {exc}") from exc
    if not all(map(lambda value: value == value, (median, sigma68))):
        raise AuditInputError("median_ns and sigma68_ns must be finite")
    if sigma68 < 0 or count <= 0:
        raise AuditInputError("sigma68_ns must be nonnegative and n must be positive")

    full_central_width = 2.0 * sigma68
    q16_lower_bound = median - full_central_width
    q84_upper_bound = median + full_central_width
    direction = None
    guaranteed_excluded_fraction = 0.0
    if q16_lower_bound > plot_high:
        direction = "ABOVE_PLOT_RANGE"
        guaranteed_excluded_fraction = 0.84
    elif q84_upper_bound < plot_low:
        direction = "BELOW_PLOT_RANGE"
        guaranteed_excluded_fraction = 0.84
    elif median < plot_low or median > plot_high:
        direction = "MEDIAN_OUTSIDE_PLOT_RANGE"
        guaranteed_excluded_fraction = 0.50

    return {
        "n": count,
        "median_ns": median,
        "sigma68_ns": sigma68,
        "q16_lower_bound_ns": q16_lower_bound,
        "q84_upper_bound_ns": q84_upper_bound,
        "plot_range_ns": [plot_low, plot_high],
        "exclusion_direction": direction,
        "guaranteed_excluded_fraction": guaranteed_excluded_fraction,
        "central_interval_guaranteed_outside": guaranteed_excluded_fraction >= 0.84,
    }


def audit_contract(
    source: Path,
    result: Path,
    *,
    source_ref: str | None = None,
    source_blob: str | None = None,
    result_ref: str | None = None,
    result_blob: str | None = None,
    source_scope: str = "LOCAL_SOURCE_FILE",
    result_scope: str = "LOCAL_RESULT_FILE",
) -> dict[str, Any]:
    source_raw, source_text = _read_text_snapshot(source, "source")
    result_raw, result_text = _read_text_snapshot(result, "result JSON")
    try:
        result_payload = json.loads(result_text)
    except json.JSONDecodeError as exc:
        raise AuditInputError(f"result JSON is invalid: {exc}") from exc

    plot_contract = inspect_histogram_contract(source_text)
    plot_low, plot_high = DEFAULT_PLOT_RANGE_NS
    coverage: dict[str, dict[str, Any]] = {}
    for tag in REQUIRED_TAGS:
        coverage[tag] = {}
        for method in PLOTTED_METHODS:
            record = _method_record(result_payload, tag, method)
            coverage[tag][method] = coverage_bound(record, plot_low, plot_high)

    findings: list[dict[str, Any]] = []
    fixed_raw = plot_contract["fixed_raw_residual_histograms"]
    if fixed_raw:
        for item in fixed_raw:
            findings.append(
                {
                    "code": "RAW_RESIDUAL_HISTOGRAM_USES_FIXED_MINUS10_TO10_RANGE",
                    "line": item["line"],
                    "detail": (
                        "The histogram consumes uncentered residuals but fixes the visible "
                        "window to [-10, 10] ns."
                    ),
                }
            )
        for tag, methods in coverage.items():
            for method, item in methods.items():
                if item["central_interval_guaranteed_outside"]:
                    findings.append(
                        {
                            "code": "CENTRAL_RESIDUAL_MASS_GUARANTEED_OUTSIDE_PLOT",
                            "tag": tag,
                            "method": method,
                            "detail": (
                                f"At least {item['guaranteed_excluded_fraction']:.0%} of "
                                "the distribution is guaranteed outside the plotted window "
                                "from the reported median and sigma68 alone."
                            ),
                        }
                    )
                elif item["guaranteed_excluded_fraction"] >= 0.50:
                    findings.append(
                        {
                            "code": "RESIDUAL_MEDIAN_OUTSIDE_PLOT",
                            "tag": tag,
                            "method": method,
                            "detail": "At least half of the distribution lies outside the plot.",
                        }
                    )
        findings.append(
            {
                "code": "PLOT_LABEL_AND_VISIBLE_HISTOGRAM_USE_DIFFERENT_SUPPORT",
                "detail": (
                    "The label reports sigma68 from the full residual vector while the "
                    "histogram silently discards values outside [-10, 10] ns."
                ),
            }
        )

    return {
        "schema": "ccb-real-data-cfd-residual-visualization-audit/1",
        "version": VERSION,
        "policy": POLICY,
        "status": "FLAWED" if findings else "VALIDATED",
        "finding_count": len(findings),
        "findings": findings,
        "source": {
            "path": str(source),
            "scope": source_scope,
            "bytes": len(source_raw),
            "sha256": hashlib.sha256(source_raw).hexdigest(),
            "repository_ref": source_ref,
            "git_blob": source_blob,
            "snapshot_method": "SINGLE_READ_STRICT_UTF8_EXACT_BYTES",
        },
        "result": {
            "path": str(result),
            "scope": result_scope,
            "bytes": len(result_raw),
            "sha256": hashlib.sha256(result_raw).hexdigest(),
            "repository_ref": result_ref,
            "git_blob": result_blob,
            "snapshot_method": "SINGLE_READ_STRICT_UTF8_EXACT_BYTES",
        },
        "plot_contract": plot_contract,
        "reported_distribution_coverage_bounds": coverage,
        "required_remediation": [
            "Center each residual vector on its documented location estimator before plotting, "
            "or use a data-driven range that covers the full displayed distribution.",
            "Record underflow, overflow, displayed count, total count, and the exact centering "
            "or range policy in plot metadata.",
            "Regenerate both residual PNGs from collision-safe composite event keys and immutable "
            "ROOT inputs before using them as timing evidence.",
        ],
        "scientific_boundary": (
            "This audit tests whether the residual plots visually cover the distributions used "
            "for their labels. It does not validate event identity, channel mapping, waveform "
            "calibration, the CFD estimator, timing resolution, or CL-002."
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-ref")
    parser.add_argument("--source-blob")
    parser.add_argument("--result-ref")
    parser.add_argument("--result-blob")
    parser.add_argument("--source-scope", default="LOCAL_SOURCE_FILE")
    parser.add_argument("--result-scope", default="LOCAL_RESULT_FILE")
    parser.add_argument("--repository")
    parser.add_argument("--initial-main")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--pr-head")
    parser.add_argument("--pr-state")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    inputs = [args.source, args.result]
    if args.output and any(_same_file(path, args.output) for path in inputs):
        print("INPUT_ERROR: output aliases an input", file=os.sys.stderr)
        return 2
    try:
        payload = audit_contract(
            args.source,
            args.result,
            source_ref=args.source_ref,
            source_blob=args.source_blob,
            result_ref=args.result_ref,
            result_blob=args.result_blob,
            source_scope=args.source_scope,
            result_scope=args.result_scope,
        )
        payload["repository_context"] = {
            "repository": args.repository,
            "initial_main": args.initial_main,
            "pull_request": args.pr_number,
            "pull_request_head": args.pr_head,
            "pull_request_state": args.pr_state,
        }
        if args.output:
            payload["output_publication"] = _atomic_write_json(args.output, payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["status"] == "VALIDATED" else 1
    except AuditInputError as exc:
        print(f"INPUT_ERROR: {exc}", file=os.sys.stderr)
        return 2
    except OSError as exc:
        print(f"OUTPUT_ERROR: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
