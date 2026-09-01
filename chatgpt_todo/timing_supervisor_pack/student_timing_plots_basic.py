#!/usr/bin/env python3
# ruff: noqa: F403, F405
"""Modular component of the student timing walkthrough."""
from student_timing_types import *  # noqa: F403
from student_timing_data import *  # noqa: F403
from student_timing_analysis import *  # noqa: F403


def save_figure(figure: plt.Figure, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(out_dir / f"{stem}.png", dpi=170, bbox_inches="tight")
    figure.savefig(out_dir / f"{stem}.svg", bbox_inches="tight")
    plt.close(figure)


def watermark(axis: plt.Axes, text: str | None) -> None:
    if not text:
        return
    axis.text(
        0.5,
        0.5,
        text,
        transform=axis.transAxes,
        ha="center",
        va="center",
        rotation=28,
        fontsize=16,
        alpha=0.22,
        zorder=20,
    )


def plot_word_count(dataset: WaveformDataset, out_dir: Path, prefix: str) -> str:
    figure, axis = plt.subplots(figsize=(7.0, 4.5))
    values, counts = np.unique(dataset.word_counts, return_counts=True)
    axis.bar(values.astype(str), counts)
    axis.set_xlabel("scalar waveform words per event")
    axis.set_ylabel("events")
    axis.set_title(f"Data contract: {dataset.label}")
    axis.grid(True, axis="y", alpha=0.25)
    stem = f"{prefix}_01_word_count_contract"
    save_figure(figure, out_dir, stem)
    return stem


def plot_waveform_atlas(
    dataset: WaveformDataset,
    result: LaneResult,
    out_dir: Path,
    prefix: str,
) -> str:
    n_channels = dataset.waveforms.shape[1]
    columns = 2
    rows = math.ceil(n_channels / columns)
    figure, axes = plt.subplots(rows, columns, figsize=(10.0, 2.7 * rows), sharex=True)
    axes_array = np.asarray(axes).reshape(-1)
    sample = np.arange(dataset.waveforms.shape[2])
    max_events = min(25_000, result.corrected.shape[0])
    values = result.corrected[:max_events]
    for channel in range(n_channels):
        axis = axes_array[channel]
        median = np.median(values[:, channel, :], axis=0)
        q16, q84 = np.quantile(values[:, channel, :], [0.16, 0.84], axis=0)
        axis.plot(sample, median, label="median")
        axis.fill_between(sample, q16, q84, alpha=0.25, label="16-84%")
        axis.axhline(0.0, linewidth=0.8)
        axis.set_title(dataset.channel_labels[channel])
        axis.set_ylabel("baseline-corrected ADC")
        axis.grid(True, alpha=0.2)
        watermark(axis, result.config.watermark)
    for axis in axes_array[n_channels:]:
        axis.set_visible(False)
    axes_array[min(n_channels - 1, len(axes_array) - 1)].set_xlabel("sample index")
    figure.suptitle(f"Waveform atlas: {result.config.name}")
    stem = f"{prefix}_02_waveform_atlas"
    save_figure(figure, out_dir, stem)
    return stem


def plot_baseline_diagnostics(
    dataset: WaveformDataset,
    result: LaneResult,
    out_dir: Path,
    prefix: str,
) -> str:
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.4))
    for stave, channel in result.config.staves.items():
        axes[0].hist(
            result.baseline_rms_adc[:, channel],
            bins=80,
            histtype="step",
            density=True,
            label=stave,
        )
        axes[1].hist(
            result.baseline_slope_adc_per_ns[:, channel],
            bins=80,
            histtype="step",
            density=True,
            label=stave,
        )
    axes[0].set_xlabel("baseline RMS (ADC)")
    axes[0].set_ylabel("density")
    axes[0].set_title("Baseline noise")
    axes[1].set_xlabel("baseline slope (ADC/ns)")
    axes[1].set_ylabel("density")
    axes[1].set_title("Baseline drift")
    for axis in axes:
        axis.grid(True, alpha=0.25)
        axis.legend()
        watermark(axis, result.config.watermark)
    stem = f"{prefix}_03_baseline_diagnostics"
    save_figure(figure, out_dir, stem)
    return stem


def plot_amplitude_peak_map(
    dataset: WaveformDataset,
    result: LaneResult,
    out_dir: Path,
    prefix: str,
) -> str:
    figure, axes = plt.subplots(2, 2, figsize=(10.5, 8.0), sharex=True)
    for axis, (stave, channel) in zip(axes.reshape(-1), result.config.staves.items(), strict=True):
        amplitude = result.selected_amplitude_adc[:, channel]
        peak = result.selected_peak_sample[:, channel]
        valid = np.isfinite(amplitude) & (peak >= 0)
        axis.hexbin(peak[valid], amplitude[valid], gridsize=(18, 45), mincnt=1, bins="log")
        axis.axhline(result.config.amplitude_cut_adc, linestyle="--", linewidth=1.0)
        axis.set_title(stave)
        axis.set_xlabel("selected peak sample")
        axis.set_ylabel("selected amplitude (ADC)")
        axis.grid(True, alpha=0.15)
        watermark(axis, result.config.watermark)
    figure.suptitle("Amplitude versus selected peak sample")
    stem = f"{prefix}_04_amplitude_peak_map"
    save_figure(figure, out_dir, stem)
    return stem


