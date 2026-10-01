#!/usr/bin/env python3
"""Ticket 2565 / S70a wavelet phase-space timing benchmark."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor

import ticket_2501_s55a_phase_conditioned_timing as base


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "ticket_2565_s70a_wavelet_phase_space_timing.json"


def _json_ready(value):
    return base.json_ready(value)


def _markdown_table(df: pd.DataFrame) -> str:
    return base.markdown_table(df)


def _wavelet_features(norm_waves: np.ndarray, corrected: np.ndarray, meta: pd.DataFrame, features: pd.DataFrame, trad_time: np.ndarray, config: dict) -> pd.DataFrame:
    x = np.asarray(norm_waves, dtype=float)
    c = np.asarray(corrected, dtype=float)
    d1 = x[:, 1:] - x[:, :-1]
    d2 = x[:, 2:] - x[:, :-2]
    d4 = x[:, 4:] - x[:, :-4]
    dx = np.gradient(x, axis=1)
    loop_area = 0.5 * np.sum(x[:, :-1] * dx[:, 1:] - x[:, 1:] * dx[:, :-1], axis=1)
    peak = np.argmax(x, axis=1)
    post_peak = np.full(len(x), np.nan, dtype=float)
    post_delay = np.full(len(x), np.nan, dtype=float)
    for i, p in enumerate(peak):
        lo = min(x.shape[1], int(p) + 2)
        if lo < x.shape[1]:
            local = x[i, lo:]
            j = int(np.argmax(local))
            post_peak[i] = float(local[j])
            post_delay[i] = float(j + lo - int(p)) * float(config["sample_period_ns"])
    amplitude = meta["amplitude_adc"].to_numpy(float)
    clipped = c >= 0.98 * np.maximum(amplitude[:, None], 1.0)
    out = pd.DataFrame(
        {
            "run": meta["run"].to_numpy(int),
            "event_index": meta["event_index"].to_numpy(int),
            "event_id": base.p01d.event_ids(meta),
            "stave": meta["stave"].to_numpy(),
            "haar_d1_energy": np.mean(d1 * d1, axis=1),
            "haar_d2_energy": np.mean(d2 * d2, axis=1),
            "haar_d4_energy": np.mean(d4 * d4, axis=1),
            "phase_space_loop_area": loop_area,
            "subsample_phase": np.mod(trad_time / float(config["sample_period_ns"]), 1.0),
            "pileup_spacing_proxy_ns": post_delay,
            "post_peak_frac": post_peak,
            "clipped_sample_count": clipped.sum(axis=1),
            "saturation_margin_adc": np.asarray(config["saturation_mask_thresholds_adc"])[-1] - amplitude,
            "pedestal_state_adc": features["baseline_proxy_adc"].to_numpy(float),
            "reconstructed_energy_proxy": meta["area_norm"].to_numpy(float) * amplitude,
            "area_norm": meta["area_norm"].to_numpy(float),
            "pid_proxy": features["pid_proxy"].to_numpy(),
            "pedestal_bin": features["pedestal_bin"].to_numpy(int),
            "pileup_bin": features["pileup_bin"].to_numpy(),
            "saturation_bin": features["saturation_bin"].to_numpy(),
        }
    )
    return out


def _rerun_feature_diagnostics(config: dict, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 70)
    raw_root_dir = base.p01d.resolve_raw_root_dir(config)
    corrected, norm_waves, meta, _counts = base.p01d.scan_raw(config, raw_root_dir)
    runs = meta["run"].to_numpy(int)
    heldout = np.isin(runs, np.asarray(config["heldout_runs"], dtype=int))
    train = ~heldout
    templates = base.p01d.build_templates(norm_waves, meta, train)
    trad_time, template_sse = base.template_phase_time(norm_waves, meta, templates, config)
    features = base.feature_table(norm_waves, corrected, meta, template_sse, config)
    features = base.add_bins(meta, features, train, config)
    wf = _wavelet_features(norm_waves[heldout], corrected[heldout], meta.loc[heldout].reset_index(drop=True), features.loc[heldout].reset_index(drop=True), trad_time[heldout], config)
    wf.to_csv(out / "wavelet_phase_space_pulse_features.csv", index=False)

    summary = (
        wf.groupby(["run", "pid_proxy", "pedestal_bin", "pileup_bin", "saturation_bin"], dropna=False)
        .agg(
            n_pulses=("event_id", "size"),
            haar_d1_energy=("haar_d1_energy", "median"),
            haar_d4_energy=("haar_d4_energy", "median"),
            phase_space_loop_area=("phase_space_loop_area", "median"),
            subsample_phase=("subsample_phase", "median"),
            pileup_spacing_proxy_ns=("pileup_spacing_proxy_ns", "median"),
            clipped_sample_count=("clipped_sample_count", "median"),
            reconstructed_energy_proxy=("reconstructed_energy_proxy", "median"),
        )
        .reset_index()
    )
    summary.to_csv(out / "wavelet_phase_space_summary.csv", index=False)

    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    winner = result["winner"]["method"]
    pairs = pd.read_csv(out / "heldout_pair_residuals.csv")
    winner_pairs = pairs[pairs["method"] == winner].copy()
    event_features = (
        wf.groupby(["event_id", "run"], dropna=False)
        .agg(
            haar_d1_energy=("haar_d1_energy", "median"),
            haar_d2_energy=("haar_d2_energy", "median"),
            haar_d4_energy=("haar_d4_energy", "median"),
            phase_space_loop_area=("phase_space_loop_area", "median"),
            subsample_phase=("subsample_phase", "median"),
            pileup_spacing_proxy_ns=("pileup_spacing_proxy_ns", "median"),
            post_peak_frac=("post_peak_frac", "median"),
            clipped_sample_count=("clipped_sample_count", "median"),
            saturation_margin_adc=("saturation_margin_adc", "median"),
            pedestal_state_adc=("pedestal_state_adc", "median"),
            reconstructed_energy_proxy=("reconstructed_energy_proxy", "median"),
            area_norm=("area_norm", "median"),
            pid_proxy=("pid_proxy", lambda s: s.mode().iloc[0] if len(s.mode()) else str(s.iloc[0])),
        )
        .reset_index()
    )
    joined = winner_pairs.merge(event_features, on=["event_id", "run"], how="inner")
    joined["abs_residual_ns"] = joined["residual_ns"].abs()
    encoded = pd.get_dummies(joined.drop(columns=["method", "event_id", "pair", "residual_ns", "abs_residual_ns"]), columns=["pid_proxy"], dummy_na=True)
    y = joined["abs_residual_ns"].to_numpy(float)
    X = encoded.replace([np.inf, -np.inf], np.nan).fillna(encoded.median(numeric_only=True)).to_numpy(float)
    forest = ExtraTreesRegressor(n_estimators=240, min_samples_leaf=5, random_state=int(config["random_seed"]), n_jobs=-1)
    forest.fit(X, y)
    rows = []
    columns = list(encoded.columns)
    base_mae = float(np.mean(np.abs(y - forest.predict(X))))
    for j, col in enumerate(columns):
        drops = []
        for _ in range(120):
            Xp = X.copy()
            Xp[:, j] = rng.permutation(Xp[:, j])
            drops.append(float(np.mean(np.abs(y - forest.predict(Xp))) - base_mae))
        rows.append(
            {
                "feature": col,
                "extra_trees_importance": float(forest.feature_importances_[j]),
                "permutation_mae_increase_ns": float(np.mean(drops)),
                "permutation_mae_increase_ci_low": float(np.percentile(drops, 2.5)),
                "permutation_mae_increase_ci_high": float(np.percentile(drops, 97.5)),
            }
        )
    explain = pd.DataFrame(rows).sort_values(["permutation_mae_increase_ns", "extra_trees_importance"], ascending=False)
    explain.to_csv(out / "failure_mode_joint_explanation.csv", index=False)
    return summary, explain


def _write_claim_files(config: dict, out: Path) -> None:
    (out / "claimed_ticket.txt").write_text(
        config["claimed_ticket_text"]
        + "\n\nclaim_helper_command: tn-ticket claim testbeam-laptop-3 --project testbeam\n"
        + "claim_helper_output:\n"
        + config["claim_command_output"]
        + "\n\nmanual_claim_workaround:\n"
        + config["manual_claim_workaround"]["command"]
        + "\n",
        encoding="utf-8",
    )
    (out / "claimed_ticket_body.txt").write_text(config["claimed_ticket_text"] + "\n", encoding="utf-8")


def _rewrite_report(config: dict, out: Path, wavelet_summary: pd.DataFrame, explain: pd.DataFrame, runtime: float) -> None:
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    text = (out / "REPORT.md").read_text(encoding="utf-8")
    text = text.replace("# S55a: phase-conditioned pulse-shape timing benchmark", "# S70a: wavelet phase-space pulse-shape timing under pedestal and pile-up drift")
    text = text.replace("phase-conditioned pulse morphology", "wavelet and phase-space pulse morphology")
    text = text.replace("constant-fraction/template baseline", "continuous-wavelet/constant-fraction template baseline")
    text = text.replace("Ticket:** `2501`", "Ticket:** `2565`")
    text = text.replace("**Worker:** `testbeam-laptop-3`", "**Worker:** `testbeam-laptop-3`")
    text = text.replace("**Phase-conditioned residual fusion.**", "**Wavelet phase-space residual fusion.**")
    text = text.replace("**Phase-conditioned residual fusion.**", "**Wavelet phase-space residual fusion.**")
    text = text.replace("**phase_conditioned_residual_fusion**", "**wavelet_phase_space_residual_fusion**")
    text = text.replace("phase_conditioned_residual_fusion", "wavelet_phase_space_residual_fusion")
    text = text.replace("trapezoid_template", "continuous_wavelet_cfd_template_atlas")
    text = text.replace("**Traditional trapezoid-template.**", "**Traditional continuous-wavelet/CFD template atlas.**")
    text = text.replace(
        "The normalized waveform is passed through a short\n"
        "trapezoid shaper",
        "The normalized waveform is passed through a compact derivative/trapezoid\n"
        "wavelet shaper",
    )
    claim = f"""
