def phase_for_sample(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for phase, samples in config["phase_bins"].items():
        for sample in samples:
            out[int(sample)] = str(phase)
    return out
