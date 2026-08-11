#!/usr/bin/env python3
"""Fail-closed event identity and inference helpers for real-data CFD timing."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

EVENT_KEY_COLUMNS: tuple[str, str] = ("run", "event_id")
POLICY = "REAL_DATA_CFD_REQUIRES_COMPOSITE_EVENT_KEYS_AND_PAIR_ONLY_INFERENCE"


@dataclass(frozen=True)
class ResidualPlotRecord:
    method: str
    n_total: int
    median_ns: float
    q16_centered_ns: float
    q84_centered_ns: float
    sigma68_ns: float
    full_range_ns: tuple[float, float]
    full_underflow: int
    full_overflow: int
    core_range_ns: tuple[float, float]
    core_displayed: int
    core_underflow: int
    core_overflow: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def require_event_columns(df: pd.DataFrame) -> None:
    missing = [name for name in (*EVENT_KEY_COLUMNS, "stave") if name not in df.columns]
    if missing:
        raise ValueError(f"missing required event columns: {missing}")
    if df[list(EVENT_KEY_COLUMNS)].isna().any(axis=None):
        raise ValueError("composite event key contains missing values")


def pivot_by_event(df: pd.DataFrame, value_column: str) -> pd.DataFrame:
    """Pivot one value per (run,event_id,stave), rejecting duplicate identities."""
    require_event_columns(df)
    if value_column not in df.columns:
        raise ValueError(f"missing value column: {value_column}")
    duplicate = df.duplicated([*EVENT_KEY_COLUMNS, "stave"], keep=False)
    if duplicate.any():
        example = df.loc[duplicate, [*EVENT_KEY_COLUMNS, "stave"]].head(5)
        raise ValueError(
            "duplicate (run,event_id,stave) rows are ambiguous: "
            f"{example.to_dict(orient='records')}"
        )
    return df.pivot(index=list(EVENT_KEY_COLUMNS), columns="stave", values=value_column)


def select_in_time_rows(
    df: pd.DataFrame,
    staves: Sequence[str],
    tolerance_samples: float,
) -> tuple[pd.DataFrame, dict[str, float], int]:
    if not staves:
        raise ValueError("at least one stave is required")
    if not np.isfinite(tolerance_samples) or tolerance_samples < 0:
        raise ValueError("tolerance_samples must be finite and nonnegative")
    require_event_columns(df)
    offsets: dict[str, float] = {}
    for stave in staves:
        values = df.loc[df["stave"] == stave, "peak_sample"].to_numpy(dtype=float)
        if values.size == 0 or not np.isfinite(values).all():
            raise ValueError(f"missing or nonfinite peak samples for stave {stave}")
        offsets[stave] = float(np.median(values))

    work = df.copy()
    work["peak_al"] = work["peak_sample"] - work["stave"].map(offsets)
    selected = work[work["stave"].isin(staves)]
    pivot = pivot_by_event(selected, "peak_al")
    pivot = pivot.reindex(columns=list(staves))
    complete = pivot.notna().all(axis=1)
    spread = pivot.max(axis=1) - pivot.min(axis=1)
    keep_index = pivot.index[complete & (spread <= tolerance_samples)]
    keys = keep_index.to_frame(index=False)
    kept = work.merge(keys, on=list(EVENT_KEY_COLUMNS), how="inner", validate="many_to_one")
    return kept, offsets, int(len(keep_index))


def pair_residual_vector(
    df: pd.DataFrame,
    method_column: str,
    stave_a: str,
    stave_b: str,
    tof_ns: Mapping[str, float],
    peak_offsets: Mapping[str, float],
    sample_period_ns: float,
) -> np.ndarray:
    if not np.isfinite(sample_period_ns) or sample_period_ns <= 0:
        raise ValueError("sample_period_ns must be finite and positive")
    selected = df[df["stave"].isin([stave_a, stave_b])].copy()
    missing_tof = [s for s in (stave_a, stave_b) if s not in tof_ns]
    missing_offset = [s for s in (stave_a, stave_b) if s not in peak_offsets]
    if missing_tof or missing_offset:
        raise ValueError(
            f"missing timing corrections: tof={missing_tof}, peak_offsets={missing_offset}"
        )
    selected["tcorr"] = (
        selected[method_column]
        - selected["stave"].map(tof_ns)
        - selected["stave"].map(
            {name: value * sample_period_ns for name, value in peak_offsets.items()}
        )
    )
    wide = pivot_by_event(selected, "tcorr")
    if stave_a not in wide.columns or stave_b not in wide.columns:
        return np.asarray([], dtype=float)
    vector = (wide[stave_a] - wide[stave_b]).dropna().to_numpy(dtype=float)
    return vector[np.isfinite(vector)]


def residual_plot_record(
    residuals: Iterable[float],
    method: str,
    core_half_width_ns: float | None = None,
) -> tuple[np.ndarray, ResidualPlotRecord]:
    vector = np.asarray(list(residuals), dtype=float)
    vector = vector[np.isfinite(vector)]
    if vector.size == 0:
        raise ValueError("residual vector is empty")
    median = float(np.median(vector))
    centered = vector - median
    q16, q84 = np.quantile(centered, [0.16, 0.84])
    sigma68 = float((q84 - q16) / 2.0)
    minimum = float(np.min(centered))
    maximum = float(np.max(centered))
    if minimum == maximum:
        pad = max(1e-9, abs(minimum) * 1e-9)
        minimum -= pad
        maximum += pad
    full_underflow = int(np.count_nonzero(centered < minimum))
    full_overflow = int(np.count_nonzero(centered > maximum))
    if core_half_width_ns is None:
        core_half_width_ns = max(5.0, 2.0 * sigma68)
    if not np.isfinite(core_half_width_ns) or core_half_width_ns <= 0:
        raise ValueError("core_half_width_ns must be finite and positive")
    core_low = -float(core_half_width_ns)
    core_high = float(core_half_width_ns)
    core_under = int(np.count_nonzero(centered < core_low))
    core_over = int(np.count_nonzero(centered > core_high))
    record = ResidualPlotRecord(
        method=method,
        n_total=int(centered.size),
        median_ns=median,
        q16_centered_ns=float(q16),
        q84_centered_ns=float(q84),
        sigma68_ns=sigma68,
        full_range_ns=(minimum, maximum),
        full_underflow=full_underflow,
        full_overflow=full_overflow,
        core_range_ns=(core_low, core_high),
        core_displayed=int(centered.size - core_under - core_over),
        core_underflow=core_under,
        core_overflow=core_over,
    )
    return centered, record


def pair_only_inference_contract() -> dict[str, object]:
    return {
        "authorized": False,
        "scope": "B6-B8 pair residual only",
        "policy": POLICY,
        "reason": (
            "A pair sigma68 does not identify either individual stave resolution. "
            "Division by sqrt(2) would require validated equal variances, zero covariance, "
            "and an estimator with a demonstrated quadrature-deconvolution law."
        ),
        "required_for_individual_stave": [
            "multi-pair or external-reference deconvolution",
            "explicit covariance/common-mode model",
            "propagated uncertainty and assumption sensitivity",
            "closure or injection-recovery validation",
        ],
    }


@dataclass(frozen=True)
class RunPopulationReport:
    requested_runs: tuple[int, ...]
    resolved_runs: tuple[int, ...]
    missing_runs: tuple[int, ...]
    empty_runs: tuple[int, ...]
    failed_runs: tuple[int, ...]
    excluded_by_policy: tuple[int, ...]
    events_per_run: dict[int, int]
    pulses_per_run: dict[int, int]
    authorising: bool
    mode: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        # JSON-friendly keys
        payload["events_per_run"] = {str(k): int(v) for k, v in self.events_per_run.items()}
        payload["pulses_per_run"] = {str(k): int(v) for k, v in self.pulses_per_run.items()}
        return payload


def assert_run_population_complete(report: RunPopulationReport) -> None:
    """Fail closed for authorising mode when requested runs are incomplete (#1004)."""
    if not report.authorising:
        return
    problems = []
    if report.missing_runs:
        problems.append(f"missing_runs={list(report.missing_runs)}")
    if report.empty_runs:
        problems.append(f"empty_runs={list(report.empty_runs)}")
    if report.failed_runs:
        problems.append(f"failed_runs={list(report.failed_runs)}")
    if problems:
        raise RuntimeError(
            "authorising CFD timing requires exact requested run completeness; "
            + "; ".join(problems)
        )


def select_complete_pair_rows(
    df: pd.DataFrame,
    staves: Sequence[str],
) -> tuple[pd.DataFrame, int]:
    """Keep events that have all requested staves, without peak-time conditioning (#1003)."""
    if not staves:
        raise ValueError("at least one stave is required")
    require_event_columns(df)
    selected = df[df["stave"].isin(staves)].copy()
    pivot = pivot_by_event(selected, "peak_sample")
    pivot = pivot.reindex(columns=list(staves))
    complete = pivot.notna().all(axis=1)
    keep_index = pivot.index[complete]
    keys = keep_index.to_frame(index=False)
    kept = selected.merge(keys, on=list(EVENT_KEY_COLUMNS), how="inner", validate="many_to_one")
    return kept, int(len(keep_index))


def peak_offset_dictionary(
    df: pd.DataFrame,
    staves: Sequence[str],
    *,
    calibration_df: pd.DataFrame | None = None,
) -> dict[str, float]:
    """Derive per-stave median peak offsets, optionally from a calibration population (#1003)."""
    source = calibration_df if calibration_df is not None else df
    require_event_columns(source)
    offsets: dict[str, float] = {}
    for stave in staves:
        values = source.loc[source["stave"] == stave, "peak_sample"].to_numpy(dtype=float)
        if values.size == 0 or not np.isfinite(values).all():
            raise ValueError(f"missing or nonfinite peak samples for stave {stave}")
        offsets[stave] = float(np.median(values))
    return offsets


def apply_intime_mask(
    df: pd.DataFrame,
    staves: Sequence[str],
    offsets: Mapping[str, float],
    tolerance_samples: float,
) -> tuple[pd.DataFrame, int]:
    """Apply a frozen peak-time tolerance using externally supplied offsets."""
    if not np.isfinite(tolerance_samples) or tolerance_samples < 0:
        raise ValueError("tolerance_samples must be finite and nonnegative")
    require_event_columns(df)
    work = df.copy()
    work["peak_al"] = work["peak_sample"] - work["stave"].map(dict(offsets))
    selected = work[work["stave"].isin(staves)]
    pivot = pivot_by_event(selected, "peak_al")
    pivot = pivot.reindex(columns=list(staves))
    complete = pivot.notna().all(axis=1)
    spread = pivot.max(axis=1) - pivot.min(axis=1)
    keep_index = pivot.index[complete & (spread <= tolerance_samples)]
    keys = keep_index.to_frame(index=False)
    kept = work.merge(keys, on=list(EVENT_KEY_COLUMNS), how="inner", validate="many_to_one")
    return kept, int(len(keep_index))
