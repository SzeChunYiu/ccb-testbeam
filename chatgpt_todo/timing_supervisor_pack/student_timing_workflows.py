#!/usr/bin/env python3
# ruff: noqa: F403, F405
"""Modular component of the student timing walkthrough."""
from student_timing_types import *  # noqa: F403
from student_timing_data import *  # noqa: F403
from student_timing_analysis import *  # noqa: F403
from student_timing_plots_basic import *  # noqa: F403
from student_timing_plots_advanced import *  # noqa: F403
from student_timing_report import *  # noqa: F403


def split_runs(runs: np.ndarray) -> tuple[tuple[int, ...], tuple[int, ...]]:
    unique = tuple(int(value) for value in sorted(np.unique(runs)))
    if len(unique) < 2:
        return unique, unique
    split = max(1, int(math.floor(0.3 * len(unique))))
    return unique[:split], unique[split:]


def make_lane_config(
    dataset: WaveformDataset,
    *,
    name: str,
    description: str,
    polarity: np.ndarray,
    authorising: bool,
    watermark_text: str | None,
    polarity_status: str,
    amplitude_cut_adc: float,
    analysis_fraction: float = 0.20,
    source_frame_authorized: bool = True,
    component_identity_authorized: bool = False,
    resolution_model_authorized: bool = False,
) -> LaneConfig:
    calibration_runs, test_runs = split_runs(dataset.runs)
    return LaneConfig(
        name=name,
        description=description,
        staves=dict(DEFAULT_STAVES),
        polarity=np.asarray(polarity, dtype=float),
        baseline_samples=(0, 1, 2, 3),
        fractions=DEFAULT_FRACTIONS,
        analysis_fraction=analysis_fraction,
        amplitude_cut_adc=float(amplitude_cut_adc),
        component_mode="first_local_peak",
        tof_ns=dict(DEFAULT_TOF_NS),
        calibration_runs=calibration_runs,
        test_runs=test_runs,
        authorising=authorising,
        source_frame_authorized=source_frame_authorized,
        component_identity_authorized=component_identity_authorized,
        resolution_model_authorized=resolution_model_authorized,
        watermark=watermark_text,
        polarity_status=polarity_status,
    )


