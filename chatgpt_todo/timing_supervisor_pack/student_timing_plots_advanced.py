#!/usr/bin/env python3
# ruff: noqa: F403, F405
"""Modular component of the student timing walkthrough."""
from student_timing_types import *  # noqa: F403
from student_timing_data import *  # noqa: F403
from student_timing_analysis import *  # noqa: F403
from student_timing_plots_basic import *  # noqa: F403


def plot_fraction_scan(result: LaneResult, out_dir: Path, prefix: str) -> str:
    pair = preferred_pair(result)
    if pair is None:
        return ""
    rows = result.pair_metrics[
        (result.pair_metrics["stave_a"] == pair[0])
        & (result.pair_metrics["stave_b"] == pair[1])
    ].sort_values("fraction")
    if rows.empty:
        return ""
    figure, axis = plt.subplots(figsize=(8.0, 4.8))
    axis.plot(rows["fraction"], rows["sigma68_ns"], marker="o", label="central sigma68")
    axis.plot(rows["fraction"], rows["core_sigma_ns"], marker="s", label="Gaussian-core sigma")
    axis.plot(rows["fraction"], rows["rms_ns"], marker="^", label="full RMS")
    axis.set_yscale("log")
    axis.set_xlabel("CFD fraction")
    axis.set_ylabel("residual scale (ns, log axis)")
    axis.set_title("Fraction scan: a narrow core is not the same as a narrow distribution")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    watermark(axis, result.config.watermark)
    stem = f"{prefix}_13_fraction_scan_core_vs_rms"
    save_figure(figure, out_dir, stem)
    return stem


def binned_width(
    x: np.ndarray,
    y: np.ndarray,
    bins: int,
) -> pd.DataFrame:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]
    if x.size < bins * 20:
        return pd.DataFrame()
    edges = np.unique(np.quantile(x, np.linspace(0.0, 1.0, bins + 1)))
    if edges.size < 3:
        return pd.DataFrame()
    categories = pd.cut(x, edges, include_lowest=True, duplicates="drop")
    frame = pd.DataFrame({"x": x, "y": y, "bin": categories})
    rows: list[dict[str, float | int]] = []
    for _category, group in frame.groupby("bin", observed=True):
        if len(group) < 20:
            continue
        rows.append(
            {
                "x_median": float(np.median(group["x"])),
                "y_median": float(np.median(group["y"])),
                "sigma68": sigma68(group["y"]),
                "n": int(len(group)),
            }
        )
    return pd.DataFrame(rows)


def plot_residual_dependencies(
    result: LaneResult,
    out_dir: Path,
    prefix: str,
) -> list[str]:
    pair = preferred_pair(result)
    if pair is None:
        return []
    table = result.pair_event_tables[(*pair, result.config.analysis_fraction)]
    if table.empty:
        return []
    centered = table["residual_ns"].to_numpy() - np.median(table["residual_ns"])
    dependencies = [
        ("amplitude_geomean_adc", "geometric-mean amplitude (ADC)", "14_residual_vs_amplitude"),
        (
            "minimum_slope_adc_per_ns",
            "minimum crossing slope (ADC/ns)",
            "15_residual_vs_slope",
        ),
        ("phase_difference", "fractional phase difference", "16_residual_vs_phase"),
    ]
    stems: list[str] = []
    for column, x_label, suffix in dependencies:
        summary = binned_width(table[column].to_numpy(), centered, bins=10)
        if summary.empty:
            continue
        figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.4))
        axes[0].plot(summary["x_median"], summary["y_median"], marker="o")
        axes[0].axhline(0.0, linewidth=0.8)
        axes[0].set_xlabel(x_label)
        axes[0].set_ylabel("median centered residual (ns)")
        axes[0].set_title("Bias dependence")
        axes[1].plot(summary["x_median"], summary["sigma68"], marker="o")
        axes[1].set_xlabel(x_label)
        axes[1].set_ylabel("sigma68 in bin (ns)")
        axes[1].set_title("Resolution dependence")
        for axis in axes:
            axis.grid(True, alpha=0.25)
            watermark(axis, result.config.watermark)
        stem = f"{prefix}_{suffix}"
        save_figure(figure, out_dir, stem)
        stems.append(stem)
    return stems


