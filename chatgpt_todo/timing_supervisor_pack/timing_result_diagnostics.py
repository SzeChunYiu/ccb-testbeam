#!/usr/bin/env python3
"""Fail-closed diagnostics for the CCB inter-stave timing claim.

This script audits the already-produced Issue #1320 result and generates plots
that make the origin and limitations of the reported sub-nanosecond numbers
visible. It intentionally does not reprocess raw ROOT waveforms; the required
raw-data plot sequence is frozen in ``diagnostic_plot_manifest.csv``.

Example
-------
python chatgpt_todo/timing_supervisor_pack/timing_result_diagnostics.py \
    --result reports/issue_1320_timing/result.json \
    --polarity-map configs/channel_polarity_v2.json \
    --out chatgpt_todo/timing_supervisor_pack/generated

The command exits with status 2 when the evidence does not authorize a physical
single-stave resolution. That is the expected outcome for the current result.
Use ``--allow-gated-exit-zero`` only for report-generation workflows.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


FROZEN_FRACTION_ROWS = [
    {
        "fraction": 0.10,
        "sigma68_ns": 0.161213,
        "core_sigma_ns": 0.197327,
        "rms_ns": 3.9221,
        "chi2_ndf": 826.8,
    },
    {
        "fraction": 0.20,
        "sigma68_ns": 0.138090,
        "core_sigma_ns": 0.146308,
        "rms_ns": 4.0920,
        "chi2_ndf": 826.7,
    },
    {
        "fraction": 0.30,
        "sigma68_ns": 0.122166,
        "core_sigma_ns": 0.132133,
        "rms_ns": 4.2549,
        "chi2_ndf": 819.7,
    },
    {
        "fraction": 0.40,
        "sigma68_ns": 0.110148,
        "core_sigma_ns": 0.129088,
        "rms_ns": 4.3971,
        "chi2_ndf": 799.4,
    },
    {
        "fraction": 0.50,
        "sigma68_ns": 0.101763,
        "core_sigma_ns": 0.128072,
        "rms_ns": 4.5236,
        "chi2_ndf": 781.9,
    },
    {
        "fraction": 0.60,
        "sigma68_ns": 0.096455,
        "core_sigma_ns": 0.128506,
        "rms_ns": 4.6267,
        "chi2_ndf": 766.5,
    },
]

ALIASES = {
    "fraction": ("fraction", "cfd_fraction", "fraction_value"),
    "sigma68_ns": ("sigma68_ns", "sigma_68_ns", "central68_ns"),
    "core_sigma_ns": (
        "core_sigma_ns",
        "gaussian_core_sigma_ns",
        "fit_sigma_ns",
        "sigma_core_ns",
    ),
    "rms_ns": ("rms_ns", "full_rms_ns", "residual_rms_ns"),
    "chi2_ndf": ("chi2_ndf", "chi2_over_ndf", "fit_chi2_ndf"),
}


@dataclass(frozen=True)
class AuditFinding:
    severity: str
    code: str
    summary: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class AuditOutcome:
    status: str
    pair_residual_authorized: bool
    single_stave_resolution_authorized: bool
    recommended_headline: str
    findings: list[AuditFinding]


def _iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def _first_alias(mapping: dict[str, Any], logical_name: str) -> Any:
    for key in ALIASES[logical_name]:
        if key in mapping:
            return mapping[key]
    return None


def _normalise_fraction_row(mapping: dict[str, Any]) -> dict[str, float] | None:
    values: dict[str, float] = {}
    for logical_name in ALIASES:
        raw = _first_alias(mapping, logical_name)
        if raw is None:
            return None
        try:
            values[logical_name] = float(raw)
        except (TypeError, ValueError):
            return None
    fraction = values["fraction"]
    if not 0.0 < fraction < 1.0:
        return None
    if min(values["sigma68_ns"], values["core_sigma_ns"], values["rms_ns"]) <= 0:
        return None
    return values


def extract_fraction_rows(result: dict[str, Any]) -> tuple[list[dict[str, float]], str]:
    candidates: list[dict[str, float]] = []
    for mapping in _iter_dicts(result):
        row = _normalise_fraction_row(mapping)
        if row is not None:
            candidates.append(row)

    deduplicated: dict[float, dict[str, float]] = {}
    for row in candidates:
        deduplicated[round(row["fraction"], 8)] = row
    rows = sorted(deduplicated.values(), key=lambda item: item["fraction"])
    if len(rows) >= 3:
        return rows, "parsed_from_result_json"
    return [dict(row) for row in FROZEN_FRACTION_ROWS], "frozen_issue_1320_table"


def _find_numeric(result: dict[str, Any], names: tuple[str, ...]) -> float | None:
    for mapping in _iter_dicts(result):
        for name in names:
            value = mapping.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing JSON input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"top-level JSON value must be an object: {path}")
    return value


def polarity_status(path: Path | None) -> tuple[str | None, dict[str, Any] | None]:
    if path is None:
        return None, None
    mapping = read_json(path)
    status = mapping.get("status")
    return str(status) if status is not None else None, mapping


def audit_result(
    result: dict[str, Any],
    rows: list[dict[str, float]],
    map_status: str | None,
) -> AuditOutcome:
    findings: list[AuditFinding] = []

    if map_status is None:
        findings.append(
            AuditFinding(
                "HIGH",
                "PROVENANCE_MAP_STATUS_MISSING",
                "No channel-polarity map status was supplied to the audit.",
                {},
            )
        )
    elif "RETRACT" in map_status.upper():
        findings.append(
            AuditFinding(
                "CRITICAL",
                "RETRACTED_POLARITY_MAP",
                "The result consumes a channel map whose repository status is retracted.",
                {"status": map_status},
            )
        )

    ratios = [row["rms_ns"] / row["sigma68_ns"] for row in rows]
    maximum_ratio = max(ratios)
    minimum_chi2_ndf = min(row["chi2_ndf"] for row in rows)
    if maximum_ratio > 3.0:
        findings.append(
            AuditFinding(
                "CRITICAL",
                "STRONGLY_NON_GAUSSIAN_RESIDUAL",
                "The full RMS is many times the central-68% width.",
                {
                    "max_rms_over_sigma68": maximum_ratio,
                    "range_rms_over_sigma68": [min(ratios), maximum_ratio],
                },
            )
        )
    if minimum_chi2_ndf > 5.0:
        findings.append(
            AuditFinding(
                "CRITICAL",
                "GAUSSIAN_CORE_FIT_REJECTED",
                "The reported Gaussian-core fit has unacceptable chi2/ndf at every fraction.",
                {"minimum_chi2_ndf": minimum_chi2_ndf},
            )
        )

    sigma68_values = np.asarray([row["sigma68_ns"] for row in rows], dtype=float)
    rms_values = np.asarray([row["rms_ns"] for row in rows], dtype=float)
    if sigma68_values[-1] < sigma68_values[0] and rms_values[-1] > rms_values[0]:
        findings.append(
            AuditFinding(
                "HIGH",
                "CORE_TAIL_TRADEOFF",
                "Increasing CFD fraction narrows the central core while widening the full distribution.",
                {
                    "sigma68_first_last_ns": [
                        float(sigma68_values[0]),
                        float(sigma68_values[-1]),
                    ],
                    "rms_first_last_ns": [float(rms_values[0]), float(rms_values[-1])],
                },
            )
        )

    complete_pairs = _find_numeric(
        result,
        ("n_complete_pair_events", "complete_pair_events", "n_pairs"),
    )
    selected_rows = _find_numeric(
        result,
        ("n_selected_events_total", "n_selected_rows_total", "selected_rows"),
    )
    if complete_pairs and selected_rows:
        ratio = selected_rows / complete_pairs
        if abs(ratio - 2.0) < 0.05:
            findings.append(
                AuditFinding(
                    "MEDIUM",
                    "WAVEFORM_ROWS_LABELLED_AS_EVENTS",
                    "The selected total is two waveform rows per complete B4-B6 event.",
                    {
                        "selected_total": selected_rows,
                        "complete_pair_events": complete_pairs,
                        "ratio": ratio,
                    },
                )
            )

    findings.append(
        AuditFinding(
            "CRITICAL",
            "PAIR_ONLY_UNDERDETERMINED",
            "One B4-B6 residual cannot identify B4 and B6 resolutions separately.",
            {
                "model": "Var(dt_B4B6)=sigma_B4^2+sigma_B6^2-2*Cov(B4,B6)",
                "unknowns": ["sigma_B4", "sigma_B6", "Cov(B4,B6)"],
            },
        )
    )
    findings.append(
        AuditFinding(
            "HIGH",
            "SIGMA68_NOT_QUADRATURE_ADDITIVE",
            "A robust interquantile width cannot generally be divided by sqrt(2).",
            {},
        )
    )

    physical_blockers = {
        "RETRACTED_POLARITY_MAP",
        "STRONGLY_NON_GAUSSIAN_RESIDUAL",
        "GAUSSIAN_CORE_FIT_REJECTED",
        "PAIR_ONLY_UNDERDETERMINED",
    }
    blocked = any(item.code in physical_blockers for item in findings)
    status = "GATED_NOT_PHYSICAL_RESOLUTION" if blocked else "PAIR_RESULT_REVIEW_REQUIRED"
    pair_authorized = map_status is not None and "RETRACT" not in map_status.upper()
    return AuditOutcome(
        status=status,
        pair_residual_authorized=pair_authorized,
        single_stave_resolution_authorized=False,
        recommended_headline=(
            "The published sub-nanosecond number is an analysis-level B4-B6 pair-core "
            "diagnostic from a retracted waveform interpretation; no intrinsic stave "
            "timing resolution is currently authorized."
        ),
        findings=findings,
    )


def write_fraction_table(rows: list[dict[str, float]], path: Path) -> None:
    fieldnames = ["fraction", "sigma68_ns", "core_sigma_ns", "rms_ns", "chi2_ndf"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_figure(figure: plt.Figure, out: Path, stem: str) -> None:
    figure.tight_layout()
    figure.savefig(out / f"{stem}.png", dpi=180)
    figure.savefig(out / f"{stem}.svg")
    plt.close(figure)


def plot_width_scan(rows: list[dict[str, float]], out: Path) -> None:
    fractions = np.asarray([row["fraction"] for row in rows])
    figure, axis = plt.subplots(figsize=(7.2, 4.8))
    axis.plot(
        fractions,
        [row["sigma68_ns"] for row in rows],
        marker="o",
        label="central 68% width",
    )
    axis.plot(
        fractions,
        [row["core_sigma_ns"] for row in rows],
        marker="s",
        label="Gaussian-core sigma",
    )
    axis.plot(
        fractions,
        [row["rms_ns"] for row in rows],
        marker="^",
        label="full RMS",
    )
    axis.set_yscale("log")
    axis.set_xlabel("CFD fraction")
    axis.set_ylabel("reported residual scale (ns, log axis)")
    axis.set_title("Issue #1320: core narrows while the full distribution stays broad")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    save_figure(figure, out, "01_reported_width_scan")


def plot_non_gaussianity(rows: list[dict[str, float]], out: Path) -> None:
    fractions = np.asarray([row["fraction"] for row in rows])
    ratios = np.asarray([row["rms_ns"] / row["sigma68_ns"] for row in rows])
    figure, axis = plt.subplots(figsize=(7.2, 4.8))
    axis.plot(fractions, ratios, marker="o")
    axis.axhline(1.0, linestyle="--", linewidth=1.0, label="Gaussian-like scale agreement")
    axis.set_xlabel("CFD fraction")
    axis.set_ylabel("RMS / central-68% width")
    axis.set_title("Large RMS/core mismatch: the residual is strongly non-Gaussian")
    axis.grid(True, alpha=0.25)
    axis.legend()
    save_figure(figure, out, "02_non_gaussianity_ratio")


def plot_fit_quality(rows: list[dict[str, float]], out: Path) -> None:
    fractions = np.asarray([row["fraction"] for row in rows])
    figure, axis = plt.subplots(figsize=(7.2, 4.8))
    axis.plot(fractions, [row["chi2_ndf"] for row in rows], marker="o")
    axis.axhline(1.0, linestyle="--", linewidth=1.0, label="ideal order of magnitude")
    axis.set_xlabel("CFD fraction")
    axis.set_ylabel("Gaussian-core fit chi2 / ndf")
    axis.set_yscale("log")
    axis.set_title("The Gaussian-core model is rejected at every scanned fraction")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    save_figure(figure, out, "03_gaussian_fit_quality")


def sigma68(values: np.ndarray) -> float:
    q16, q84 = np.quantile(values, [0.16, 0.84])
    return float(0.5 * (q84 - q16))


def plot_deconvolution_counterexamples(
    out: Path, seed: int = 20260831
) -> list[dict[str, float | str]]:
    rng = np.random.default_rng(seed)
    n = 400_000
    cases: list[tuple[str, np.ndarray, np.ndarray]] = []

    a = rng.normal(0.0, 1.0, n)
    b = rng.normal(0.0, 1.0, n)
    cases.append(("equal independent normal", a, b))

    a = rng.normal(0.0, 1.0, n)
    b = rng.normal(0.0, 2.0, n)
    cases.append(("unequal independent normal", a, b))

    common = rng.normal(0.0, 1.0, n)
    a = common + rng.normal(0.0, 1.0, n)
    b = common + rng.normal(0.0, 1.0, n)
    cases.append(("equal with common jitter", a, b))

    a = rng.laplace(0.0, 1.0, n)
    b = rng.laplace(0.0, 1.0, n)
    cases.append(("equal independent Laplace", a, b))

    records: list[dict[str, float | str]] = []
    for name, first, second in cases:
        pair = first - second
        naive = sigma68(pair) / math.sqrt(2.0)
        true_first = sigma68(first)
        records.append(
            {
                "case": name,
                "true_stave_A_sigma68": true_first,
                "pair_sigma68": sigma68(pair),
                "naive_pair_over_sqrt2": naive,
                "relative_error_percent": 100.0 * (naive / true_first - 1.0),
            }
        )

    labels = [str(record["case"]) for record in records]
    errors = [float(record["relative_error_percent"]) for record in records]
    figure, axis = plt.subplots(figsize=(8.4, 5.2))
    positions = np.arange(len(labels))
    axis.bar(positions, errors)
    axis.axhline(0.0, linewidth=1.0)
    axis.set_xticks(positions, labels, rotation=18, ha="right")
    axis.set_ylabel("error of pair sigma68 / sqrt(2) vs stave-A sigma68 (%)")
    axis.set_title("The sqrt(2) conversion is a special-case assumption, not a general estimator")
    axis.grid(True, axis="y", alpha=0.25)
    save_figure(figure, out, "04_sqrt2_counterexamples")
    return records


def plot_inference_gate(out: Path) -> None:
    figure, axis = plt.subplots(figsize=(9.2, 5.8))
    axis.set_axis_off()
    boxes = [
        (0.05, 0.76, "1. Validate raw frame shape, map status, and real pulse identity"),
        (0.05, 0.57, "2. Produce pair residuals with held-out cuts and full tail diagnostics"),
        (0.05, 0.38, "3. Measure at least 3 connected pairs or use a calibrated reference"),
        (0.05, 0.19, "4. Model covariance and close the estimator on simulation/injection"),
    ]
    for x, y, text in boxes:
        axis.text(
            x,
            y,
            text,
            transform=axis.transAxes,
            fontsize=11,
            va="center",
            bbox={"boxstyle": "round,pad=0.5", "facecolor": "none", "edgecolor": "black"},
        )
    for y_top, y_bottom in [(0.72, 0.63), (0.53, 0.44), (0.34, 0.25)]:
        axis.annotate(
            "",
            xy=(0.5, y_bottom),
            xytext=(0.5, y_top),
            xycoords="axes fraction",
            arrowprops={"arrowstyle": "->"},
        )
    axis.text(
        0.64,
        0.48,
        "Current Issue #1320 evidence stops here:\nretracted map + non-Gaussian pair only",
        transform=axis.transAxes,
        fontsize=11,
        va="center",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "none", "edgecolor": "black"},
    )
    axis.text(
        0.63,
        0.12,
        "Only after all gates pass:\nquote per-stave resolution with uncertainty",
        transform=axis.transAxes,
        fontsize=11,
        va="center",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "none", "edgecolor": "black"},
    )
    axis.set_title(
        "Fail-closed path from waveform samples to an intrinsic stave resolution",
        pad=18,
    )
    save_figure(figure, out, "05_resolution_inference_gate")


def write_markdown_summary(
    out: Path,
    rows_source: str,
    map_status: str | None,
    outcome: AuditOutcome,
    counterexamples: list[dict[str, float | str]],
) -> None:
    lines = [
        "# Generated timing-claim audit",
        "",
        f"- Fraction table source: `{rows_source}`",
        f"- Channel-map status: `{map_status}`",
        f"- Audit status: **{outcome.status}**",
        f"- Pair residual authorized as detector timing: **{outcome.pair_residual_authorized}**",
        f"- Single-stave resolution authorized: **{outcome.single_stave_resolution_authorized}**",
        "",
        "## Recommended headline",
        "",
        outcome.recommended_headline,
        "",
        "## Findings",
        "",
    ]
    for finding in outcome.findings:
        lines.extend(
            [
                f"### {finding.severity}: {finding.code}",
                "",
                finding.summary,
                "",
                "```json",
                json.dumps(finding.evidence, indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Fixed-seed sqrt(2) counterexamples",
            "",
            "| case | true stave-A sigma68 | pair sigma68 | pair/sqrt(2) | relative error |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for record in counterexamples:
        lines.append(
            "| {case} | {true_stave_A_sigma68:.4f} | {pair_sigma68:.4f} | "
            "{naive_pair_over_sqrt2:.4f} | {relative_error_percent:+.2f}% |".format(
                **record
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This audit does not reprocess immutable ROOT inputs. It diagnoses the published "
            "result contract and demonstrates why the current pair statistic cannot be promoted "
            "to an intrinsic stave resolution. Raw-data promotion requires every gate in "
            "`diagnostic_plot_manifest.csv` to pass.",
            "",
        ]
    )
    (out / "AUDIT_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def run_self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result_path = root / "result.json"
        map_path = root / "map.json"
        result_path.write_text(
            json.dumps(
                {
                    "n_selected_events_total": 200,
                    "n_complete_pair_events": 100,
                    "scan": FROZEN_FRACTION_ROWS,
                }
            ),
            encoding="utf-8",
        )
        map_path.write_text(json.dumps({"status": "RETRACTED_TEST"}), encoding="utf-8")
        result = read_json(result_path)
        rows, source = extract_fraction_rows(result)
        status, _ = polarity_status(map_path)
        outcome = audit_result(result, rows, status)
        assert source == "parsed_from_result_json"
        assert outcome.single_stave_resolution_authorized is False
        codes = {finding.code for finding in outcome.findings}
        assert "RETRACTED_POLARITY_MAP" in codes
        assert "WAVEFORM_ROWS_LABELLED_AS_EVENTS" in codes
        assert "PAIR_ONLY_UNDERDETERMINED" in codes
    print("self-test: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, help="Issue/result JSON to audit")
    parser.add_argument("--polarity-map", type=Path, help="Channel polarity JSON")
    parser.add_argument("--out", type=Path, default=Path("timing_diagnostic_output"))
    parser.add_argument(
        "--allow-gated-exit-zero",
        action="store_true",
        help="Return zero even when no physical resolution is authorized",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0
    if args.result is None:
        raise SystemExit("--result is required unless --self-test is used")

    args.out.mkdir(parents=True, exist_ok=True)
    result = read_json(args.result)
    rows, rows_source = extract_fraction_rows(result)
    map_status, _ = polarity_status(args.polarity_map)
    outcome = audit_result(result, rows, map_status)

    write_fraction_table(rows, args.out / "fraction_metrics.csv")
    plot_width_scan(rows, args.out)
    plot_non_gaussianity(rows, args.out)
    plot_fit_quality(rows, args.out)
    counterexamples = plot_deconvolution_counterexamples(args.out)
    plot_inference_gate(args.out)

    payload = asdict(outcome)
    payload["fraction_table_source"] = rows_source
    payload["polarity_map_status"] = map_status
    payload["sqrt2_counterexamples"] = counterexamples
    (args.out / "audit_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    write_markdown_summary(args.out, rows_source, map_status, outcome, counterexamples)

    print(json.dumps(payload, indent=2, sort_keys=True))
    if outcome.single_stave_resolution_authorized or args.allow_gated_exit_zero:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
