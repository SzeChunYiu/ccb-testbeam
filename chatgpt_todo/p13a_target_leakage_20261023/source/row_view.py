
def row_view(
    config: dict,
    waves: np.ndarray,
    meta: pd.DataFrame,
    pulse_idx: np.ndarray,
    template_norm: np.ndarray,
    interp_norm: np.ndarray,
) -> dict:
    nsamp = int(config["samples_per_channel"])
    phase_lookup = phase_for_sample(config)
    wf = waves[pulse_idx].astype(np.float32)
    amp = meta["amplitude_adc"].to_numpy(dtype=np.float32)[pulse_idx]
    norm = wf / np.maximum(amp[:, None], 1.0)
    n_pulse = len(pulse_idx)
    sample_idx = np.tile(np.arange(nsamp, dtype=np.int16), n_pulse)
    pulse_row = np.repeat(np.arange(n_pulse, dtype=np.int32), nsamp)
    raw_pulse_index = np.repeat(pulse_idx.astype(np.int32), nsamp)
    target_norm = norm.reshape(-1).astype(np.float32)
    target_adc = wf.reshape(-1).astype(np.float32)
    amp_row = np.repeat(amp, nsamp).astype(np.float32)
    run_row = np.repeat(meta["run"].to_numpy(dtype=np.int16)[pulse_idx], nsamp)
    stave_idx = np.repeat(meta["stave_idx"].to_numpy(dtype=np.int8)[pulse_idx], nsamp)
    peak = np.repeat(meta["peak_sample"].to_numpy(dtype=np.int8)[pulse_idx], nsamp)
    area_over_amp = np.repeat((meta["area_adc_samples"].to_numpy(dtype=np.float32)[pulse_idx] / np.maximum(amp, 1.0)), nsamp)
    context = np.repeat(norm, nsamp, axis=0)
    context[np.arange(len(context)), sample_idx] = 0.0
    sample_onehot = np.zeros((len(context), nsamp), dtype=np.float32)
    sample_onehot[np.arange(len(context)), sample_idx] = 1.0
    stave_onehot = np.zeros((len(context), len(STAVE_NAMES)), dtype=np.float32)
    stave_onehot[np.arange(len(context)), stave_idx] = 1.0
    template_row = template_norm.reshape(-1).astype(np.float32)
    interp_row = interp_norm.reshape(-1).astype(np.float32)
    aux = np.column_stack(
        [
            np.log1p(amp_row),
            peak.astype(np.float32) / max(1, nsamp - 1),
            area_over_amp.astype(np.float32),
            sample_idx.astype(np.float32) / max(1, nsamp - 1),
            template_row,
            interp_row,
        ]
    ).astype(np.float32)
    x_tab = np.hstack([context, sample_onehot, stave_onehot, aux]).astype(np.float32)
    return {
        "x_tab": x_tab,
        "context": context.astype(np.float32),
        "aux": np.hstack([sample_onehot, stave_onehot, aux]).astype(np.float32),
        "target_norm": target_norm,
        "target_adc": target_adc,
        "amp": amp_row,
        "sample_idx": sample_idx,
        "phase": np.asarray([phase_lookup[int(s)] for s in sample_idx], dtype=object),
        "run": run_row,
        "stave_idx": stave_idx,
        "raw_pulse_index": raw_pulse_index,
        "pulse_row": pulse_row,
        "template": template_row,
        "interp": interp_row,
    }
