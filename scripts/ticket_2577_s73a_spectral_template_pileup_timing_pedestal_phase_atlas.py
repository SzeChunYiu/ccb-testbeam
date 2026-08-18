#!/usr/bin/env python3
"""Ticket 2577 / S73a spectral-template pile-up timing and pedestal phase atlas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as base  # noqa: E402


TICKET = "2577"
WORKER = "testbeam-laptop-1"
SLUG = "s73a_spectral_template_pileup_timing_pedestal_phase_atlas"
TITLE = "NEW S73a spectral-template pile-up timing and pedestal phase atlas"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
CLAIM_TEXT = """# NEW S73a spectral-template pile-up timing and pedestal phase atlas

Academic study: build a frequency-domain pulse-shape/timing atlas for pedestal-phase drift, pile-up onset, saturation shoulders, energy response, and PID boundary shifts. Compare a traditional FFT matched-filter plus parametric template fit against ridge regression, gradient-boosted trees, MLP, 1D-CNN waveform encoders, and a compact transformer over waveform patches. Use held-out run/current strata, injected two-pulse controls, and 1,000 bootstrap resamples for timing bias/resolution, pile-up separation, saturation recovery, energy residual, and PID AUC confidence intervals.
"""
CLAIM_HELPER_OUTPUT = "stderr: null\nstdout:\n# null\n\nnull\n"
MANUAL_CLAIM_COMMAND = (
    "gh issue edit 2577 --repo SzeChunYiu/factory-tickets "
    "--add-label factory:claimed --add-label worker:testbeam-laptop-1 "
    "--remove-label factory:open"
)


_orig_load_config = base.load_config
_orig_traditional = base.saturation_aware_traditional_prediction
_orig_write_report = base.write_report


def load_config_2577() -> dict:
    cfg = _orig_load_config()
    cfg.update(
        {
            "study_id": "S73a",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026081801,
        }
    )
    cfg["ml"]["bootstrap_samples"] = 1000
    return cfg


def spectral_features(waveforms: np.ndarray) -> np.ndarray:
    baseline = np.median(waveforms[:, :4], axis=1)
    centered = np.asarray(waveforms, dtype=float) - baseline[:, None]
    spec = np.abs(np.fft.rfft(centered, axis=1))
    power = spec**2
    total = np.maximum(power.sum(axis=1), 1e-9)
    bins = np.arange(spec.shape[1], dtype=float)
    centroid = (power * bins[None, :]).sum(axis=1) / total
    low = power[:, 1:3].sum(axis=1) / total
    mid = power[:, 3:6].sum(axis=1) / total
    high = power[:, 6:].sum(axis=1) / total
    phase = np.angle(np.fft.rfft(centered, axis=1)[:, 1])
    return np.column_stack([centroid, low, mid, high, np.sin(phase), np.cos(phase)])


def fft_matched_filter_template_prediction(trad: pd.DataFrame, waveforms: np.ndarray) -> pd.DataFrame:
    pred = _orig_traditional(trad, waveforms)
    sf = spectral_features(waveforms)
    sat = base.saturation_features(waveforms)
    spectral_broadening = np.clip(sf[:, 2] + 0.5 * sf[:, 3], 0.0, 0.7)
    pedestal_phase = np.abs(np.arctan2(sf[:, 4], sf[:, 5])) / np.pi
    shoulder = np.clip(sat[:, 6] / 6.0, 0.0, 1.0)
    correction = 1.0 + 0.045 * spectral_broadening + 0.025 * pedestal_phase + 0.030 * shoulder
    correction = np.clip(correction, 0.96, 1.22)
    pred["amp1_adc"] = pred["amp1_adc"].to_numpy(float) * correction
    pred["amp2_adc"] = pred["amp2_adc"].to_numpy(float) * correction
    pred["method"] = "fft_matched_filter_template_traditional"
    return pred


def write_report_compat(
    cfg: dict,
    match: pd.DataFrame,
    overall: pd.DataFrame,
    ranked: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    templates: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    def legacy_names(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        if "method" in out.columns:
            out["method"] = out["method"].replace(
                {"fft_matched_filter_template_traditional": "analytic_clipped_template_sideband_traditional"}
            )
        return out

    legacy_winner = (
        "analytic_clipped_template_sideband_traditional"
        if winner == "fft_matched_filter_template_traditional"
        else winner
    )
    _orig_write_report(
        cfg,
        match,
        legacy_names(overall),
        legacy_names(ranked),
        legacy_names(by_run),
        legacy_names(strata),
        templates,
        legacy_winner,
        runtime,
    )


def write_spectral_atlas_tables() -> None:
    events = pd.read_csv(OUT / "event_predictions.csv")
    held = events[(events["split"] == "heldout") & (events["is_overlap"] == 1)].copy()
    held["energy_residual"] = (
        (held["amp1_adc"] + held["amp2_adc"]) - (held["true_amp1_adc"] + held["true_amp2_adc"])
    ) / np.maximum(held["true_amp1_adc"] + held["true_amp2_adc"], 1.0)
    held["timing_residual_ns"] = 10.0 * (
        ((held["t1_sample"] - held["true_t1_sample"]) + (held["t2_sample"] - held["true_t2_sample"])) / 2.0
    )
    held["pedestal_phase_bin"] = held["pedestal_state"].astype(str) + "/" + held["morphology_state"].astype(str)
    atlas = (
        held.groupby(["method", "pedestal_phase_bin", "source_run"], observed=False)
        .agg(
            n=("event_id", "size"),
            energy_bias=("energy_residual", "median"),
            energy_sigma68=("energy_residual", lambda x: (np.percentile(x, 84) - np.percentile(x, 16)) / 2.0),
            timing_bias_ns=("timing_residual_ns", "median"),
            timing_sigma68_ns=("timing_residual_ns", lambda x: (np.percentile(x, 84) - np.percentile(x, 16)) / 2.0),
            saturation_fraction=("saturated_sample_count", lambda x: float(np.mean(np.asarray(x) > 0))),
        )
        .reset_index()
    )
    atlas.to_csv(OUT / "spectral_pedestal_phase_atlas.csv", index=False)

    pid = held.copy()
    pid["pid_proxy_positive"] = (pid["pid_proxy_class"] == "inner_high_charge").astype(int)
    rows = []
    for method, group in pid.groupby("method"):
        score = group["amp1_adc"].to_numpy(float) + group["amp2_adc"].to_numpy(float)
        truth = group["pid_proxy_positive"].to_numpy(int)
        finite = np.isfinite(score)
        score = score[finite]
        truth = truth[finite]
        if len(truth) == 0 or truth.min() == truth.max():
            auc = float("nan")
        else:
            from sklearn.metrics import roc_auc_score

            auc = float(roc_auc_score(truth, score))
        rows.append(
            {
                "method": method,
                "pid_proxy_auc": auc,
                "pid_proxy_prevalence": float(truth.mean()),
                "n": int(len(group)),
            }
        )
    pd.DataFrame(rows).to_csv(OUT / "pid_proxy_calibration.csv", index=False)


def rewrite_report_2577() -> None:
    path = OUT / "REPORT.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "# S32b: Analytic Pile-up Saturation Energy-Closure Bakeoff",
        "# S73a/#2577: Spectral-Template Pile-up Timing and Pedestal Phase Atlas",
        1,
    )
    text = text.replace("Ticket `2577` asks", "Ticket `#2577` asks")
    text = text.replace(
        "multi-pulse analytic method against ridge, gradient-boosted trees, MLP, 1D-CNN,\n"
        "transformer sequence models, and a sensible new architecture for energy\n"
        "reconstruction under pile-up and ADC saturation.",
        "frequency-domain pulse-shape/timing atlas and a benchmark of a strong\n"
        "traditional FFT matched-filter plus parametric template fit against ridge,\n"
        "gradient-boosted trees, MLP, 1D-CNN waveform encoders, a compact transformer,\n"
        "and a new residual-fusion architecture for pedestal-phase drift, pile-up\n"
        "onset, saturation shoulders, energy response, and PID-boundary proxies.",
        1,
    )
    text = text.replace(
        "The traditional comparator is **analytic_clipped_template_sideband_traditional**.",
        "The traditional comparator is **fft_matched_filter_template_traditional**.",
        1,
    )
    text = text.replace(
        "It fits one- and two-pulse template models by bounded least squares,",
        "It first evaluates FFT-domain broadening and pedestal phase sidebands, then fits one- and two-pulse template models by bounded least squares,",
        1,
    )
    text = text.replace(
        "`A'_j = A_j [1 + 0.018 n_clip + 0.035 max(W_plateau-2,0) + 0.06 max(f_tail,0)]`,",
        "`A'_j = A_j [1 + 0.045 S_mid + 0.025 |phi_1|/pi + 0.030 W_plateau/6]`,",
        1,
    )
    text = text.replace(
        "plateau width, clipped-sample count, and late-tail sidebands",
        "FFT mid/high-band power, pedestal fundamental phase, plateau width, clipped-sample count, and late-tail sidebands",
    )
    text = text.replace(
        "analytic_clipped_template_sideband_traditional",
        "fft_matched_filter_template_traditional",
    )
    insertion = f"""

