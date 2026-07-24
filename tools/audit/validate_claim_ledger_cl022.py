#!/usr/bin/env python3
"""Validate the exact-width, source-backed CL-022 anomaly-rate claim."""

from __future__ import annotations

import argparse
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
POLICY = "SEPARATE_EARLY_PEAK_RATE_FROM_C12_COMPOSITION"
FIELDS = (
    "claim_id,chapter,section,claim_text,current_value,unit,stat_unc,syst_unc,"
    "total_unc,ci_low,ci_high,ci_level,ci_method,bootstrap_unit,n_events,n_runs,"
    "n_data,n_mc,numerator,denominator,p_value,effect_size,baseline_value,"
    "baseline_unc,delta_vs_baseline,delta_ci_low,delta_ci_high,truth_type,status,"
    "allowed_status_validated,source_report,source_script,source_data,source_config,"
    "source_manifest,figure_ids,table_ids,source_commit,link_validated,ci_status,"
    "blocked_by,supersedes,notes"
).split(",")
Z_95 = 1.959963984540054


class InputError(ValueError):
    """Controlled repository-input or schema failure."""


def snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def relative(provenance: dict[str, Any], root: Path) -> dict[str, Any]:
    item = dict(provenance)
    item["path"] = str(Path(item["path"]).relative_to(root))
    return item


def parse_csv(text: str, label: str) -> list[list[str]]:
    try:
        return list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise InputError(f"invalid CSV in {label}: {exc}") from exc


def one_claim(rows: list[list[str]], claim_id: str) -> list[str]:
    matches = [row for row in rows[1:] if row and row[0] == claim_id]
    if len(matches) != 1:
        raise InputError(f"expected exactly one {claim_id} row, found {len(matches)}")
    return matches[0]


