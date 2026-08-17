#!/usr/bin/env python3
"""Ticket 2558 / S61a pulse-shape timing pedestal phase benchmark."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s43b_1784349946_602_171c4316_waveform_derivative_pulse_shape_timing_benchmark as base


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ticket_2558_s61a_pulse_shape_timing_pedestal_phase.json"


def _md_table(df: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    view = df.loc[:, columns].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    lines = ["| " + " | ".join(view.columns) + " |", "| " + " | ".join(["---"] * len(view.columns)) + " |"]
    for _, row in view.iterrows():
        lines.append("| " + " | ".join(str(row[c]).replace("|", "\\|") for c in view.columns) + " |")
    return "\n".join(lines)


def _write_atom_coefficients(out: Path) -> pd.DataFrame:
    data = pd.read_csv(out / "benchmark_rows.csv.gz")
    bmod = base.load_base()
    cols = bmod.feature_columns(data)
    train = data["split"].eq("train").to_numpy()
    y = data["target_onset_residual_ns"].to_numpy(float)
    model = make_pipeline(StandardScaler(), Ridge(alpha=3.0))
    model.fit(data.loc[train, cols].to_numpy(float), y[train])
    coefs = model.named_steps["ridge"].coef_
    rows = []
    for feature, coef in zip(cols, coefs):
        if feature.startswith("w"):
            family = "normalized_sample_atom"
        elif feature.startswith("d1_"):
            family = "first_derivative_atom"
        elif feature.startswith("d2_"):
            family = "curvature_atom"
        elif feature in {"baseline", "pretrigger_slope", "pretrigger_derivative_rms"}:
            family = "pedestal_atom"
        elif feature in {"amplitude", "peak_sample", "cfd20_sample", "cfd50_sample", "cfd80_sample", "rise_time_sample"}:
            family = "fixed_timing_amplitude_covariate"
        else:
            family = "shape_summary_atom"
        rows.append({"feature": feature, "family": family, "ridge_standardized_coef_ns": float(coef), "abs_coef_ns": float(abs(coef))})
    atoms = pd.DataFrame(rows).sort_values("abs_coef_ns", ascending=False).reset_index(drop=True)
    atoms.to_csv(out / "pulse_shape_atom_coefficients.csv", index=False)
    return atoms


def _write_placebo_controls(out: Path, seed: int) -> pd.DataFrame:
    data = pd.read_csv(out / "benchmark_rows.csv.gz")
    bmod = base.load_base()
    cols = bmod.feature_columns(data)
    rng = np.random.default_rng(seed)
    train = data["split"].eq("train").to_numpy()
    y = data["target_onset_residual_ns"].to_numpy(float).copy()
    shuffled = y.copy()
    for run in sorted(data["run"].unique()):
        idx = data.index[data["run"].eq(run)].to_numpy()
        shuffled[idx] = rng.permutation(shuffled[idx])
    rows = []
    models = {
        "ridge_runwise_target_placebo": make_pipeline(StandardScaler(), Ridge(alpha=3.0)),
        "hgb_runwise_target_placebo": HistGradientBoostingRegressor(max_iter=80, learning_rate=0.05, l2_regularization=0.05, random_state=seed),
    }
    for name, model in models.items():
        model.fit(data.loc[train, cols].to_numpy(float), shuffled[train])
        pred = model.predict(data.loc[:, cols].to_numpy(float))
        frame = data[["run", "split", "target_onset_residual_ns"]].copy()
        frame["error_ns"] = frame["target_onset_residual_ns"] - pred
        held = frame[frame["split"].eq("heldout")]
        vals = bmod.metric_values(held)
        rows.append({"control": name, "n": int(len(held)), **vals})
    placebo = pd.DataFrame(rows)
    placebo.to_csv(out / "placebo_controls.csv", index=False)
    return placebo


def _rewrite_report(config: dict, out: Path, runtime: float, atoms: pd.DataFrame, placebo: pd.DataFrame) -> None:
    report = out / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    text = text.replace(
        "# S43b Waveform Derivative Pulse-Shape Timing Benchmark",
        "# S61a Pulse-Shape Timing Pedestal Phase Benchmark",
    )
    text = text.replace(
        "Ticket `2558` asks whether waveform derivative and curvature\n"
        "information improves arrival-time extraction under pedestal drift.",
        "Ticket `#2558` asks which pulse-shape degrees of freedom explain timing\n"
        "residuals once pedestal, polarity, peak phase, and amplitude are fixed.",
    )
    text = text.replace(
        "under pedestal drift.  The study\n",
        "under fixed pedestal, polarity, peak-phase, and amplitude covariates.  The study\n",
    )
    provenance = f"""
