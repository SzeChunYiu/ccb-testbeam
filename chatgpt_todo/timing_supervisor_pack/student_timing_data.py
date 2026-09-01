#!/usr/bin/env python3
# ruff: noqa: F403, F405
"""Modular component of the student timing walkthrough."""
from student_timing_types import *  # noqa: F403


def pulse_shape(
    sample_times_ns: np.ndarray,
    onset_ns: np.ndarray,
    amplitude_adc: np.ndarray,
    rise_ns: float,
    fall_ns: float,
    plateau_ns: float = 0.0,
) -> np.ndarray:
    relative = sample_times_ns[None, :] - onset_ns[:, None]
    rising = np.clip(relative / rise_ns, 0.0, 1.0)
    after_plateau = np.maximum(relative - rise_ns - plateau_ns, 0.0)
    decay = np.exp(-after_plateau / fall_ns)
    return amplitude_adc[:, None] * rising * decay


def generate_physical_demo(n_events: int, seed: int) -> WaveformDataset:
    rng = np.random.default_rng(seed)
    n_channels = 8
    n_samples = 18
    sample_period_ns = 10.0
    sample_times = np.arange(n_samples, dtype=float) * sample_period_ns
    run_count = 10
    runs = np.repeat(np.arange(1, run_count + 1), math.ceil(n_events / run_count))[:n_events]
    event_ids = np.arange(n_events, dtype=np.int64)
    pedestals = np.asarray([7200, 7200, 8300, 8300, 6900, 6900, 7600, 7600], dtype=float)
    waveforms = np.empty((n_events, n_channels, n_samples), dtype=np.float32)
    common_time = 44.0 + rng.uniform(-4.0, 4.0, size=n_events)
    # B4--B6 has an injected pair width sqrt(0.065^2 + 0.075^2) = 0.099 ns.
    # The common trigger phase cancels in pair differences.  The voltage noise
    # is deliberately small so the known-answer deconvolution can close.
    truth_sigma = {"B2": 0.055, "B4": 0.065, "B6": 0.075, "B8": 0.090}
    truth_times: dict[str, np.ndarray] = {}
    stave_channels = DEFAULT_STAVES

    for channel in range(n_channels):
        waveforms[:, channel, :] = pedestals[channel] + rng.normal(
            0.0, 1.5, size=(n_events, n_samples)
        )

    for stave_index, (stave, even_channel) in enumerate(stave_channels.items()):
        tof = DEFAULT_TOF_NS[stave]
        intrinsic = rng.normal(0.0, truth_sigma[stave], size=n_events)
        onset = common_time + tof + intrinsic
        truth_times[stave] = onset
        amplitude = rng.lognormal(mean=math.log(2600.0), sigma=0.16, size=n_events)
        # A plateau longer than one sampling interval guarantees that at least
        # one sample observes the true peak.  The dCFD threshold therefore uses
        # a stable amplitude while the linear leading edge allows exact
        # sub-sample interpolation in the noiseless limit.
        pulse = pulse_shape(
            sample_times,
            onset,
            amplitude,
            20.0,
            34.0,
            plateau_ns=15.0,
        )
        waveforms[:, even_channel, :] += pulse
        waveforms[:, even_channel + 1, :] -= 0.96 * pulse

    return WaveformDataset(
        label="synthetic_physical_three_stave",
        runs=runs,
        event_ids=event_ids,
        waveforms=waveforms,
        sample_period_ns=sample_period_ns,
        channel_labels=[f"ch{index}" for index in range(n_channels)],
        word_counts=np.full(n_events, n_channels * n_samples, dtype=int),
        truth_times_ns=truth_times,
        truth_sigma_ns=truth_sigma,
        metadata={
            "generator": "piecewise-linear rising pulse with high SNR",
            "purpose": "sub-sample interpolation and three-stave closure",
            "authorising": False,
        },
    )


