#!/usr/bin/env python3
"""Rebuild the S00 selected B-stack pulse table from reduced raw ROOT files."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml

from ccb_mc_validation.s00_selector_contract import (
    S00SelectorConfigError,
    s00_selector_model_identity,
    validate_s00_selector_contract,
)
from ccb_mc_validation.selector import estimate_pedestal_v1_batched
from ccb_mc_validation.daq.s00_saturation_field import legacy_world_a_diagnostic
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from channel_polarity import apply_polarity, load_polarity_map  # noqa: E402
from tools.audit.validate_hrd_waveform_contract import (
    BatchValidation,
    validate_and_reshape_rows,
)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


#: Env-var name used to override the amplitude cut without editing the YAML.
#: The canonical value lives in configs/s00_reproduction.yaml; CLI and env only
#: OVERRIDE it (no hardcoded default inside the script), per the repo rule that
#: every numeric parameter be config/env/CLI-addressable.
AMPLITUDE_CUT_ENV = "CCB_AMPLITUDE_CUT_ADC"

# --- Gate-state constants (used by write_manifest and main authorising logic) ---
GATE_PASS = "PASS"
GATE_FAIL = "FAIL"
GATE_NOT_RUN_MISSING_INPUT = "NOT_RUN_MISSING_INPUT"
GATE_NOT_APPLICABLE = "NOT_APPLICABLE"
SCHEMA_VERSION = "v1"


def _require_finite_nonnegative_cut(value: float, *, label: str) -> float:
    """Reject NaN/Inf/overflow before any waveform scan (issue #1031)."""
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite non-negative float, got {value!r}") from exc
    if not math.isfinite(v):
        raise ValueError(f"{label} must be finite, got {value!r}")
    if v < 0:
        raise ValueError(f"{label} must be non-negative, got {v}")
    return v


def resolve_amplitude_cut(config: dict, cli_value: Optional[float]) -> Tuple[float, str]:
    """Resolve the amplitude cut [ADC] with provenance: CLI > env > config.

    Returns (effective_cut, source) so the manifest records where the value
    came from. The YAML config remains the single documented default.
    Domain: finite non-negative ADC (issue #1031).
    """
    cfg_val = _require_finite_nonnegative_cut(
        config["amplitude_cut_adc"], label="config amplitude_cut_adc"
    )
    env_raw = os.environ.get(AMPLITUDE_CUT_ENV)
    if cli_value is not None:
        v = _require_finite_nonnegative_cut(cli_value, label="amplitude cut")
        return v, f"cli(--amplitude-cut-adc={cli_value})"
    if env_raw is not None and env_raw.strip() != "":
        try:
            env_val = float(env_raw)
        except ValueError as exc:
            raise ValueError(
                f"{AMPLITUDE_CUT_ENV} must be a finite non-negative float, got {env_raw!r}"
            ) from exc
        v = _require_finite_nonnegative_cut(env_val, label=AMPLITUDE_CUT_ENV)
        return v, f"env({AMPLITUDE_CUT_ENV}={env_raw})"
    return cfg_val, f"config({cfg_val})"

# --- S00 implementation-consistency check (audit S00-001 / S00-002 / STAT-002) ------------
# The S00 "ML check" is NOT a scientific benchmark: the label is defined
# deterministically by the amplitude cut (``selected = amplitude > cut``), so
# the column ``amplitude_adc`` cannot be used as a prediction feature without
# making every metric trivially perfect. The output is therefore reframed as
# an *implementation consistency check* and a leakage guard is enforced below.
TARGET_DEFINING_COLUMN = "amplitude_adc"
ML_FEATURES_DEFAULT = ("area_adc_samples", "peak_sample", "baseline_adc")

#: Env vars that override case-control sampling rates and the bootstrap
#: replicate count without editing the YAML (repo rule: no arbitrary hardcoded
#: numbers in code; the YAML remains the documented default when present).
CASE_CONTROL_KEEP_SELECTED_ENV = "CCB_ML_CASE_CONTROL_KEEP_SELECTED"
CASE_CONTROL_KEEP_REJECTED_ENV = "CCB_ML_CASE_CONTROL_KEEP_REJECTED"
ML_BOOTSTRAP_REPS_ENV = "CCB_ML_BOOTSTRAP_REPS"


def resolve_ml_features(config: dict) -> List[str]:
    """Feature columns for the implementation-consistency check.

    Fail-closed leakage guard (audit S00-001): the label is
    ``amplitude_adc > cut``, so ``amplitude_adc`` (the target-defining column)
    MUST NOT appear in the feature set -- otherwise every metric is perfect by
    construction. Raises ``ValueError`` on any leak.
    """
    raw = config.get("ml_check", {}).get("features")
    features = list(ML_FEATURES_DEFAULT) if raw is None else [str(c) for c in raw]
    leaked = sorted(set(features) & {TARGET_DEFINING_COLUMN})
    if leaked:
        raise ValueError(
            "Feature-target leakage (S00-001): the label is defined by "
            f"'{TARGET_DEFINING_COLUMN} > cut', so these feature(s) make any "
            f"metric trivially perfect: {leaked}. Remove them from "
            "ml_check.features."
        )
    return features


def resolve_case_control_keep(config: dict) -> Tuple[float, float]:
    """Return ``(keep_selected, keep_rejected)`` case-control sampling rates.

    Precedence: env > config > documented default (0.20, 0.05). The defaults
    are the historical S00 design values; they are surfaced here so callers can
    build inverse-probability weights that restore population prevalence
    (audit S00-002).
    """
    ml = config.get("ml_check", {}).get("case_control_keep", {})
    sel_default = float(ml.get("selected", 0.20)) if isinstance(ml, dict) else 0.20
    rej_default = float(ml.get("rejected", 0.05)) if isinstance(ml, dict) else 0.05

    def _resolve(env_var: str, default: float, what: str) -> float:
        raw = os.environ.get(env_var)
        value = default if raw is None or str(raw).strip() == "" else float(raw)
        if not np.isfinite(value) or not (0.0 < value <= 1.0):
            raise ValueError(f"{what} must satisfy 0 < p <= 1, got {raw!r}")
        return value

    return _resolve(CASE_CONTROL_KEEP_SELECTED_ENV, sel_default, "keep_selected"), _resolve(
        CASE_CONTROL_KEEP_REJECTED_ENV, rej_default, "keep_rejected"
    )


def resolve_ml_bootstrap_reps(config: dict) -> int:
    """Return the bootstrap replicate count (env > config > default 300)."""
    default = int(config.get("ml_check", {}).get("bootstrap_reps", 300))
    raw = os.environ.get(ML_BOOTSTRAP_REPS_ENV)
    value = default if raw is None or str(raw).strip() == "" else int(raw)
    if value < 1:
        raise ValueError(f"bootstrap_reps must be >= 1, got {value}")
    return value


def apply_two_stage_design_weights(
    ml_rows: "pd.DataFrame",
    *,
    max_sample: int,
    random_seed: int,
    keep_selected: float,
    keep_rejected: float,
) -> tuple["pd.DataFrame", dict]:
    """Apply per-class Stage-2 caps and recompute two-stage design weights.

    Stage 1 retention probabilities are ``keep_selected`` / ``keep_rejected``.
    Conditional on the Stage-1 sample of size ``n1_c``, the uniform within-class
    cap retains each row with ``p2_c = min(1, max_sample / n1_c)``. The design
    weight that reconstructs the finite population is

        w_c = 1 / (p1_c * p2_c).

    Returns the capped frame plus a provenance dict of pre/post counts.
    """
    if ml_rows is None or len(ml_rows) == 0:
        empty = ml_rows.copy() if ml_rows is not None else pd.DataFrame()
        return empty, {
            "max_sample_per_class": int(max_sample),
            "stage1_counts": {},
            "stage2_counts": {},
            "p_cap_conditional": {},
        }

    capped_parts: list[pd.DataFrame] = []
    stage1_counts: dict[str, int] = {}
    stage2_counts: dict[str, int] = {}
    p_cap: dict[str, float] = {}

    for selected_value, subset in ml_rows.groupby("selected", sort=True):
        key = str(int(selected_value))
        n1 = int(len(subset))
        n_keep = min(n1, int(max_sample))
        p2 = 1.0 if n1 <= 0 else float(n_keep) / float(n1)
        drawn = subset.sample(
            n=n_keep,
            random_state=int(random_seed) + int(selected_value),
        ).copy()
        p1 = float(keep_selected) if int(selected_value) == 1 else float(keep_rejected)
        # Guard against numerical underflow; p2 is in (0, 1].
        p2_safe = max(p2, 1e-15)
        drawn["p_case_control"] = p1
        drawn["p_cap_conditional"] = p2
        drawn["pi_total"] = p1 * p2
        drawn["design_weight"] = 1.0 / (p1 * p2_safe)
        drawn["sampling_weight"] = drawn["design_weight"].to_numpy(dtype=float)
        capped_parts.append(drawn)
        stage1_counts[key] = n1
        stage2_counts[key] = int(len(drawn))
        p_cap[key] = float(p2)

    out = pd.concat(capped_parts, ignore_index=True) if capped_parts else ml_rows.iloc[0:0].copy()
    provenance = {
        "max_sample_per_class": int(max_sample),
        "stage1_counts": stage1_counts,
        "stage2_counts": stage2_counts,
        "p_cap_conditional": p_cap,
        "keep_selected": float(keep_selected),
        "keep_rejected": float(keep_rejected),
        "weight_definition": "1/(p_case_control * p_cap_conditional)",
        "estimand_label": "two_stage_design_weighted_population_diagnostic",
    }
    return out, provenance


def case_control_sampling_weight(
    selected_mask: np.ndarray, keep_selected: float, keep_rejected: float
) -> np.ndarray:
    """Inverse-probability-of-inclusion weight for the case-control design.

    Each kept row represents ``1 / p(class)`` population rows, so multiplying
    any held-out evaluation by these weights restores population prevalence
    (audit S00-002). ``selected_mask`` is the boolean label of the KEPT sample.
    """
    sel = np.asarray(selected_mask, dtype=bool)
    return np.where(sel, 1.0 / float(keep_selected), 1.0 / float(keep_rejected))


def make_run_event_clusters(runs: np.ndarray, eventnos: np.ndarray) -> np.ndarray:
    """Build a ``(run, event)`` cluster label array for the cluster bootstrap.

    Rows sharing both ``run`` and ``event`` are one cluster (audit STAT-002):
    pulses from the same DAQ event share baseline / physics and must move
    together under resampling.
    """
    runs = np.asarray(runs)
    eventnos = np.asarray(eventnos)
    if runs.shape != eventnos.shape:
        raise ValueError(
            f"runs shape {runs.shape} must match eventnos shape {eventnos.shape}"
        )
    # 1-D object array of (run, event) TUPLES (not a 2-D array): each element
    # is a single hashable/comparable cluster label so np.unique and
    # ``clusters == k`` behave as cluster-level (not element-wise) operations.
    labels = np.empty(runs.shape[0], dtype=object)
    labels[:] = [tuple(z) for z in zip(runs.tolist(), eventnos.tolist())]
    return labels


def build_ml_rows_for_batch(
    *,
    run: int,
    group: str,
    event_numbers: np.ndarray,
    stave_grid: np.ndarray,
    amplitude: np.ndarray,
    area: np.ndarray,
    peak_sample: np.ndarray,
    baseline: np.ndarray,
    peak_code_adc: np.ndarray,
    saturation: np.ndarray,
    selected_mask: np.ndarray,
    keep_mask: np.ndarray,
    keep_selected: float,
    keep_rejected: float,
) -> pd.DataFrame:
    """Pure helper: build per-batch implementation-consistency rows.

    Carries ``eventno`` (needed for the ``(run, event)`` cluster bootstrap,
    STAT-002) and ``sampling_weight`` (inverse-probability weight that restores
    population prevalence under case-control sampling, S00-002). Factored out
    of ``scan_raw`` so it is unit-testable without raw ROOT data.
    """
    n_staves = int(stave_grid.shape[0])
    flat_stave = np.tile(np.arange(n_staves), len(event_numbers))
    flat_event = np.repeat(np.arange(len(event_numbers)), n_staves)
    kept_event = flat_event[keep_mask]
    kept_stave = flat_stave[keep_mask]
    kept_selected = selected_mask.ravel()[keep_mask].astype(bool)
    n_kept = int(keep_mask.sum())
    return pd.DataFrame(
        {
            "run": np.full(n_kept, int(run), dtype=int),
            "group": np.full(n_kept, str(group), dtype=object),
            "eventno": event_numbers[kept_event].astype(int),
            "stave": stave_grid[kept_stave],
            "amplitude_adc": amplitude[kept_event, kept_stave],
            "peak_height_adc": amplitude[kept_event, kept_stave],
            "peak_code_adc": peak_code_adc[kept_event, kept_stave],
            "saturation": saturation[kept_event, kept_stave],
            "area_adc_samples": area[kept_event, kept_stave],
            "peak_sample": peak_sample[kept_event, kept_stave].astype(int),
            "baseline_adc": baseline[kept_event, kept_stave],
            "selected": kept_selected.astype(int),
            "sampling_weight": case_control_sampling_weight(
                kept_selected, keep_selected, keep_rejected
            ),
        }
    )


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def raw_file(raw_root_dir: Path, run: int) -> Path:
    return raw_root_dir / f"hrdb_run_{run:04d}.root"


def sorted_file(sorted_b_dir: Path, run: int) -> Path:
    return sorted_b_dir / f"hrdb_run_{run:04d}-sorted.root"


def pulse_quantities(
    waveforms: np.ndarray,
    baseline_indices: List[int],
    polarity: np.ndarray | None = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    # Baseline via the versioned S00 selector (v1 = first-four median), so the
    # produced pulse table records the canonical estimator identically instead
    # of an inline np.median call (Issue #1109).
    # Polarity is applied after baseline subtraction (#954); never use abs().
    baseline = estimate_pedestal_v1_batched(waveforms, baseline_indices)
    corrected = waveforms - baseline[..., None]
    if polarity is not None:
        corrected = apply_polarity(corrected, polarity)
    amplitude = corrected.max(axis=-1)
    peak_sample = corrected.argmax(axis=-1)
    area = corrected.sum(axis=-1)
    return baseline, amplitude, peak_sample, area


def resolve_analysis_polarity(n_channels: int, config: dict | None = None) -> tuple[np.ndarray, dict]:
    """Load versioned channel polarity; fail closed if map is incomplete (#954)."""
    from sipm_waveC_gates import polarity_authorisation_report

    path = Path(os.environ.get(
        "CCB_CHANNEL_POLARITY_PATH",
        str(Path(__file__).resolve().parents[1] / "configs" / "channel_polarity_v1.json"),
    ))
    polarity_map = load_polarity_map(path)
    vec = polarity_map.polarity_vector(n_channels)
    if np.any(np.asarray(vec) == 0):
        raise ValueError(
            "channel polarity map contains unset (0) entries; refuse amplitude extraction (#954)"
        )
    meta = {
        "path": str(path),
        "version": polarity_map.version,
        "status": polarity_map.status,
        "channel_polarity": {str(i): int(vec[i]) for i in range(n_channels)},
    }
    auth = polarity_authorisation_report(polarity_map.status)
    meta.update(auth)
    require = True if config is None else bool(config.get("channel_polarity_required", True))
    if config is not None:
        meta["config_hint"] = require
    if require and not auth["authorising_waveform_amplitude_claims"]:
        raise ValueError(
            "channel polarity map is not authorising for amplitude/timing extraction: "
            + "; ".join(auth["blocked_reasons"])
            + " (#954)"
        )
    return vec, meta



def iter_raw_events(path: Path, step_size: int = 10000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    branches = ["EVENTNO", "EVT", "HRDv"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def init_count_dict() -> dict:
    return {
        "events_with_selected": 0,
        "selected_pulses": 0,
        "staves": defaultdict(int),
        "events_total": 0,
    }


def scan_raw(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, dict], pd.DataFrame, pd.DataFrame]:
    raw_root_dir = Path(config["raw_root_dir"])
    cut = float(config["amplitude_cut_adc"])
    baseline_indices = [int(i) for i in config["baseline_samples"]]
    samples_per_channel = int(config["samples_per_channel"])
    staves = {name: int(idx) for name, idx in config["staves"].items()}
    group_for_run = run_group_lookup(config)
    rng = np.random.default_rng(int(config["ml_check"]["random_seed"]))

    counts_by_run: List[dict] = []
    counts_by_group: Dict[str, dict] = defaultdict(init_count_dict)
    selected_frames: List[pd.DataFrame] = []
    # Population prevalence accumulators (pre-case-control-subsampling) so the
    # implementation-consistency check can document/report population prevalence
    # and de-bias case-control evaluation (audit S00-002).
    pop_total = 0
    pop_selected = 0
    keep_selected, keep_rejected = resolve_case_control_keep(config)
    ml_frames: List[pd.DataFrame] = []
    max_sample = int(config["ml_check"]["max_train_per_class"]) + int(config["ml_check"]["max_test_per_class"])
    stave_names = list(staves.keys())
    stave_channels = np.asarray([staves[name] for name in stave_names], dtype=int)
    stave_grid = np.asarray(stave_names)
    full_polarity, polarity_meta = resolve_analysis_polarity(8, config)
    stave_polarity = full_polarity[stave_channels]
    scan_raw.polarity_meta = polarity_meta  # type: ignore[attr-defined]

    for run in configured_runs(config):
        path = raw_file(raw_root_dir, run)
        if not path.exists():
            raise FileNotFoundError(f"Configured run {run} is missing: {path}")

        group = group_for_run[run]
        run_counts = init_count_dict()
        for batch in iter_raw_events(path):
            event_numbers = np.asarray(batch["EVENTNO"])
            evt_numbers = np.asarray(batch["EVT"])
            # ---- Per-event HRD waveform width contract (#952) ----
            # The legacy batch-level reshape (np.stack(...).reshape(-1, 8, N))
            # can silently mix ADC words across event boundaries: nine 8x16
            # events (9*128 words) reshape cleanly into eight 8x18 pseudo-events
            # (8*144 words) under an 8x18 config. Every event must pass the
            # per-event scalar-width gate BEFORE any stacking (fail closed).
            waveforms, hrd_summary = validate_and_reshape_rows(
                batch["HRDv"],
                n_channels=8,
                samples_per_channel=samples_per_channel,
            )
            if hrd_summary.malformed_events:
                raise ValueError(
                    "HRD waveform contract violation (#952): "
                    f"{hrd_summary.malformed_events}/{hrd_summary.events} events have "
                    f"width != {hrd_summary.expected_words} words "
                    f"({8}x{samples_per_channel}); recheck the versioned schema "
                    "before producing a pulse table. First malformed indices: "
                    f"{hrd_summary.malformed_indices[:10]}"
                )
            all_events = waveforms.astype(np.float64)
            waveforms = all_events[:, stave_channels, :]
            baseline, amplitude, peak_sample, area = pulse_quantities(
                waveforms, baseline_indices, polarity=stave_polarity
            )
# Absolute peak (raw max) for peak_code_adc and hardware saturation
            # flag (World-A diagnostic: legacy 14-bit CAEN-V1742 16383-code ceiling,
            # non-authorising per s00_saturation_field DIAGNOSTIC_ONLY_ADC_WORLD_UNRESOLVED).
            peak_code_adc = waveforms.max(axis=-1)
            saturation, _sat_meta = legacy_world_a_diagnostic(peak_code_adc)
            if not hasattr(scan_raw, 'saturation_contract'):
                scan_raw.saturation_contract = _sat_meta
            selected_mask = amplitude > cut
            event_selected = selected_mask.any(axis=1)

            run_counts["events_total"] += int(len(event_numbers))
            counts_by_group[group]["events_total"] += int(len(event_numbers))
            run_counts["events_with_selected"] += int(event_selected.sum())
            counts_by_group[group]["events_with_selected"] += int(event_selected.sum())
            run_counts["selected_pulses"] += int(selected_mask.sum())
            counts_by_group[group]["selected_pulses"] += int(selected_mask.sum())
            for idx, stave in enumerate(stave_names):
                stave_count = int(selected_mask[:, idx].sum())
                run_counts["staves"][stave] += stave_count
                counts_by_group[group]["staves"][stave] += stave_count

            event_idx, stave_idx = np.where(selected_mask)
            if len(event_idx):
                selected_frames.append(
                    pd.DataFrame(
                        {
                            "run": run,
                            "group": group,
                            "eventno": event_numbers[event_idx].astype(int),
                            "evt": evt_numbers[event_idx].astype(int),
                            "stave": stave_grid[stave_idx],
                            "channel": stave_channels[stave_idx].astype(int),
                            "baseline_adc": baseline[event_idx, stave_idx],
                            "amplitude_adc": amplitude[event_idx, stave_idx],
                            "peak_code_adc": peak_code_adc[event_idx, stave_idx],
                            "saturation": saturation[event_idx, stave_idx],
                            "peak_sample": peak_sample[event_idx, stave_idx].astype(int),
                            "area_adc_samples": area[event_idx, stave_idx],
                        }
                    )
                )

            flat_selected = selected_mask.ravel()
            # Case-control subsample for the bounded implementation-consistency
            # check; the per-class cap is applied after all runs so held-out runs
            # remain represented. The keep rates are config/env-driven
            # (resolve_case_control_keep) and each kept row carries an
            # inverse-probability sampling_weight so held-out evaluation can
            # restore population prevalence (audit S00-002).
            pop_total += int(flat_selected.shape[0])
            pop_selected += int(flat_selected.sum())
            keep_probability = np.where(flat_selected, keep_selected, keep_rejected)
            keep = rng.random(flat_selected.shape[0]) < keep_probability
            if keep.any():
                ml_frames.append(
                    build_ml_rows_for_batch(
                        run=run,
                        group=group,
                        event_numbers=event_numbers,
                        stave_grid=stave_grid,
                        amplitude=amplitude,
                        area=area,
                        peak_sample=peak_sample,
                        baseline=baseline,
                        peak_code_adc=peak_code_adc,
                        saturation=saturation,
                        selected_mask=selected_mask,
                        keep_mask=keep,
                        keep_selected=keep_selected,
                        keep_rejected=keep_rejected,
                    )
                )

        row = {
            "run": run,
            "group": group,
            "events_total": run_counts["events_total"],
            "events_with_selected": run_counts["events_with_selected"],
            "selected_pulses": run_counts["selected_pulses"],
        }
        row.update({stave: int(run_counts["staves"][stave]) for stave in staves})
        counts_by_run.append(row)

    group_rows = []
    for group in config["run_groups"]:
        counts = counts_by_group[group]
        row = {
            "group": group,
            "events_total": counts["events_total"],
            "events_with_selected": counts["events_with_selected"],
            "selected_pulses": counts["selected_pulses"],
        }
        row.update({stave: int(counts["staves"][stave]) for stave in staves})
        group_rows.append(row)

    selected = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
    ml_rows = pd.concat(ml_frames, ignore_index=True) if ml_frames else pd.DataFrame()
    from ccb_mc_validation.statistics.case_control import apply_second_stage_class_cap

    sampling_design_manifest = {
        "stages": ["case_control_bernoulli"],
        "keep_selected": float(keep_selected),
        "keep_rejected": float(keep_rejected),
        "max_sample_per_class": int(max_sample),
    }
    if not ml_rows.empty:
        ml_rows, cap_manifest = apply_second_stage_class_cap(
            ml_rows,
            max_sample=max_sample,
            random_seed=int(config["ml_check"]["random_seed"]),
        )
        sampling_design_manifest.update(cap_manifest)
    population_prevalence = {
        "selected": int(pop_selected),
        "total": int(pop_total),
        "prevalence": float(pop_selected / pop_total) if pop_total else float("nan"),
        "sampling_design": sampling_design_manifest,
    }
    return (
        pd.DataFrame(counts_by_run),
        pd.DataFrame(group_rows),
        counts_by_group,
        selected,
        ml_rows,
        population_prevalence,
    )


def compare_expected(config: dict, counts_by_group: pd.DataFrame) -> pd.DataFrame:
    expected = config["expected_counts"]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": int(counts_by_group["selected_pulses"].sum()),
            "tolerance": 0,
        }
    ]
    for group, group_expected in expected["groups"].items():
        row = counts_by_group[counts_by_group["group"] == group].iloc[0]
        if "events" in group_expected:
            rows.append(
                {
                    "quantity": f"{group} events with selected pulse",
                    "report_value": int(group_expected["events"]),
                    "reproduced": int(row["events_with_selected"]),
                    "tolerance": 0,
                }
            )
        if "pulses" in group_expected:
            rows.append(
                {
                    "quantity": f"{group} selected pulses",
                    "report_value": int(group_expected["pulses"]),
                    "reproduced": int(row["selected_pulses"]),
                    "tolerance": 0,
                }
            )
        for stave, value in group_expected.get("staves", {}).items():
            rows.append(
                {
                    "quantity": f"{group} {stave} selected pulses",
                    "report_value": int(value),
                    "reproduced": int(row[stave]),
                    "tolerance": 0,
                }
            )

    result = pd.DataFrame(rows)
    result["delta"] = result["reproduced"] - result["report_value"]
    result["pass"] = result["delta"].abs() <= result["tolerance"]
    return result[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def sorted_crosscheck(config: dict) -> pd.DataFrame:
    """Like-for-like selection crosscheck + waveform identity vs the sorted-B tree.

    The sorted tree stores per event: ``hrd/hrd.sample`` (baseline-subtracted,
    sign-inverted on the odd duplicate channels per the duplicate-readout
    convention), ``hrd/hrd.baseline`` (per-channel pedestal broadcast across
    the channel's samples), and ``hrdMax`` (max of the sorted pipeline's OWN
    firmware-baseline-subtracted samples). Counting ``hrdMax > cut`` is NOT
    comparable to the raw-side pulse_schema_v1 selector (first-four-median
    baseline): on run 44 hrdMax exceeds the raw-path amplitude by a mean
    +149 ADC, and its near-threshold selection counts exceed the raw counts on
    every run — two different estimators, not two different datasets.

    This crosscheck instead RECONSTRUCTS the absolute word frame from the
    sorted tree (``baseline + polarity * sample``, polarity from the SAME
    authorising map as scan_raw) and (a) verifies cell-exact identity with the
    raw HRDv frame of the same EVT number — the staging-integrity detector
    that would have caught the 128-word truncation desync (#952) — and
    (b) runs the identical pulse_quantities selector on the reconstructed
    words, so the per-run counts are comparable at zero tolerance.
    """
    sorted_b_dir = Path(config["sorted_b_dir"])
    raw_root_dir = Path(config["raw_root_dir"])
    cut = float(config["amplitude_cut_adc"])
    baseline_indices = [int(i) for i in config["baseline_samples"]]
    samples_per_channel = int(config["samples_per_channel"])
    n_channels = 8
    staves = {name: int(idx) for name, idx in config["staves"].items()}
    stave_names = list(staves.keys())
    stave_channels = np.asarray([staves[name] for name in stave_names], dtype=int)
    full_polarity, _polarity_meta = resolve_analysis_polarity(n_channels, config)
    stave_polarity = full_polarity[stave_channels]
    # Per-channel polarity repeated across that channel's sample slots.
    sign_row = np.repeat(np.asarray(full_polarity, dtype=np.int64), samples_per_channel)
    rows = []
    for run in configured_runs(config):
        path = sorted_file(sorted_b_dir, run)
        if not path.exists():
            raise FileNotFoundError(f"Configured run {run} is missing: {path}")
        raw_path = raw_file(raw_root_dir, run)
        if not raw_path.exists():
            raise FileNotFoundError(f"Configured run {run} is missing: {raw_path}")
        counts = defaultdict(int)
        events_with_selected = 0
        events_total = 0
        exact_events = 0
        mismatch_cells = 0
        evt_mismatch = 0
        raw_tree = uproot.open(raw_path)["h101"]
        sorted_tree = uproot.open(path)["tree"]
        n_raw, n_sorted = raw_tree.num_entries, sorted_tree.num_entries
        raw_iter = raw_tree.iterate(["EVT", "HRDv"], step_size=10000, library="np")
        sorted_iter = sorted_tree.iterate(
            ["hrdEvtNo", "hrd/hrd.sample", "hrd/hrd.baseline"],
            step_size=10000,
            library="np",
        )
        while True:
            rb = next(raw_iter, None)
            sb = next(sorted_iter, None)
            if rb is None or sb is None:
                break
            r_evt = np.asarray(rb["EVT"])
            s_evt = np.asarray(sb["hrdEvtNo"])
            n_pair = min(len(r_evt), len(s_evt))
            evt_mismatch += abs(len(r_evt) - len(s_evt))
            evt_mismatch += int((r_evt[:n_pair] != s_evt[:n_pair]).sum())
            R = np.vstack([np.asarray(w, dtype=np.int64) for w in rb["HRDv"][:n_pair]])
            S = np.vstack([np.asarray(x, dtype=np.int64) for x in sb["hrd/hrd.sample"][:n_pair]])
            B = np.vstack([np.asarray(x, dtype=np.int64) for x in sb["hrd/hrd.baseline"][:n_pair]])
            if R.shape[1] != sign_row.size or S.shape[1] != sign_row.size:
                raise ValueError(
                    "sorted crosscheck width contract (#952): expected "
                    f"{sign_row.size} words/event ({n_channels}x{samples_per_channel}), "
                    f"got raw {R.shape[1]} / sorted {S.shape[1]}"
                )
            reconstructed = B + sign_row * S
            mismatch_cells += int((reconstructed != R).sum())
            exact_events += int((reconstructed == R).all(axis=1).sum())
            events_total += n_pair
            waveforms = reconstructed.astype(np.float64).reshape(n_pair, n_channels, samples_per_channel)
            waveforms = waveforms[:, stave_channels, :]
            _, amplitude, _, _ = pulse_quantities(
                waveforms, baseline_indices, polarity=stave_polarity
            )
            selected_mask = amplitude > cut
            events_with_selected += int(selected_mask.any(axis=1).sum())
            for idx, stave in enumerate(stave_names):
                counts[stave] += int(selected_mask[:, idx].sum())
        evt_mismatch += abs(n_raw - n_sorted)
        row = {
            "run": run,
            "events_with_selected": events_with_selected,
            "selected_pulses": sum(counts.values()),
            "identity_events": events_total,
            "identity_exact_events": exact_events,
            "identity_mismatch_cells": mismatch_cells,
            "identity_evt_mismatches": evt_mismatch,
        }
        row.update({stave: int(counts[stave]) for stave in stave_names})
        rows.append(row)
    return pd.DataFrame(rows)


def run_ml_check(
    config: dict,
    ml_rows: pd.DataFrame,
    out_dir: Path,
    *,
    population_prevalence: Optional[dict] = None,
) -> pd.DataFrame:
    """S00 *implementation consistency check* (NOT a scientific benchmark).

    The label is deterministic (``selected = amplitude > cut``), so this checks
    that the run-split logistic fit is *consistent* with the deterministic rule
    using only NON-target-defining features (``amplitude_adc`` is excluded by
    :func:`resolve_ml_features` -- leakage guard, audit S00-001). Metrics are
    reported both raw (case-control, prevalence-distorted) and inverse-probability
    weighted so the population prevalence is restored (audit S00-002). The
    accuracy interval uses a ``(run, event)`` cluster bootstrap so pulses from
    one DAQ event move together (audit STAT-002).
    """
    from sklearn.calibration import calibration_curve
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.preprocessing import StandardScaler

    from ccb_mc_validation.statistics.bootstrap import weighted_cluster_bootstrap, weighted_mean

    # S00-001 leakage guard: raises if amplitude_adc (target-defining) is a feature.
    features = resolve_ml_features(config)
    n_boot = resolve_ml_bootstrap_reps(config)
    heldout = set(int(run) for run in config["ml_check"]["heldout_runs"])
    train = ml_rows[~ml_rows["run"].isin(heldout)].copy()
    test = ml_rows[ml_rows["run"].isin(heldout)].copy()
    c_values = [float(value) for value in config["ml_check"]["regularization_c"]]
    if "sampling_weight" not in train.columns or "sampling_weight" not in test.columns:
        raise ValueError(
            "sampling_weight is required for group-aware weighted ML selection "
            "(issue #959); refusing silent unweighted fallback"
        )
    if "eventno" not in train.columns or "eventno" not in test.columns:
        raise ValueError(
            "eventno is required for group-aware folds (issue #959); "
            "refusing row-wise StratifiedKFold leakage"
        )
    w_train = train["sampling_weight"].to_numpy(dtype=float)
    w_test = test["sampling_weight"].to_numpy(dtype=float)
    sw = w_test
    if np.any(w_train < 0) or np.any(w_test < 0) or not np.all(np.isfinite(w_train)) or not np.all(np.isfinite(w_test)):
        raise ValueError("sampling_weight must be finite and nonnegative")
    if float(np.sum(w_train)) <= 0 or float(np.sum(w_test)) <= 0:
        raise ValueError("sampling_weight sums must be positive")
    train_groups = make_run_event_clusters(train["run"].to_numpy(), train["eventno"].to_numpy())
    n_groups = int(len(set(train_groups.tolist())))
    n_splits = int(config["ml_check"]["cv_folds"])
    if n_groups < n_splits:
        raise ValueError(
            f"group-aware CV requires >= n_splits groups; got {n_groups} < {n_splits}"
        )
    cv = StratifiedGroupKFold(
        n_splits=n_splits,
        shuffle=True,
        random_state=int(config["ml_check"]["random_seed"]),
    )

    def _fit_scaled_logistic(X, y, weights, C):
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
        clf = LogisticRegression(C=float(C), max_iter=1000, solver="lbfgs")
        try:
            clf.fit(Xs, y, sample_weight=weights)
        except TypeError as exc:
            raise RuntimeError(
                "LogisticRegression rejected sample_weight; refusing silent "
                f"unweighted fallback (issue #959). sklearn error: {exc}"
            ) from exc
        return scaler, clf

    def _weighted_group_roc_auc(X, y, groups, weights, C):
        scores = []
        fold_rows = []
        X_arr = np.asarray(X, dtype=float)
        y_arr = np.asarray(y)
        for fold_id, (tr_idx, te_idx) in enumerate(cv.split(X_arr, y_arr, groups)):
            if set(groups[tr_idx]).intersection(groups[te_idx]):
                raise ValueError("group leakage detected in StratifiedGroupKFold split")
            scaler, clf = _fit_scaled_logistic(X_arr[tr_idx], y_arr[tr_idx], weights[tr_idx], C)
            proba = clf.predict_proba(scaler.transform(X_arr[te_idx]))[:, 1]
            score = float(roc_auc_score(y_arr[te_idx], proba, sample_weight=weights[te_idx]))
            scores.append(score)
            fold_rows.append(
                {
                    "fold": int(fold_id),
                    "n_train": int(len(tr_idx)),
                    "n_test": int(len(te_idx)),
                    "n_train_groups": int(len(set(groups[tr_idx].tolist()))),
                    "n_test_groups": int(len(set(groups[te_idx].tolist()))),
                    "roc_auc_weighted": score,
                }
            )
        return scores, fold_rows

    cv_rows = []
    fold_assignment_rows = []
    X_train = train[features]
    y_train = train["selected"]
    for c_value in c_values:
        scores, fold_rows = _weighted_group_roc_auc(
            X_train, y_train, train_groups, w_train, c_value
        )
        for row in fold_rows:
            fold_assignment_rows.append({"C": float(c_value), **row})
        cv_rows.append(
            {
                "C": c_value,
                "cv_roc_auc_mean": float(np.mean(scores)),
                "cv_roc_auc_std": float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0,
                "grouping_key": "(run,event)",
                "scoring": "roc_auc_sample_weight",
                "sklearn_version": __import__("sklearn").__version__,
            }
        )
    best_c = max(cv_rows, key=lambda row: row["cv_roc_auc_mean"])["C"]

    # Group-aware isotonic calibration with sample weights; no Pipeline/sample_weight
    # API gap and no silent unweighted fallback (issue #959).
    from sklearn.isotonic import IsotonicRegression

    cal_splits = min(3, n_groups)
    if cal_splits < 2:
        raise ValueError("calibration requires >=2 train groups")
    cal_cv = StratifiedGroupKFold(
        n_splits=cal_splits,
        shuffle=True,
        random_state=int(config["ml_check"]["random_seed"]) + 1,
    )
    X_train_arr = np.asarray(train[features], dtype=float)
    y_train_arr = np.asarray(train["selected"])
    oof = np.full(len(train), np.nan, dtype=float)
    for tr_idx, te_idx in cal_cv.split(X_train_arr, y_train_arr, train_groups):
        if set(train_groups[tr_idx]).intersection(train_groups[te_idx]):
            raise ValueError("group leakage detected in calibration folds")
        scaler, clf = _fit_scaled_logistic(
            X_train_arr[tr_idx], y_train_arr[tr_idx], w_train[tr_idx], best_c
        )
        oof[te_idx] = clf.predict_proba(scaler.transform(X_train_arr[te_idx]))[:, 1]
    if not np.all(np.isfinite(oof)):
        raise RuntimeError("calibration OOF probabilities incomplete; refuse unweighted fallback")
    try:
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(oof, y_train_arr, sample_weight=w_train)
    except TypeError as exc:
        raise RuntimeError(
            "IsotonicRegression rejected sample_weight; refusing silent unweighted "
            f"fallback (issue #959). sklearn error: {exc}"
        ) from exc
    # Final base model on all train rows; apply OOF-fit calibrator to held-out runs.
    final_scaler, final_clf = _fit_scaled_logistic(X_train_arr, y_train_arr, w_train, best_c)
    raw_test = final_clf.predict_proba(final_scaler.transform(np.asarray(test[features], dtype=float)))[:, 1]
    probability = calibrator.transform(raw_test)
    predicted = probability >= 0.5
    y_test = test["selected"].to_numpy()

    # ---- Prevalence bookkeeping (audit S00-002) ----
    pop = population_prevalence or {}
    cc_prevalence = float(np.mean(y_test)) if len(y_test) else float("nan")
    if sw is not None and len(y_test) and float(np.sum(sw)) > 0:
        weighted_prevalence = float(np.sum(sw * y_test) / np.sum(sw))
    else:
        weighted_prevalence = cc_prevalence

    # ---- Weighted held-out metrics (S00-002: restore population prevalence) ----
    kw = {"sample_weight": sw} if sw is not None else {}
    weighted_accuracy = (
        float(np.sum(sw * (predicted == y_test)) / np.sum(sw))
        if sw is not None else float(np.mean(predicted == y_test))
    )
    weighted_brier = float(brier_score_loss(y_test, probability, **kw))
    weighted_roc_auc = float(roc_auc_score(y_test, probability, **kw))
    weighted_ap = float(average_precision_score(y_test, probability, **kw))

    # ---- (run, event) cluster bootstrap of WEIGHTED accuracy (issues #960) ----
    rng = np.random.default_rng(int(config["ml_check"]["random_seed"]))
    correctness = (predicted == y_test).astype(float)
    bootstrap_status = "NOT_ESTIMABLE"
    bootstrap_meta = {
        "n_boot_requested": int(n_boot),
        "n_boot_success": 0,
        "n_boot_failure": 0,
        "n_clusters": 0,
        "effective_sample_size": float("nan"),
        "estimand": "pulse_ipw_accuracy",
        "resampling_unit": "(run,event)_cluster",
    }
    if len(correctness) and len(test):
        clusters = make_run_event_clusters(test["run"].to_numpy(), test["eventno"].to_numpy())
        try:
            boot = weighted_cluster_bootstrap(
                correctness, sw, clusters, rng, n_boot=n_boot, alpha=0.05
            )
            lo = float(boot["ci_low"])
            hi = float(boot["ci_high"])
            bootstrap_status = str(boot["status"])
            bootstrap_meta.update(
                {
                    "n_boot_success": int(boot["n_boot_success"]),
                    "n_boot_failure": int(boot["n_boot_failure"]),
                    "n_clusters": int(boot["n_clusters"]),
                    "effective_sample_size": float(boot["effective_sample_size"]),
                }
            )
            # Point estimate must match the same estimand as the CI.
            weighted_accuracy = float(boot["point"])
        except ValueError:
            # Fail closed: never emit a falsely precise zero-width interval (#960).
            lo = float("nan")
            hi = float("nan")
            bootstrap_status = "NOT_ESTIMABLE"
    else:
        lo = float("nan")
        hi = float("nan")

    # ---- Reference rule (label = rule; trivially perfect by construction) ----
    deterministic = test["amplitude_adc"].to_numpy() > float(config["amplitude_cut_adc"])

    ml_summary = pd.DataFrame(
        [
            {
                "method": "reference: deterministic amplitude-cut rule (label=rule, tautological)",
                "heldout_runs": ",".join(str(run) for run in sorted(heldout)),
                "metric": "selection accuracy",
                "value": float(np.mean(deterministic == y_test)) if len(y_test) else float("nan"),
                "ci_low": float("nan"),
                "ci_high": float("nan"),
                "roc_auc": float("nan"),
                "average_precision": float("nan"),
                "brier": float("nan"),
                "weighted_value": float("nan"),
                "notes": (
                    "Implementation-consistency reference, NOT a benchmark: the label "
                    "is DEFINED as amplitude > cut, so this rule reproduces it with "
                    "probability 1 by construction. Excluded from scientific claims."
                ),
            },
            {
                "method": "implementation-consistency: calibrated logistic regression",
                "heldout_runs": ",".join(str(run) for run in sorted(heldout)),
                "metric": "selection accuracy",
                "value": float(np.mean(predicted == y_test)) if len(y_test) else float("nan"),
                "ci_low": lo,
                "ci_high": hi,
                "roc_auc": weighted_roc_auc,
                "average_precision": weighted_ap,
                "brier": weighted_brier,
                "weighted_value": weighted_accuracy,
                "features": ",".join(features),
                "n_boot": int(n_boot),
                "cluster_unit": "(run,event)",
                "bootstrap_status": bootstrap_status,
                "bootstrap_n_success": int(bootstrap_meta["n_boot_success"]),
                "bootstrap_n_failure": int(bootstrap_meta["n_boot_failure"]),
                "bootstrap_n_clusters": int(bootstrap_meta["n_clusters"]),
                "bootstrap_ess": float(bootstrap_meta["effective_sample_size"]),
                "estimand": "pulse_ipw_accuracy",
                "cc_prevalence": cc_prevalence,
                "weighted_prevalence": weighted_prevalence,
                "population_prevalence": float(pop.get("prevalence", float("nan"))),
                "notes": (
                    "Implementation-consistency check, NOT a scientific benchmark. "
                    "Features exclude the target-defining column (amplitude_adc). "
                    "Metrics are inverse-probability weighted (two-stage HT when the "
                    "per-class cap binds; issue #958). Model selection uses "
                    "StratifiedGroupKFold + weighted ROC-AUC with no unweighted "
                    f"fallback (#959). CI uses weighted (run,event) cluster bootstrap "
                    f"(#960); status={bootstrap_status}."
                ),
            },
        ]
    )
    pd.DataFrame(cv_rows).to_csv(out_dir / "ml_cv_scan.csv", index=False)
    pd.DataFrame(fold_assignment_rows).to_csv(out_dir / "ml_cv_fold_assignments.csv", index=False)
    ml_summary.to_csv(out_dir / "implementation_consistency.csv", index=False)

    try:
        frac_pos, mean_pred = calibration_curve(
            y_test, probability, n_bins=10, strategy="quantile", sample_weight=sw
        )
    except TypeError as exc:
        raise RuntimeError(
            "calibration_curve rejected sample_weight; refusing silent unweighted "
            f"fallback (issue #959). sklearn error: {exc}"
        ) from exc
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot([0, 1], [0, 1], color="black", lw=1, linestyle="--")
    ax.plot(mean_pred, frac_pos, marker="o")
    ax.set_xlabel("Mean predicted probability (case-control subsample)")
    ax.set_ylabel("Observed selected fraction")
    ax.set_title(
        "S00 implementation-consistency calibration\n"
        f"cc prevalence={cc_prevalence:.3f} vs weighted={weighted_prevalence:.3f}"
    )
    fig.tight_layout()
    fig.savefig(out_dir / "fig_ml_reliability.png", dpi=160)
    plt.close(fig)

    return ml_summary


def write_checksums(
    config: dict,
    out_dir: Path,
    *,
    skip_sorted: bool = False,
) -> pd.DataFrame:
    """Hash inputs that exist/were consumed; record missing expected inputs (#973).

    ``--skip-sorted`` no longer requires ``--skip-sha256``. Raw hashes are always
    retained when raw files exist. Sorted files skipped by gate state are recorded
    with an explicit ``missing_reason`` instead of unconditionally opening them.
    """
    rows: List[dict] = []

    def _append(
        path: Path,
        *,
        role: str,
        expected: bool,
        consumed: bool,
        missing_reason: str | None = None,
    ) -> None:
        present = path.is_file()
        if present:
            rows.append(
                {
                    "file": str(path),
                    "role": role,
                    "expected_input": bool(expected),
                    "present": True,
                    "consumed": bool(consumed),
                    "sha256": sha256_file(path),
                    "bytes": int(path.stat().st_size),
                    "missing_reason": None if consumed else (missing_reason or "not_consumed"),
                }
            )
            return
        rows.append(
            {
                "file": str(path),
                "role": role,
                "expected_input": bool(expected),
                "present": False,
                "consumed": False,
                "sha256": None,
                "bytes": None,
                "missing_reason": missing_reason or "missing_file",
            }
        )

    for path in sorted(Path("data/raw").glob("**/*")):
        if path.is_file():
            _append(path, role="data_raw_tree", expected=False, consumed=True)

    raw_root = Path(config["raw_root_dir"])
    sorted_b = Path(config.get("sorted_b_dir") or "")
    for run in configured_runs(config):
        _append(
            raw_file(raw_root, run),
            role="raw_root",
            expected=True,
            consumed=True,
            missing_reason="missing_raw_root",
        )
        sorted_path = (
            sorted_file(sorted_b, run)
            if str(sorted_b)
            else Path(f"hrdb_run_{run:04d}-sorted.root")
        )
        if skip_sorted:
            reason = "skip_sorted" if not sorted_path.is_file() else "not_consumed_skip_sorted"
            _append(
                sorted_path,
                role="sorted_b",
                expected=True,
                consumed=False,
                missing_reason=reason,
            )
        else:
            _append(
                sorted_path,
                role="sorted_b",
                expected=True,
                consumed=True,
                missing_reason="missing_sorted_root",
            )

    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "input_sha256.csv", index=False)
    return df


def make_figures(counts_by_run: pd.DataFrame, selected: pd.DataFrame, out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(counts_by_run["run"].astype(str), counts_by_run["selected_pulses"], color="#3b6ea8")
    ax.set_xlabel("Run")
    ax.set_ylabel("Selected B-stave pulses")
    ax.set_title("S00 selected pulses by run")
    ax.tick_params(axis="x", labelrotation=90)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_counts_by_run.png", dpi=160)
    plt.close(fig)

    group_staves = selected.groupby(["group", "stave"]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(8, 4))
    group_staves.plot(kind="bar", ax=ax)
    ax.set_xlabel("Run group")
    ax.set_ylabel("Selected pulses")
    ax.set_title("S00 selected pulses by group and stave")
    ax.tick_params(axis="x", labelrotation=30)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_counts_by_group_stave.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    for stave, subset in selected.groupby("stave"):
        values = np.log10(subset["amplitude_adc"].to_numpy())
        ax.hist(values, bins=60, histtype="step", linewidth=1.4, label=stave)
    ax.set_xlabel("log10(amplitude ADC)")
    ax.set_ylabel("Selected pulses")
    ax.set_title("S00 selected-pulse amplitude distributions")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_amplitude_distributions.png", dpi=160)
    plt.close(fig)


# --- Publication-transaction safety (ARU-S00-OVERRIDE-ARTIFACT-001, #1110) ----------
# Canonical S00 artifacts may only be replaced by the canonical selector/config under
# an explicit AUTHORISING transaction. Alternate thresholds digitize into an isolated,
# self-describing sensitivity namespace. Every run stages to a temp dir and publishes
# atomically only after all P0 gates pass; a failing/non-authorising or interrupted run
# leaves the last authorising artifact set byte-identical.
SENSITIVITY_SUBDIR = "sensitivity"



def git_source_commit() -> str:
    """Best-effort source commit hash for model identity (never fails the run)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False, cwd=Path(__file__).parent.parent,
        )
        rev = out.stdout.strip()
        return rev if rev else "unknown"
    except Exception:
        return "unknown"


def config_digest(config: dict, cut: float, cut_source: str) -> str:
    """Stable model-identity digest: config + effective cut + its provenance.

    The canonical config is digested WITHOUT mutating it (the effective cut is
    folded in explicitly so M1 != M2 (different thresholds) never collide.
    """
    identity = {
        "config": config,
        "effective_amplitude_cut_adc": cut,
        "amplitude_cut_source": cut_source,
    }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]


def is_canonical_run(config: dict, cut: float, cut_source: str) -> bool:
    """True only when the run uses the canonical config threshold from config.

    CLI/env overrides are sensitivity runs by policy (H1): they must never touch
    the canonical 1000-ADC artifacts. Precedence CLI > env > config, so a match
    against the config value is only authoritative when the source IS the config.
    """
    cfg_val = float(config["amplitude_cut_adc"])
    return cut == cfg_val and cut_source.startswith("config(")


def resolve_output_namespace(config: dict, cut: float, cut_source: str) -> Tuple[Path, Path]:
    """Return (output_dir, pulse_table_path) bound to the run's model identity.

    Canonical runs inherit the canonical paths (published transactionally).
    Sensitivity runs get an isolated, parameter-bound namespace so a 500-ADC
    study can never be resolved under the canonical pulse-table path.
    """
    if is_canonical_run(config, cut, cut_source):
        return Path(config["output_dir"]), Path(config["pulse_table_path"])
    out_dir = Path(config["output_dir"]) / SENSITIVITY_SUBDIR / f"amplitude_cut_adc={cut:g}"
    slug = Path(config["pulse_table_path"]).stem
    table = out_dir / f"{slug}.csv.gz"
    return out_dir, table


def atomic_publish(staging_dir: Path, target_dir: Path) -> None:
    """Atomically replace target_dir's contents with staging_dir's.

    Writes go to a sibling temp dir that is renamed over the target only after
    all gates pass. On any left-over staging from a prior interrupted run the
    rename is still atomic (POSIX rename). The canonical namespace is only
    touched by this transaction, never by direct writes. Stale staging dirs
    from interrupted prior runs are swept once the new set is in place.
    """
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    # The publish temp dir MUST NOT share main()'s staging-name formula
    # (`.{name}.staging-{pid}`): sharing it made the rmtree guard below delete
    # the run's own staging before the rename, so every authorising publish
    # self-destructed (found on the #952 corrected-staging rerun, 2026-08-16).
    tmp = target_dir.parent / f".{target_dir.name}.publish-{os.getpid()}"
    if tmp.exists():
        shutil.rmtree(tmp)
    staging_dir.rename(tmp)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    tmp.rename(target_dir)
    # Sweep staging dirs left over from interrupted prior runs; the canonical
    # namespace is now authoritative so none of them can become visible.
    for stale in target_dir.parent.glob(f".{target_dir.name}.staging-*"):
        shutil.rmtree(stale, ignore_errors=True)


def write_manifest(out_dir: Path, config_path: Path, comparison: pd.DataFrame, selected_path: Path,
                   amplitude_cut_adc: float, amplitude_cut_source: str, *,
canonical: bool, model_identity: dict, gate_states: dict,
                   input_hashes: Optional[dict] = None,
                   saturation_contract: Optional[dict] = None) -> None:
    """Write self-describing manifest with model identity + gate state.

    Every downstream consumer must resolve artifacts via this model-bound
    manifest rather than assuming a mutable canonical path is authoritative
    (ARU-S00-OVERRIDE-ARTIFACT-001 acceptance: downstream resolves via a
model-bound manifest/pointer). An authorising run requires every P0 gate
    to be PASS (issue #972): a skipped or failed gate is recorded as a
    non-authorising condition, never fabricated as a measured PASS.
    """
    passed = bool(comparison["pass"].all()) if len(comparison) else False
    authorising = bool(
        canonical
        and passed
        and gate_states.get("sorted_even_channel_crosscheck") == GATE_PASS
        and gate_states.get("sorted_waveform_identity") == GATE_PASS
    )
    manifest = {
        "config": str(config_path),
        "schema_version": SCHEMA_VERSION,
        "model_identity": model_identity,
        "claim_status": "canonical-authorising" if authorising else "sensitivity-only",
        "canonical": canonical,
        "count_match_passed": passed,
        "authorising": authorising,
        "selected_pulse_table": str(selected_path),
        "amplitude_cut_adc": float(amplitude_cut_adc),
        "amplitude_cut_source": amplitude_cut_source,
        "amplitude_cut_env_var": AMPLITUDE_CUT_ENV,
        "input_sha256": input_hashes or {},
        "gate_states": {k: v for k, v in sorted(gate_states.items())},
        "saturation_field": saturation_contract or {"contract": "not_recorded"},
        "artifacts": sorted(path.name for path in out_dir.iterdir() if path.is_file()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def write_sensitivity_report(out_dir: Path, cut: float, cut_source: str, counts_by_group: pd.DataFrame,
                             canonical_expected: pd.DataFrame) -> None:
    """Sensitivity contract for non-canonical thresholds (H1).

    Replaces the exact-closure fixed-count comparison with the correct
    sensitivity semantics: report the effective threshold, the selection counts
    and a migration matrix vs the canonical 1000-ADC expected counts (retained
    only as a canonical negative/control gate, never as an exact-closure gate).
    """
    summary = {
        "effective_amplitude_cut_adc": float(cut),
        "amplitude_cut_source": cut_source,
        "claim_status": "sensitivity-only",
        "note": (
            "Non-canonical threshold: exact-count closure against the canonical "
            "1000-ADC expected_counts is NOT expected. Canonical expected counts "
            "are retained only as a negative/control reference (selection shrinks "
            "as the threshold rises)."
        ),
    }
    summary_df = pd.DataFrame([summary])
    summary_df.to_csv(out_dir / "sensitivity_summary.csv", index=False)

    total = int(counts_by_group["selected_pulses"].sum())
    canonical_total = int(canonical_expected.loc[
        canonical_expected["quantity"] == "total selected B-stave pulses", "report_value"
    ].iloc[0]) if len(canonical_expected) and (
        canonical_expected["quantity"] == "total selected B-stave pulses"
    ).any() else None
    migration = pd.DataFrame(
        [{
            "quantity": "total selected B-stave pulses",
            "canonical_1000_adc_expected": canonical_total,
            "this_threshold_selected": total,
            "delta_vs_canonical": (total - canonical_total) if canonical_total is not None else None,
        }]
    )
    migration.to_csv(out_dir / "sensitivity_migration_matrix.csv", index=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/s00_reproduction.yaml", type=Path)
    parser.add_argument("--skip-ml", action="store_true", help="Skip the run-split ML sanity check.")
    parser.add_argument("--skip-sha256", action="store_true", help="Skip checksum manifest generation.")
    parser.add_argument("--skip-sorted", action="store_true", help="Skip the sorted even-channel crosscheck (no sorted ROOT available).")
    parser.add_argument(
        "--amplitude-cut-adc",
        type=float,
        default=None,
        help="Override the config amplitude_cut_adc [ADC]. Precedence: this flag "
             "> env CCB_AMPLITUDE_CUT_ADC > the YAML config value. Sensitivity runs "
             "publish to an isolated parameter-bound namespace (ARU-S00-OVERRIDE-ARTIFACT-001).",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    # The named v1 selector is a fixed semantic object, not a free YAML axis.
    # Validate immediately after YAML parsing and before namespace resolution,
    # staging creation, raw-file traversal, or ROOT access (#1141).
    try:
        validate_s00_selector_contract(config)
    except S00SelectorConfigError as exc:
        print(f"[s00] selector/config preflight failed: {exc}")
        return 2

    # Resolve the amplitude cut once and propagate it into the in-memory config
    # so every consumer (scan_raw, sorted_crosscheck, run_ml_check) reads the
    # SAME overridden value. The YAML file is never modified.
    cut, cut_source = resolve_amplitude_cut(config, args.amplitude_cut_adc)
    config["amplitude_cut_adc"] = cut

    # ---- Model identity and namespace (ARU-S00-OVERRIDE-ARTIFACT-001) ----
    # Resolve the effective config/model BEFORE creating output paths. Determine
    # whether this is a canonical production run (authorising) or a sensitivity
    # run (isolated, self-describing, non-authorising).
    canonical = is_canonical_run(config, cut, cut_source)
    model_id = config_digest(config, cut, cut_source)
    src_commit = git_source_commit()
    out_dir, selected_path = resolve_output_namespace(config, cut, cut_source)

    # ---- Staging directory ----
    # All writes go to a staging dir first. On successful completion of all P0
    # gates, the staging is atomically published to the canonical namespace.
    # A failing/non-authorising run leaves the last authorising artifact set
    # byte-identical (invariant: rollback/atomicity).
    staging = out_dir.parent / f".{out_dir.name}.staging-{os.getpid()}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    staging_selected = staging / selected_path.name
    staging_selected.parent.mkdir(parents=True, exist_ok=True)

    # ---- Run the selector ----
    counts_by_run, counts_by_group, _, selected, ml_rows, population_prevalence = scan_raw(config)

    # ---- Gate: fixed-count comparison ----
    # For sensitivity runs the fixed-count expected comparison is a negative/control
    # reference only (selection shrinks as the threshold rises, so exact closure is
    # NOT expected). We still compute it for diagnostic output but the return code
    # is governed by the sensitivity contract, not the fixed-count gate.
    comparison = compare_expected(config, counts_by_group)
    fixed_count_pass = bool(comparison["pass"].all()) if len(comparison) else True

    # ---- Gate: sorted even-channel crosscheck ----
    if args.skip_sorted or not Path(config.get("sorted_b_dir", "")).exists():
        print("[s00] skipping sorted even-channel crosscheck (no sorted_b_dir or --skip-sorted)")
        sorted_counts = counts_by_run[["run", "selected_pulses", "B2", "B4", "B6", "B8"]].copy()
        sorted_compare = sorted_counts.copy()
        # Issue #972: a skipped sorted crosscheck must be recorded as an explicit
        # gate state, never fabricated as a raw-as-sorted value or a benign note.
        sorted_compare["gate_state"] = GATE_NOT_RUN_MISSING_INPUT
        sorted_gate_pass = True
    else:
        sorted_counts = sorted_crosscheck(config)
        identity_cols = [
            "identity_events",
            "identity_exact_events",
            "identity_mismatch_cells",
            "identity_evt_mismatches",
        ]
        sorted_compare = counts_by_run[["run", "selected_pulses", "B2", "B4", "B6", "B8"]].merge(
            sorted_counts[["run", "selected_pulses", "B2", "B4", "B6", "B8"] + identity_cols],
            on="run",
            suffixes=("_raw", "_sorted_even"),
        )
        sorted_diff = sorted_compare["selected_pulses_raw"] - sorted_compare["selected_pulses_sorted_even"]
        # Identity gate (#952): the absolute words reconstructed from the sorted
        # tree must equal the raw HRDv frame cell for cell and EVT numbers must
        # align 1:1. Any mismatch is exactly the staging-desync failure mode
        # (128-word truncation read as 8x16) this gate exists to catch.
        identity_pass = bool(
            (sorted_counts["identity_mismatch_cells"] == 0).all()
            and (sorted_counts["identity_evt_mismatches"] == 0).all()
        )
        sorted_gate_pass = identity_pass and bool((sorted_diff.abs() <= 0).all())
        sorted_compare["gate_state"] = GATE_PASS if sorted_gate_pass else GATE_FAIL

# ---- All gates pass? ----
    all_gates_pass = fixed_count_pass and sorted_gate_pass

    # ---- Write all artifacts to staging ----
    counts_by_run.to_csv(staging / "counts_by_run.csv", index=False)
    counts_by_group.to_csv(staging / "counts_by_group.csv", index=False)
    comparison.to_csv(staging / "count_match_table.csv", index=False)
    sorted_compare.to_csv(staging / "sorted_even_channel_crosscheck.csv", index=False)
    selected.to_csv(staging_selected, index=False, compression="gzip")
    make_figures(counts_by_run, selected, staging)

    if not args.skip_ml:
        run_ml_check(config, ml_rows, staging, population_prevalence=population_prevalence)
    if not args.skip_sha256:
        write_checksums(config, staging)
    # ---- Model identity for manifest ----
    input_hashes = None
    if not args.skip_sha256:
        try:
            checksums = pd.read_csv(staging / "input_sha256.csv")
            input_hashes = dict(zip(checksums["file"], checksums["sha256"]))
        except Exception:
            input_hashes = {}
    selector_identity = s00_selector_model_identity()
    model_identity = {
        "effective_amplitude_cut_adc": float(cut),
        "amplitude_cut_source": cut_source,
        "selector": f"ccb_mc_validation.selector {selector_identity['selector_id']}",
        "hrd_waveform_schema": f"hrd-8x{int(config['samples_per_channel'])}-v1",
        "config_digest": model_id,
        "source_commit": src_commit,
        **selector_identity,
    }
    # ---- Gate-state model (issue #972) ----
    # Every P0 data-integrity gate is recorded with an explicit state. A skipped
    # or missing sorted crosscheck is NOT_RUN_MISSING_INPUT (never fabricated as
    # PASS), which is a non-authorising condition. The pulse-schema gate is
    # structurally PASS here (the selected table is written by this selector).
    if args.skip_sorted or not Path(config.get("sorted_b_dir", "")).exists():
        sorted_gate_state = GATE_NOT_RUN_MISSING_INPUT
        sorted_identity_state = GATE_NOT_RUN_MISSING_INPUT
    else:
        sorted_gate_state = GATE_PASS if sorted_gate_pass else GATE_FAIL
        sorted_identity_state = GATE_PASS if identity_pass else GATE_FAIL
    gate_states = {
        "count_match": GATE_PASS if fixed_count_pass else GATE_FAIL,
        "sorted_even_channel_crosscheck": sorted_gate_state,
        "sorted_waveform_identity": sorted_identity_state,
        "pulse_schema_v1": GATE_PASS,
    }

    # An authorising run requires every P0 data-integrity gate to be PASS.
    # A missing/failed sorted closure or pulse-schema violation is a non-authorising condition.
    authorising = (
        bool(comparison["pass"].all())
        and gate_states["sorted_even_channel_crosscheck"] == GATE_PASS
        and gate_states["sorted_waveform_identity"] == GATE_PASS
        and gate_states["pulse_schema_v1"] == GATE_PASS
    )

    if canonical:
        # ---- Canonical production: authorising transaction ----
        if authorising:
            # Write manifest, then atomically publish staging -> canonical out_dir
            write_manifest(staging, args.config, comparison, staging_selected, cut, cut_source,
                           canonical=True, model_identity=model_identity, gate_states=gate_states,
                           input_hashes=input_hashes,
                           saturation_contract=getattr(scan_raw, 'saturation_contract', None))
            atomic_publish(staging, out_dir)
            print(f"[s00] canonical artifacts published: {out_dir}")
            print(f"[s00] selected pulse table: {selected_path}")
        else:
            # Gate failure: write the failure manifest to staging but DO NOT
            # publish. The last authorising artifact set is preserved byte-identical.
            write_manifest(staging, args.config, comparison, staging_selected, cut, cut_source,
                           canonical=True, model_identity=model_identity, gate_states=gate_states,
                           input_hashes=input_hashes,
                           saturation_contract=getattr(scan_raw, 'saturation_contract', None))
            shutil.rmtree(staging)
            print("[s00] CANONICAL RUN FAILED GATES — staging discarded; last authorising artifacts preserved.")
            print(comparison.to_string(index=False))
            # Also surface the comparison to stdout so CI/scripts can parse it
            print(comparison.to_string(index=False))
            print(f"\nselected pulse table: {selected_path}")
            print(f"report artifacts: {out_dir}")
            print(f"[s00] exit code 1 (gate failure)")
            return 1
    else:
        # ---- Sensitivity run: non-authorising, isolated namespace ----
        # Replace fixed-count comparison with the correct sensitivity contract:
        # report effective threshold, selection counts and migration matrix.
        # Canonical expected counts are retained only as a negative/control reference.
        write_sensitivity_report(staging, cut, cut_source, counts_by_group, comparison)
        write_manifest(staging, args.config, comparison, staging_selected, cut, cut_source,
                       canonical=False, model_identity=model_identity, gate_states=gate_states,
                       input_hashes=input_hashes,
                       saturation_contract=getattr(scan_raw, 'saturation_contract', None))
        # Publish staging to the sensitivity namespace (always — sensitivity runs
        # are self-describing and replace their own namespace, not the canonical one).
        atomic_publish(staging, out_dir)
        print(f"[s00] sensitivity artifacts: {out_dir}")
        print(comparison.to_string(index=False))
        print(f"\nselected pulse table: {selected_path}")
        print(f"report artifacts: {out_dir}")
        print("[s00] sensitivity run complete (non-authorising; exact-count closure is NOT expected).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