def plot_run_stability(result: LaneResult, out_dir: Path, prefix: str) -> str:
    pair = preferred_pair(result)
    if pair is None:
        return ""
    table = result.pair_event_tables[(*pair, result.config.analysis_fraction)]
    rows: list[dict[str, float | int]] = []
    for run, group in table.groupby("run"):
        metrics = robust_metrics(group["residual_ns"].to_numpy())
        rows.append({"run": int(run), **metrics})
    frame = pd.DataFrame(rows).sort_values("run")
    if frame.empty:
        return ""
    figure, axis = plt.subplots(figsize=(8.5, 4.8))
    axis.plot(frame["run"], frame["sigma68_ns"], marker="o", label="sigma68")
    axis.plot(frame["run"], frame["rms_ns"], marker="s", label="RMS")
    axis.set_xlabel("run")
    axis.set_ylabel("residual scale (ns)")
    axis.set_title("Run stability: one run must not create the headline")
    axis.grid(True, alpha=0.25)
    axis.legend()
    watermark(axis, result.config.watermark)
    stem = f"{prefix}_17_run_stability"
    save_figure(figure, out_dir, stem)
    return stem


def plot_correction_stages(result: LaneResult, out_dir: Path, prefix: str) -> str:
    pair = preferred_pair(result)
    if pair is None:
        return ""
    table = result.pair_event_tables[(*pair, result.config.analysis_fraction)]
    if table.empty:
        return ""
    stages = [
        ("raw difference", table["raw_difference_ns"].to_numpy()),
        ("after TOF", table["tof_corrected_ns"].to_numpy()),
        ("after peak-offset alignment", table["residual_ns"].to_numpy()),
    ]
    rows = []
    for name, vector in stages:
        metrics = robust_metrics(vector)
        rows.append(
            {
                "stage": name,
                "median_ns": metrics["median_ns"],
                "sigma68_ns": metrics["sigma68_ns"],
                "rms_ns": metrics["rms_ns"],
            }
        )
    frame = pd.DataFrame(rows)
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.4))
    axes[0].plot(frame["stage"], frame["median_ns"], marker="o")
    axes[0].tick_params(axis="x", rotation=20)
    axes[0].set_ylabel("median (ns)")
    axes[0].set_title("Constant corrections move the center")
    axes[1].plot(frame["stage"], frame["sigma68_ns"], marker="o", label="sigma68")
    axes[1].plot(frame["stage"], frame["rms_ns"], marker="s", label="RMS")
    axes[1].tick_params(axis="x", rotation=20)
    axes[1].set_ylabel("width (ns)")
    axes[1].set_title("A constant shift must not change the width")
    axes[1].legend()
    for axis in axes:
        axis.grid(True, alpha=0.25)
        watermark(axis, result.config.watermark)
    stem = f"{prefix}_18_correction_stages"
    save_figure(figure, out_dir, stem)
    return stem


def plot_pair_matrix(result: LaneResult, out_dir: Path, prefix: str) -> str:
    staves = list(result.config.staves)
    matrix = np.full((len(staves), len(staves)), np.nan)
    for first_index, first in enumerate(staves):
        matrix[first_index, first_index] = 0.0
        for second_index in range(first_index + 1, len(staves)):
            second = staves[second_index]
            vector = result.pair_vectors.get(
                (first, second, result.config.analysis_fraction), np.asarray([])
            )
            if vector.size:
                matrix[first_index, second_index] = sigma68(vector)
                matrix[second_index, first_index] = matrix[first_index, second_index]
    if np.all(~np.isfinite(matrix)):
        return ""
    figure, axis = plt.subplots(figsize=(6.2, 5.4))
    image = axis.imshow(matrix)
    figure.colorbar(image, ax=axis, label="pair sigma68 (ns)")
    axis.set_xticks(np.arange(len(staves)), staves)
    axis.set_yticks(np.arange(len(staves)), staves)
    for row in range(len(staves)):
        for column in range(len(staves)):
            if np.isfinite(matrix[row, column]):
                axis.text(column, row, f"{matrix[row, column]:.3f}", ha="center", va="center")
    axis.set_title("All-pair residual matrix")
    watermark(axis, result.config.watermark)
    stem = f"{prefix}_19_pair_matrix"
    save_figure(figure, out_dir, stem)
    return stem


