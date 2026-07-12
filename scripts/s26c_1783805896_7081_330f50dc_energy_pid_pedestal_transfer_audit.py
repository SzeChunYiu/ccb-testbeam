#!/usr/bin/env python3
"""S26c energy-PID pedestal transfer audit.

This runner reuses the raw-ROOT reproduction and controlled-injection machinery
from S25b, but makes the primary endpoint saturated-pulse energy recovery with
timing resolution as a co-primary diagnostic.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover - torch is expected in the project env.
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


TICKET = "1783805896.7081.330f50dc"
SLUG = "s26c_energy_pid_pedestal_transfer_audit"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")
WORKER = "testbeam-laptop-4"


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S26c",
            "ticket_id": TICKET,
            "title": "Energy-PID pedestal transfer audit",
            "worker": WORKER,
            "output_dir": str(OUT),
            "random_seed": 2026071206,
            "max_clean_pulses_per_run_stave": 92,
            "injected_per_train_run": 52,
            "clean_per_train_run": 52,
            "injected_per_heldout_run": 72,
            "clean_per_heldout_run": 72,
        }
    )
    cfg["raw_root_dir"] = str(RAW_ROOT_DIR)
    cfg["ml"].update({"bootstrap_samples": 400, "cnn_epochs": 90, "cnn_channels": 12, "max_iter": 240})
    return cfg


class TinySequenceTransformer(nn.Module):
    def __init__(self, n_samples: int) -> None:
        super().__init__()
        self.value = nn.Linear(1, 24)
        self.position = nn.Parameter(torch.zeros(1, n_samples, 24))
        layer = nn.TransformerEncoderLayer(
            d_model=24,
            nhead=4,
            dim_feedforward=64,
            dropout=0.05,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=1)
        self.norm = nn.LayerNorm(24)
        self.class_head = nn.Linear(24, 1)
        self.reg_head = nn.Linear(24, 4)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.value(x[..., None]) + self.position
        h = self.encoder(h)
        pooled = self.norm(h.mean(dim=1))
        return self.class_head(pooled).squeeze(-1), self.reg_head(pooled)


def transformer_prediction(events: pd.DataFrame, waveforms: np.ndarray, cfg: dict) -> pd.DataFrame:
    if torch is None:
        raise RuntimeError("torch is required for the S26c transformer benchmark")
    seed = int(cfg["random_seed"]) + 200
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    x_np = waveforms.astype(np.float32)
    x_np = x_np - np.median(x_np[:, :4], axis=1, keepdims=True)
    scale = np.maximum(np.percentile(np.abs(x_np), 95, axis=1, keepdims=True), 1.0)
    x_np = np.clip(x_np / scale, -4.0, 4.0).astype(np.float32)
    y_class = events["is_overlap"].to_numpy(dtype=np.float32)
    y_reg, max_amp = base.regression_targets(events, waveforms)
    y_reg = y_reg.astype(np.float32)
    train = events["split"].to_numpy() == "train"

    ds = TensorDataset(
        torch.from_numpy(x_np[train]),
        torch.from_numpy(y_class[train]),
        torch.from_numpy(y_reg[train]),
    )
    loader = DataLoader(ds, batch_size=64, shuffle=True, generator=torch.Generator().manual_seed(seed))
    model = TinySequenceTransformer(waveforms.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=1.5e-3, weight_decay=2e-3)
    bce = nn.BCEWithLogitsLoss()
    mse = nn.SmoothL1Loss()
    for _epoch in range(80):
        model.train()
        for xb, yc, yr in loader:
            opt.zero_grad(set_to_none=True)
            logits, reg = model(xb)
            loss = bce(logits, yc) + 1.8 * mse(reg, yr)
            loss.backward()
            opt.step()

    model.eval()
    probs = []
    regs = []
    with torch.no_grad():
        for start in range(0, len(x_np), 512):
            xb = torch.from_numpy(x_np[start : start + 512])
            logits, reg = model(xb)
            probs.append(torch.sigmoid(logits).cpu().numpy())
            regs.append(reg.cpu().numpy())
    score = np.concatenate(probs)
    pred = np.vstack(regs)
    return base.as_prediction(events, score, pred, max_amp, "tiny_sequence_transformer")


def winner_table(overall: pd.DataFrame) -> pd.DataFrame:
    out = overall.copy()
    out["winner_score"] = (
        out["energy_fractional_sigma68"]
        + 0.01 * out["time_sigma68_ns"]
        + 0.05 * out["pileup_miss_rate"]
        + 0.05 * out["false_split_rate"]
    )
    return out.sort_values(["winner_score", "energy_fractional_sigma68", "time_sigma68_ns"]).reset_index(drop=True)


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    view = df[cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def write_report(
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
    best = ranked.iloc[0]
    trad = overall[overall["method"] == "two_pulse_template_cfd_baseline"].iloc[0]
    text = f"""# S26c: energy-PID pedestal transfer audit

## Abstract

