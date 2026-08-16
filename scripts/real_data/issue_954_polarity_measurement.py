#!/usr/bin/env python3
"""Measured per-run channel-polarity study (#954).

Closes the measurement gap: `configs/channel_polarity_v1.json` is locked from the
duplicate-readout convention; this study independently MEASURES the sign of every
channel in every one of the 33 manifest runs of the pre-threshold 8x16 raw product,
tests stationarity across runs, cross-checks the locked map, and records synthetic
negative controls (sign-flip recovery, low-SNR fail-closed, low-word dropout
robustness). It does not mutate the locked map; a confirmation/contradiction
verdict is written to reports/studies/paper_954_polarity/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import uproot

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from channel_polarity import (  # noqa: E402
    ChannelPolarityMap,
    infer_channel_polarity,
    load_polarity_map,
    mask_isolated_dropouts,
)

N_CHANNELS = 8
SAMPLES_PER_CHANNEL = 16
BASELINE_SAMPLES = [0, 1, 2, 3]


def compute_file_sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def read_waveforms(path: Path) -> np.ndarray:
    """Read HRD ROOT waveforms -> (n_events, 8, 16) int32 (same contract as #1318)."""
    with uproot.open(path) as f:
        tree = f["h101;1"]
        hrdv = tree["HRDv"].array(library="np")
    waveforms = np.zeros((len(hrdv), N_CHANNELS * SAMPLES_PER_CHANNEL), dtype=np.int32)
    for i, evt in enumerate(hrdv):
        waveforms[i, :] = evt
    return waveforms.reshape(len(hrdv), N_CHANNELS, SAMPLES_PER_CHANNEL)


def independent_sign_stats(raw: np.ndarray, k_sigma: float = 8.0) -> dict:
    """Run-level independent estimator: MAD-noise-normalised excursion vote.

    Deliberately independent of channel_polarity.infer_channel_polarity: noise is
    the robust MAD of the RAW pretrigger samples (no positivity-forcing, no
    baseline-subtracted residual noise), and the sign is the majority vote among
    events whose excursion on either side exceeds k_sigma.
    """
    raw = np.asarray(raw, dtype=float)
    base = np.median(raw[:, :, BASELINE_SAMPLES], axis=-1)
    sigma = 1.4826 * np.median(
        np.abs(raw[:, :, BASELINE_SAMPLES] - base[:, :, None]), axis=-1
    ) + 1e-9
    corrected = raw - base[:, :, None]
    corrected = mask_isolated_dropouts(corrected)
    pos_exc = (np.max(corrected, axis=-1) / sigma) >= k_sigma
    neg_exc = (-np.min(corrected, axis=-1) / sigma) >= k_sigma
    stats = {}
    for ch in range(raw.shape[1]):
        votes_pos = int(np.sum(pos_exc[:, ch] & ~neg_exc[:, ch]))
        votes_neg = int(np.sum(neg_exc[:, ch] & ~pos_exc[:, ch]))
        n_both = int(np.sum(pos_exc[:, ch] & neg_exc[:, ch]))
        n_none = int(np.sum(~pos_exc[:, ch] & ~neg_exc[:, ch]))
        decided = votes_pos + votes_neg
        if decided == 0:
            stats[str(ch)] = {
                "sign": 0, "status": "UNMEASURED_LOW_SNR",
                "votes_pos": votes_pos, "votes_neg": votes_neg,
                "n_both_sided": n_both, "n_no_excursion": n_none,
                "frac_positive": None, "authorising": False,
            }
            continue
        sign = 1 if votes_pos >= votes_neg else -1
        stats[str(ch)] = {
            "sign": sign,
            "status": "MEASURED",
            "votes_pos": votes_pos, "votes_neg": votes_neg,
            "n_both_sided": n_both, "n_no_excursion": n_none,
            "frac_positive": votes_pos / decided,
            "authorising": votes_pos / decided > 0.5 or votes_neg / decided > 0.5,
        }
    return stats


def stationarity(per_run: dict) -> dict:
    """Channel-level stationarity across runs + agreement between the two estimators."""
    out = {}
    for ch in range(N_CHANNELS):
        key = str(ch)
        module_signs = [v["module"][key]["assigned"] for v in per_run.values()
                        if v["module"][key]["assigned"] is not None]
        indep_signs = [v["independent"][key]["sign"] for v in per_run.values()]
        distinct_module = sorted({s for s in module_signs})
        distinct_indep = sorted({s for s in indep_signs})
        out[key] = {
            "module_signs": distinct_module,
            "independent_signs": distinct_indep,
            "module_stationary": len(distinct_module) == 1 and distinct_module != [0],
            "independent_stationary": len(distinct_indep) == 1 and distinct_indep != [0],
            "estimators_agree": distinct_module == distinct_indep
            and len(distinct_module) == 1,
        }
    return out


# --- synthetic negative controls (recorded into the artifact) ---

def toy_batch(signs: list[int], n_events: int = 500, seed: int = 954) -> np.ndarray:
    """Deterministic batch: per channel a clean pulse of the given sign on a pedestal."""
    rng = np.random.default_rng(seed)
    data = np.zeros((n_events, N_CHANNELS, SAMPLES_PER_CHANNEL))
    for ch, s in enumerate(signs):
        base = 5000.0 + 100 * ch
        data[:, ch, :4] = base + rng.normal(0, 2.0, (n_events, 4))
        amp = 400.0 + 50 * ch
        shape = np.zeros(SAMPLES_PER_CHANNEL)
        shape[6:10] = amp * np.array([0.3, 1.0, 0.8, 0.4])
        data[:, ch, 4:] = base + s * shape[4:] + rng.normal(0, 2.0, (n_events, 12))
    return data


def negative_controls() -> dict:
    truth = [1, -1, 1, -1, 1, -1, 1, -1]
    batch = toy_batch(truth)
    pol_mod, diag_mod = infer_channel_polarity(batch, BASELINE_SAMPLES)
    indep = independent_sign_stats(batch)
    recovered = [int(pol_mod[ch]) for ch in range(N_CHANNELS)]

    flipped = toy_batch([-s for s in truth], seed=955)
    pol_flip, _ = infer_channel_polarity(flipped, BASELINE_SAMPLES)
    recovered_flipped = [int(pol_flip[ch]) for ch in range(N_CHANNELS)]

    noise = np.full((200, N_CHANNELS, SAMPLES_PER_CHANNEL), 5000.0)
    rng = np.random.default_rng(1)
    noise += rng.normal(0, 2.0, noise.shape)
    pol_noise, diag_noise = infer_channel_polarity(noise, BASELINE_SAMPLES)

    dropout = toy_batch(truth, n_events=300, seed=956).copy()
    dropout[:, 0::2, 9] = -16383.0  # low-word dropout on every positive channel
    pol_drop, _ = infer_channel_polarity(dropout, BASELINE_SAMPLES)
    indep_drop = independent_sign_stats(dropout)
    recovered_dropout = [int(pol_drop[ch]) for ch in range(N_CHANNELS)]

    return {
        "sign_truth": truth,
        "synthetic_truth_recovered": recovered == truth,
        "sign_flipped_truth_recovered": recovered_flipped == [-s for s in truth],
        "low_snr_fails_closed": all(
            pol_noise[ch] == 0 and not diag_noise["channels"][str(ch)]["authorising"]
            for ch in range(N_CHANNELS)
        ),
        "dropout_does_not_flip_module": recovered_dropout == truth,
        "dropout_independent_signs": {
            ch: indep_drop[ch]["sign"] for ch in indep_drop
        },
        "dropout_does_not_flip_independent": all(
            indep_drop[str(ch)]["sign"] == truth[ch] for ch in range(N_CHANNELS)
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=REPO_ROOT
                    / "reports/studies/paper_1318_depth_profile/manifest_8x16.json")
    ap.add_argument("--polarity-config", type=Path, default=REPO_ROOT
                    / "configs/channel_polarity_v1.json")
    ap.add_argument("--output-dir", type=Path, default=REPO_ROOT
                    / "reports/studies/paper_954_polarity")
    ap.add_argument("--snr-cut", type=float, default=8.0)
    ap.add_argument("--verify-sha", action="store_true", default=True)
    args = ap.parse_args(argv)

    manifest = json.loads(args.manifest.read_text())
    locked = load_polarity_map(args.polarity_config)
    per_run = {}
    sha_ok = True
    for entry in manifest["input_files"]:
        run = int(entry["run"])
        path = Path(entry["path"])
        if not path.exists():
            per_run[str(run)] = {"error": f"missing raw file {path}"}
            sha_ok = False
            continue
        if args.verify_sha:
            got = compute_file_sha256(path)
            if got != entry["sha256"]:
                per_run[str(run)] = {"error": f"sha mismatch {path}"}
                sha_ok = False
                continue
        raw = read_waveforms(path)
        pol, diag = infer_channel_polarity(raw, BASELINE_SAMPLES, snr_cut=args.snr_cut)
        per_run[str(run)] = {
            "n_events": int(raw.shape[0]),
            "module": {str(ch): {
                "assigned": int(pol[ch]) if pol[ch] != 0 else None,
                **{k: diag["channels"][str(ch)][k] for k in
                   ("status", "n_strong", "frac_positive_preference", "authorising")},
            } for ch in range(N_CHANNELS)},
            "independent": independent_sign_stats(raw, k_sigma=args.snr_cut),
        }

    stat = stationarity(per_run) if all("error" not in v for v in per_run.values()) else {}
    controls = negative_controls()
    agreement_with_locked = {
        str(ch): {
            "locked": locked.polarity_for_channel(ch),
            "measured_module": stat[str(ch)]["module_signs"],
            "measured_independent": stat[str(ch)]["independent_signs"],
            "confirmed": (stat[str(ch)]["module_signs"] == [locked.polarity_for_channel(ch)]
                          and stat[str(ch)]["independent_signs"] == [locked.polarity_for_channel(ch)]),
        } for ch in range(N_CHANNELS)
    } if stat else {}

    all_confirmed = bool(stat) and all(v["confirmed"] for v in agreement_with_locked.values())
    all_controls_pass = all(
        controls[k] for k in
        ("synthetic_truth_recovered", "sign_flipped_truth_recovered",
         "low_snr_fails_closed", "dropout_does_not_flip_module",
         "dropout_does_not_flip_independent")
    )

    result = {
        "schema": "issue_954_polarity_measurement_v1",
        "issue": 954,
        "manifest_source": str(args.manifest.relative_to(REPO_ROOT)),
        "n_runs": len(per_run),
        "sha256_all_verified": sha_ok,
        "snr_cut": args.snr_cut,
        "baseline_samples": BASELINE_SAMPLES,
        "per_run": per_run,
        "stationarity": stat,
        "agreement_with_locked_map": agreement_with_locked,
        "negative_controls": controls,
        "verdict": {
            "all_runs_sha_verified": sha_ok,
            "all_channels_measured": bool(stat) and all(
                stat[str(ch)]["module_signs"] not in ([], [0]) for ch in range(N_CHANNELS)),
            "stationary_across_runs": bool(stat) and all(
                stat[str(ch)]["module_stationary"] and stat[str(ch)]["independent_stationary"]
                for ch in range(N_CHANNELS)),
            "estimators_agree": bool(stat) and all(
                stat[str(ch)]["estimators_agree"] for ch in range(N_CHANNELS)),
            "locked_map_confirmed": all_confirmed,
            "negative_controls_pass": all_controls_pass,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "result.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result["verdict"], indent=1))
    return 0 if (sha_ok and stat) else 1


if __name__ == "__main__":
    raise SystemExit(main())