def generate_artifact_demo(n_events: int, seed: int) -> tuple[WaveformDataset, WaveformDataset]:
    rng = np.random.default_rng(seed)
    n_channels = 8
    true_samples = 18
    sample_period_ns = 10.0
    sample_times = np.arange(true_samples, dtype=float) * sample_period_ns
    runs = np.repeat(np.arange(1, 11), math.ceil(n_events / 10))[:n_events]
    event_ids = np.arange(n_events, dtype=np.int64)
    # Pairwise pedestal steps reproduce the qualitative truncation mechanism:
    # when 144 words are cut to 128 and reshaped as 8 x 16, blocks contain the
    # tail of one channel followed by the head of the next channel.
    pedestals = np.asarray([7100, 9350, 6950, 9300, 6900, 9250, 6850, 9200], dtype=float)
    true_waveforms = np.empty((n_events, n_channels, true_samples), dtype=np.float32)
    for channel in range(n_channels):
        true_waveforms[:, channel, :] = pedestals[channel] + rng.normal(
            0.0, 21.0, size=(n_events, true_samples)
        )

    common_time = 48.0 + rng.uniform(-3.0, 3.0, size=n_events)
    amplitude = rng.lognormal(mean=math.log(3000.0), sigma=0.12, size=n_events)
    pulse = pulse_shape(sample_times, common_time, amplitude, 18.0, 32.0)
    true_waveforms[:, 0, :] += pulse
    true_waveforms[:, 1, :] -= 0.98 * pulse

    correct = WaveformDataset(
        label="synthetic_correct_8x18_only_B2_has_pulses",
        runs=runs,
        event_ids=event_ids,
        waveforms=true_waveforms,
        sample_period_ns=sample_period_ns,
        channel_labels=[f"true_ch{index}" for index in range(n_channels)],
        word_counts=np.full(n_events, 144, dtype=int),
        metadata={
            "authorising": False,
            "purpose": "show correct frame and quiet downstream channels",
        },
    )

    flat = true_waveforms.reshape(n_events, 144)
    legacy_flat = flat[:, :128].copy()
    legacy_waveforms = legacy_flat.reshape(n_events, 8, 16)
    # Roughly one percent of events receives an earlier negative excursion in
    # legacy block 4.  With the retracted -1 polarity this becomes a positive
    # pseudo-pulse several samples before the pedestal boundary.  The central
    # population remains near 0.1 ns while the full RMS grows to several ns,
    # matching the qualitative core/tail contradiction of the historical scan.
    outlier_rows = np.flatnonzero(rng.random(n_events) < 0.009)
    if outlier_rows.size:
        legacy_waveforms[outlier_rows, 4, 4] -= rng.uniform(
            2500.0, 5000.0, size=outlier_rows.size
        )
    legacy = WaveformDataset(
        label="synthetic_legacy_truncated_8x16_artifact",
        runs=runs,
        event_ids=event_ids,
        waveforms=legacy_waveforms,
        sample_period_ns=sample_period_ns,
        channel_labels=[f"legacy_block{index}" for index in range(n_channels)],
        word_counts=np.full(n_events, 128, dtype=int),
        metadata={
            "authorising": False,
            "watermark": "NON_PHYSICAL_DELIBERATE_TRUNCATION_ARTIFACT",
            "purpose": "reproduce a narrow residual from pedestal boundaries",
        },
    )
    return correct, legacy


def parse_run_from_path(path: Path, fallback: int) -> int:
    match = re.search(r"run[_-]?(\d+)", path.name, flags=re.IGNORECASE)
    return int(match.group(1)) if match else int(fallback)


