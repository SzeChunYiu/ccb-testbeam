#!/usr/bin/env python3
# ruff: noqa: F403, F405
"""Modular component of the student timing walkthrough."""
from student_timing_types import *  # noqa: F403
from student_timing_data import *  # noqa: F403


def analyze_lane(dataset: WaveformDataset, config: LaneConfig) -> LaneResult:
    if len(config.polarity) != dataset.waveforms.shape[1]:
        raise ValueError("polarity vector length must match dataset channel count")
    if config.authorising and config.polarity_status is not None:
        status_upper = config.polarity_status.upper()
        if "RETRACT" in status_upper or "NON_PHYSICAL" in status_upper:
            raise ValueError(
                f"authorising lane refuses polarity status {config.polarity_status!r}"
            )
    event_keys = pd.MultiIndex.from_arrays(
        [dataset.runs, dataset.event_ids], names=["run", "event_id"]
    )
    if event_keys.has_duplicates:
        duplicate = event_keys[event_keys.duplicated()][0]
        raise ValueError(
            "duplicate composite event identity detected; timing rows cannot be paired "
            f"unambiguously (first duplicate={tuple(duplicate)})"
        )

    baseline, baseline_rms, baseline_slope = baseline_features(
        dataset.waveforms,
        config.baseline_samples,
        dataset.sample_period_ns,
    )
    corrected = (dataset.waveforms - baseline[:, :, None]) * config.polarity[None, :, None]
    (
        global_amplitude,
        global_peak,
        selected_amplitude,
        selected_peak,
        selected_ratio,
        selector_status,
        times,
        statuses,
        crossing_slopes,
        phases,
    ) = cfd_features(
        corrected,
        config.fractions,
        config.component_mode,
        dataset.sample_period_ns,
    )

    calibration_mask = np.isin(dataset.runs, np.asarray(config.calibration_runs, dtype=int))
    if not np.any(calibration_mask):
        raise ValueError("calibration_runs select no events")
    test_mask = np.isin(dataset.runs, np.asarray(config.test_runs, dtype=int))
    if not np.any(test_mask):
        raise ValueError("test_runs select no events")
    peak_offsets: dict[str, float] = {}
    for stave, channel in config.staves.items():
        values = selected_peak[calibration_mask, channel]
        values = values[values >= 0]
        peak_offsets[stave] = float(np.median(values)) if values.size else float("nan")

    analysis_time = times[config.analysis_fraction]
    analysis_status = statuses[config.analysis_fraction]
    cutflow = build_cutflow(
        dataset,
        config,
        {
            "selected_amplitude": selected_amplitude,
            "selected_peak": selected_peak,
            "finite_time": np.isfinite(analysis_time) & (analysis_status == "OK"),
            "baseline_rms": baseline_rms,
        },
    )

    pair_vectors: dict[tuple[str, str, float], np.ndarray] = {}
    pair_tables: dict[tuple[str, str, float], pd.DataFrame] = {}
    metric_rows: list[dict[str, Any]] = []
    stave_names = list(config.staves)
    for first_index in range(len(stave_names)):
        for second_index in range(first_index + 1, len(stave_names)):
            stave_a = stave_names[first_index]
            stave_b = stave_names[second_index]
            if not np.isfinite(peak_offsets[stave_a]) or not np.isfinite(peak_offsets[stave_b]):
                continue
            for fraction in config.fractions:
                table = unique_pair_table(
                    dataset,
                    None,
                    times[fraction],
                    selected_amplitude,
                    crossing_slopes[fraction],
                    phases[fraction],
                    stave_a,
                    stave_b,
                    config,
                    peak_offsets,
                )
                table = table[np.isin(table["run"], np.asarray(config.test_runs, dtype=int))].copy()
                key = (stave_a, stave_b, float(fraction))
                pair_tables[key] = table
                vector = table["residual_ns"].to_numpy(dtype=float)
                pair_vectors[key] = vector
                metrics = robust_metrics(vector)
                fit = gaussian_core_diagnostic(vector)
                metric_rows.append(
                    {
                        "stave_a": stave_a,
                        "stave_b": stave_b,
                        "fraction": float(fraction),
                        **metrics,
                        **fit,
                    }
                )
    pair_metrics = pd.DataFrame(metric_rows)

    analysis_pair_variances: dict[tuple[str, str], float] = {}
    for first_index in range(len(stave_names)):
        for second_index in range(first_index + 1, len(stave_names)):
            pair = (stave_names[first_index], stave_names[second_index])
            vector = pair_vectors.get((*pair, config.analysis_fraction), np.asarray([]))
            vector = vector[np.isfinite(vector)]
            if vector.size > 2:
                analysis_pair_variances[pair] = float(np.var(vector, ddof=1))
    inference = solve_independent_stave_variances(analysis_pair_variances, stave_names)
    candidate_pass = bool(inference.get("authorized", False))
    declared_words = int(dataset.waveforms.shape[1] * dataset.waveforms.shape[2])
    frame_width_consistent = bool(
        dataset.word_counts.size > 0 and np.all(dataset.word_counts == declared_words)
    )
    map_not_retracted = bool(
        config.polarity_status is not None
        and "RETRACT" not in config.polarity_status.upper()
        and "NON_PHYSICAL" not in config.polarity_status.upper()
    )
    run_split_disjoint = bool(
        set(config.calibration_runs).isdisjoint(set(config.test_runs))
        and len(config.calibration_runs) > 0
        and len(config.test_runs) > 0
    )
    pair_timing_authorized = bool(
        config.authorising
        and config.source_frame_authorized
        and frame_width_consistent
        and map_not_retracted
        and config.component_identity_authorized
        and run_split_disjoint
    )
    inference["candidate_model_fit_pass"] = candidate_pass
    inference["pair_timing_authorized"] = pair_timing_authorized
    inference["resolution_model_authorized_by_config"] = bool(
        config.resolution_model_authorized
    )
    synthetic_closure = bool(
        dataset.truth_sigma_ns is not None
        and candidate_pass
        and config.source_frame_authorized
        and config.component_identity_authorized
        and config.resolution_model_authorized
        and run_split_disjoint
    )
    physical_resolution = bool(
        dataset.truth_sigma_ns is None
        and candidate_pass
        and pair_timing_authorized
        and config.resolution_model_authorized
    )
    inference["authorized"] = bool(synthetic_closure or physical_resolution)
    inference["authorization_scope"] = (
        "synthetic_method_closure"
        if dataset.truth_sigma_ns is not None and inference["authorized"]
        else "physical_single_stave_resolution"
        if config.authorising and inference["authorized"]
        else "not_authorized"
    )
    if dataset.truth_sigma_ns is not None:
        inference["truth_sigma_ns"] = dict(dataset.truth_sigma_ns)
        if inference.get("authorized"):
            inference["relative_error"] = {
                stave: (
                    inference["stave_sigma_ns"][stave] / dataset.truth_sigma_ns[stave] - 1.0
                )
                for stave in dataset.truth_sigma_ns
                if stave in inference["stave_sigma_ns"]
            }

    analysis_rows = pair_metrics[pair_metrics["fraction"] == config.analysis_fraction]
    summary = {
        "schema": SCHEMA,
        "lane": config.name,
        "description": config.description,
        "dataset": dataset.label,
        "authorising": config.authorising,
        "watermark": config.watermark,
        "polarity_status": config.polarity_status,
        "analysis_fraction": config.analysis_fraction,
        "amplitude_cut_adc": config.amplitude_cut_adc,
        "n_events": int(dataset.waveforms.shape[0]),
        "calibration_runs": list(config.calibration_runs),
        "test_runs": list(config.test_runs),
        "peak_offsets_samples": peak_offsets,
        "authorization_gates": {
            "declared_frame_words": declared_words,
            "frame_width_consistent": frame_width_consistent,
            "source_frame_authorized": bool(config.source_frame_authorized),
            "polarity_map_not_retracted": map_not_retracted,
            "component_identity_authorized": bool(
                config.component_identity_authorized
            ),
            "calibration_test_runs_disjoint": run_split_disjoint,
            "pair_timing_authorized": pair_timing_authorized,
            "resolution_model_authorized": bool(
                config.resolution_model_authorized
            ),
            "single_stave_resolution_authorized": bool(
                physical_resolution
            ),
            "synthetic_method_closure_authorized": bool(synthetic_closure),
        },
        "analysis_pair_metrics": analysis_rows.to_dict(orient="records"),
        "inference": inference,
    }
    return LaneResult(
        config=config,
        dataset_label=dataset.label,
        baseline_adc=baseline,
        baseline_rms_adc=baseline_rms,
        baseline_slope_adc_per_ns=baseline_slope,
        corrected=corrected,
        global_amplitude_adc=global_amplitude,
        global_peak_sample=global_peak,
        selected_amplitude_adc=selected_amplitude,
        selected_peak_sample=selected_peak,
        selected_to_global_ratio=selected_ratio,
        selector_status=selector_status,
        times_ns=times,
        cfd_status=statuses,
        crossing_slope_adc_per_ns=crossing_slopes,
        fractional_phase=phases,
        cutflow=cutflow,
        pair_metrics=pair_metrics,
        pair_vectors=pair_vectors,
        pair_event_tables=pair_tables,
        peak_offsets_samples=peak_offsets,
        inference=inference,
        summary=summary,
    )
