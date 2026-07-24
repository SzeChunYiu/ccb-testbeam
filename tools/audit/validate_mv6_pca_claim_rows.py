#!/usr/bin/env python3
"""Validate CL-023/CL-024 against the tracked MV6 PCA producer and summary."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import html
import io
import json
import math
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "MV6_PCA_CLAIMS_MUST_MATCH_TRACKED_SYNTHETIC_WAVEFORM_OUTPUT"
EXPECTED_FIELDS = (
    "claim_id",
    "chapter",
    "section",
    "claim_text",
    "current_value",
    "unit",
    "stat_unc",
    "syst_unc",
    "total_unc",
    "ci_low",
    "ci_high",
    "ci_level",
    "ci_method",
    "bootstrap_unit",
    "n_events",
    "n_runs",
    "n_data",
    "n_mc",
    "numerator",
    "denominator",
    "p_value",
    "effect_size",
    "baseline_value",
    "baseline_unc",
    "delta_vs_baseline",
    "delta_ci_low",
    "delta_ci_high",
    "truth_type",
    "status",
    "allowed_status_validated",
    "source_report",
    "source_script",
    "source_data",
    "source_config",
    "source_manifest",
    "figure_ids",
    "table_ids",
    "source_commit",
    "link_validated",
    "ci_status",
    "blocked_by",
    "supersedes",
    "notes",
)

CLAIM_SPECS = {
    "CL-023": {
        "claim_text": (
            "MV6 synthetic-waveform PCA cumulative explained variance at 3 components"
        ),
        "component_count": 3,
        "superseded_value": "0.89",
    },
    "CL-024": {
        "claim_text": (
            "MV6 synthetic-waveform PCA cumulative explained variance at 8 components"
        ),
        "component_count": 8,
        "superseded_value": "0.997",
    },
}

SOURCE_REPORT = "reports/mv6_representation_1782678362/REPORT.md"
SOURCE_SCRIPT = "scripts/mv6_representation_study.py"
SOURCE_DATA = (
    "reports/mv6_representation_1782678362/mv6_representation_summary.json"
)
SOURCE_COMMIT = "3c5ff5cf587c8ca9cefda20cb220ba29effd2170"
CI_STATUS = "NOT_APPLICABLE_FIXED_OUTPUT_SCIENTIFIC_UNCERTAINTY_NOT_EVALUATED"


class ValidationError(ValueError):
    """Controlled input or schema error."""


def _read_utf8(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValidationError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def _parse_ledger(text: str) -> dict[str, dict[str, str]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise ValidationError(f"invalid claim-ledger CSV: {exc}") from exc
    if not rows:
        raise ValidationError("claim ledger is empty")
    if tuple(rows[0]) != EXPECTED_FIELDS:
        raise ValidationError("claim ledger header is not the canonical 43-column schema")

    selected: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        claim_id = row[0].strip() if row else ""
        if claim_id not in CLAIM_SPECS:
            continue
        if len(row) != len(EXPECTED_FIELDS):
            raise ValidationError(
                f"{claim_id} row {row_number} has {len(row)} columns; expected 43"
            )
        if claim_id in selected:
            raise ValidationError(f"duplicate {claim_id} row")
        selected[claim_id] = dict(zip(EXPECTED_FIELDS, row, strict=True))

    missing = sorted(set(CLAIM_SPECS) - set(selected))
    if missing:
        raise ValidationError(f"missing required claims: {', '.join(missing)}")
    return selected


def _parse_summary(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid MV6 summary JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError("MV6 summary must be a JSON object")
    return payload


def _validate_summary(payload: dict[str, Any]) -> dict[str, Any]:
    values = payload.get("pca_explained_variance_ratio")
    if not isinstance(values, list) or len(values) < 8:
        raise ValidationError("MV6 summary requires at least eight PCA variance ratios")

    ratios: list[float] = []
    for index, value in enumerate(values, start=1):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(f"PCA ratio {index} is not numeric")
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0.0:
            raise ValidationError(f"PCA ratio {index} is nonfinite or negative")
        ratios.append(numeric)

    cumulative_3 = math.fsum(ratios[:3])
    cumulative_4 = math.fsum(ratios[:4])
    cumulative_8 = math.fsum(ratios[:8])
    recorded_4 = payload.get("pca_cumulative_at_4")
    recorded_8 = payload.get("pca_cumulative_at_8")
    if float(recorded_4) != cumulative_4:
        raise ValidationError("summary pca_cumulative_at_4 disagrees with component list")
    if float(recorded_8) != cumulative_8:
        raise ValidationError("summary pca_cumulative_at_8 disagrees with component list")

    n_events = payload.get("n_events_scanned")
    n_tracks = payload.get("n_tracks")
    if not isinstance(n_events, int) or n_events <= 0:
        raise ValidationError("summary n_events_scanned must be a positive integer")
    if not isinstance(n_tracks, int) or n_tracks <= 0:
        raise ValidationError("summary n_tracks must be a positive integer")

    return {
        "pca_variance_ratios": ratios,
        "cumulative_at_3": cumulative_3,
        "cumulative_at_4": cumulative_4,
        "cumulative_at_8": cumulative_8,
        "n_events_scanned": n_events,
        "n_tracks": n_tracks,
        "seed": payload.get("seed"),
    }


def _validate_producer(text: str) -> dict[str, Any]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise ValidationError(f"invalid MV6 producer Python: {exc}") from exc

    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    pca_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Name) and node.func.id == "PCA"
    ]
    gmm_calls = [
        node
        for node in calls
        if isinstance(node.func, ast.Name) and node.func.id == "GaussianMixture"
    ]
    if len(pca_calls) != 1:
        raise ValidationError("MV6 producer must contain exactly one PCA constructor")
    if len(gmm_calls) != 1:
        raise ValidationError("MV6 producer must contain exactly one GMM constructor")

    required_tokens = (
        "X = waves - PED",
        "peak = X.max(axis=1, keepdims=True)",
        "Xn = X / peak",
        "pca = PCA(n_components=min(10, NSAMP))",
        "Z = pca.fit_transform(Xn)",
        'summary["pca_explained_variance_ratio"] = evr.tolist()',
        'summary["pca_cumulative_at_4"] = float(evr[:4].sum())',
        'summary["pca_cumulative_at_8"] = float(evr[:8].sum())',
        "GaussianMixture(n_components=4, random_state=SEED, n_init=3)",
        "gmm.fit_predict(Z[:, :4])",
    )
    missing = [token for token in required_tokens if token not in text]
    if missing:
        raise ValidationError(
            "MV6 producer contract is missing: " + "; ".join(missing)
        )
    return {
        "normalization": "PEDESTAL_SUBTRACTED_PEAK_NORMALIZED",
        "pca_components_fitted": 10,
        "gmm_components": 4,
        "gmm_pcs": 4,
        "seed": 42,
    }


def _row_issues(
    claim_id: str,
    row: dict[str, str],
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    spec = CLAIM_SPECS[claim_id]
    count = int(spec["component_count"])
    expected_value = math.fsum(source["pca_variance_ratios"][:count])
    issues: list[dict[str, Any]] = []

    exact = {
        "chapter": "ML",
        "section": "6",
        "claim_text": str(spec["claim_text"]),
        "unit": "fraction",
        "n_events": str(source["n_events_scanned"]),
        "n_runs": "1",
        "n_data": "",
        "n_mc": str(source["n_tracks"]),
        "truth_type": "synthetic_waveform_mc",
        "status": "TRUTH_LEVEL_MC_ONLY",
        "allowed_status_validated": "YES",
        "source_report": SOURCE_REPORT,
        "source_script": SOURCE_SCRIPT,
        "source_data": SOURCE_DATA,
        "source_config": "",
        "source_manifest": "",
        "figure_ids": "FIG-AN-001",
        "table_ids": "",
        "source_commit": SOURCE_COMMIT,
        "link_validated": "YES",
        "ci_status": CI_STATUS,
        "blocked_by": "",
        "supersedes": str(spec["superseded_value"]),
    }
    for field, expected in exact.items():
        if row[field] != expected:
            issues.append({
                "code": "FIELD_MISMATCH",
                "claim_id": claim_id,
                "field": field,
                "expected": expected,
                "actual": row[field],
            })

    try:
        actual_value = float(row["current_value"])
    except ValueError:
        actual_value = math.nan
    if not math.isfinite(actual_value) or actual_value != expected_value:
        issues.append({
            "code": "VALUE_MISMATCH",
            "claim_id": claim_id,
            "expected": repr(expected_value),
            "actual": row["current_value"],
        })

    empty_fields = (
        "stat_unc",
        "syst_unc",
        "total_unc",
        "ci_low",
        "ci_high",
        "ci_level",
        "ci_method",
        "bootstrap_unit",
        "numerator",
        "denominator",
        "p_value",
        "effect_size",
        "baseline_value",
        "baseline_unc",
        "delta_vs_baseline",
        "delta_ci_low",
        "delta_ci_high",
    )
    for field in empty_fields:
        if row[field] != "":
            issues.append({
                "code": "UNSUPPORTED_STATISTICAL_FIELD",
                "claim_id": claim_id,
                "field": field,
                "actual": row[field],
            })

    note_tokens = (
        "fixed synthetic-waveform MC output",
        "peak-normalized",
        "not beam-data PCA",
        f"supersedes {spec['superseded_value']}",
    )
    for token in note_tokens:
        if token not in row["notes"]:
            issues.append({
                "code": "MISSING_CAVEAT",
                "claim_id": claim_id,
                "token": token,
            })
    return issues


def validate_texts(
    ledger_text: str,
    summary_text: str,
    producer_text: str,
) -> dict[str, Any]:
    rows = _parse_ledger(ledger_text)
    summary = _validate_summary(_parse_summary(summary_text))
    producer = _validate_producer(producer_text)
    issues: list[dict[str, Any]] = []
    claim_results: dict[str, Any] = {}

    for claim_id in CLAIM_SPECS:
        row_issues = _row_issues(claim_id, rows[claim_id], summary)
        issues.extend(row_issues)
        count = int(CLAIM_SPECS[claim_id]["component_count"])
        claim_results[claim_id] = {
            "component_count": count,
            "current_value": rows[claim_id]["current_value"],
            "source_value": math.fsum(summary["pca_variance_ratios"][:count]),
            "row_columns": len(EXPECTED_FIELDS),
            "issues": row_issues,
        }

    return {
        "validator": "validate_mv6_pca_claim_rows.py",
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not issues else "FLAWED",
        "source_summary": summary,
        "producer_contract": producer,
        "claims": claim_results,
        "issues": issues,
        "n_issues": len(issues),
    }


def audit(ledger: Path, summary: Path, producer: Path) -> dict[str, Any]:
    ledger_text, ledger_provenance = _read_utf8(ledger)
    summary_text, summary_provenance = _read_utf8(summary)
    producer_text, producer_provenance = _read_utf8(producer)
    result = validate_texts(ledger_text, summary_text, producer_text)
    result["inputs"] = {
        "claim_ledger": ledger_provenance,
        "mv6_summary": summary_provenance,
        "mv6_producer": producer_provenance,
    }
    return result


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_svg(path: Path, payload: dict[str, Any]) -> None:
    old_values = [0.89, 0.997]
    new_values = [
        payload["claims"]["CL-023"]["source_value"],
        payload["claims"]["CL-024"]["source_value"],
    ]
    labels = ["3 PCs", "8 PCs"]
    width, height = 900, 520
    left, top, chart_w, chart_h = 110, 100, 700, 290
    bar_w = 72
    group_gap = 250
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">MV6 PCA claim reconstruction</title>',
        '<desc id="desc">Synthetic software evidence comparing superseded PCA claims '
        'with values recomputed from the tracked MV6 summary. Not detector data.</desc>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="30" y="35" font-family="sans-serif" font-size="23" '
        'font-weight="bold">CL-023 / CL-024 source reconstruction</text>',
        '<text x="30" y="62" font-family="sans-serif" font-size="14">'
        'Synthetic software/provenance evidence — not beam data or a transfer claim</text>',
    ]
    for tick in range(0, 11, 2):
        value = tick / 10
        y = top + chart_h * (1.0 - value)
        parts.extend([
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + chart_w}" y2="{y:.1f}" '
            'stroke="#cccccc" stroke-width="1"/>',
            f'<text x="{left - 12}" y="{y + 5:.1f}" text-anchor="end" '
            f'font-family="sans-serif" font-size="12">{value:.1f}</text>',
        ])
    for index, label in enumerate(labels):
        center = left + 150 + index * group_gap
        for offset, value, name, pattern in (
            (-bar_w, old_values[index], "superseded", "url(#hatch)"),
            (10, new_values[index], "tracked MV6", "#d9d9d9"),
        ):
            x = center + offset
            bar_h = chart_h * value
            y = top + chart_h - bar_h
            parts.extend([
                f'<rect x="{x}" y="{y:.1f}" width="{bar_w}" height="{bar_h:.1f}" '
                f'fill="{pattern}" stroke="black"/>',
                f'<text x="{x + bar_w / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" '
                f'font-family="monospace" font-size="12">{value:.6f}</text>',
                f'<text x="{x + bar_w / 2:.1f}" y="{top + chart_h + 22:.1f}" '
                f'text-anchor="middle" font-family="sans-serif" font-size="11">{name}</text>',
            ])
        parts.append(
            f'<text x="{center + 5}" y="{top + chart_h + 52}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="15" font-weight="bold">{label}</text>'
        )
    parts[3:3] = [
        '<defs><pattern id="hatch" width="8" height="8" '
        'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        '<line x1="0" y1="0" x2="0" y2="8" stroke="#555" stroke-width="2"/>'
        '</pattern></defs>'
    ]
    parts.extend([
        f'<line x1="{left}" y1="{top + chart_h}" x2="{left + chart_w}" '
        f'y2="{top + chart_h}" stroke="black" stroke-width="2"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + chart_h}" '
        'stroke="black" stroke-width="2"/>',
        f'<text x="28" y="{top + chart_h / 2:.1f}" transform="rotate(-90 28 '
        f'{top + chart_h / 2:.1f})" text-anchor="middle" font-family="sans-serif" '
        'font-size="14">cumulative explained-variance fraction</text>',
        f'<text x="30" y="480" font-family="sans-serif" font-size="13">Status: '
        f'{html.escape(payload["status"])}; exact row width: 43; policy: '
        f'{html.escape(payload["policy"])}</text>',
        '</svg>',
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("mv6_summary", type=Path)
    parser.add_argument("mv6_producer", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--svg", type=Path)
    args = parser.parse_args(argv)

    try:
        result = audit(args.claim_ledger, args.mv6_summary, args.mv6_producer)
    except ValidationError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2

    if args.output:
        _write_json(args.output, result)
    if args.svg:
        _write_svg(args.svg, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