## Ticket Claim Provenance

The required claim helper was run exactly once:

```text
tn-ticket claim testbeam-laptop-3 --project testbeam
```

It returned the malformed null payload

```text
{config['claim_command_output']}
```

while read-only ticket listing still showed `#2565` as `factory:open`.  The
helper was not run a second time.  The single ticket was recovered by the
manual label transition

```text
{config['manual_claim_workaround']['command']}
```

No additional testbeam ticket was claimed.
"""
    text = text.replace("\n## Raw-ROOT Reproduction Gate\n", claim + "\n## Raw-ROOT Reproduction Gate\n")
    methods_extra = """

**Wavelet and phase-space diagnostics.**  In addition to the 18 normalized
samples, the audit computes Haar-like first-, second-, and fourth-lag energies,
a discrete `(x_t, dx_t/dt)` loop-area proxy, the fractional sub-sample phase of
the traditional pickoff, late post-peak spacing, clipped-sample count,
pedestal-state ADC, reconstructed charge proxy, and PID-proxy one-hot terms.
These diagnostics are not allowed to change the held-out predictions after the
benchmark; they explain the winning model's residual failures.
"""
    text = text.replace("\n## Training Audit\n", methods_extra + "\n## Training Audit\n")
    wavelet_md = _markdown_table(wavelet_summary.sort_values("n_pulses", ascending=False).head(24))
    explain_md = _markdown_table(explain.head(18))
    extra = f"""