Ticket `{TICKET}` asks whether raw B-stack HRD waveforms support a stronger
architecture for saturated pulse energy and timing recovery than a traditional
saturation-knee/template correction.  The worker was `{WORKER}`.  Before fitting
any model, the raw ROOT selected-pulse anchor was reproduced exactly:
`{int(match.iloc[0]['reproduced'])}` selected B-stave pulses versus the reference
`{int(match.iloc[0]['report_value'])}`, with delta `{int(match.iloc[0]['delta'])}`.

The winner is `{winner}` by the predeclared composite ordering

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.05 r_miss,m + 0.05 r_false,m`,

where `sigma_E` is held-out fractional energy sigma68, `sigma_t` is constituent
timing sigma68 in ns, and the final two terms penalize missed injected pile-up and
false splitting of clean controls.  `{winner}` obtains `sigma_E =
{best['energy_fractional_sigma68']:.4g}` with 95% run-block bootstrap CI
[{best['energy_fractional_sigma68_ci_low']:.4g},
{best['energy_fractional_sigma68_ci_high']:.4g}] and timing sigma68
`{best['time_sigma68_ns']:.4g}` ns.

## Raw ROOT reproduction

Raw files were read from `{cfg['raw_root_dir']}`.  Each `h101/HRDv` object was
reshaped to `(event, channel, sample)` with 18 samples per channel.  B2/B4/B6/B8
were pedestal-subtracted with `b_c = median(x_c[0:4])`; selected pulses satisfy
`max_t (x_c(t)-b_c) > 1000 ADC`.  This reproduces the existing analysis count and
guards against benchmarking on a derived cache with incompatible semantics.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Train-only pulse templates

Clean single-pulse templates were estimated only from train runs
`{cfg['benchmark_runs']['train']}`.  Candidate clean pulses required amplitude
1500--12000 ADC and peak sample 4--12.  For pulse `i` on stave `s`, the normalized
waveform is shifted to a common CFD20 reference and the template is

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

## Benchmark design

The split is by source run, not by event: train runs `{cfg['benchmark_runs']['train']}`
and held-out runs `{cfg['benchmark_runs']['heldout']}`.  Controlled saturated
doublets are generated from raw-ROOT-derived clean pulses:

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_r(t) + p`.

Here `Delta` spans sub-sample to multi-sample overlap, `r` spans weak to nearly
equal second pulses, `epsilon_r(t)` is a run-local residual sampled from real clean
pulses, and `p` is a pedestal excursion.  The saturation proxy is the injected
summed amplitude above the high-charge knee; strata include amplitude ceiling,
pulse-shape spacing, pile-up ratio, pedestal excursion through run-local residuals,
and a PID proxy through stave and amplitude composition.

## Methods

The traditional method is `two_pulse_template_cfd_baseline`, a bounded
saturation-knee two-template fit.  For one or two constituents it minimizes

`SSE_k = sum_t [w(t) - b - sum_{{j=1}}^k A_j T_s(t-t_j)]^2`,

with positive amplitudes, bounded baseline, constrained separations, and a
template-derived CFD initialization.  Its classification score is the fractional
improvement `(SSE_1-SSE_2)/SSE_1`.

The machine-learning panel contains the required ridge model, histogram
gradient-boosted trees, MLP, compact 1D-CNN, and two architecture candidates:
`tiny_sequence_transformer`, a one-layer self-attention encoder over the 18-sample
waveform, and `template_residual_boosted_stack_new`, a physics-residual stack that
feeds the traditional fit estimates into boosted residual classifiers/regressors.
All non-traditional models are trained only on train runs.

## Metrics and uncertainty

For detected injected doublets, constituent timing error is

`e_t = 10 ns * (hat t - t_true)`,

and recovered total energy error is

`e_E = [(hat A_1 + hat A_2) - (A_1 + A_2)] / (A_1 + A_2)`.

For either endpoint,

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

Confidence intervals are 95% percentile intervals from
`{int(cfg['ml']['bootstrap_samples'])}` bootstrap resamples of held-out runs.

## Overall held-out results

{md_table(ranked, ['method', 'winner_score', 'energy_fractional_bias', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high', 'time_bias_ns', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate'])}

Relative to the traditional baseline, `{winner}` changes fractional energy sigma68
by `{best['energy_fractional_sigma68'] - trad['energy_fractional_sigma68']:.4g}`
and timing sigma68 by `{best['time_sigma68_ns'] - trad['time_sigma68_ns']:.4g}` ns.
The score deliberately keeps failure rates visible because an apparently sharp
energy residual after rejecting difficult doublets would not be a usable recovery
algorithm.

## Run-held-out stability

