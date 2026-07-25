#!/usr/bin/env python3
"""Finalize the claimed G4-02 ticket artifacts from the benchmark outputs."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/g4_02_1781212364_2054355_4a1327ef_energy_calibration.yaml"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def fmt_ci(values: object, digits: int = 5) -> str:
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except json.JSONDecodeError:
            return values
    lo, hi = values
    return f"[{lo:.{digits}f}, {hi:.{digits}f}]"


def md_table(frame: pd.DataFrame, columns: list[str], digits: int = 5) -> str:
    sub = frame[columns].copy()
    for col in sub.columns:
        if sub[col].dtype.kind in "fc":
            sub[col] = sub[col].map(lambda v: "" if pd.isna(v) else f"{v:.{digits}g}")
        else:
            sub[col] = sub[col].astype(str)
    widths = [max(len(str(c)), int(sub[c].map(len).max() if len(sub) else 0)) for c in sub.columns]
    header = "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |"
    sep = "| " + " | ".join("---" for _ in sub.columns) + " |"
    rows = [
        "| " + " | ".join(str(row[c]).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |"
        for _, row in sub.iterrows()
    ]
    return "\n".join([header, sep] + rows)


def main() -> None:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]
    docs = ROOT / "docs/reports"
    docs.mkdir(parents=True, exist_ok=True)
    figures = out / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    metrics = pd.read_csv(out / "method_metrics.csv")
    byrun = pd.read_csv(out / "run_heldout_summary.csv")
    counts = pd.read_csv(out / "counts_by_run.csv")
    prior = pd.read_csv(out / "geant4_stave_priors.csv")
    range_table = pd.read_csv(out / "geant4_range_table.csv")
    birks = pd.read_csv(out / "birks_fit.csv").iloc[0].to_dict()
    leakage = pd.read_csv(out / "leakage_checks.csv")
    repro = pd.read_csv(out / "reproduction_match_table.csv").iloc[0].to_dict()

    metrics = metrics.sort_values("res68_frac").reset_index(drop=True)
    trad = metrics.loc[metrics["method"].eq("geant4_birks_lookup")].iloc[0]
    winner = metrics.iloc[0]
    best_ml = metrics.loc[metrics["family"].str.startswith(("ml_", "neural_"))].sort_values("res68_frac").iloc[0]
    delta_ml_trad = float(best_ml["res68_frac"] - trad["res68_frac"])
    verdict = (
        f"ML loses: traditional {trad['res68_frac']:.5f} beats ML {best_ml['res68_frac']:.5f}; "
        "the GEANT4/Birks lookup is the production candidate for this closure metric."
    )

    calib = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "status": "conditional",
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "res68_frac": float(winner["res68_frac"]),
            "res68_ci95": json.loads(str(winner["res68_ci95"]).replace("'", '"')),
            "bias_frac": float(winner["bias_frac"]),
            "mae_mev": float(winner["mae_mev"]),
        },
        "traditional_calibration": {
            "method": "geant4_birks_lookup",
            "alpha_adc_per_MeV": float(birks["alpha_adc_per_MeV"]),
            "kB_cm_per_MeV": float(birks["kB_cm_per_MeV"]),
            "dedx_table": config["dedx_table"],
            "nominal_geometry": config["nominal_geometry"],
            "stave_thickness_cm": float(config["stave_thickness_cm"]),
            "beam_energy_mev": float(config["beam_energy_mev"]),
            "adoption_gate": "calibration-only; absolute adoption remains blocked until G4-01 and G4-04 pass",
        },
        "stave_priors": json.loads(prior.to_json(orient="records")),
        "raw_reproduction": result["raw_reproduction"],
    }
    calib_path = docs / "G4_02_energy_calibration_calib.json"
    calib_path.write_text(json.dumps(calib, indent=2) + "\n", encoding="utf-8")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=130)
    axes[0].plot(range_table["range_cm"], range_table["energy_mev"], color="#1f77b4", lw=2)
    axes[0].scatter(prior["center_cm"], prior["residual_energy_mev"], color="#d62728", zorder=3, label="B-stave centers")
    for _, row in prior.iterrows():
        axes[0].annotate(row["stave"], (row["center_cm"], row["residual_energy_mev"]), xytext=(5, 4), textcoords="offset points")
    axes[0].set_xlabel("Integrated range in CD2 [cm]")
    axes[0].set_ylabel("Residual proton kinetic energy [MeV]")
    axes[0].set_title("G4-02 range-energy anchor")
    axes[0].legend()

    order = metrics.sort_values("res68_frac", ascending=True)
    axes[1].barh(order["method"], order["res68_frac"], color=["#2ca02c" if m == winner["method"] else "#7f7f7f" for m in order["method"]])
    axes[1].set_xlabel("Held-out res68 fractional energy error")
    axes[1].set_title("Run-held-out model benchmark")
    fig.tight_layout()
    fig_path = figures / "fig_G4_02_range_energy_benchmark.png"
    fig.savefig(fig_path)
    plt.close(fig)

    metrics_report = metrics.copy()
    for col in ["res68_ci95", "mae_mev_ci95", "bias_ci95"]:
        if col in metrics_report.columns:
            metrics_report[col] = metrics_report[col].map(lambda v: fmt_ci(json.loads(str(v).replace("'", '"')) if str(v).startswith("[") else v))

    selected_byrun = byrun[byrun["method"].isin(["geant4_birks_lookup", str(best_ml["method"])])].copy()
    selected_byrun = selected_byrun.sort_values(["run", "method"])
    run_summary = (
        selected_byrun.groupby("method")
        .agg(n_runs=("run", "nunique"), median_res68=("res68_frac", "median"), min_res68=("res68_frac", "min"), max_res68=("res68_frac", "max"))
        .reset_index()
    )

    report = f"""# G4-02 - Energy calibration vs GEANT4 truth deposited energy