def plot_component_identity(
    result: LaneResult,
    out_dir: Path,
    prefix: str,
) -> str:
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.4))
    channels = [result.config.staves[stave] for stave in result.config.staves]
    ratio = result.selected_to_global_ratio[:, channels].reshape(-1)
    peak_difference = (
        result.selected_peak_sample[:, channels] - result.global_peak_sample[:, channels]
    ).reshape(-1)
    axes[0].hist(ratio[np.isfinite(ratio)], bins=80, range=(0.0, 1.05))
    axes[0].set_xlabel("selected amplitude / global amplitude")
    axes[0].set_ylabel("waveform rows")
    axes[0].set_title("Is the timed component the global pulse?")
    axes[1].hist(peak_difference[np.isfinite(peak_difference)], bins=np.arange(-18.5, 19.5, 1.0))
    axes[1].set_xlabel("selected peak sample - global peak sample")
    axes[1].set_ylabel("waveform rows")
    axes[1].set_title("Component-switch diagnostic")
    for axis in axes:
        axis.grid(True, alpha=0.25)
        watermark(axis, result.config.watermark)
    stem = f"{prefix}_05_component_identity"
    save_figure(figure, out_dir, stem)
    return stem


def choose_cfd_examples(
    result: LaneResult,
    stave: str,
    count: int = 6,
) -> np.ndarray:
    channel = result.config.staves[stave]
    fraction = result.config.analysis_fraction
    finite = np.isfinite(result.times_ns[fraction][:, channel])
    amplitude_pass = result.selected_amplitude_adc[:, channel] > result.config.amplitude_cut_adc
    candidates = np.flatnonzero(finite & amplitude_pass)
    if candidates.size <= count:
        return candidates
    quantile_indices = np.linspace(0, candidates.size - 1, count).astype(int)
    order = np.argsort(result.selected_amplitude_adc[candidates, channel])
    return candidates[order[quantile_indices]]


def plot_cfd_examples(
    dataset: WaveformDataset,
    result: LaneResult,
    out_dir: Path,
    prefix: str,
    stave: str,
) -> str:
    examples = choose_cfd_examples(result, stave)
    if examples.size == 0:
        return ""
    figure, axes = plt.subplots(len(examples), 1, figsize=(9.0, 2.4 * len(examples)), sharex=True)
    axes_array = np.atleast_1d(axes)
    channel = result.config.staves[stave]
    fraction = result.config.analysis_fraction
    sample_times = np.arange(dataset.waveforms.shape[2]) * dataset.sample_period_ns
    for axis, event_index in zip(axes_array, examples, strict=True):
        waveform = result.corrected[event_index, channel]
        amplitude = result.selected_amplitude_adc[event_index, channel]
        threshold = fraction * amplitude
        crossing = result.times_ns[fraction][event_index, channel]
        peak = result.selected_peak_sample[event_index, channel]
        axis.plot(sample_times, waveform, marker="o", label="samples")
        axis.axhline(threshold, linestyle="--", label=f"{fraction:.0%} threshold")
        axis.axvline(crossing, linestyle=":", label=f"crossing {crossing:.3f} ns")
        axis.axvline(peak * dataset.sample_period_ns, linewidth=0.8, label="selected peak")
        axis.set_ylabel("ADC")
        axis.grid(True, alpha=0.25)
        axis.legend(fontsize=8, ncol=4)
        watermark(axis, result.config.watermark)
    axes_array[-1].set_xlabel("time in waveform window (ns)")
    figure.suptitle(f"Event-by-event CFD construction for {stave}")
    stem = f"{prefix}_06_cfd_examples_{stave.lower()}"
    save_figure(figure, out_dir, stem)
    return stem


def plot_cutflow(result: LaneResult, out_dir: Path, prefix: str) -> str:
    figure, axis = plt.subplots(figsize=(8.0, 4.8))
    axis.barh(result.cutflow["stage"], result.cutflow["events"])
    axis.invert_yaxis()
    axis.set_xlabel("unique events")
    axis.set_title("Cut flow: every loss has a name")
    axis.grid(True, axis="x", alpha=0.25)
    watermark(axis, result.config.watermark)
    stem = f"{prefix}_07_cutflow"
    save_figure(figure, out_dir, stem)
    return stem