def plot_resolution_inference(result: LaneResult, out_dir: Path, prefix: str) -> str:
    inference = result.inference
    if not inference.get("authorized") or not inference.get("stave_sigma_ns"):
        return ""
    staves = list(inference["stave_sigma_ns"])
    inferred = [inference["stave_sigma_ns"][stave] for stave in staves]
    truth = None
    if "truth_sigma_ns" in inference:
        truth = [inference["truth_sigma_ns"].get(stave, np.nan) for stave in staves]
    figure, axis = plt.subplots(figsize=(7.5, 4.8))
    positions = np.arange(len(staves))
    width = 0.38
    axis.bar(positions - width / 2, inferred, width=width, label="inferred")
    if truth is not None:
        axis.bar(positions + width / 2, truth, width=width, label="injected truth")
    axis.set_xticks(positions, staves)
    axis.set_ylabel("single-stave sigma (ns)")
    axis.set_title("Independent-variance deconvolution and closure")
    axis.grid(True, axis="y", alpha=0.25)
    axis.legend()
    watermark(axis, result.config.watermark)
    stem = f"{prefix}_20_resolution_inference"
    save_figure(figure, out_dir, stem)
    return stem


def plot_tail_waveforms(
    dataset: WaveformDataset,
    result: LaneResult,
    out_dir: Path,
    prefix: str,
) -> str:
    pair = preferred_pair(result)
    if pair is None:
        return ""
    table = result.pair_event_tables[(*pair, result.config.analysis_fraction)]
    if len(table) < 10:
        return ""
    centered = table["residual_ns"] - np.median(table["residual_ns"])
    central = table.iloc[np.argsort(np.abs(centered.to_numpy()))[:3]]
    tail = table.iloc[np.argsort(np.abs(centered.to_numpy()))[-3:]]
    selected = pd.concat([central.assign(kind="central"), tail.assign(kind="tail")])
    figure, axes = plt.subplots(6, 1, figsize=(9.0, 13.5), sharex=True)
    sample = np.arange(dataset.waveforms.shape[2])
    for axis, (_, row) in zip(axes, selected.iterrows(), strict=True):
        event_index = int(np.flatnonzero(dataset.event_ids == int(row["event_id"]))[0])
        for stave in pair:
            channel = result.config.staves[stave]
            axis.plot(sample, result.corrected[event_index, channel], marker="o", label=stave)
        axis.set_ylabel("ADC")
        axis.set_title(f"{row['kind']} event, centered residual={float(row['residual_ns'] - np.median(table['residual_ns'])):.3f} ns")
        axis.grid(True, alpha=0.25)
        axis.legend()
        watermark(axis, result.config.watermark)
    axes[-1].set_xlabel("sample index")
    figure.suptitle("Waveforms behind the core and the tails")
    stem = f"{prefix}_21_tail_waveform_examples"
    save_figure(figure, out_dir, stem)
    return stem