- Study ID:      G4-02
- Ticket ID:     {config['ticket_id']}
- Title:         Energy calibration vs GEANT4 truth deposited energy
- Date:          2026-07-10
- Status:        DONE
- Authors:       CCB analysis fleet
- Dependencies:  S00 selected-pulse gate; S14g GEANT4/Birks energy bridge; G4-01/G4-04 pending for adoption
- Data anchor:   {int(repro['reproduced']):,} selected B-stave pulses

**{verdict}**

## Reproduction Gate

Command:

```bash
/home/billy/anaconda3/bin/python scripts/s14g_0000000003_1_g4energy.py --config configs/g4_02_1781212364_2054355_4a1327ef_energy_calibration.yaml
```

Expected: {int(repro['expected']):,} selected B-stave pulses from raw B-stack ROOT files in `{config['raw_root_dir']}`.

Actual: {int(repro['reproduced']):,}; delta {int(repro['delta']):+d}; pass `{str(repro['pass']).lower()}`.

Seed: numpy/sklearn/torch random seed {int(config['random_seed'])}; run-block bootstrap seed is derived from the method name and uses {int(config['bootstrap_reps'])} resamples.

Selection: baseline is the median of samples {config['baseline_samples']}; a selected B pulse is an even physical B-stave channel B2/B4/B6/B8 with peak amplitude greater than {float(config['amplitude_cut_adc']):.1f} ADC.

## Key Metrics Table

The primary score is the 68th percentile of absolute fractional energy residuals, `res68 = P68(|(Ehat - Eodd)/Eodd|)`, evaluated only on held-out runs.

{md_table(metrics_report, ['method', 'family', 'n', 'bias_frac', 'res68_frac', 'res68_ci95', 'mae_mev', 'mae_mev_ci95'])}

## Physics Motivation