def plot_timestamp_distributions(
    result: LaneResult,
    out_dir: Path,
    prefix: str,
) -> str:
    fraction = result.config.analysis_fraction
    figure, axis = plt.subplots(figsize=(8.0, 4.8))
    for stave, channel in result.config.staves.items():
        values = result.times_ns[fraction][:, channel]
        mask = np.isfinite(values) & (
            result.selected_amplitude_adc[:, channel] > result.config.amplitude_cut_adc
        )
        if np.any(mask):
            axis.hist(values[mask], bins=80, histtype="step", density=True, label=stave)
    axis.set_xlabel("CFD timestamp (ns)")
    axis.set_ylabel("density")
    axis.set_title(f"Per-stave timestamps at CFD {fraction:.0%}")
    axis.grid(True, alpha=0.25)
    axis.legend()
    watermark(axis, result.config.watermark)
    stem = f"{prefix}_08_timestamp_distributions"
    save_figure(figure, out_dir, stem)
    return stem


def preferred_pair(result: LaneResult) -> tuple[str, str] | None:
    preferred = ("B4", "B6")
    key = (*preferred, result.config.analysis_fraction)
    if key in result.pair_event_tables and len(result.pair_event_tables[key]) > 0:
        return preferred
    rows = result.pair_metrics[
        (result.pair_metrics["fraction"] == result.config.analysis_fraction)
        & (result.pair_metrics["n"] > 0)
    ]
    if rows.empty:
        return None
    first = rows.sort_values("n", ascending=False).iloc[0]
    return str(first["stave_a"]), str(first["stave_b"])


def plot_timestamp_correlation(
    result: LaneResult,
    out_dir: Path,
    prefix: str,
) -> str:
    pair = preferred_pair(result)
    if pair is None:
        return ""
    table = result.pair_event_tables[(*pair, result.config.analysis_fraction)]
    figure, axis = plt.subplots(figsize=(6.4, 5.4))
    axis.hexbin(table["t_a_ns"], table["t_b_ns"], gridsize=60, mincnt=1, bins="log")
    axis.set_xlabel(f"{pair[0]} timestamp (ns)")
    axis.set_ylabel(f"{pair[1]} timestamp (ns)")
    axis.set_title("Do the two staves move together event by event?")
    axis.grid(True, alpha=0.15)
    watermark(axis, result.config.watermark)
    stem = f"{prefix}_09_timestamp_correlation_{pair[0].lower()}_{pair[1].lower()}"
    save_figure(figure, out_dir, stem)
    return stem


def plot_residual_views(
    result: LaneResult,
    out_dir: Path,
    prefix: str,
) -> list[str]:
    pair = preferred_pair(result)
    if pair is None:
        return []
    vector = result.pair_vectors[(*pair, result.config.analysis_fraction)]
    vector = vector[np.isfinite(vector)]
    if vector.size == 0:
        return []
    centered = vector - np.median(vector)
    metrics = robust_metrics(vector)
    stems: list[str] = []

    figure, axis = plt.subplots(figsize=(8.0, 4.8))
    axis.hist(centered, bins=120)
    axis.set_xlabel("pair residual - median (ns)")
    axis.set_ylabel("events")
    axis.set_title(
        f"Full {pair[0]}-{pair[1]} residual: sigma68={metrics['sigma68_ns']:.3f} ns, "
        f"RMS={metrics['rms_ns']:.3f} ns"
    )
    axis.grid(True, alpha=0.25)
    watermark(axis, result.config.watermark)
    stem = f"{prefix}_10_residual_full_linear"
    save_figure(figure, out_dir, stem)
    stems.append(stem)

    figure, axis = plt.subplots(figsize=(8.0, 4.8))
    axis.hist(centered, bins=160, log=True)
    axis.set_xlabel("pair residual - median (ns)")
    axis.set_ylabel("events (log scale)")
    axis.set_title("The log view exposes tails hidden by the central peak")
    axis.grid(True, alpha=0.25)
    watermark(axis, result.config.watermark)
    stem = f"{prefix}_11_residual_full_log"
    save_figure(figure, out_dir, stem)
    stems.append(stem)

    core_half_width = max(0.5, 5.0 * float(metrics["sigma68_ns"]))
    figure, axis = plt.subplots(figsize=(8.0, 4.8))
    axis.hist(centered, bins=150, range=(-core_half_width, core_half_width))
    axis.axvline(-float(metrics["sigma68_ns"]), linestyle="--", linewidth=1.0)
    axis.axvline(float(metrics["sigma68_ns"]), linestyle="--", linewidth=1.0)
    axis.set_xlabel("pair residual - median (ns)")
    axis.set_ylabel("events")
    axis.set_title("Zoomed central core: where the ~0.1 ns number comes from")
    axis.grid(True, alpha=0.25)
    watermark(axis, result.config.watermark)
    stem = f"{prefix}_12_residual_zoomed_core"
    save_figure(figure, out_dir, stem)
    stems.append(stem)
    return stems
