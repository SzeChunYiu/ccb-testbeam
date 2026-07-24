#!/usr/bin/env python3
"""Validate Chapter 9 against the tracked MV6 producer and summary."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "CHAPTER9_MUST_MATCH_TRACKED_MV6_PRODUCER_AND_SUMMARY"
Z_95 = 1.959963984540054

CHAPTER_PATH = Path("docs/academic_chapters/09_anomaly_id.md")
SUMMARY_PATH = Path(
    "reports/mv6_representation_1782678362/mv6_representation_summary.json"
)
PRODUCER_PATH = Path("scripts/mv6_representation_study.py")
LEDGER_PATH = Path("docs/claim_ledger.csv")

FIELDS = (
    "claim_id,chapter,section,claim_text,current_value,unit,stat_unc,syst_unc,"
    "total_unc,ci_low,ci_high,ci_level,ci_method,bootstrap_unit,n_events,n_runs,"
    "n_data,n_mc,numerator,denominator,p_value,effect_size,baseline_value,"
    "baseline_unc,delta_vs_baseline,delta_ci_low,delta_ci_high,truth_type,status,"
    "allowed_status_validated,source_report,source_script,source_data,source_config,"
    "source_manifest,figure_ids,table_ids,source_commit,link_validated,ci_status,"
    "blocked_by,supersedes,notes"
).split(",")


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
    item["path"] = str(Path(item["path"]).resolve().relative_to(root.resolve()))
    return item


def parse_json(text: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON in {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise InputError(f"expected JSON object in {label}")
    return value


def parse_ledger(text: str) -> dict[str, dict[str, str]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise InputError(f"invalid claim-ledger CSV: {exc}") from exc
    if not rows or rows[0] != FIELDS:
        raise InputError("claim ledger header is not the canonical 43-column schema")
    claims: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        if not row:
            continue
        if len(row) != len(FIELDS):
            continue
        claim = dict(zip(FIELDS, row))
        claims[claim["claim_id"]] = claim
    return claims


def wilson_interval(k: int, n: int) -> tuple[float, float]:
    if n <= 0 or k < 0 or k > n:
        raise InputError(f"invalid binomial count k={k}, n={n}")
    p = k / n
    denom = 1.0 + Z_95 * Z_95 / n
    centre = (p + Z_95 * Z_95 / (2.0 * n)) / denom
    half = (
        Z_95
        * math.sqrt(p * (1.0 - p) / n + Z_95 * Z_95 / (4.0 * n * n))
        / denom
    )
    return centre - half, centre + half


def close(actual: float, expected: float, *, tolerance: float = 5e-15) -> bool:
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance)


def issue(issues: list[dict[str, Any]], code: str, **details: Any) -> None:
    issues.append({"code": code, **details})


def require_text(
    issues: list[dict[str, Any]], text: str, phrase: str, *, code: str
) -> None:
    normalized_text = " ".join(text.split())
    normalized_phrase = " ".join(phrase.split())
    if normalized_phrase.lower() not in normalized_text.lower():
        issue(issues, code, phrase=phrase)


def forbid_pattern(
    issues: list[dict[str, Any]], text: str, pattern: str, *, code: str
) -> None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if match:
        issue(issues, code, match=match.group(0), pattern=pattern)


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    chapter_text, chapter_prov = snapshot(root / CHAPTER_PATH)
    summary_text, summary_prov = snapshot(root / SUMMARY_PATH)
    producer_text, producer_prov = snapshot(root / PRODUCER_PATH)
    ledger_text, ledger_prov = snapshot(root / LEDGER_PATH)

    summary = parse_json(summary_text, str(SUMMARY_PATH))
    claims = parse_ledger(ledger_text)
    issues: list[dict[str, Any]] = []

    try:
        n_events = int(summary["n_events_scanned"])
        n_tracks = int(summary["n_tracks"])
        morphology = summary["morphology_counts"]
        species_counts = summary["species_counts"]
        composition = summary["early_peak_species_composition"]
        evr4 = float(summary["pca_cumulative_at_4"])
        evr8 = float(summary["pca_cumulative_at_8"])
        clusters = summary["gmm_clusters"]
        early_peak = int(morphology["early_peak"])
        low_area = int(morphology.get("low_area", 0))
        c12_total = int(species_counts["C12"])
        c12_early = int(composition["C12"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InputError(f"invalid MV6 summary structure: {exc}") from exc

    expected_scalars = {
        "n_events_scanned": (n_events, 220000),
        "n_tracks": (n_tracks, 87555),
        "early_peak": (early_peak, 283),
        "low_area": (low_area, 0),
        "C12_tracks": (c12_total, 7302),
        "C12_early_peak": (c12_early, 156),
    }
    for field, (actual, expected) in expected_scalars.items():
        if actual != expected:
            issue(
                issues,
                "SUMMARY_COUNT_MISMATCH",
                field=field,
                expected=expected,
                actual=actual,
            )

    for field, actual, expected in (
        ("pca_cumulative_at_4", evr4, 0.745517570480533),
        ("pca_cumulative_at_8", evr8, 0.821883926913117),
    ):
        if not close(actual, expected):
            issue(
                issues,
                "SUMMARY_PCA_MISMATCH",
                field=field,
                expected=expected,
                actual=actual,
            )

    expected_clusters = {
        "0": (22345, "deuteron", 0),
        "1": (28191, "proton", 1),
        "2": (14587, "C12", 282),
        "3": (22432, "proton", 0),
    }
    if set(clusters) != set(expected_clusters):
        issue(
            issues,
            "SUMMARY_CLUSTER_SET_MISMATCH",
            expected=sorted(expected_clusters),
            actual=sorted(clusters),
        )
    else:
        for cluster_id, (expected_n, expected_species, expected_early) in (
            expected_clusters.items()
        ):
            cluster = clusters[cluster_id]
            actual_n = int(cluster["n"])
            actual_species = str(cluster["dominant_species"])
            actual_early = int(cluster["morphology_composition"].get("early_peak", 0))
            if (actual_n, actual_species, actual_early) != (
                expected_n,
                expected_species,
                expected_early,
            ):
                issue(
                    issues,
                    "SUMMARY_CLUSTER_MISMATCH",
                    cluster=cluster_id,
                    expected={
                        "n": expected_n,
                        "dominant_species": expected_species,
                        "early_peak": expected_early,
                    },
                    actual={
                        "n": actual_n,
                        "dominant_species": actual_species,
                        "early_peak": actual_early,
                    },
                )

    producer_requirements = (
        "PCA(n_components=min(10, NSAMP))",
        "GaussianMixture(n_components=4, random_state=SEED, n_init=3)",
        "gmm.fit_predict(Z[:, :4])",
        'summary["pca_cumulative_at_4"]',
        'summary["pca_cumulative_at_8"]',
    )
    for phrase in producer_requirements:
        require_text(
            issues,
            producer_text,
            phrase,
            code="PRODUCER_CONTRACT_MISSING",
        )
    forbid_pattern(
        issues,
        producer_text,
        r"Bayesian Information Criterion|\bBIC\b",
        code="PRODUCER_UNDECLARED_BIC_PRESENT",
    )

    chapter_requirements = (
        "truth-labelled Monte Carlo",
        "283 / 87,555",
        "156 / 283",
        "156 / 7,302",
        "0.745517570480533",
        "0.821883926913117",
        "K = 4 on the first four PCs",
        "No BIC scan was run",
        "not identified as carbon-12",
        "matched data/MC closure",
        "Simulation alone cannot establish empirical beam-data performance",
        "CHAPTER9_MUST_MATCH_TRACKED_MV6_PRODUCER_AND_SUMMARY",
    )
    for phrase in chapter_requirements:
        require_text(
            issues,
            chapter_text,
            phrase,
            code="CHAPTER_REQUIRED_STATEMENT_MISSING",
        )

    forbidden_chapter_patterns = (
        r"The BIC minimum at K\s*=\s*7",
        r"captures 99\.7\s*% of the pulse shape variance",
        r"convergence was achieved in 127 iterations",
        r"captures\s*>?99%\s+of\s+C12",
        r"truth-labelled MC thus assigns a concrete particle identity",
        r"manual review of all 283",
        r"validating the physical model",
    )
    for pattern in forbidden_chapter_patterns:
        forbid_pattern(
            issues,
            chapter_text,
            pattern,
            code="CHAPTER_UNSUPPORTED_CLAIM_PRESENT",
        )

    cl022 = claims.get("CL-022")
    if cl022 is None:
        issue(issues, "CANONICAL_CL022_MISSING")
    else:
        expected_claim_fields = {
            "current_value": "0.003232254011764034",
            "numerator": "283",
            "denominator": "87555",
            "truth_type": "mc_truth_only",
            "status": "TRUTH_LEVEL_MC_ONLY",
            "source_script": str(PRODUCER_PATH),
            "source_data": str(SUMMARY_PATH),
            "blocked_by": "AUD-ANOM-001",
        }
        for field, expected in expected_claim_fields.items():
            actual = cl022[field]
            if actual != expected:
                issue(
                    issues,
                    "CANONICAL_CL022_FIELD_MISMATCH",
                    field=field,
                    expected=expected,
                    actual=actual,
                )

    total_ci = wilson_interval(early_peak + low_area, n_tracks)
    composition_ci = wilson_interval(c12_early, early_peak)
    c12_rate_ci = wilson_interval(c12_early, c12_total)

    metrics = {
        "early_peak_rate": {
            "numerator": early_peak + low_area,
            "denominator": n_tracks,
            "estimate": (early_peak + low_area) / n_tracks,
            "ci_low": total_ci[0],
            "ci_high": total_ci[1],
            "ci_method": "Wilson_score",
        },
        "c12_share_of_early_peak": {
            "numerator": c12_early,
            "denominator": early_peak,
            "estimate": c12_early / early_peak,
            "ci_low": composition_ci[0],
            "ci_high": composition_ci[1],
            "ci_method": "Wilson_score",
        },
        "early_peak_rate_within_c12": {
            "numerator": c12_early,
            "denominator": c12_total,
            "estimate": c12_early / c12_total,
            "ci_low": c12_rate_ci[0],
            "ci_high": c12_rate_ci[1],
            "ci_method": "Wilson_score",
        },
        "representation": {
            "pca_cumulative_at_4": evr4,
            "pca_cumulative_at_8": evr8,
            "gmm_components": 4,
            "gmm_input_components": 4,
            "bic_scan": False,
        },
    }

    return {
        "status": "VALIDATED" if not issues else "FLAWED",
        "policy": POLICY,
        "validator_version": VERSION,
        "issues": issues,
        "metrics": metrics,
        "provenance": {
            "chapter": relative(chapter_prov, root),
            "summary": relative(summary_prov, root),
            "producer": relative(producer_prov, root),
            "claim_ledger": relative(ledger_prov, root),
        },
        "limitations": [
            "truth-labelled simulation only",
            "no matched beam-data closure",
            "no efficiency or false-positive measurement",
            "finite-count intervals exclude simulation-model uncertainty",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = audit(args.root)
    except InputError as exc:
        result = {
            "status": "INPUT_ERROR",
            "policy": POLICY,
            "validator_version": VERSION,
            "error": str(exc),
        }
        exit_code = 2
    else:
        exit_code = 0 if result["status"] == "VALIDATED" else 1

    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
