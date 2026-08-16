"""#954 falsification check: does the 8x16 depth-profile claim survive the
measured polarity map?

Recomputes the #1318 depth-profile observable directly from the raw ROOT files
(SHA-256-verified by the measurement study) under three polarity hypotheses:

* ``v1``    — locked map (channels 2-7 wrong per the measurement study);
* ``meas_even`` — measured signs on the even (stave) channels;
* ``meas_odd``  — measured signs on the odd duplicate-partner channels.

Same samples, thresholds, amplitude convention and normalization as
``analyze_depth_profile_8x16.py``. The v1 arm reproduces the committed
``depth_profile_result_thresh_0.json`` numbers exactly, which validates the
recomputation pipeline before the corrected arms are read.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "real_data"))

import numpy as np  # noqa: E402
from channel_polarity import mask_isolated_dropouts  # noqa: E402
from issue_954_polarity_measurement import read_waveforms  # noqa: E402

MEASURED = np.array([1, -1, -1, 1, -1, 1, -1, 1])
V1 = np.array([1, -1, 1, -1, 1, -1, 1, -1])
EVEN = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
ODD = {"B2": 1, "B4": 3, "B6": 5, "B8": 7}
SAMPLE_I = [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42,
            44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]
SAMPLE_II = [58, 59, 60, 61, 62, 63, 64, 65]
THRESHOLDS = (0, 500, 750, 1000)
ROOT_DIR = Path("/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root")


def profile(sums: dict, tag: str, staves: dict, threshold: int, sample: str) -> dict:
    means = {}
    for stave, ch in staves.items():
        s, n = sums[(tag, sample, ch, threshold)]
        means[stave] = s / n if n else 0.0
    total = sum(means.values())
    return {
        "amplitude_means": {k: round(v, 1) for k, v in means.items()},
        "normalized": {k: (round(v / total, 4) if total else 0.0) for k, v in means.items()},
        "b8_over_b2": round(means["B8"] / means["B2"], 4) if means["B2"] else None,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root-dir", type=Path, default=ROOT_DIR)
    ap.add_argument("--output", type=Path,
                    default=REPO / "reports/studies/paper_954_polarity/depth_profile_falsification.json")
    args = ap.parse_args(argv)

    sums: dict = {}
    for run in SAMPLE_I + SAMPLE_II:
        sample = "I" if run in SAMPLE_I else "II"
        raw = read_waveforms(args.root_dir / f"hrdb_run_{run:04d}.root")
        baseline = np.median(raw[:, :, :4], axis=-1, keepdims=True)
        corrected = mask_isolated_dropouts(raw - baseline)
        for tag, polarity in (("v1", V1), ("meas", MEASURED)):
            amp = np.where(polarity == 1, corrected.max(axis=-1), -corrected.min(axis=-1))
            for ch in range(8):
                for threshold in THRESHOLDS:
                    mask = amp[:, ch] >= threshold
                    key = (tag, sample, ch, threshold)
                    s, n = sums.get(key, (0.0, 0))
                    sums[key] = (s + float(amp[mask, ch].sum()), n + int(mask.sum()))
        del raw, corrected

    out = {"schema": "issue_954_profile_falsification_v1",
           "thresholds": list(THRESHOLDS),
           "profiles": {}}
    for threshold in THRESHOLDS:
        for sample in ("I", "II"):
            out["profiles"].setdefault(str(threshold), {})[sample] = {
                "v1": profile(sums, "v1", EVEN, threshold, sample),
                "meas_even": profile(sums, "meas", EVEN, threshold, sample),
                "meas_odd": profile(sums, "meas", ODD, threshold, sample),
            }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=1))
    print(json.dumps(out["profiles"]["0"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