def load_raw_dataset(config: Mapping[str, Any]) -> WaveformDataset:
    if validate_and_reshape_rows is None or load_polarity_map is None or canonical_cfd is None:
        raise RuntimeError(
            "raw mode must be run from a complete ccb-testbeam checkout with the canonical "
            "waveform-contract, polarity, and digital_cfd modules available"
        )
    try:
        import uproot
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("raw mode requires uproot; install the repository [root] extra") from exc

    input_patterns = config.get("inputs", [])
    if not input_patterns:
        raise ValueError("raw config must define at least one input path or glob")
    paths: list[Path] = []
    for pattern in input_patterns:
        pattern_path = Path(str(pattern))
        if any(character in str(pattern_path) for character in "*?[]"):
            paths.extend(sorted(pattern_path.parent.glob(pattern_path.name)))
        else:
            paths.append(pattern_path)
    paths = sorted(dict.fromkeys(paths))
    if not paths:
        raise FileNotFoundError("raw input patterns resolved to no files")

    tree_name = str(config.get("tree", "h101"))
    event_branch = str(config.get("event_branch", "EVENTNO"))
    waveform_branch = str(config.get("waveform_branch", "HRDv"))
    n_channels = int(config.get("n_channels", 8))
    samples_per_channel = int(config["samples_per_channel"])
    max_events = int(config.get("max_events", 200_000))
    step_size = int(config.get("step_size", 20_000))

    all_runs: list[np.ndarray] = []
    all_events: list[np.ndarray] = []
    all_waveforms: list[np.ndarray] = []
    all_lengths: list[np.ndarray] = []
    hashes: dict[str, str] = {}
    remaining = max_events
    for file_index, path in enumerate(paths):
        if remaining <= 0:
            break
        if not path.exists():
            raise FileNotFoundError(path)
        hashes[str(path)] = file_sha256(path)
        run = parse_run_from_path(path, file_index + 1)
        with uproot.open(path) as root_file:
            if tree_name not in root_file:
                raise KeyError(f"tree {tree_name!r} missing from {path}")
            tree = root_file[tree_name]
            for batch in tree.iterate(
                [event_branch, waveform_branch],
                step_size=step_size,
                library="np",
            ):
                rows = list(batch[waveform_branch])
                if remaining < len(rows):
                    rows = rows[:remaining]
                lengths = np.asarray([np.asarray(row).size for row in rows], dtype=int)
                waveforms, _summary = validate_and_reshape_rows(
                    rows,
                    n_channels=n_channels,
                    samples_per_channel=samples_per_channel,
                )
                event_values = np.asarray(batch[event_branch], dtype=np.int64)[: len(rows)]
                all_runs.append(np.full(len(rows), run, dtype=int))
                all_events.append(event_values)
                all_waveforms.append(waveforms.astype(np.float32))
                all_lengths.append(lengths)
                remaining -= len(rows)
                if remaining <= 0:
                    break

    if not all_waveforms:
        raise RuntimeError("no raw waveform events were loaded")
    return WaveformDataset(
        label=str(config.get("label", "raw_root_dataset")),
        runs=np.concatenate(all_runs),
        event_ids=np.concatenate(all_events),
        waveforms=np.concatenate(all_waveforms),
        sample_period_ns=float(config.get("sample_period_ns", 10.0)),
        channel_labels=[f"ch{index}" for index in range(n_channels)],
        word_counts=np.concatenate(all_lengths),
        source_files=[str(path) for path in paths],
        source_sha256=hashes,
        metadata={
            "tree": tree_name,
            "event_branch": event_branch,
            "waveform_branch": waveform_branch,
            "n_channels": n_channels,
            "samples_per_channel": samples_per_channel,
        },
    )