def run_demo(out_dir: Path, n_events: int, seed: int) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    physical_dataset = generate_physical_demo(n_events, seed)
    physical_config = make_lane_config(
        physical_dataset,
        name="physical_subsample_timing_demo",
        description=(
            "Known pulses are present on every stave. The pair residual is expected to be near "
            "0.1 ns because the injected stave jitters and voltage-noise/slope term are small."
        ),
        polarity=PHYSICAL_MAP,
        authorising=False,
        watermark_text="SYNTHETIC_METHOD_CLOSURE_NOT_BEAM_DATA",
        polarity_status="SYNTHETIC_TRUTH",
        amplitude_cut_adc=800.0,
        analysis_fraction=0.50,
        component_identity_authorized=True,
        resolution_model_authorized=True,
    )
    physical_result = analyze_lane(physical_dataset, physical_config)
    physical_stems = generate_lane_plots(
        physical_dataset, physical_result, out_dir, "physical"
    )
    closure_stem = plot_closure_grid(out_dir / "plots", seed + 17)
    physical_stems.append(closure_stem)

    correct_dataset, legacy_dataset = generate_artifact_demo(n_events, seed + 1)
    correct_config = make_lane_config(
        correct_dataset,
        name="correct_8x18_pulse_identity_demo",
        description=(
            "The correct frame contains a real pulse on B2 and its duplicate, while B4/B6/B8 "
            "are quiet. The analysis should stop before claiming downstream pair timing."
        ),
        polarity=PHYSICAL_MAP,
        authorising=False,
        watermark_text="SYNTHETIC_FRAME_IDENTITY_DEMO",
        polarity_status="LOCKED_FROM_DUPLICATE_READOUT_CONVENTION",
        amplitude_cut_adc=800.0,
        component_identity_authorized=False,
    )
    correct_result = analyze_lane(correct_dataset, correct_config)
    correct_stems = generate_lane_plots(correct_dataset, correct_result, out_dir, "correct")

    legacy_config = make_lane_config(
        legacy_dataset,
        name="legacy_truncation_artifact_reproduction",
        description=(
            "Each correct 144-word event is deliberately truncated to 128 words and reshaped "
            "as 8 x 16. Pedestal boundaries become pseudo-pulses and create a narrow pair core."
        ),
        polarity=RETRACTED_ARTIFACT_MAP,
        authorising=False,
        watermark_text="NON_PHYSICAL_DELIBERATE_TRUNCATION_ARTIFACT",
        polarity_status="RETRACTED_20260816_TRUNCATED_STAGING_DESYNC",
        amplitude_cut_adc=800.0,
        analysis_fraction=0.60,
        source_frame_authorized=False,
        component_identity_authorized=False,
    )
    legacy_result = analyze_lane(legacy_dataset, legacy_config)
    legacy_stems = generate_lane_plots(legacy_dataset, legacy_result, out_dir, "legacy")
    comparison = plot_correct_legacy_comparison(
        correct_dataset,
        correct_result,
        legacy_dataset,
        legacy_result,
        out_dir / "plots",
    )
    comparison_stems = [comparison]

    lane_records = [
        (physical_dataset, physical_result, physical_stems),
        (correct_dataset, correct_result, correct_stems),
        (legacy_dataset, legacy_result, legacy_stems),
    ]
    for _dataset, result, _stems in lane_records:
        result.pair_metrics.to_csv(
            out_dir / f"{result.config.name}_pair_metrics.csv", index=False
        )
        result.cutflow.to_csv(out_dir / f"{result.config.name}_cutflow.csv", index=False)
    summary = {
        "schema": SCHEMA,
        "mode": "demo",
        "physical": physical_result.summary,
        "correct_frame": correct_result.summary,
        "legacy_artifact": legacy_result.summary,
        "comparison_plots": comparison_stems,
    }
    (out_dir / "analysis_summary.json").write_text(
        json.dumps(
            json_safe(summary), indent=2, sort_keys=True, allow_nan=False
        ),
        encoding="utf-8",
    )
    write_report(out_dir, lane_records, comparison_stems)
    return summary


def polarity_from_json(path: Path, n_channels: int) -> tuple[np.ndarray, str]:
    if load_polarity_map is None:
        raise RuntimeError("canonical channel_polarity module is unavailable")
    polarity_map = load_polarity_map(path)
    return polarity_map.polarity_vector(n_channels), polarity_map.status


