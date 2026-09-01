#!/usr/bin/env python3
"""Fail-closed diagnostics for the CCB inter-stave timing claim.

This script has two jobs:

1. Audit the already-produced Issue #1320 timing result without silently
   promoting a pair residual to an intrinsic stave resolution.
2. Generate a compact set of plots that make the origin and limitations of
   the reported sub-nanosecond numbers visible.

It intentionally does *not* reprocess raw ROOT waveforms.  The raw-waveform
plot sequence and its acceptance criteria are frozen in
``diagnostic_plot_manifest.csv``.  A future raw-data producer must satisfy that
contract and must refuse retracted channel maps or inconsistent frame shapes.

Example
-------
python chatgpt_todo/timing_supervisor_pack/timing_result_diagnostics.py \
    --result reports/issue_1320_timing/result.json \
    --polarity-map configs/channel_polarity_v2.json \
    --out chatgpt_todo/timing_supervisor_pack/generated

The command exits with status 2 when the evidence does not authorize a physical
single-stave resolution.  That is the expected outcome for the current result.
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
        "sigma68_ns": 0.16112333977627546,
        "core_sigma_ns": 0.1290269473142366,
        "rms_ns": 3.9174668662332692,
        "chi2_ndf": 720.2675768277162,
    },
    {
        "fraction": 0.20,
        "sigma68_ns": 0.1459809921292674,
        "core_sigma_ns": 0.124188124410562,
        "rms_ns": 3.94692303243605,
        "chi2_ndf": 790.5339395913193,
    },
    {
        "fraction": 0.30,
        "sigma68_ns": 0.13158221770966883,
        "core_sigma_ns": 0.12090128826554383,
        "rms_ns": 4.024482988801127,
        "chi2_ndf": 827.2547994910406,
    },
    {
        "fraction": 0.40,
        "sigma68_ns": 0.11826494175383218,
        "core_sigma_ns": 0.1288119194159857,
        "rms_ns": 4.157859912323973,
        "chi2_ndf": 827.4795544205273,
    },
    {
        "fraction": 0.50,
        "sigma68_ns": 0.10653271728252633,
        "core_sigma_ns": 0.12933315483290825,
        "rms_ns": 4.35537925558032,
        "chi2_ndf": 812.9717647860406,
    },
    {
        "fraction": 0.60,
        "sigma68_ns": 0.09634985742446744,
        "core_sigma_ns": 0.12906252542873511,
        "rms_ns": 4.63043802316874,
        "chi2_ndf": 765.9514422181784,
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
    "chi2_ndf": (
        "chi2_ndf",
        "core_chi2_ndf",
        "chi2_over_ndf",
        "fit_chi2_ndf",
    ),
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


def extract_fraction_rows(
    result: dict[str, Any], *, allow_frozen_fallback: bool = False
) -> tuple[list[dict[str, float]], str]:
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
    if allow_frozen_fallback:
        return [dict(row) for row in FROZEN_FRACTION_ROWS], "frozen_issue_1320_table"
    raise ValueError(
        "fewer than three live fraction rows were parsed; refuse to substitute a "
        "frozen table unless --allow-frozen-fallback is explicit"
    )


def _find_numeric(result: dict[str, Any], names: tuple[str, ...]) -> float | None:
    for mapping in _iter_dicts(result):
        for name in names:
            value = mapping.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
    return None


def _find_numeric_values(result: dict[str, Any], name: str) -> list[float]:
    values: list[float] = []
    for mapping in _iter_dicts(result):
        value = mapping.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


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
                (
                    "Increasing CFD fraction narrows the central core while widening "
                    "the full distribution."
                ),
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
        (
            "n_complete_pair_events",
            "complete_pair_events",
            "n_pairs",
        ),
    )
    selected_rows = _find_numeric(
        result,
        (
            "n_selected_events_total",
            "n_selected_rows_total",
            "selected_rows",
        ),
    )
    if selected_rows is None:
        # The live Issue #1320 producer stores one finite-CFD count per stave row
        # under cfd_status.*.n_finite.  A two-stave pair therefore has roughly
        # two finite rows per unique pair event.  Use the maximum fraction count
        # as the direct machine-readable event/row diagnostic.
        finite_counts = _find_numeric_values(result, "n_finite")
        if finite_counts:
            selected_rows = max(finite_counts)
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
    return AuditOutcome(
        status=status,
        pair_residual_authorized=not (
            map_status is None or "RETRACT" in map_status.upper()
        ),
        single_stave_resolution_authorized=False,
        recommended_headline=(
            "The published sub-nanosecond number is an analysis-level B4-B6 pair-core "
            "diagnostic from a retracted waveform interpretation; no intrinsic stave "
            "timing resolution is currently authorized."
        ),
        findings=findings,
    )
