"""Evidence-bound paper-grade figure set for the CCB wiki and manuscript.

Every plotted number is read from a tracked CSV/JSON/claim-ledger row.  Missing,
duplicate or non-finite inputs fail closed.  Captions remain outside the plotting
area so the image contains only the visual evidence needed to answer one question.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from .export import atomic_write_json, export_figure, sha256_file
from .style import OKABE_ITO, figure_size, light_axis_grid, paper_style


@dataclass(frozen=True)
class FigureSpec:
    figure_id: str
    stem: str
    title: str
    question: str
    caption: str
    status: str
    evidence_class: str
    column: str
    height_mm: float
    source_paths: tuple[str, ...]
    renderer: Callable[[Path], tuple[Figure, pd.DataFrame]]


def _require_file(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"required figure input is missing: {relative}")
    return path


def _load_json(root: Path, relative: str) -> dict[str, Any]:
    path = _require_file(root, relative)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {relative}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{relative} must contain a JSON object")
    return payload


def _load_csv(root: Path, relative: str, required: set[str]) -> pd.DataFrame:
    path = _require_file(root, relative)
    frame = pd.read_csv(path)
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{relative} is missing columns {sorted(missing)}")
    if frame.empty:
        raise ValueError(f"{relative} is empty")
    return frame


def _finite(value: Any, *, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not numeric: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} is not finite: {value!r}")
    return number


def _claim(ledger: pd.DataFrame, claim_id: str) -> pd.Series:
    rows = ledger.loc[ledger["claim_id"].astype(str) == claim_id]
    if len(rows) != 1:
        raise ValueError(f"expected exactly one {claim_id} row, found {len(rows)}")
    return rows.iloc[0]


def _wilson(k: float, n: float, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0 or k < 0 or k > n:
        raise ValueError(f"invalid binomial counts k={k}, n={n}")
    p = k / n
    denominator = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denominator
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denominator
    return centre - half, centre + half


def _new_figure(spec: FigureSpec) -> tuple[Figure, Any]:
    fig, axis = plt.subplots(figsize=figure_size(column=spec.column, height_mm=spec.height_mm))
    axis.set_title(spec.title, loc="left", pad=5)
    return fig, axis


def _selected_pulse_inventory(root: Path) -> tuple[Figure, pd.DataFrame]:
    source = _load_csv(
        root,
        "reports/S00_data_integrity_pipeline_reproduction/count_match_table.csv",
        {"quantity", "report_value", "reproduced", "delta", "pass"},
    )
    wanted = source[
        source["quantity"].str.contains("analysis B[2468] selected pulses", regex=True)
    ].copy()
    if len(wanted) != 8 or not wanted["pass"].astype(bool).all():
        raise ValueError("S00 analysis-by-stave rows are incomplete or not exact-pass")
    wanted["sample"] = np.where(
        wanted["quantity"].str.startswith("sample_i_analysis"), "Sample I", "Sample II"
    )
    wanted["stave"] = wanted["quantity"].str.extract(r"(B[2468])", expand=False)
    pivot = wanted.pivot(index="sample", columns="stave", values="reproduced").loc[
        ["Sample I", "Sample II"]
    ]

    spec = SPECS_BY_ID["FIG-WIKI-001"]
    fig, axis = _new_figure(spec)
    display_scale = 1e5
    left = np.zeros(len(pivot), dtype=float)
    staves = ["B2", "B4", "B6", "B8"]
    colours = [OKABE_ITO["blue"], OKABE_ITO["sky"], OKABE_ITO["orange"], OKABE_ITO["purple"]]
    for stave, colour in zip(staves, colours, strict=True):
        values = pivot[stave].to_numpy(dtype=float) / display_scale
        axis.barh(
            pivot.index,
            values,
            left=left,
            height=0.52,
            label=stave,
            color=colour,
            linewidth=0,
        )
        left += values
    axis.set_xlabel(r"Selected pulses ($\times 10^5$)")
    axis.invert_yaxis()
    light_axis_grid(axis, which="x")
    axis.legend(ncol=2, loc="center right", bbox_to_anchor=(0.985, 0.50), columnspacing=0.8)

    table = wanted[["sample", "stave", "reproduced", "report_value", "delta", "pass"]].rename(
        columns={"reproduced": "selected_pulses"}
    )
    return fig, table


def _claim_status_overview(root: Path) -> tuple[Figure, pd.DataFrame]:
    ledger = _load_csv(
        root, "docs/claim_ledger.csv", {"claim_id", "status", "ci_status", "truth_type"}
    )
    counts = (
        ledger["status"]
        .fillna("MISSING")
        .astype(str)
        .value_counts()
        .rename_axis("status")
        .reset_index(name="claims")
    )
    order = [
        "VALIDATED",
        "DONE_DATA_ONLY",
        "TRUTH_LEVEL_MC_ONLY",
        "GATED",
        "REVIEW",
        "TENSION",
        "FLAWED",
        "BLOCKED",
        "SUPERSEDED",
    ]
    counts["rank"] = (
        counts["status"].map({name: index for index, name in enumerate(order)}).fillna(len(order))
    )
    counts = counts.sort_values(["rank", "status"]).drop(columns="rank")
    palette = {
        "VALIDATED": OKABE_ITO["green"],
        "DONE_DATA_ONLY": OKABE_ITO["blue"],
        "TRUTH_LEVEL_MC_ONLY": OKABE_ITO["sky"],
        "GATED": OKABE_ITO["orange"],
        "REVIEW": OKABE_ITO["grey"],
        "TENSION": OKABE_ITO["vermillion"],
        "FLAWED": OKABE_ITO["purple"],
        "BLOCKED": "#9A9A9A",
        "SUPERSEDED": "#C8C8C8",
    }

    spec = SPECS_BY_ID["FIG-WIKI-002"]
    fig, axis = _new_figure(spec)
    y = np.arange(len(counts))
    bars = axis.barh(
        y,
        counts["claims"],
        color=[palette.get(item, OKABE_ITO["grey"]) for item in counts["status"]],
        height=0.62,
    )
    display_status = {
        "DONE_DATA_ONLY": "DATA ONLY",
        "TRUTH_LEVEL_MC_ONLY": "TRUTH MC ONLY",
    }
    axis.set_yticks(
        y, [display_status.get(item, item.replace("_", " ")) for item in counts["status"]]
    )
    axis.invert_yaxis()
    axis.set_xlabel("Claims in canonical ledger")
    axis.set_xticks(range(0, int(counts["claims"].max()) + 1, 2))
    light_axis_grid(axis, which="x")
    for bar, value in zip(bars, counts["claims"], strict=True):
        axis.text(
            value + 0.18,
            bar.get_y() + bar.get_height() / 2,
            f"{int(value)}",
            va="center",
            ha="left",
            fontsize=5.8,
        )
    axis.set_xlim(0, float(counts["claims"].max()) + 1.7)
    return fig, counts


def _timing_mc_method_closure(root: Path) -> tuple[Figure, pd.DataFrame]:
    metrics = _load_json(root, "reports/studies/clusterB/metrics.json")
    try:
        residuals = metrics["VIS-TIM-001"]["sigma68_residual_ns"]
        combined = metrics["VIS-TIM-005"]["combined_sigma68_ns"]
    except KeyError as exc:
        raise ValueError(f"clusterB metrics missing timing field {exc}") from exc
    rows = [
        ("Combined (4 sensors)", _finite(combined, label="combined sigma68"), True),
        ("CFD", _finite(residuals["cfd"], label="CFD sigma68"), False),
        ("Template", _finite(residuals["templ"], label="template sigma68"), False),
        ("Leading edge", _finite(residuals["lead"], label="leading-edge sigma68"), False),
    ]
    table = pd.DataFrame(rows, columns=["estimator", "sigma68_ns", "nominal"])

    spec = SPECS_BY_ID["FIG-WIKI-003"]
    fig, axis = _new_figure(spec)
    y = np.arange(len(table))
    colours = [OKABE_ITO["blue"] if item else OKABE_ITO["grey"] for item in table["nominal"]]
    axis.hlines(y, 0, table["sigma68_ns"], color=OKABE_ITO["light_grey"], linewidth=0.7)
    axis.scatter(table["sigma68_ns"], y, c=colours, marker="o", zorder=3)
    axis.set_yticks(y, table["estimator"])
    axis.invert_yaxis()
    axis.set_xlabel(r"Residual width, $\sigma_{68}$ (ns)")
    axis.set_xlim(0, 0.82)
    light_axis_grid(axis, which="x")
    return fig, table


def _pid_mc_validation(root: Path) -> tuple[Figure, pd.DataFrame]:
    counts = _load_json(root, "reports/studies/clusterA/counts.json")
    folds = counts.get("pid_oof_auc_5fold")
    if not isinstance(folds, list) or len(folds) != 5:
        raise ValueError("clusterA pid_oof_auc_5fold must contain five values")
    fold_values = [
        _finite(value, label=f"PID fold {index}") for index, value in enumerate(folds, start=1)
    ]
    full_auc = _finite(counts.get("pid_full_auc"), label="PID full AUC")
    table = pd.DataFrame({"fold": np.arange(1, 6), "auc": fold_values})
    table["full_auc"] = full_auc

    spec = SPECS_BY_ID["FIG-WIKI-004"]
    fig, axis = _new_figure(spec)
    axis.scatter(
        table["fold"], table["auc"], color=OKABE_ITO["blue"], label="Held-out folds", zorder=3
    )
    axis.axhline(
        full_auc, color=OKABE_ITO["vermillion"], linestyle="--", linewidth=0.8, label="Full sample"
    )
    axis.set_xlabel("Grouped fold")
    axis.set_ylabel("ROC AUC")
    axis.set_xticks(table["fold"])
    axis.set_ylim(min(fold_values) - 0.012, max(fold_values) + 0.012)
    light_axis_grid(axis, which="y")
    axis.legend(loc="lower right")
    return fig, table


def _adc_mc_calibration(root: Path) -> tuple[Figure, pd.DataFrame]:
    metrics = _load_json(root, "reports/studies/clusterC/metrics.json")
    try:
        block = metrics["VIS-ENE-001"]
        rows = [
            (
                "Proton",
                block["proton"]["slope_adc_per_MeV"],
                block["proton"]["pull_rms"],
                block["proton"]["n_events"],
            ),
            (
                "Deuteron",
                block["deuteron"]["slope_adc_per_MeV"],
                block["deuteron"]["pull_rms"],
                block["deuteron"]["n_events"],
            ),
        ]
    except KeyError as exc:
        raise ValueError(f"clusterC metrics missing calibration field {exc}") from exc
    table = pd.DataFrame(rows, columns=["estimate", "slope_adc_per_MeV", "pull_rms", "n_events"])
    for column in ["slope_adc_per_MeV", "pull_rms", "n_events"]:
        table[column] = table[column].map(lambda value: _finite(value, label=f"ADC {column}"))
    table["uncertainty_adc_per_MeV"] = 0.0
    table["evidence"] = "SIMULATION_RESULT"

    ledger = _load_csv(
        root,
        "docs/claim_ledger.csv",
        {"claim_id", "current_value", "syst_unc", "status", "ci_status"},
    )
    mv0 = _claim(ledger, "CL-013")
    table = pd.concat(
        [
            table,
            pd.DataFrame(
                [
                    {
                        "estimate": "MV0 data/MC proxy",
                        "slope_adc_per_MeV": _finite(mv0["current_value"], label="CL-013 gain"),
                        "pull_rms": np.nan,
                        "n_events": np.nan,
                        "uncertainty_adc_per_MeV": _finite(
                            mv0["syst_unc"], label="CL-013 heuristic envelope"
                        ),
                        "evidence": str(mv0["status"]),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    spec = SPECS_BY_ID["FIG-WIKI-005"]
    fig, axis = _new_figure(spec)
    y = np.arange(len(table))
    colours = [OKABE_ITO["blue"], OKABE_ITO["orange"], OKABE_ITO["grey"]]
    axis.errorbar(
        table["slope_adc_per_MeV"],
        y,
        xerr=table["uncertainty_adc_per_MeV"],
        fmt="none",
        ecolor=OKABE_ITO["grey"],
        capsize=2.0,
        zorder=2,
    )
    axis.scatter(table["slope_adc_per_MeV"], y, color=colours, zorder=3)
    axis.axvline(
        120.0,
        color=OKABE_ITO["grey"],
        linestyle="--",
        linewidth=0.7,
    )
    axis.set_yticks(y, table["estimate"])
    axis.invert_yaxis()
    axis.set_xlabel("Gain estimate (ADC/MeV)")
    axis.set_xlim(58.0, 124.0)
    light_axis_grid(axis, which="x")
    return fig, table


def _birks_mc_comparison(root: Path) -> tuple[Figure, pd.DataFrame]:
    metrics = _load_json(root, "reports/studies/clusterC/metrics.json")
    try:
        block = metrics["VIS-ENE-002"]
        rows = [
            ("Digitizer default", block["kB_digitizer_default"], "configuration"),
            ("Total-deposit proxy", block["kB_best_total_edep_proxy"], "proxy fit"),
            ("Per-track dE/dx", block["kB_best_per_track_dEdx"], "preferred MC fit"),
        ]
    except KeyError as exc:
        raise ValueError(f"clusterC metrics missing Birks field {exc}") from exc
    table = pd.DataFrame(rows, columns=["method", "kB_cm_per_MeV", "role"])
    table["kB_cm_per_MeV"] = table["kB_cm_per_MeV"].map(
        lambda value: _finite(value, label="Birks kB")
    )

    spec = SPECS_BY_ID["FIG-WIKI-006"]
    fig, axis = _new_figure(spec)
    y = np.arange(len(table))
    colours = [OKABE_ITO["grey"], OKABE_ITO["orange"], OKABE_ITO["blue"]]
    axis.hlines(y, 0, table["kB_cm_per_MeV"], color=OKABE_ITO["light_grey"], linewidth=0.7)
    axis.scatter(table["kB_cm_per_MeV"], y, c=colours, zorder=3)
    axis.set_yticks(y, table["method"])
    axis.invert_yaxis()
    axis.set_xlabel(r"Birks coefficient $k_B$ (cm/MeV)")
    axis.set_xlim(0, 0.0175)
    light_axis_grid(axis, which="x")
    return fig, table


def _pileup_digitizer_mc(root: Path) -> tuple[Figure, pd.DataFrame]:
    metrics = _load_json(root, "reports/studies/clusterC/metrics.json")
    try:
        block = metrics["VIS-PU-002"]
        window_ns = _finite(block["T_acq_ns"], label="acquisition window")
        rate5_hz = _finite(block["rate_at_5pct_overlap_Hz"], label="5% scan rate")
        rate10_hz = _finite(block["Rmax_quality_Hz"], label="10% scan rate")
        observed_max = _finite(block["observed_overlap_at_max_rate"], label="observed max overlap")
        poisson_max = _finite(block["poisson_overlap_at_max_rate"], label="Poisson max overlap")
    except KeyError as exc:
        raise ValueError(f"clusterC metrics missing pile-up field {exc}") from exc
    window_s = window_ns * 1e-9
    scan = [
        ("nearest 5% point", rate5_hz, 1.0 - math.exp(-rate5_hz * window_s), np.nan),
        ("nearest 10% point", rate10_hz, 1.0 - math.exp(-rate10_hz * window_s), np.nan),
        ("maximum scan rate", -math.log1p(-poisson_max) / window_s, poisson_max, observed_max),
    ]
    table = pd.DataFrame(scan, columns=["point", "rate_Hz", "poisson_overlap", "observed_overlap"])
    table["rate_MHz"] = table["rate_Hz"] / 1e6
    table["acquisition_window_ns"] = window_ns

    spec = SPECS_BY_ID["FIG-WIKI-007"]
    fig, axis = _new_figure(spec)
    rates = np.linspace(0.0, max(1.05, float(table["rate_MHz"].max()) * 1.05), 300)
    analytic = 1.0 - np.exp(-(rates * 1e6) * window_s)
    axis.plot(rates, analytic * 100.0, color=OKABE_ITO["blue"], label="Poisson model")
    axis.scatter(
        table["rate_MHz"].iloc[:2],
        table["poisson_overlap"].iloc[:2] * 100.0,
        color=OKABE_ITO["orange"],
        marker="o",
        label="Stored scan points",
        zorder=3,
    )
    axis.scatter(
        table["rate_MHz"].iloc[2],
        observed_max * 100.0,
        color=OKABE_ITO["vermillion"],
        marker="s",
        label="Simulation at max rate",
        zorder=3,
    )
    for target in (5.0, 10.0):
        axis.axhline(target, color=OKABE_ITO["light_grey"], linewidth=0.55, zorder=0)
    axis.set_xlabel("Event rate (MHz)")
    axis.set_ylabel("Overlap probability (%)")
    axis.set_xlim(0, rates.max())
    axis.set_ylim(0, max(18.5, observed_max * 115.0))
    light_axis_grid(axis, which="x")
    axis.legend(loc="upper left")
    return fig, table


def _stopping_b8_tension(root: Path) -> tuple[Figure, pd.DataFrame]:
    ledger = _load_csv(
        root,
        "docs/claim_ledger.csv",
        {"claim_id", "current_value", "numerator", "denominator", "status"},
    )
    rows: list[dict[str, Any]] = []
    for claim_id, sample in [("CL-020", "Selected data"), ("CL-019", "Thresholded MC")]:
        row = _claim(ledger, claim_id)
        k = _finite(row["numerator"], label=f"{claim_id} numerator")
        n = _finite(row["denominator"], label=f"{claim_id} denominator")
        fraction = k / n
        ledger_fraction = _finite(row["current_value"], label=f"{claim_id} current value")
        if not math.isclose(fraction, ledger_fraction, rel_tol=0.0, abs_tol=1e-14):
            raise ValueError(f"{claim_id} fraction does not match exact counts")
        low, high = _wilson(k, n)
        rows.append(
            {
                "claim_id": claim_id,
                "sample": sample,
                "numerator": int(k),
                "denominator": int(n),
                "fraction": fraction,
                "ci_low": low,
                "ci_high": high,
                "status": str(row["status"]),
            }
        )
    table = pd.DataFrame(rows)

    spec = SPECS_BY_ID["FIG-WIKI-008"]
    fig, axis = _new_figure(spec)
    y = np.arange(len(table))
    x = table["fraction"].to_numpy() * 100.0
    lower = (table["fraction"] - table["ci_low"]).to_numpy() * 100.0
    upper = (table["ci_high"] - table["fraction"]).to_numpy() * 100.0
    axis.errorbar(
        x,
        y,
        xerr=np.vstack([lower, upper]),
        fmt="o",
        color=OKABE_ITO["vermillion"],
        ecolor=OKABE_ITO["grey"],
        capsize=2.0,
    )
    axis.set_yticks(y, table["sample"])
    axis.invert_yaxis()
    axis.set_xlabel("Tracks/events assigned to B8 (%)")
    axis.set_xlim(0, 25)
    light_axis_grid(axis, which="x")
    return fig, table


def _anomaly_truth_mc(root: Path) -> tuple[Figure, pd.DataFrame]:
    ledger = _load_csv(
        root, "docs/claim_ledger.csv", {"claim_id", "numerator", "denominator", "notes", "status"}
    )
    row = _claim(ledger, "CL-022")
    total_k = _finite(row["numerator"], label="CL-022 numerator")
    total_n = _finite(row["denominator"], label="CL-022 denominator")
    notes = str(row["notes"])
    match = re.search(r"C12 early-peak rate is ([0-9]+)/([0-9]+)", notes)
    if match is None:
        raise ValueError("CL-022 notes do not contain the C12 early-peak source counts")
    c12_k = float(match.group(1))
    c12_n = float(match.group(2))
    total_ci = _wilson(total_k, total_n)
    c12_ci = _wilson(c12_k, c12_n)
    table = pd.DataFrame(
        [
            {
                "population": "All charged B-arm MC",
                "numerator": int(total_k),
                "denominator": int(total_n),
                "fraction": total_k / total_n,
                "ci_low": total_ci[0],
                "ci_high": total_ci[1],
            },
            {
                "population": "C12 truth subset",
                "numerator": int(c12_k),
                "denominator": int(c12_n),
                "fraction": c12_k / c12_n,
                "ci_low": c12_ci[0],
                "ci_high": c12_ci[1],
            },
        ]
    )

    spec = SPECS_BY_ID["FIG-WIKI-009"]
    fig, axis = _new_figure(spec)
    y = np.arange(len(table))
    x = table["fraction"].to_numpy() * 100.0
    lower = (table["fraction"] - table["ci_low"]).to_numpy() * 100.0
    upper = (table["ci_high"] - table["fraction"]).to_numpy() * 100.0
    axis.errorbar(
        x,
        y,
        xerr=np.vstack([lower, upper]),
        fmt="o",
        color=OKABE_ITO["blue"],
        ecolor=OKABE_ITO["grey"],
        capsize=2.0,
    )
    axis.set_yticks(y, table["population"])
    axis.invert_yaxis()
    axis.set_xlabel("Early-peak morphology rate (%)")
    axis.set_xlim(0, 2.6)
    light_axis_grid(axis, which="x")
    return fig, table


def _pca_truth_mc(root: Path) -> tuple[Figure, pd.DataFrame]:
    ledger = _load_csv(
        root, "docs/claim_ledger.csv", {"claim_id", "current_value", "n_mc", "status"}
    )
    rows = []
    for claim_id, components in [("CL-023", 3), ("CL-024", 8)]:
        row = _claim(ledger, claim_id)
        rows.append(
            {
                "claim_id": claim_id,
                "components": components,
                "cumulative_explained_variance": _finite(row["current_value"], label=claim_id),
                "n_mc": int(_finite(row["n_mc"], label=f"{claim_id} n_mc")),
                "status": str(row["status"]),
            }
        )
    table = pd.DataFrame(rows)

    spec = SPECS_BY_ID["FIG-WIKI-010"]
    fig, axis = _new_figure(spec)
    axis.plot(
        table["components"],
        table["cumulative_explained_variance"] * 100.0,
        color=OKABE_ITO["blue"],
        marker="o",
    )
    axis.set_xlabel("Principal components")
    axis.set_ylabel("Cumulative explained variance (%)")
    axis.set_xticks([3, 8])
    axis.set_xlim(2.4, 8.6)
    axis.set_ylim(68, 86)
    light_axis_grid(axis, which="y")
    return fig, table


def _systematic_sensitivity_inputs(root: Path) -> tuple[Figure, pd.DataFrame]:
    source = _load_csv(
        root,
        "reports/studies/clusterE/systematic_budget.csv",
        {"nuisance", "abs_elasticity_adc", "source"},
    )
    numeric = pd.to_numeric(source["abs_elasticity_adc"], errors="coerce")
    # Keep only dimensionless elasticities.  The final three rows mix a heuristic
    # envelope, a physical kB span and a material column density, so combining them
    # in one bar chart would be dimensionally invalid.
    table = source.loc[
        numeric.notna() & source["source"].astype(str).str.startswith("clusterD")
    ].copy()
    table["abs_elasticity_adc"] = pd.to_numeric(table["abs_elasticity_adc"], errors="raise")
    table = table.sort_values("abs_elasticity_adc", ascending=True).reset_index(drop=True)
    if len(table) != 11:
        raise ValueError(f"expected 11 dimensionless sensitivity rows, found {len(table)}")

    spec = SPECS_BY_ID["FIG-WIKI-011"]
    fig, axis = _new_figure(spec)
    y = np.arange(len(table))
    axis.hlines(y, 5e-3, table["abs_elasticity_adc"], color=OKABE_ITO["light_grey"], linewidth=0.7)
    axis.scatter(table["abs_elasticity_adc"], y, color=OKABE_ITO["blue"], zorder=3)
    axis.set_yticks(y, table["nuisance"].str.replace("_", " "))
    axis.set_xscale("log")
    axis.set_xlabel("Absolute ADC-response elasticity")
    axis.set_xlim(5e-3, 5.0)
    light_axis_grid(axis, which="x")
    return fig, table


SPECS: tuple[FigureSpec, ...] = (
    FigureSpec(
        "FIG-WIKI-001",
        "selected_pulse_inventory",
        "Selected-pulse inventory",
        "How are the exact S00 analysis pulses distributed across samples and staves?",
        "Exact S00 reproduction. Sample I is dominated by B2; Sample II reaches deeper staves more often. Counts are deterministic for the fixed raw inputs and selection; CL-001 remains GATED pending data-contract closure (#952/#953/#954), so this figure is not an authorising ledger row.",  # noqa: E501
        "GATED",
        "DATA_MEASUREMENT",
        "single",
        49.0,
        ("reports/S00_data_integrity_pipeline_reproduction/count_match_table.csv",),
        _selected_pulse_inventory,
    ),
    FigureSpec(
        "FIG-WIKI-002",
        "claim_status_overview",
        "Claim ledger is mostly gated or blocked",
        "What fraction of the project claim surface is currently publication-authorized?",
        "Status counts from the canonical claim ledger (docs/claim_ledger.csv). Visual polish must not promote gated, blocked, flawed or superseded evidence.",  # noqa: E501
        "REVIEW",
        "GOVERNANCE_LEDGER",
        "single",
        70.0,
        ("docs/claim_ledger.csv",),
        _claim_status_overview,
    ),
    FigureSpec(
        "FIG-WIKI-003",
        "timing_mc_method_closure",
        "Timing estimator closure on MC",
        "How much does the four-sensor estimator improve the MC residual width?",
        "Krakow MC method closure. The combined four-sensor estimator reaches σ68 = 0.089 ns; this is not a detector timing measurement on beam data.",  # noqa: E501
        "MC_METHOD_CLOSURE",
        "MC_METHOD_CLOSURE",
        "single",
        53.0,
        ("reports/studies/clusterB/metrics.json",),
        _timing_mc_method_closure,
    ),
    FigureSpec(
        "FIG-WIKI-004",
        "pid_mc_validation",
        "Grouped-fold PID stability on MC",
        "Is the realistic-chain proton/deuteron AUC stable across grouped folds?",
        "Five contiguous event-block folds from the realistic ΔE–E MC chain. Fold ordering is categorical, so points are deliberately not connected. Transfer to beam data remains unvalidated.",  # noqa: E501
        "SIMULATION_RESULT",
        "SIMULATION_RESULT",
        "single",
        51.0,
        ("reports/studies/clusterA/counts.json",),
        _pid_mc_validation,
    ),
    FigureSpec(
        "FIG-WIKI-005",
        "adc_mc_calibration",
        "Gain closure and gated data/MC proxy",
        "How does MC digitizer closure compare with the gated MV0 data/MC proxy?",
        "MC fits recover 119.168 ADC/MeV for both species near the configured 120 ADC/MeV. The separate MV0 proxy is 92 ADC/MeV with a 28 ADC/MeV heuristic systematic envelope, not a confidence interval, and remains gated.",  # noqa: E501
        "GATED",
        "MC_CLOSURE_PLUS_GATED_DATA_MC_PROXY",
        "single",
        50.0,
        ("reports/studies/clusterC/metrics.json", "docs/claim_ledger.csv"),
        _adc_mc_calibration,
    ),
    FigureSpec(
        "FIG-WIKI-006",
        "birks_mc_comparison",
        "Birks-model dependence on MC",
        "How strongly does the inferred Birks coefficient depend on the fitting observable?",
        "The per-track dE/dx fit gives kB = 0.0156 cm/MeV, above both the total-deposit proxy and the digitizer default. The spread is model dependence, not a confidence interval.",  # noqa: E501
        "SIMULATION_RESULT",
        "SIMULATION_RESULT",
        "single",
        48.0,
        ("reports/studies/clusterC/metrics.json",),
        _birks_mc_comparison,
    ),
    FigureSpec(
        "FIG-WIKI-007",
        "pileup_digitizer_mc",
        "Digitizer-domain overlap scan",
        "Which event rates correspond to the stored 5% and 10% overlap scan points?",
        "Poisson overlap for the 180 ns acquisition window. The stored nearest scan points are 0.289 MHz (5.06%, not exactly 5%) and 0.605 MHz (10.31%, not exactly 10%). These are simulation-domain criteria; canonical detector Rmax remains blocked.",  # noqa: E501
        "SIMULATION_RESULT",
        "SIMULATION_RESULT",
        "single",
        54.0,
        ("reports/studies/clusterC/metrics.json",),
        _pileup_digitizer_mc,
    ),
    FigureSpec(
        "FIG-WIKI-008",
        "stopping_b8_tension",
        "B8 stopping assignment disagrees",
        "How large is the exact B8 fraction mismatch in the legacy data/MC stopping profile?",
        "Exact tracked counts give 2.30% in selected data and 22.29% in thresholded MC. Wilson intervals show counting uncertainty only; unresolved geometry, trigger, gain and selection transfer dominate the scientific interpretation.",  # noqa: E501
        "TENSION",
        "LEGACY_DATA_MC_DIAGNOSTIC",
        "single",
        43.0,
        ("docs/claim_ledger.csv",),
        _stopping_b8_tension,
    ),
    FigureSpec(
        "FIG-WIKI-009",
        "anomaly_truth_mc",
        "Early-peak morphology in truth MC",
        "How frequent is the early-peak morphology overall and within truth-labelled C12 tracks?",
        "Truth-labelled MC rates with Wilson 95% intervals: 283/87,555 overall and 156/7,302 within C12. C12 forms 156/283 early-peak tracks, but the separate beam-data anomaly is not identified as C12.",  # noqa: E501
        "TRUTH_LEVEL_MC_ONLY",
        "TRUTH_LEVEL_MC_ONLY",
        "single",
        46.0,
        ("docs/claim_ledger.csv",),
        _anomaly_truth_mc,
    ),
    FigureSpec(
        "FIG-WIKI-010",
        "pca_truth_mc",
        "Synthetic-waveform PCA compression",
        "How much variance is captured by compact PCA representations of the MC waveforms?",
        "Fixed synthetic-waveform MC output: three components explain 72.5% and eight explain 82.2%. These values supersede stale 0.89/0.997 statements and are not beam-data PCA results.",  # noqa: E501
        "TRUTH_LEVEL_MC_ONLY",
        "SYNTHETIC_WAVEFORM_MC",
        "single",
        48.0,
        ("docs/claim_ledger.csv",),
        _pca_truth_mc,
    ),
    FigureSpec(
        "FIG-WIKI-011",
        "systematic_sensitivity_inputs",
        "ADC-response sensitivity inputs",
        "Which dimensionless nuisance elasticities dominate the current MC sensitivity scan?",
        "Dimensionless cluster-D ADC-response elasticities only. Mixed-unit rows (gain envelope, kB span and missing material) are excluded rather than combined. This is a sensitivity inventory, not a propagated uncertainty budget.",  # noqa: E501
        "REVIEW",
        "SENSITIVITY_INPUTS",
        "single",
        76.0,
        ("reports/studies/clusterE/systematic_budget.csv",),
        _systematic_sensitivity_inputs,
    ),
)
SPECS_BY_ID = {spec.figure_id: spec for spec in SPECS}


def _source_signature(frame: pd.DataFrame) -> str:
    raw = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_all(repo_root: Path, output_dir: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_dir = output_dir / "source_tables"
    source_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []

    with paper_style():
        for spec in SPECS:
            fig, source = spec.renderer(repo_root)
            try:
                metadata_columns = {
                    "figure_id": spec.figure_id,
                    "figure_status": spec.status,
                    "figure_evidence_class": spec.evidence_class,
                }
                collisions = set(metadata_columns) & set(source.columns)
                if collisions:
                    raise ValueError(
                        f"{spec.figure_id}: source table metadata collision {sorted(collisions)}"
                    )
                source = source.copy()
                for name, value in reversed(tuple(metadata_columns.items())):
                    source.insert(0, name, value)
                source_path = source_dir / f"{spec.stem}_source.csv"
                source.to_csv(source_path, index=False, lineterminator="\n")
                export = export_figure(
                    fig,
                    output_dir=output_dir,
                    stem=spec.stem,
                    column=spec.column,
                    height_mm=spec.height_mm,
                    title=spec.title,
                )
            finally:
                plt.close(fig)

            # Express output/file_check paths relative to repo_root.
            # output_dir may be a worktree not under repo_root (Mac workflow),
            # so anchor on output_dir and then express via output_dir's own
            # repo-relative path.
            try:
                output_dir_rel = output_dir.relative_to(repo_root)
            except ValueError:
                output_dir_rel = Path(*output_dir.parts)

            for output in export["outputs"].values():
                output_path = Path(str(output["path"]))
                if output_path.is_relative_to(output_dir):
                    output["path"] = (output_dir_rel / output_path.relative_to(output_dir)).as_posix()
                elif output_path.is_relative_to(repo_root):
                    output["path"] = output_path.relative_to(repo_root).as_posix()
            for fc in export.get("file_checks", []):
                fc_path = Path(str(fc["path"]))
                if fc_path.is_relative_to(output_dir):
                    fc["path"] = (output_dir_rel / fc_path.relative_to(output_dir)).as_posix()
                elif fc_path.is_relative_to(repo_root):
                    fc["path"] = fc_path.relative_to(repo_root).as_posix()
            records.append(
                {
                    "figure_id": spec.figure_id,
                    "stem": spec.stem,
                    "title": spec.title,
                    "question": spec.question,
                    "caption": spec.caption,
                    "status": spec.status,
                    "evidence_class": spec.evidence_class,
                    "source_paths": list(spec.source_paths),
                    "source_table": (
                        source_path.relative_to(repo_root).as_posix()
                        if source_path.is_relative_to(repo_root)
                        else source_path.as_posix()
                    ),
                    "source_table_sha256": sha256_file(source_path),
                    "plotted_data_sha256": _source_signature(source),
                    **export,
                }
            )

    manifest = {
        "schema": "ccb-paper-grade-wiki-figures/1",
        "evidence_policy": "NO_HAND_ENTERED_HEADLINES_FAIL_CLOSED_SOURCE_TABLE_PER_FIGURE",
        "repository_head": os.environ.get("CCB_SOURCE_COMMIT"),
        "figure_count": len(records),
        "figures": records,
    }
    atomic_write_json(output_dir / "manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("docs/figures/paper"))
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    manifest = build_all(root, output)
    print(f"generated {manifest['figure_count']} paper-grade figures in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