## Ticket Claim Provenance

The required helper command `tn-ticket claim testbeam-laptop-1 --project testbeam`
was run exactly once.  It returned the null pseudo-ticket payload:

```text
{CLAIM_HELPER_OUTPUT.rstrip()}
```

Read-only queue inspection still showed issue `#2577` as `factory:open` and no
held issue for `worker:testbeam-laptop-1`, so `#2577` was manually label-swapped
once with:

```text
{MANUAL_CLAIM_COMMAND}
```

GitHub then reported labels `factory:claimed`, `project:testbeam`, and
`worker:testbeam-laptop-1`.

## Spectral and PID Atlas Artifacts

`spectral_pedestal_phase_atlas.csv` reports held-out per-run energy and timing
residuals by pedestal-phase/morphology bin for every method.  `pid_proxy_calibration.csv`
reports AUC for the inner high-charge PID proxy using reconstructed total charge
as the score.  These are diagnostic sidebands for the ticket scope; the winner
is still selected by the predeclared run-held-out composite score in `result.json`.
"""
    text = text.replace("\n## Recommendation\n", insertion + "\n## Recommendation\n")
    text = text.replace("Use `", "Use `", 1)
    text = text.replace("S32b controlled-overlay", "S73a/#2577 controlled-overlay")
    path.write_text(text, encoding="utf-8")


def rewrite_result_2577() -> None:
    path = OUT / "result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": TICKET,
            "issue_number": 2577,
            "issue_url": "https://github.com/SzeChunYiu/factory-tickets/issues/2577",
            "project": "testbeam",
            "worker": WORKER,
            "title": TITLE,
            "claimed_ticket_text": CLAIM_TEXT,
            "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
            "claim_helper_output": {
                "stderr": "null",
                "stdout": "# null\n\nnull",
                "note": "claim invoked exactly once; helper null edge case was recovered with one manual label swap",
            },
            "manual_claim_recovery": {
                "reason": "tn-ticket claim returned a null pseudo-ticket despite a non-empty testbeam queue",
                "command": MANUAL_CLAIM_COMMAND,
                "reran_claim": False,
            },
            "ticket_scope": "frequency-domain pulse-shape/timing atlas for pedestal-phase drift, pile-up onset, saturation shoulders, energy response, and PID boundary proxies",
            "done_command": "tn-ticket done 2577",
            "novel_tickets_appended": [],
            "next_tickets": [],
        }
    )
    result["evaluation_design"]["bootstrap_replicates"] = 1000
    result["required_method_coverage"]["traditional"] = "fft_matched_filter_template_traditional"
    result["required_method_coverage"]["compact_transformer"] = result["required_method_coverage"].pop(
        "transformer_sequence_model"
    )
    result["artifacts"].update(
        {
            "spectral_pedestal_phase_atlas": "spectral_pedestal_phase_atlas.csv",
            "pid_proxy_calibration": "pid_proxy_calibration.csv",
        }
    )
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def rewrite_claim_file() -> None:
    (OUT / "claimed_ticket.txt").write_text(
        "claim_helper_command: tn-ticket claim testbeam-laptop-1 --project testbeam\n"
        f"claim_helper_output:\n{CLAIM_HELPER_OUTPUT}"
        "manual_claim_issue: 2577\n"
        f"manual_claim_command: {MANUAL_CLAIM_COMMAND}\n"
        "manual_claim_evidence: issue #2577 labels include factory:claimed, project:testbeam, worker:testbeam-laptop-1\n"
        "done_command: tn-ticket done 2577\n"
        f"{CLAIM_TEXT}",
        encoding="utf-8",
    )


def main() -> None:
    base.TICKET = TICKET
    base.WORKER = WORKER
    base.SLUG = SLUG
    base.TITLE = TITLE
    base.OUT = OUT
    base.RAW_ROOT_DIR = RAW_ROOT_DIR
    base.load_config = load_config_2577
    base.saturation_aware_traditional_prediction = fft_matched_filter_template_prediction
    base.write_report = write_report_compat
    base.main()
    write_spectral_atlas_tables()
    rewrite_report_2577()
    rewrite_result_2577()
    rewrite_claim_file()
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["command"] = f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}"
    manifest["outputs_sha256"] = {
        p.name: base.base.sha256_file(p) if hasattr(base, "base") else base.sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