def run_raw(config_path: Path, out_dir: Path) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("raw config must be a YAML mapping")
    dataset = load_raw_dataset(config)
    n_channels = dataset.waveforms.shape[1]
    staves = {str(key): int(value) for key, value in config.get("staves", DEFAULT_STAVES).items()}
    polarity_path = Path(config["polarity_map"])
    polarity, polarity_status = polarity_from_json(polarity_path, n_channels)
    calibration_runs = tuple(int(value) for value in config["calibration_runs"])
    test_runs = tuple(int(value) for value in config["test_runs"])
    physical_config = LaneConfig(
        name="raw_physical_lane",
        description="Correct per-event frame, source-bound polarity, and held-out run split.",
        staves=staves,
        polarity=polarity,
        baseline_samples=tuple(int(value) for value in config.get("baseline_samples", [0, 1, 2, 3])),
        fractions=tuple(float(value) for value in config.get("fractions", DEFAULT_FRACTIONS)),
        analysis_fraction=float(config.get("analysis_fraction", 0.20)),
        amplitude_cut_adc=float(config.get("amplitude_cut_adc", 1000.0)),
        component_mode="first_local_peak",
        tof_ns={str(key): float(value) for key, value in config.get("tof_ns", DEFAULT_TOF_NS).items()},
        calibration_runs=calibration_runs,
        test_runs=test_runs,
        authorising=bool(config.get("authorising", True)),
        source_frame_authorized=bool(
            config.get("source_frame_authorized", False)
        ),
        component_identity_authorized=bool(
            config.get("component_identity_authorized", False)
        ),
        resolution_model_authorized=bool(
            config.get("allow_independent_zero_covariance_resolution_model", False)
        ),
        watermark=None,
        polarity_status=polarity_status,
    )
    physical_result = analyze_lane(dataset, physical_config)
    physical_stems = generate_lane_plots(dataset, physical_result, out_dir, "raw")
    lane_records: list[tuple[WaveformDataset, LaneResult, list[str]]] = [
        (dataset, physical_result, physical_stems)
    ]
    comparison_stems: list[str] = []

    legacy_config_raw = config.get("legacy_artifact_reproduction", {})
    legacy_summary = None
    if bool(legacy_config_raw.get("enabled", False)):
        truncate_words = int(legacy_config_raw.get("truncate_words", 128))
        legacy_samples = int(legacy_config_raw.get("samples_per_channel", 16))
        if dataset.waveforms.shape[1] * dataset.waveforms.shape[2] < truncate_words:
            raise ValueError("input frame is shorter than requested legacy truncation")
        legacy_flat = dataset.waveforms.reshape(dataset.waveforms.shape[0], -1)[:, :truncate_words]
        if truncate_words != dataset.waveforms.shape[1] * legacy_samples:
            raise ValueError("legacy truncate_words must equal n_channels * legacy samples")
        legacy_dataset = WaveformDataset(
            label=f"{dataset.label}_legacy_truncated",
            runs=dataset.runs,
            event_ids=dataset.event_ids,
            waveforms=legacy_flat.reshape(dataset.waveforms.shape[0], n_channels, legacy_samples),
            sample_period_ns=dataset.sample_period_ns,
            channel_labels=[f"legacy_block{index}" for index in range(n_channels)],
            word_counts=np.full(dataset.waveforms.shape[0], truncate_words),
            source_files=dataset.source_files,
            source_sha256=dataset.source_sha256,
            metadata={"watermark": "NON_PHYSICAL_LEGACY_REPRODUCTION"},
        )
        legacy_polarity_path = Path(legacy_config_raw["polarity_map"])
        legacy_polarity, legacy_status = polarity_from_json(legacy_polarity_path, n_channels)
        legacy_config = LaneConfig(
            name="raw_legacy_artifact_lane",
            description="Explicit diagnostic reproduction of a non-authorising legacy frame.",
            staves=staves,
            polarity=legacy_polarity,
            baseline_samples=tuple(int(value) for value in config.get("baseline_samples", [0, 1, 2, 3])),
            fractions=physical_config.fractions,
            analysis_fraction=physical_config.analysis_fraction,
            amplitude_cut_adc=physical_config.amplitude_cut_adc,
            component_mode="first_local_peak",
            tof_ns=physical_config.tof_ns,
            calibration_runs=calibration_runs,
            test_runs=test_runs,
            authorising=False,
            source_frame_authorized=False,
            component_identity_authorized=False,
            resolution_model_authorized=False,
            watermark="NON_PHYSICAL_LEGACY_REPRODUCTION",
            polarity_status=legacy_status,
        )
        legacy_result = analyze_lane(legacy_dataset, legacy_config)
        legacy_stems = generate_lane_plots(
            legacy_dataset, legacy_result, out_dir, "raw_legacy"
        )
        comparison_stems.append(
            plot_correct_legacy_comparison(
                dataset,
                physical_result,
                legacy_dataset,
                legacy_result,
                out_dir / "plots",
            )
        )
        lane_records.append((legacy_dataset, legacy_result, legacy_stems))
        legacy_summary = legacy_result.summary

    out_dir.mkdir(parents=True, exist_ok=True)
    for _dataset, result, _stems in lane_records:
        result.pair_metrics.to_csv(
            out_dir / f"{result.config.name}_pair_metrics.csv", index=False
        )
        result.cutflow.to_csv(out_dir / f"{result.config.name}_cutflow.csv", index=False)
    summary = {
        "schema": SCHEMA,
        "mode": "raw",
        "config": str(config_path),
        "source_files": dataset.source_files,
        "source_sha256": dataset.source_sha256,
        "physical": physical_result.summary,
        "legacy_artifact": legacy_summary,
        "comparison_plots": comparison_stems,
    }
    (out_dir / "analysis_summary.json").write_text(
        json.dumps(
            json_safe(summary), indent=2, sort_keys=True, allow_nan=False
        ),
        encoding="utf-8",
    )
    write_report(out_dir, lane_records, comparison_stems)
    return summary
