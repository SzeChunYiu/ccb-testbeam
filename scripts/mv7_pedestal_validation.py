#!/usr/bin/env python3
"""
mv7_pedestal_validation.py
==========================
MV7 — pedestal-estimator validation on the MC zero-signal sample.

Compares two pedestal estimators against the KNOWN truth pedestal on the
pure pedestal+noise records emitted by
``scripts/mc02_build_mc_pulse_table.py --zero-signal N``:

  1. adaptive estimator  — median(samples 0-3), i.e. exactly the s00/data
     ``baseline_adc`` estimator;
  2. learned estimator   — closed-form ridge regression (numpy, no sklearn)
     from all 18 samples to the truth pedestal, trained on the first half of
     the records and evaluated on the held-out second half.

Reported metric: MAE [ADC] of each estimator on the held-out half (the
adaptive estimator is evaluated on the same held-out half for a paired
comparison).

LIMITATION (state clearly): this closes the 'no true pedestal sample' gap AT
MC LEVEL ONLY. Real data provides no true-pedestal ground truth; the MC noise
model is white Gaussian at the card noise scale with a uniform per-record
pedestal jitter over the observed data baseline range [6737, 7029] ADC.
Correlated noise, baseline drift within a waveform, and signal contamination
of the pre-pulse window are NOT modelled here, so these MAEs are a lower
bound on real-data pedestal error.

Usage:
  mv7_pedestal_validation.py --zero-signal <mc02_zero_signal.csv.gz> --out <dir>
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))


def load_zero_signal(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (samples[N,18], pedestal_true[N], baseline_adc[N])."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
        sample_cols = [i for i, c in enumerate(header) if c.startswith("s") and c[1:].isdigit()]
        ped_col = header.index("pedestal_true_adc")
        base_col = header.index("baseline_adc")
        samples, ped, base = [], [], []
        for line in handle:
            parts = line.rstrip("\n").split(",")
            samples.append([float(parts[i]) for i in sample_cols])
            ped.append(float(parts[ped_col]))
            base.append(float(parts[base_col]))
    return np.asarray(samples), np.asarray(ped), np.asarray(base)


def ridge_fit(X: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> tuple[np.ndarray, float]:
    """Closed-form ridge regression with intercept (features centred)."""
    x_mean = X.mean(axis=0)
    y_mean = float(y.mean())
    Xc = X - x_mean
    yc = y - y_mean
    n_feat = X.shape[1]
    w = np.linalg.solve(Xc.T @ Xc + alpha * np.eye(n_feat), Xc.T @ yc)
    b = y_mean - float(x_mean @ w)
    return w, b


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zero-signal", required=True, help="mc02_zero_signal.csv.gz")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--ridge-alpha", type=float, default=1.0)
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    samples, ped_true, baseline = load_zero_signal(Path(args.zero_signal))
    n = len(ped_true)
    if n < 100:
        raise SystemExit(f"zero-signal sample too small for a split ({n} records)")
    half = n // 2  # deterministic split; records are i.i.d. by construction

    # adaptive (s00) estimator: median of samples 0-3 — recompute to be
    # self-contained, and cross-check against the stored baseline_adc column
    adaptive = np.median(samples[:, :4], axis=1)
    if not np.allclose(adaptive, baseline, atol=0.51):
        raise SystemExit("stored baseline_adc disagrees with median(samples 0-3)")

    w, b = ridge_fit(samples[:half], ped_true[:half], alpha=args.ridge_alpha)
    learned = samples[half:] @ w + b

    err_adaptive = adaptive[half:] - ped_true[half:]
    err_learned = learned - ped_true[half:]
    summary = {
        "study_id": "MV7",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "input": str(Path(args.zero_signal).resolve()),
        "n_records": n,
        "n_train": half,
        "n_test": n - half,
        "adaptive_estimator": {
            "definition": "median(samples 0-3) — identical to the s00 data baseline_adc",
            "mae_adc": float(np.abs(err_adaptive).mean()),
            "rmse_adc": float(np.sqrt((err_adaptive ** 2).mean())),
            "bias_adc": float(err_adaptive.mean()),
        },
        "learned_estimator": {
            "definition": f"ridge regression on all {samples.shape[1]} samples (alpha={args.ridge_alpha}), half/half split",
            "mae_adc": float(np.abs(err_learned).mean()),
            "rmse_adc": float(np.sqrt((err_learned ** 2).mean())),
            "bias_adc": float(err_learned.mean()),
        },
        "limitation": (
            "MC-level closure only: real data has no true-pedestal ground truth. "
            "White-Gaussian noise + uniform pedestal jitter [6737, 7029] ADC; "
            "correlated noise / in-waveform drift / signal contamination of the "
            "pre-pulse window are not modelled, so these MAEs are lower bounds."
        ),
    }
    out_path = out_dir / "mv7_pedestal_validation.json"
    out_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"[mv7] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