The experiment needs an energy observable that is tied to deposited energy rather than only to ADC charge. GEANT4 provides a stopping-power and range-energy prior, while the real data provide duplicate readout closure: even channels predict an odd-channel target after train-run calibration. This G4-02 study asks whether ML improves that calibration enough to justify replacing a transparent GEANT4/Birks rule.

## Methodology

### Data Selection

Raw ROOT branches `HRDv`, `EVENTNO`, and `EVT` are read directly. Waveforms are reshaped into 8 channels by {int(config['samples_per_channel'])} samples; even channels 0/2/4/6 are treated as physical B2/B4/B6/B8 readout and odd channels 1/3/5/7 as duplicate closure readout. After the reproduction gate, events are retained for the energy benchmark when both even and odd event charge sums exceed 100 ADC; pulse rows entering the Birks fit require odd charge above 20 ADC.

Counts by run:

{md_table(counts, ['run', 'group', 'events_total', 'events_with_selected', 'selected_pulses'])}

### GEANT4 Range-Energy Prior

The GEANT4 stopping table `{config['dedx_table']}` is interpreted as kinetic energy `E` in MeV and stopping power `S(E)=dE/dx` in GeV/mm, converted by {float(config['dedx_to_mev_per_cm']):.0f} to MeV/cm. The continuous-slowing-down range is

```text
R(E) = integral_0^E [1 / S(E')] dE' .
```

For each stave center `z_j`, residual kinetic energy is `E_j = R^{-1}(R(E0)-z_j)`, with `E0 = {float(config['beam_energy_mev']):.1f} MeV`. The layer truth prior is

```text
DeltaE_j = E(front_j) - E(back_j)
```

for a {float(config['stave_thickness_cm']):.1f} cm effective layer thickness. This produces the following per-layer priors:

{md_table(prior, ['stave', 'center_cm', 'residual_energy_mev', 'dedx_mev_cm', 'expected_edep_mev'])}

### Traditional Baselines

The strongest traditional method is `geant4_birks_lookup`. On train runs, duplicate odd charges fit the one-parameter Birks-like response

```text
Q_j = alpha * DeltaE_j / (1 + kB * S_j).
```

The fitted constants are `alpha = {float(birks['alpha_adc_per_MeV']):.6g} ADC/MeV` and `kB = {float(birks['kB_cm_per_MeV']):.6g} cm/MeV`. Even-channel charges are inverted with the same response and summed over selected staves. A weaker but transparent empirical incumbent, `old_power_law`, fits `log(Eodd) = beta0 + beta1 log(Qeven)` on train runs.

### ML And Neural Methods

All ML methods use only even-readout information: event multiplicity, depth index, even total charge, maximum even amplitude, saturation count, per-stave log charge, per-stave log amplitude, hit indicators, normalized peak positions, and early/late charge fractions. Odd charge, event identifiers, and run labels are excluded. The evaluated methods are:

- `ridge`: standardized ridge regression on log energy.
- `gradient_boosted_trees`: scikit-learn gradient boosting with 60 depth-3 trees, learning rate 0.05, and 0.75 subsampling.
- `mlp`: tabular PyTorch MLP with one hidden layer and SmoothL1 loss.
- `1d_cnn`: small 1D convolutional network over the four B-stave waveforms plus tabular features.
- `physics_residual_mlp`: the new architecture for this benchmark; it predicts a multiplicative residual correction to the GEANT4/Birks baseline, i.e. `Ehat = Ebirks * exp(f_theta(x, log Ebirks))`.

Training uses sample I calibration runs and run 64; held-out scoring uses sample I analysis runs 44-57 and sample II analysis runs 58-63 and 65.

### Leakage Controls

{md_table(leakage, ['check', 'value', 'pass'])}

## Results