## Ticket Claim Provenance

The required `tn-ticket claim testbeam-laptop-3 --project testbeam` command was
run exactly once.  It returned:

```text
{config['claim_command_output'].rstrip()}
```

Read-only GitHub inspection showed no issue claimed by
`worker:testbeam-laptop-3`, so issue `#2558` was manually label-swapped without
rerunning the helper:

```text
{config['manual_claim_workaround']['command']}
```

No second `tn-ticket claim` command was run.
"""
    text = text.replace("\n## Raw ROOT Reproduction\n", provenance + "\n## Raw ROOT Reproduction\n")
    insert = f"""
## Pulse-Shape Atom Coefficients and Placebo Controls

The coefficient table `pulse_shape_atom_coefficients.csv` fits a standardized
ridge model on training runs only, using the same leakage-controlled feature
matrix as the tabular methods.  The largest pulse-shape atoms are:

{_md_table(atoms, ['feature', 'family', 'ridge_standardized_coef_ns', 'abs_coef_ns'], max_rows=20)}

Run-wise target shuffling keeps run composition and covariate marginal
distributions but breaks within-run timing association.  These placebo rows are
diagnostics for leakage or memorization:

{_md_table(placebo, ['control', 'n', 'bias_ns', 'sigma68_ns', 'rms_ns', 'tail_fraction_abs_gt_5ns'])}
"""
    text = text.replace("\n## Interpretation, Systematics, and Caveats\n", insert + "\n## Interpretation, Systematics, and Caveats\n")
    text = text.replace("Runtime was `", f"Ticket-local wrapper runtime was `{runtime:.1f} s`; benchmark runtime was `")
    report.write_text(text, encoding="utf-8")


def _augment_result(config: dict, out: Path, runtime: float, atoms: pd.DataFrame, placebo: pd.DataFrame) -> None:
    path = out / "result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": str(config["ticket_id"]),
            "ticket_number": int(config["ticket_number"]),
            "study_id": config["study_id"],
            "worker": config["worker"],
            "title": config["title"],
            "claim_command": config["claim_command"],
            "claim_command_output": config["claim_command_output"],
            "manual_claim_workaround": config["manual_claim_workaround"],
            "ticket_scope": "pulse-shape timing residual explanation after fixing pedestal, polarity, peak phase, and amplitude",
            "traditional_method": "polarity-bound CFD/template time-walk correction with robust first-samples pedestal and peak-phase covariates",
            "wrapper_script_sha256": base.sha256_path(Path(__file__)),
            "wrapper_runtime_sec": runtime,
            "pulse_shape_atom_top10": base.json_safe(atoms.head(10).to_dict("records")),
            "placebo_controls": base.json_safe(placebo.to_dict("records")),
            "novel_tickets_appended": [],
            "next_tickets": [],
        }
    )
    result["artifacts"]["pulse_shape_atom_coefficients"] = "pulse_shape_atom_coefficients.csv"
    result["artifacts"]["placebo_controls"] = "placebo_controls.csv"
    path.write_text(json.dumps(base.json_safe(result), indent=2) + "\n", encoding="utf-8")


def _write_claim_files(config: dict, out: Path) -> None:
    (out / "claimed_ticket.txt").write_text(
        config["claimed_ticket_text"]
        + "\nclaim_helper_command: "
        + config["claim_command"]
        + "\nclaim_helper_output:\n"
        + config["claim_command_output"]
        + "\nmanual_claim_workaround:\n"
        + config["manual_claim_workaround"]["command"]
        + "\n",
        encoding="utf-8",
    )
    (out / "claimed_ticket_body.txt").write_text(config["claimed_ticket_text"], encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
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

    atoms = _write_atom_coefficients(out)
    placebo = _write_placebo_controls(out, int(config["random_seed"]) + 11)
    runtime = time.time() - started
    _rewrite_report(config, out, runtime, atoms, placebo)
    _augment_result(config, out, runtime, atoms, placebo)
    _write_claim_files(config, out)
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    (out / "manifest.json").write_text(json.dumps(base.artifact_manifest(out, config, result), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