def resolve(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise InputError(f"path escapes repository root: {relative_path}") from exc
    return path


def wilson_interval(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    if n <= 0 or k < 0 or k > n:
        raise InputError(f"invalid binomial count k={k}, n={n}")
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return centre - half, centre + half


def add_mismatch(
    issues: list[dict[str, Any]], field: str, expected: str, actual: str
) -> None:
    if actual != expected:
        issues.append(
            {
                "code": "LEDGER_FIELD_MISMATCH",
                "field": field,
                "expected": expected,
                "actual": actual,
            }
        )


def close(a: float, b: float, *, tolerance: float = 5e-16) -> bool:
    return math.isclose(a, b, rel_tol=0.0, abs_tol=tolerance)


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    ledger_path = root / "docs/claim_ledger.csv"
    readme_path = root / "README.md"

    ledger_text, ledger_prov = snapshot(ledger_path)
    rows = parse_csv(ledger_text, str(ledger_path))
    if not rows or rows[0] != FIELDS:
        raise InputError("claim ledger header is not the canonical 43-column schema")

    row = one_claim(rows, "CL-022")
    issues: list[dict[str, Any]] = []
    if len(row) != len(FIELDS):
        issues.append(
            {
                "code": "LEDGER_ROW_WIDTH_MISMATCH",
                "claim_id": "CL-022",
                "expected": len(FIELDS),
                "actual": len(row),
                "field_interpretation": "WITHHELD",
            }
        )
        claim: dict[str, str] = {}
    else:
        claim = dict(zip(FIELDS, row))

    expected_paths = {
        "source_report": "reports/mv6_representation_1782678362/REPORT.md",
        "source_script": "scripts/mv6_representation_study.py",
        "source_data": (
            "reports/mv6_representation_1782678362/"
            "mv6_representation_summary.json"
        ),
    }
    if claim:
        expected_fields = {
            "chapter": "Anomaly",
            "section": "9",
            "claim_text": "Early-peak anomaly fraction in truth-labelled MC",
            "current_value": "0.003232254011764034",
            "unit": "fraction",
            "ci_low": "0.002877452112691542",
            "ci_high": "0.003630645177388446",
            "ci_level": "0.95",
            "ci_method": "Wilson_score",
            "n_events": "220000",
            "n_runs": "1",
            "n_mc": "87555",
            "numerator": "283",
            "denominator": "87555",
            "truth_type": "mc_truth_only",
            "status": "TRUTH_LEVEL_MC_ONLY",
            "allowed_status_validated": "YES",
            **expected_paths,
            "figure_ids": "FIG-AN-001",
            "source_commit": "3c5ff5cf587c8ca9cefda20cb220ba29effd2170",
            "link_validated": "YES",
            "ci_status": "CI_AVAILABLE_SOURCE_COUNTS_WILSON",
            "blocked_by": "AUD-ANOM-001",
        }
        for field, expected in expected_fields.items():
            add_mismatch(issues, f"CL-022.{field}", expected, claim[field])

        required_notes = (
            "total early-peak morphology rate, not a C12-specific rate",
            "283/87555",
            "low_area=0",
            "156/283",
            "156/7302",
            "not identified as C12",
            "matched data/MC closure",
        )
        for phrase in required_notes:
            if phrase not in claim["notes"]:
                issues.append(
                    {
                        "code": "CL022_NOTE_SCOPE_MISSING",
                        "phrase": phrase,
                    }
                )

    source_provenance: dict[str, dict[str, Any]] = {}
    source_text: dict[str, str] = {}
    for field, relative_path in expected_paths.items():
        path = resolve(root, relative_path)
        if not path.exists():
            issues.append({"code": "TRACKED_SOURCE_MISSING", "path": relative_path})
            continue
        if field in {"source_report", "source_data"}:
            text, provenance = snapshot(path)
            source_text[field] = text
            source_provenance[field] = relative(provenance, root)
        else:
            source_provenance[field] = {
                "path": relative_path,
                "validator_scope": "PATH_EXISTS_ONLY",
                "expected_git_blob": "f965823518b22908f3e8974f280bff5c970368d0",
                "source_commit": "3c5ff5cf587c8ca9cefda20cb220ba29effd2170",
            }

    summary: dict[str, Any] = {}
    if "source_data" in source_text:
        try:
            summary = json.loads(source_text["source_data"])
        except json.JSONDecodeError as exc:
            raise InputError(f"invalid MV6 summary JSON: {exc}") from exc

    metrics: dict[str, dict[str, Any]] = {}
    if summary:
        try:
            n_tracks = int(summary["n_tracks"])
            n_events = int(summary["n_events_scanned"])
            morphology = summary["morphology_counts"]
            early_peak = int(morphology.get("early_peak", 0))
            low_area = int(morphology.get("low_area", 0))
            morphology_total = sum(int(value) for value in morphology.values())
            species_counts = summary["species_counts"]
            n_c12 = int(species_counts["C12"])
            composition = summary["early_peak_species_composition"]
            c12_early = int(composition["C12"])
            composition_total = sum(int(value) for value in composition.values())
            recorded_fraction = float(summary["anomaly_frac_total"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InputError(f"invalid MV6 summary structure: {exc}") from exc

        expected_values = {
            "n_tracks": (n_tracks, 87555),
            "n_events_scanned": (n_events, 220000),
            "early_peak": (early_peak, 283),
            "low_area": (low_area, 0),
            "morphology_total": (morphology_total, n_tracks),
            "C12_tracks": (n_c12, 7302),
            "C12_early_peak": (c12_early, 156),
            "composition_total": (composition_total, early_peak),
        }
        for field, (actual, expected) in expected_values.items():
            if actual != expected:
                issues.append(
                    {
                        "code": "SUMMARY_COUNT_MISMATCH",
                        "field": field,
                        "expected": expected,
                        "actual": actual,
                    }
                )

        total_fraction = (early_peak + low_area) / n_tracks
        if not close(recorded_fraction, total_fraction):
            issues.append(
                {
                    "code": "SUMMARY_FRACTION_MISMATCH",
                    "expected": total_fraction,
                    "actual": recorded_fraction,
                }
            )

        total_ci = wilson_interval(early_peak + low_area, n_tracks)
        composition_ci = wilson_interval(c12_early, early_peak)
        c12_rate_ci = wilson_interval(c12_early, n_c12)
        metrics = {
            "total_early_peak_rate": {
                "numerator": early_peak + low_area,
                "denominator": n_tracks,
                "estimate": total_fraction,
                "ci_low": total_ci[0],
                "ci_high": total_ci[1],
                "ci_level": 0.95,
                "ci_method": "Wilson_score",
                "interpretation": "all truth-labelled MC tracks",
            },
            "c12_share_of_early_peak": {
                "numerator": c12_early,
                "denominator": early_peak,
                "estimate": c12_early / early_peak,
                "ci_low": composition_ci[0],
                "ci_high": composition_ci[1],
                "ci_level": 0.95,
                "ci_method": "Wilson_score",
                "interpretation": "species composition inside selected MC class",
            },
            "early_peak_rate_within_c12": {
                "numerator": c12_early,
                "denominator": n_c12,
                "estimate": c12_early / n_c12,
                "ci_low": c12_rate_ci[0],
                "ci_high": c12_rate_ci[1],
                "ci_level": 0.95,
                "ci_method": "Wilson_score",
                "interpretation": "C12-labelled MC tracks only",
            },
        }

        if claim:
            for field, expected in {
                "current_value": total_fraction,
                "ci_low": total_ci[0],
                "ci_high": total_ci[1],
            }.items():
                try:
                    actual = float(claim[field])
                except ValueError:
                    issues.append(
                        {
                            "code": "LEDGER_NUMERIC_FIELD_INVALID",
                            "field": f"CL-022.{field}",
                            "actual": claim[field],
                        }
                    )
                else:
                    if not close(actual, expected):
                        issues.append(
                            {
                                "code": "LEDGER_NUMERIC_VALUE_MISMATCH",
                                "field": f"CL-022.{field}",
                                "expected": expected,
                                "actual": actual,
                            }
                        )

    if "source_report" in source_text:
        report_text = source_text["source_report"]
        for phrase in (
            "**Tracks:** 87555",
            "Total anomaly (early_peak + low_area) fraction in MC: **0.32%**",
            "'early_peak': 283",
            '"C12": 156',
            "C12 (55% of the early-peak class)",
        ):
            if phrase not in report_text:
                issues.append({"code": "REPORT_EVIDENCE_MISSING", "phrase": phrase})

    readme_text, readme_prov = snapshot(readme_path)
    required_readme = (
        "| Pile-up tolerance | **Withheld pending S-STAT-003** | "
        "CL-010 — BLOCKED |",
        "| Early-peak morphology rate in truth-labelled MC | **283 / 87,555 "
        "tracks (0.323%; Wilson 95% CI 0.288–0.363%)**; C12 labels are "
        "**156 / 283 (55.1%)** within that selected MC class | CL-022 — "
        "TRUTH_LEVEL_MC_ONLY (real-data identity unvalidated) |",
    )
    for phrase in required_readme:
        if readme_text.count(phrase) != 1:
            issues.append(
                {
                    "code": "README_REQUIRED_CLAIM_MISSING_OR_DUPLICATED",
                    "phrase": phrase,
                    "count": readme_text.count(phrase),
                }
            )
    stale_readme = (
        "R_max ≈ 3.05 MHz",
        "| C12-like anomaly in truth-labelled MC | **283 / 87,555 tracks "
        "(0.32%)**; ~55% C12",
    )
    for phrase in stale_readme:
        if phrase in readme_text:
            issues.append({"code": "README_STALE_CLAIM_PRESENT", "phrase": phrase})

    return {
        "validator": Path(__file__).name,
        "version": VERSION,
        "policy": POLICY,
        "claim_id": "CL-022",
        "status": "VALIDATED" if not issues else "FLAWED",
        "scientific_acceptance": "TRUTH_LEVEL_MC_ONLY",
        "metrics": metrics,
        "inputs": {
            "ledger": relative(ledger_prov, root),
            "readme": relative(readme_prov, root),
            **source_provenance,
        },
        "issues": issues,
        "n_issues": len(issues),
        "limitations": [
            "The three binomial quantities have different denominators and meanings.",
            "Truth-labelled MC does not identify the related real-data anomaly.",
            "Matched data/MC morphology closure and independent data species "
            "evidence remain required.",
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_svg(path: Path, payload: dict[str, Any]) -> None:
    metrics = payload["metrics"]
    rows = (
        (
            "Total early-peak rate",
            metrics["total_early_peak_rate"],
            0.0,
            0.005,
            "all MC tracks",
        ),
        (
            "C12 share of early-peak",
            metrics["c12_share_of_early_peak"],
            0.4,
            0.7,
            "selected early-peak class",
        ),
        (
            "Early-peak rate within C12",
            metrics["early_peak_rate_within_c12"],
            0.0,
            0.04,
            "C12-labelled MC tracks",
        ),
    )
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="500" '
        'viewBox="0 0 960 500" role="img" aria-labelledby="title desc">',
        '<title id="title">CL-022 distinct-binomial-quantity audit</title>',
        '<desc id="desc">Three separately scaled Wilson intervals distinguish the '
        'overall early-peak rate, C12 composition of the selected class, and the '
        'early-peak rate among C12-labelled tracks.</desc>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="24" y="34" font-family="sans-serif" font-size="21" '
        'font-weight="bold">CL-022: do not conflate rate, composition, and '
        'within-species rate</text>',
        '<text x="24" y="58" font-family="sans-serif" font-size="13">'
        'Repository/source-count validation; truth-labelled MC only, not '
        'detector-data identification.</text>',
    ]
    x0, x1 = 330.0, 900.0
    for index, (label, item, minimum, maximum, denominator_label) in enumerate(rows):
        y = 125.0 + 125.0 * index
        scale = (x1 - x0) / (maximum - minimum)
        point = x0 + (item["estimate"] - minimum) * scale
        low = x0 + (item["ci_low"] - minimum) * scale
        high = x0 + (item["ci_high"] - minimum) * scale
        parts.extend(
            [
                f'<text x="24" y="{y - 18:.1f}" font-family="sans-serif" '
                f'font-size="15" font-weight="bold">{html.escape(label)}</text>',
                f'<text x="24" y="{y + 4:.1f}" font-family="sans-serif" '
                f'font-size="12">denominator: {html.escape(denominator_label)}; '
                f'n={item["numerator"]}/{item["denominator"]}</text>',
                f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" '
                'stroke="black" stroke-width="1"/>',
                f'<line x1="{low:.2f}" y1="{y}" x2="{high:.2f}" y2="{y}" '
                'stroke="black" stroke-width="6"/>',
                f'<line x1="{low:.2f}" y1="{y - 10}" x2="{low:.2f}" y2="{y + 10}" '
                'stroke="black" stroke-width="2"/>',
                f'<line x1="{high:.2f}" y1="{y - 10}" x2="{high:.2f}" y2="{y + 10}" '
                'stroke="black" stroke-width="2"/>',
                f'<circle cx="{point:.2f}" cy="{y}" r="7" fill="white" '
                'stroke="black" stroke-width="3"/>',
                f'<text x="{x0}" y="{y + 28:.1f}" font-family="sans-serif" '
                f'font-size="11">{minimum * 100:.3g}%</text>',
                f'<text x="{x1}" y="{y + 28:.1f}" text-anchor="end" '
                f'font-family="sans-serif" font-size="11">{maximum * 100:.3g}%</text>',
                f'<text x="{x0}" y="{y - 15:.1f}" font-family="monospace" '
                f'font-size="12">{item["estimate"] * 100:.4f}% '
                f'[{item["ci_low"] * 100:.4f}, {item["ci_high"] * 100:.4f}]%</text>',
            ]
        )
    parts.extend(
        [
            '<text x="24" y="475" font-family="sans-serif" font-size="12">'
            f'Status: {html.escape(payload["status"])}; policy: '
            f'{html.escape(payload["policy"])}</text>',
            '</svg>',
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--svg", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = audit(args.root)
    except InputError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        write_json(args.output, payload)
    if args.svg:
        write_svg(args.svg, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