The named winner in `result.json` is `{winner['method']}`. It is a traditional method, not an ML win: the best ML/NN method is `{best_ml['method']}` with res68 {float(best_ml['res68_frac']):.5f}, worse than the GEANT4/Birks baseline at {float(trad['res68_frac']):.5f}. The ML-minus-traditional delta is {delta_ml_trad:+.5f}; since smaller is better, the positive delta means ML loses.

Run-level spread for the production candidate and best ML method:

{md_table(run_summary, ['method', 'n_runs', 'median_res68', 'min_res68', 'max_res68'])}

The range-energy and benchmark figure is archived at `{fig_path.relative_to(ROOT)}`.

## Interpretation

The result supports a conservative calibration policy. GEANT4 truth supplies a physically motivated layer-energy prior, and the duplicate readout shows that a simple Birks inversion transfers across held-out real runs better than the learned models. The ML panel is still informative: gradient-boosted trees approach the traditional candidate in MAE, but their res68 tails and run-block CIs do not justify replacing the transparent physics rule.

This does not establish an absolute calorimetric energy scale for data. The target is duplicate-readout closure after a GEANT4/dE/dx prior, not an independent event-level truth label. Absolute adoption is therefore blocked until G4-01 validates the geometry/material response and G4-04 constrains Birks quenching and light-yield systematics.

## MC Verdict

MC validation is partially available through the GEANT4 stopping-power prior and range-energy curve used here, but not yet sufficient for production adoption. The calibration is marked conditional: use `{calib_path.relative_to(ROOT)}` as a calibration artifact only after G4-01 and G4-04 pass.

## Systematics And Caveats

- Birks quenching: the fitted `kB` absorbs scintillator quenching and electronics response; G4-04 must separate these effects.
- Light yield and ADC scale: `alpha` is learned from duplicate readout and is not an independent absolute light-yield measurement.
- Geometry and layer alignment: the nominal `center_4cm` geometry fixes the MeV scale; alternate center spacings can shift the range-energy prior.
- Particle composition: the ticket asks for proton/deuteron control regions, but current raw ROOT labels do not provide event-level particle truth. This study therefore reports the proton dE/dx anchored closure and flags PID-separated adoption as pending.
- Saturation: saturated pulses remain represented through saturation count and clipped waveform features; high-charge tails can bias neural losses.
- Closure target: odd readout is a duplicate electronics channel, not true deposited energy. It validates transfer consistency, not absolute truth.

## Open Questions

1. G4-04: vary Birks constants and light-yield maps in GEANT4, then test whether `kB` and `alpha` remain stable under duplicate-readout closure.
2. G4-01: propagate material budget and stave-center uncertainty into the G4-02 range-energy curve and report the induced MeV scale envelope.
3. G4-02b: add event-level PID control labels and repeat the benchmark separately for proton and deuteron control regions.

## Provenance

```text
Git commit:        {git_commit()}
Ticket:            {config['ticket_id']}
Data SHA256:       see {out.relative_to(ROOT) / 'input_sha256.csv'}
Python:            {platform.python_version()}
numpy:             {np.__version__}
pandas:            {pd.__version__}
Run host/job:      local testbeam-laptop-4
Artifacts:         {out.relative_to(ROOT)}/{{REPORT.md,result.json,manifest.json,figures/}}
Calibration JSON:  {calib_path.relative_to(ROOT)}
```
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")
    (docs / "G4_02_energy_calibration.md").write_text(report, encoding="utf-8")

    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["command"] = "/home/billy/anaconda3/bin/python scripts/s14g_0000000003_1_g4energy.py --config configs/g4_02_1781212364_2054355_4a1327ef_energy_calibration.yaml && /home/billy/anaconda3/bin/python scripts/g4_02_finalize.py"
    for path in [out / "REPORT.md", docs / "G4_02_energy_calibration.md", calib_path, fig_path]:
        manifest.setdefault("outputs", {})[str(path.relative_to(ROOT))] = sha256_file(path)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"finalized {out.relative_to(ROOT)} winner={winner['method']} calib={calib_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