def plot_correct_legacy_comparison(
    correct_dataset: WaveformDataset,
    correct_result: LaneResult,
    legacy_dataset: WaveformDataset,
    legacy_result: LaneResult,
    out_dir: Path,
) -> str:
    figure, axes = plt.subplots(2, 2, figsize=(11.0, 7.5), sharex="col")
    for row_index, stave in enumerate(("B4", "B6")):
        correct_channel = correct_result.config.staves[stave]
        legacy_channel = legacy_result.config.staves[stave]
        correct_median = np.median(correct_result.corrected[:, correct_channel, :], axis=0)
        legacy_median = np.median(legacy_result.corrected[:, legacy_channel, :], axis=0)
        axes[row_index, 0].plot(np.arange(correct_dataset.waveforms.shape[2]), correct_median, marker="o")
        axes[row_index, 0].set_title(f"Correct 8x18 {stave}: quiet physical channel")
        axes[row_index, 1].plot(np.arange(legacy_dataset.waveforms.shape[2]), legacy_median, marker="o")
        axes[row_index, 1].set_title(f"Truncated 8x16 {stave}: pedestal step")
        for column in range(2):
            axes[row_index, column].set_ylabel("median corrected ADC")
            axes[row_index, column].grid(True, alpha=0.25)
    axes[-1, 0].set_xlabel("sample index")
    axes[-1, 1].set_xlabel("sample index")
    watermark(axes[0, 1], "NON_PHYSICAL_DELIBERATE_TRUNCATION_ARTIFACT")
    watermark(axes[1, 1], "NON_PHYSICAL_DELIBERATE_TRUNCATION_ARTIFACT")
    figure.suptitle("How the historical 0.1 ns-like core can be manufactured")
    stem = "comparison_01_correct_vs_legacy_frame"
    save_figure(figure, out_dir, stem)
    return stem


def plot_closure_grid(out_dir: Path, seed: int = 20260901) -> str:
    rng = np.random.default_rng(seed)
    injected: list[float] = []
    recovered: list[float] = []
    staves = ["A", "B", "C", "D"]
    pairs = [(first, second) for index, first in enumerate(staves) for second in staves[index + 1 :]]
    for _scenario in range(20):
        truth = {stave: float(rng.uniform(0.04, 0.20)) for stave in staves}
        n_events = 60_000
        common = rng.normal(0.0, 1.5, size=n_events)
        timestamps = {
            stave: common + rng.normal(0.0, truth[stave], size=n_events) for stave in staves
        }
        pair_variance = {
            pair: float(np.var(timestamps[pair[1]] - timestamps[pair[0]], ddof=1))
            for pair in pairs
        }
        solution = solve_independent_stave_variances(pair_variance, staves)
        for stave in staves:
            injected.append(truth[stave])
            recovered.append(solution["stave_sigma_ns"][stave])
    figure, axis = plt.subplots(figsize=(6.2, 5.6))
    axis.scatter(injected, recovered, alpha=0.65)
    limits = [0.03, 0.21]
    axis.plot(limits, limits, linestyle="--", label="perfect recovery")
    axis.set_xlim(limits)
    axis.set_ylim(limits)
    axis.set_xlabel("injected stave sigma (ns)")
    axis.set_ylabel("recovered stave sigma (ns)")
    axis.set_title("Injection/recovery closure for the independent-variance model")
    axis.grid(True, alpha=0.25)
    axis.legend()
    stem = "physical_22_injection_recovery_closure"
    save_figure(figure, out_dir, stem)
    return stem


def generate_lane_plots(
    dataset: WaveformDataset,
    result: LaneResult,
    out_dir: Path,
    prefix: str,
) -> list[str]:
    plot_dir = out_dir / "plots"
    stems = [
        plot_word_count(dataset, plot_dir, prefix),
        plot_waveform_atlas(dataset, result, plot_dir, prefix),
        plot_baseline_diagnostics(dataset, result, plot_dir, prefix),
        plot_amplitude_peak_map(dataset, result, plot_dir, prefix),
        plot_component_identity(result, plot_dir, prefix),
        plot_cfd_examples(dataset, result, plot_dir, prefix, next(iter(result.config.staves))),
        plot_cutflow(result, plot_dir, prefix),
        plot_timestamp_distributions(result, plot_dir, prefix),
        plot_timestamp_correlation(result, plot_dir, prefix),
        *plot_residual_views(result, plot_dir, prefix),
        plot_fraction_scan(result, plot_dir, prefix),
        *plot_residual_dependencies(result, plot_dir, prefix),
        plot_run_stability(result, plot_dir, prefix),
        plot_correction_stages(result, plot_dir, prefix),
        plot_pair_matrix(result, plot_dir, prefix),
        plot_resolution_inference(result, plot_dir, prefix),
        plot_tail_waveforms(dataset, result, plot_dir, prefix),
    ]
    return [stem for stem in stems if stem]