{md_table(by_run, ['method', 'heldout_run', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Strata and systematic checks

The stratum table scans pulse-shape spacing, amplitude ratio, stave/PID proxy, and
the high-amplitude saturation proxy.  The main systematic vulnerability is that
truth comes from controlled injections into raw single-pulse residuals, not from
electronics saturation metadata.  The run split probes transfer across observed
run conditions, while the finite number of held-out runs limits CI granularity.

{md_table(strata, ['stratum', 'value', 'method', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate'])}

## Caveats

The study establishes an architecture ordering under controlled raw-ROOT-derived
truth, not the real pile-up occurrence rate in beam data.  The saturation label is
an amplitude-ceiling proxy; if hardware saturation flags become available, this
benchmark should be repeated with those labels.  The 18-sample window restricts
sub-sample overlap identifiability and makes pedestal excursions partly degenerate
with a broad late tail.  Bootstrap intervals are run-block transfer intervals, not
event-level asymptotic uncertainties.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s26b")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(TICKET + "\n", encoding="utf-8")
    cfg = load_config()
    rng = np.random.default_rng(int(cfg["random_seed"]))

    match = p05a.reproduce_counts(cfg)
    match.to_csv(OUT / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    runs = cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]
    clean = p05a.read_clean_pulses(cfg, runs, rng)
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(cfg["benchmark_runs"]["train"])], cfg)
    template_summary.to_csv(OUT / "template_summary.csv", index=False)
    train_events, train_waves = p05a.generate_benchmark(clean, templates, cfg, "train", cfg["benchmark_runs"]["train"], rng)
    held_events, held_waves = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waves = np.vstack([train_waves, held_waves])

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    preds = [base.template_prediction(trad_raw)]
    preds.extend(base.run_sklearn_methods(events, waves, int(cfg["random_seed"])))
    preds.append(base.cnn_prediction(events, waves, cfg))
    preds.append(transformer_prediction(events, waves, cfg))
    preds.append(base.add_residual_stack(events, waves, trad_raw, int(cfg["random_seed"])))

    all_pred = pd.concat(preds, ignore_index=True)
    base_cols = [
        "event_id",
        "split",
        "source_run",
        "stave",
        "is_overlap",
        "true_t1_sample",
        "true_t2_sample",
        "true_amp1_adc",
        "true_amp2_adc",
        "true_sep_sample",
        "true_ratio",
    ]
    joined = all_pred.merge(events[base_cols], on="event_id", how="left")
    joined.to_csv(OUT / "event_predictions.csv", index=False)
    overall = base.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = winner_table(overall)
    by_run = base.by_run_summary(joined)
    strata = base.strata_summary(joined)
    overall.to_csv(OUT / "method_metrics.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, overall, ranked, by_run, strata, template_summary, winner, runtime)

    input_rows = []
    for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root")):
        input_rows.append({"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    result = {
        "ticket_id": TICKET,
        "project": "testbeam",
        "worker": WORKER,
        "title": cfg["title"],
        "status": "complete",
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
        "raw_root_reproduction": {
            "passed": bool(match["pass"].all()),
            "raw_root_glob": str(RAW_ROOT_DIR / "hrdb_run_*.root"),
            "expected_selected_pulses": int(match.iloc[0]["report_value"]),
            "reproduced_selected_pulses": int(match.iloc[0]["reproduced"]),
            "delta": int(match.iloc[0]["delta"]),
            "evidence_table": "reproduction_match_table.csv",
        },
        "evaluation_design": {
            "split": "train and held-out sets are disjoint by source run",
            "train_runs": cfg["benchmark_runs"]["train"],
            "heldout_runs": cfg["benchmark_runs"]["heldout"],
            "bootstrap": "held-out run-block percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "negative_control": "clean single-pulse controls with matched source-run distribution",
            "winner_score": "energy_fractional_sigma68 + 0.01*time_sigma68_ns + 0.05*pileup_miss_rate + 0.05*false_split_rate",
        },
        "required_method_coverage": {
            "traditional": "two_pulse_template_cfd_baseline",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "transformer": "tiny_sequence_transformer",
            "new_architecture": "template_residual_boosted_stack_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum held-out composite saturation-energy/timing score with run-block bootstrap CIs reported",
            "winner_score": float(ranked.iloc[0]["winner_score"]),
            "energy_fractional_sigma68": float(ranked.iloc[0]["energy_fractional_sigma68"]),
            "energy_fractional_sigma68_ci95": [
                float(ranked.iloc[0]["energy_fractional_sigma68_ci_low"]),
                float(ranked.iloc[0]["energy_fractional_sigma68_ci_high"]),
            ],
            "time_sigma68_ns": float(ranked.iloc[0]["time_sigma68_ns"]),
            "time_sigma68_ci95": [
                float(ranked.iloc[0]["time_sigma68_ns_ci_low"]),
                float(ranked.iloc[0]["time_sigma68_ns_ci_high"]),
            ],
            "pileup_miss_rate": float(ranked.iloc[0]["pileup_miss_rate"]),
            "false_split_rate": float(ranked.iloc[0]["false_split_rate"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Truth comes from controlled injections into raw-ROOT-derived clean pulses.",
            "Saturation is represented by an amplitude-ceiling proxy rather than electronics saturation flags.",
            "Bootstrap CIs resample held-out runs and should be read as run-transfer intervals.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": TICKET,
        "git_commit": base.git_commit(),
        "command": f"{sys.executable} scripts/s26c_1783805896_7081_330f50dc_energy_pid_pedestal_transfer_audit.py",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            p.name: base.sha256_file(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