def baseline_features(
    waveforms: np.ndarray,
    baseline_samples: Sequence[int],
    sample_period_ns: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    indices = np.asarray(tuple(baseline_samples), dtype=int)
    if indices.size < 2:
        raise ValueError("at least two baseline samples are required")
    if np.any(indices < 0) or np.any(indices >= waveforms.shape[2]):
        raise ValueError("baseline sample index lies outside the waveform")
    baseline_region = waveforms[:, :, indices]
    baseline = np.median(baseline_region, axis=2)
    residual = baseline_region - baseline[:, :, None]
    baseline_rms = np.sqrt(np.mean(residual**2, axis=2))
    x = indices.astype(float) * sample_period_ns
    x_centered = x - np.mean(x)
    denominator = float(np.sum(x_centered**2))
    slope = np.sum(residual * x_centered[None, None, :], axis=2) / denominator
    return baseline, baseline_rms, slope


def unique_pair_table(
    dataset: WaveformDataset,
    result: LaneResult | None,
    times: np.ndarray,
    amplitudes: np.ndarray,
    slopes: np.ndarray,
    phases: np.ndarray,
    stave_a: str,
    stave_b: str,
    config: LaneConfig,
    peak_offsets_samples: Mapping[str, float],
) -> pd.DataFrame:
    channel_a = config.staves[stave_a]
    channel_b = config.staves[stave_b]
    frame = pd.DataFrame(
        {
            "run": dataset.runs,
            "event_id": dataset.event_ids,
            "t_a_ns": times[:, channel_a],
            "t_b_ns": times[:, channel_b],
            "amp_a_adc": amplitudes[:, channel_a],
            "amp_b_adc": amplitudes[:, channel_b],
            "slope_a_adc_per_ns": slopes[:, channel_a],
            "slope_b_adc_per_ns": slopes[:, channel_b],
            "phase_a": phases[:, channel_a],
            "phase_b": phases[:, channel_b],
        }
    )
    frame["finite"] = np.isfinite(frame["t_a_ns"]) & np.isfinite(frame["t_b_ns"])
    frame["amplitude_pass"] = (
        frame["amp_a_adc"] > config.amplitude_cut_adc
    ) & (frame["amp_b_adc"] > config.amplitude_cut_adc)
    frame["complete_pair"] = frame["finite"] & frame["amplitude_pass"]
    frame = frame[frame["complete_pair"]].copy()
    peak_alignment_ns = (
        peak_offsets_samples[stave_b] - peak_offsets_samples[stave_a]
    ) * dataset.sample_period_ns
    tof_difference = config.tof_ns[stave_b] - config.tof_ns[stave_a]
    frame["raw_difference_ns"] = frame["t_b_ns"] - frame["t_a_ns"]
    frame["tof_corrected_ns"] = frame["raw_difference_ns"] - tof_difference
    frame["residual_ns"] = frame["tof_corrected_ns"] - peak_alignment_ns
    frame["amplitude_geomean_adc"] = np.sqrt(frame["amp_a_adc"] * frame["amp_b_adc"])
    frame["minimum_slope_adc_per_ns"] = np.minimum(
        frame["slope_a_adc_per_ns"], frame["slope_b_adc_per_ns"]
    )
    frame["phase_difference"] = frame["phase_b"] - frame["phase_a"]
    return frame


def solve_independent_stave_variances(
    pair_variances: Mapping[tuple[str, str], float],
    staves: Sequence[str],
) -> dict[str, Any]:
    stave_list = list(staves)
    pair_list = sorted(pair_variances)
    if len(stave_list) < 3 or len(pair_list) < 3:
        return {
            "authorized": False,
            "reason": "at least three connected pair variances are required",
            "stave_sigma_ns": {},
        }
    design = np.zeros((len(pair_list), len(stave_list)), dtype=float)
    target = np.zeros(len(pair_list), dtype=float)
    for row_index, pair in enumerate(pair_list):
        first, second = pair
        design[row_index, stave_list.index(first)] = 1.0
        design[row_index, stave_list.index(second)] = 1.0
        target[row_index] = float(pair_variances[pair])
    variance_solution, residual_norm = nnls(design, target)
    predicted = design @ variance_solution
    target_norm = float(np.linalg.norm(target))
    relative_closure_residual = (
        float(residual_norm / target_norm) if target_norm > 0.0 else float("inf")
    )
    model_closure_pass = bool(relative_closure_residual <= 0.10)
    return {
        "authorized": model_closure_pass,
        "fit_available": True,
        "model_closure_pass": model_closure_pass,
        "relative_closure_residual": relative_closure_residual,
        "model": "independent_zero_covariance_variance_model",
        "stave_variance_ns2": {
            stave: float(value) for stave, value in zip(stave_list, variance_solution, strict=True)
        },
        "stave_sigma_ns": {
            stave: float(math.sqrt(max(value, 0.0)))
            for stave, value in zip(stave_list, variance_solution, strict=True)
        },
        "pair_variance_observed_ns2": {
            f"{first}-{second}": float(pair_variances[(first, second)])
            for first, second in pair_list
        },
        "pair_variance_predicted_ns2": {
            f"{first}-{second}": float(predicted[index])
            for index, (first, second) in enumerate(pair_list)
        },
        "nnls_residual_norm": float(residual_norm),
        "warning": (
            "This solution is valid only if pair populations match and inter-stave "
            "covariances are negligible or modeled separately."
        ),
    }


def build_cutflow(
    dataset: WaveformDataset,
    config: LaneConfig,
    result_parts: Mapping[str, np.ndarray],
) -> pd.DataFrame:
    channels = [config.staves[stave] for stave in config.staves]
    selected_amplitude = result_parts["selected_amplitude"][:, channels]
    selected_peak = result_parts["selected_peak"][:, channels]
    finite_time = result_parts["finite_time"][:, channels]
    baseline_rms = result_parts["baseline_rms"][:, channels]
    n_events = dataset.waveforms.shape[0]
    amplitude_any = np.any(selected_amplitude > config.amplitude_cut_adc, axis=1)
    physical_window = np.any(
        (selected_peak > 0) & (selected_peak < dataset.waveforms.shape[2] - 1), axis=1
    )
    finite_any = np.any(finite_time, axis=1)
    stable_baseline = np.any(np.isfinite(baseline_rms), axis=1)
    rows = [
        ("raw events", n_events),
        ("baseline computed", int(np.count_nonzero(stable_baseline))),
        ("at least one selected component", int(np.count_nonzero(physical_window))),
        ("at least one amplitude pass", int(np.count_nonzero(amplitude_any))),
        ("at least one finite CFD time", int(np.count_nonzero(finite_any))),
    ]
    return pd.DataFrame(rows, columns=["stage", "events"])