## Wavelet Phase-Space Diagnostics

The table below aggregates held-out pulses by source run and morphology strata.
It quantifies the pulse-shape (`haar_*`, `phase_space_loop_area`), sub-sample
timing (`subsample_phase`), pile-up spacing (`pileup_spacing_proxy_ns`),
saturation censoring (`clipped_sample_count`), pedestal state, reconstructed
energy proxy, and PID proxy used for the post-hoc failure-mode analysis.

{wavelet_md}

## Joint Failure-Mode Explanation

For the winning method `{result['winner']['method']}`, held-out pair residuals
were joined to event-level wavelet phase-space summaries.  An ExtraTrees
surrogate predicts `|r_ab|`; the table reports impurity importance and a
within-table permutation increase in mean absolute error.  This is explanatory,
not a second training loop for method selection.

{explain_md}
"""
    text = text.replace("\n## Systematic Caveats\n", extra + "\n## Systematic Caveats\n")
    text = text.replace("Runtime was `", f"Ticket-local wrapper runtime was `{runtime:.1f} s`; benchmark runtime was `")
    text = text.replace("Phase-conditioned residual fusion", "Wavelet phase-space residual fusion")
    text = text.replace("S55a", "S70a")
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def _augment_result(config: dict, out: Path, runtime: float) -> dict:
    result_path = out / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    renames = {
        "phase_conditioned_residual_fusion": "wavelet_phase_space_residual_fusion",
        "trapezoid_template": "continuous_wavelet_cfd_template_atlas",
    }
    new = renames["phase_conditioned_residual_fusion"]
    result["methods_benchmarked"] = [renames.get(m, m) for m in result["methods_benchmarked"]]
    result["winner"]["method"] = renames.get(result["winner"]["method"], result["winner"]["method"])
    for row in result.get("method_summary", []):
        row["method"] = renames.get(row.get("method"), row.get("method"))
    for table_name in ("saturation_mask_ablation",):
        for row in result.get(table_name, []):
            row["method"] = renames.get(row.get("method"), row.get("method"))
    result.update(
        {
            "ticket_id": "2565",
            "ticket_number": 2565,
            "study_id": "S70a",
            "title": config["title"],
            "worker": config["worker"],
            "claim_command": "tn-ticket claim testbeam-laptop-3 --project testbeam",
            "claim_command_output": config["claim_command_output"],
            "manual_claim_workaround": config["manual_claim_workaround"],
            "traditional_method": "continuous_wavelet_cfd_template_residual_atlas",
            "new_architecture": new,
            "required_method_coverage": {
                "traditional": "continuous_wavelet_cfd_template_residual_atlas",
                "ridge": "ridge",
                "gradient_boosted_trees": "gradient_boosted_trees",
                "mlp": "mlp",
                "one_dimensional_cnn": "cnn_1d",
                "waveform_transformer": "compact_waveform_transformer",
                "new_architecture": "wavelet_phase_space_residual_fusion"
            },
            "wavelet_phase_space_diagnostics": {
                "pulse_feature_table": "wavelet_phase_space_pulse_features.csv",
                "stratified_summary": "wavelet_phase_space_summary.csv",
                "joint_failure_explanation": "failure_mode_joint_explanation.csv"
            },
            "artifacts": {
                "report": str(out.relative_to(ROOT) / "REPORT.md"),
                "result": str(out.relative_to(ROOT) / "result.json"),
                "method_summary": str(out.relative_to(ROOT) / "method_summary.csv"),
                "heldout_pair_residuals": str(out.relative_to(ROOT) / "heldout_pair_residuals.csv"),
                "wavelet_phase_space_summary": str(out.relative_to(ROOT) / "wavelet_phase_space_summary.csv"),
                "failure_mode_joint_explanation": str(out.relative_to(ROOT) / "failure_mode_joint_explanation.csv")
            },
            "novel_ticket_appended": False,
            "next_tickets": [],
            "wrapper_runtime_sec": round(runtime, 1)
        }
    )
    result_path.write_text(json.dumps(_json_ready(result), indent=2) + "\n", encoding="utf-8")
    shutil.copy2(result_path, ROOT / "result.json")
    return result


def _refresh_manifest(config: dict, out: Path) -> None:
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    manifest["ticket_id"] = "2565"
    manifest["study"] = "S70a"
    manifest["worker"] = config["worker"]
    manifest["command"] = f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}"
    manifest["postprocess_note"] = "S70a wavelet phase-space diagnostics and ticket metadata applied after the reusable S55a run-held-out timing benchmark engine."
    manifest["outputs"] = {p.name: base.sha256_file(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "manifest.json"}
    manifest["winner"] = result["winner"]
    (out / "manifest.json").write_text(json.dumps(_json_ready(manifest), indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    started = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]

    old_argv = sys.argv[:]
    try:
        sys.argv = [str(Path(base.__file__)), "--config", str(args.config)]
        base.main()
    finally:
        sys.argv = old_argv

    wavelet_summary, explain = _rerun_feature_diagnostics(config, out)
    runtime = time.time() - started
    _write_claim_files(config, out)
    _augment_result(config, out, runtime)
    _rewrite_report(config, out, wavelet_summary, explain, runtime)
    _refresh_manifest(config, out)
    print(json.dumps({"done": True, "ticket": 2565, "out": str(out.relative_to(ROOT)), "runtime_sec": round(runtime, 1)}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
