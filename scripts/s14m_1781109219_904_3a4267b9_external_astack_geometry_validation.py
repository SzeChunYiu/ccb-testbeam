#!/usr/bin/env python3
"""S14m: external A-stack geometry validation of S14f saturation stress bands."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
import uproot
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def configured_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def heldout_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for group in config["heldout_groups"]:
        runs.extend(int(run) for run in config["run_groups"][group])
    return sorted(set(runs))


def current_lookup(config: dict) -> dict[int, str]:
    out: dict[int, str] = {}
    for label, runs in config["current_strata"].items():
        for run in runs:
            out[int(run)] = label
    return out


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def iter_root(path: Path, branches: Sequence[str]) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=25000, library="np")


def raw_path(config: dict, stack: str, run: int) -> Path:
    return ROOT / config["raw_root_dir"] / f"hrd{stack}_run_{run:04d}.root"


def reproduce_b_counts(config: dict) -> pd.DataFrame:
    rows = []
    channels = [int(v) for v in config["staves"].values()]
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    for run in configured_runs(config):
        selected = 0
        events = 0
        path = raw_path(config, "b", run)
        for batch in iter_root(path, ["HRDv"]):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)[:, channels, :]
            baseline = np.median(raw[:, :, baseline_idx], axis=-1)
            amp = (raw - baseline[:, :, None]).max(axis=-1)
            selected += int((amp > cut).sum())
            events += int(raw.shape[0])
        rows.append({"run": run, "events_total": events, "selected_pulses": selected})
    return pd.DataFrame(rows)


def astack_summary(config: dict) -> pd.DataFrame:
    rows = []
    channels = [int(v) for v in config["astack_staves"].values()]
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    current = current_lookup(config)
    for run in configured_runs(config):
        path = raw_path(config, "a", run)
        if not path.exists():
            continue
        event_rows = []
        for batch in iter_root(path, ["EVT", "HRDv"]):
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)[:, channels, :]
            baseline = np.median(raw[:, :, baseline_idx], axis=-1)
            corr = raw - baseline[:, :, None]
            amp = corr.max(axis=-1)
            area = np.clip(corr, 0.0, None).sum(axis=-1)
            selected = amp > cut
            has = selected.any(axis=1)
            both = selected.all(axis=1)
            if has.any():
                event_rows.append(
                    pd.DataFrame(
                        {
                            "evt": evt[has],
                            "a_selected_count": selected[has].sum(axis=1),
                            "a_both_selected": both[has],
                            "a_charge_sum": (area[has] * selected[has]).sum(axis=1),
                            "a_charge_asym": (area[has, 0] - area[has, 1])
                            / np.maximum(area[has, 0] + area[has, 1], 1.0),
                            "a_amp_max": (amp[has] * selected[has]).max(axis=1),
                        }
                    )
                )
        if not event_rows:
            rows.append({"run": run, "current_family": current.get(run, "unknown"), "a_events": 0})
            continue
        frame = pd.concat(event_rows, ignore_index=True)
        rows.append(
            {
                "run": run,
                "current_family": current.get(run, "unknown"),
                "a_events": int(len(frame)),
                "a_both_fraction": float(frame["a_both_selected"].mean()),
                "a_charge_median": float(frame["a_charge_sum"].median()),
                "a_charge_iqr_frac": float((frame["a_charge_sum"].quantile(0.75) - frame["a_charge_sum"].quantile(0.25)) / max(frame["a_charge_sum"].median(), 1.0)),
                "a_asym_abs_median": float(frame["a_charge_asym"].abs().median()),
                "a_amp_p95": float(frame["a_amp_max"].quantile(0.95)),
            }
        )
    return pd.DataFrame(rows)


def ci(values: Sequence[float]) -> list:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [None, None]
    return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]


def bootstrap_scores(frame: pd.DataFrame, rng: np.random.Generator, reps: int) -> pd.DataFrame:
    rows = []
    methods = sorted(frame["method"].unique())
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {run: frame[frame["run"].eq(run)] for run in runs}
    for method in methods:
        sub = frame[frame["method"].eq(method)].copy()
        resid = sub["saturated_energy_res68"].to_numpy(dtype=float)
        ainst = sub["a_charge_iqr_frac"].to_numpy(dtype=float)
        central_res = float(np.average(resid, weights=np.maximum(sub["n_saturated"], 1.0)))
        central_astack = float(abs(np.corrcoef(resid, ainst)[0, 1])) if len(sub) > 2 and np.std(resid) > 0 and np.std(ainst) > 0 else 0.0
        central_score = central_res * (1.0 + central_astack)
        boot_res = []
        boot_astack = []
        boot_score = []
        for _ in range(reps):
            chosen = rng.choice(runs, size=len(runs), replace=True)
            sample = pd.concat([by_run[int(run)][by_run[int(run)]["method"].eq(method)] for run in chosen], ignore_index=True)
            if sample.empty:
                continue
            r = sample["saturated_energy_res68"].to_numpy(dtype=float)
            a = sample["a_charge_iqr_frac"].to_numpy(dtype=float)
            val_res = float(np.average(r, weights=np.maximum(sample["n_saturated"], 1.0)))
            val_astack = float(abs(np.corrcoef(r, a)[0, 1])) if len(sample) > 2 and np.std(r) > 0 and np.std(a) > 0 else 0.0
            boot_res.append(val_res)
            boot_astack.append(val_astack)
            boot_score.append(val_res * (1.0 + val_astack))
        rows.append(
            {
                "method": method,
                "family": str(sub["family"].iloc[0]) if "family" in sub else "unknown",
                "n_runs": int(sub["run"].nunique()),
                "n_saturated": int(sub["n_saturated"].sum()),
                "mean_b_saturated_res68": central_res,
                "mean_b_saturated_res68_ci95": ci(boot_res),
                "abs_corr_b_res68_vs_astack_iqr": central_astack,
                "abs_corr_b_res68_vs_astack_iqr_ci95": ci(boot_astack),
                "external_transfer_score": central_score,
                "external_transfer_score_ci95": ci(boot_score),
            }
        )
    return pd.DataFrame(rows).sort_values("external_transfer_score").reset_index(drop=True)


def md_table(frame: pd.DataFrame, cols: Sequence[str], limit: int = 40) -> str:
    sub = frame.loc[:, list(cols)].head(limit).copy()
    for col in sub.columns:
        sub[col] = sub[col].map(lambda v: "[" + ", ".join(f"{x:.5g}" if x is not None else "NA" for x in v) + "]" if isinstance(v, list) else (f"{v:.5g}" if isinstance(v, float) else str(v)))
    widths = [max(len(c), int(sub[c].map(len).max() if len(sub) else 0)) for c in sub.columns]
    lines = ["| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |", "| " + " | ".join("---" for _ in sub.columns) + " |"]
    for _, row in sub.iterrows():
        lines.append("| " + " | ".join(str(row[c]).ljust(widths[i]) for i, c in enumerate(sub.columns)) + " |")
    return "\n".join(lines)


def write_report(out_dir: Path, config: dict, result: dict, repro: pd.DataFrame, astack: pd.DataFrame, run_panel: pd.DataFrame, scores: pd.DataFrame) -> None:
    winner = result["winner"]
    text = f"""# S14m: external A-stack geometry validation of S14f saturation stress bands

## Abstract

This study asks whether the S14f geometry-stable saturated B-stack correction bands transfer to an external A-stack detector handle. The B-stack raw ROOT reproduction gate passes exactly at {result['raw_reproduction']['reproduced_selected_pulses']:,} selected B2/B4/B6/B8 pulses. The external-transfer winner is **{winner['method']}**, with score {winner['external_transfer_score']:.5g} and run-bootstrap 95% CI {winner['external_transfer_score_ci95']}. The score combines held-out saturated B-stack energy-proxy resolution with the absolute run-level correlation to A-stack charge instability, so a method wins only if it remains accurate and does not track an external A-stack nuisance.

## 1. Raw ROOT Reproduction

The B-stack count was rebuilt directly from `h101/HRDv` in `data/root/root`. For each configured run and B channel, the baseline is the median of samples 0--3; a pulse is selected when the baseline-subtracted maximum exceeds 1000 ADC.

| Quantity | Expected | Reproduced | Delta | Pass |
|---|---:|---:|---:|:---|
| B-stack selected pulses | {result['raw_reproduction']['expected_selected_pulses']:,} | {result['raw_reproduction']['reproduced_selected_pulses']:,} | {result['raw_reproduction']['delta']:+,} | {str(result['raw_reproduction']['pass']).lower()} |

Per-run reproduction excerpt:

{md_table(repro, ['run', 'events_total', 'selected_pulses'], 40)}

## 2. External A-stack Handle

The A-stack handle is independently rebuilt from `hrda_run_*.root` using channels A1 and A3. The external nuisance variable is the run-level fractional interquartile width of selected A-stack charge,

\\[
I_A(r)=\\frac{{Q_{{75}}(Q_A\\mid r)-Q_{{25}}(Q_A\\mid r)}}{{\\operatorname{{median}}(Q_A\\mid r)}} ,
\\]

with the selected-event support and A1/A3 balance retained as diagnostics. This handle is not used to train any S14f method; it is an external transfer stress variable.

{md_table(astack, ['run', 'current_family', 'a_events', 'a_both_fraction', 'a_charge_median', 'a_charge_iqr_frac', 'a_asym_abs_median'], 40)}

## 3. Benchmark Panel

The method panel is inherited from the S14f run-held-out saturated geometry benchmark: observed even charge, a strong traditional rising-edge template/range lookup, ridge regression, gradient-boosted trees, MLP, 1D-CNN, and the new template-residual MLP architecture. The S14f outputs supply per-run saturated energy-proxy resolution and method families; this study joins those per-run rows to the raw A-stack run summaries.

For method \(m\) and held-out run \(r\), let \(R_m(r)\) be S14f saturated energy-proxy \(R_{{68}}\) and \(I_A(r)\) the A-stack charge-width handle above. The external-transfer score is

\\[
S_m=\\bar R_m\\left(1+\\left|\\rho_R(R_m(r),I_A(r))\\right|\\right),
\\qquad
\\bar R_m=\\frac{{\\sum_r n_{{m,r}}R_m(r)}}{{\\sum_r n_{{m,r}}}} .
\\]

The bootstrap resamples held-out runs with replacement and recomputes both terms. This penalizes a method whose apparent B-stack correction strength is coupled to independent A-stack charge instability.

{md_table(scores, ['method', 'family', 'n_runs', 'n_saturated', 'mean_b_saturated_res68', 'mean_b_saturated_res68_ci95', 'abs_corr_b_res68_vs_astack_iqr', 'abs_corr_b_res68_vs_astack_iqr_ci95', 'external_transfer_score', 'external_transfer_score_ci95'], 80)}

## 4. Run-Level Join Diagnostics

{md_table(run_panel.sort_values(['method', 'run']), ['run', 'current_family', 'method', 'n_saturated', 'saturated_energy_res68', 'a_charge_iqr_frac', 'a_both_fraction'], 120)}

## 5. Systematics and Caveats

The A-stack handle is external but run-level: it tests whether S14f saturated B-stack performance transfers across independent A-stack charge/topology conditions, not event-by-event calorimetric truth. Matching by run avoids inventing an unverified cross-detector event identity beyond shared run/DAQ context. The S14f target remains duplicate-readout closure mapped to a range-order proxy, so Birks quenching, particle identity, and material survey uncertainties remain outside this validation. The correlation penalty is intentionally conservative: it treats strong dependence on A-stack charge width as a transfer risk even when the B-stack point estimate is good.

## 6. Finding

{result['finding']}

## 7. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14m_1781109219_904_3a4267b9_external_astack_geometry_validation.py --config configs/s14m_1781109219_904_3a4267b9_external_astack_geometry_validation.yaml
```

Artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `astack_run_summary.csv`, `method_external_transfer_scores.csv`, `method_run_external_panel.csv`, `input_sha256.csv`, and `manifest.json`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14m_1781109219_904_3a4267b9_external_astack_geometry_validation.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    repro_runs = reproduce_b_counts(config)
    reproduced = int(repro_runs["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if reproduced != expected:
        raise RuntimeError(f"raw reproduction failed: {reproduced} != {expected}")
    repro = pd.DataFrame([{"quantity": "B-stack selected pulses", "expected": expected, "reproduced": reproduced, "delta": reproduced - expected, "pass": True}])

    s14f_dir = ROOT / config["s14f_dir"]
    per_run = pd.read_csv(s14f_dir / "per_run_acceptance.csv")
    metrics = pd.read_csv(s14f_dir / "method_metrics.csv")[["method", "family"]].drop_duplicates()
    per_run = per_run.merge(metrics, on="method", how="left")
    astack = astack_summary(config)
    run_panel = per_run.merge(astack, on=["run", "current_family"], how="inner")
    run_panel = run_panel[run_panel["run"].isin(heldout_runs(config))].reset_index(drop=True)
    scores = bootstrap_scores(run_panel, np.random.default_rng(int(config["random_seed"])), int(config["bootstrap_reps"]))

    winner = scores.iloc[0].to_dict()
    finding = (
        f"{winner['method']} has the best external-transfer score ({winner['external_transfer_score']:.5g}), "
        f"combining mean held-out saturated B-stack R68 {winner['mean_b_saturated_res68']:.5g} "
        f"with absolute A-stack instability correlation {winner['abs_corr_b_res68_vs_astack_iqr']:.5g}. "
        "The result supports S14f transfer only as a run-level external validation; it is not an event-level absolute energy calibration."
    )
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction": {"expected_selected_pulses": expected, "reproduced_selected_pulses": reproduced, "delta": reproduced - expected, "pass": True},
        "split": {"train_runs": sorted(set(configured_runs(config)) - set(heldout_runs(config))), "heldout_runs": heldout_runs(config), "split_unit": "run"},
        "primary_metric": "external_transfer_score = weighted held-out B saturated R68 times one plus absolute run-level correlation with A-stack charge IQR fraction",
        "winner": {
            "method": winner["method"],
            "family": winner["family"],
            "external_transfer_score": float(winner["external_transfer_score"]),
            "external_transfer_score_ci95": winner["external_transfer_score_ci95"],
            "mean_b_saturated_res68": float(winner["mean_b_saturated_res68"]),
            "mean_b_saturated_res68_ci95": winner["mean_b_saturated_res68_ci95"],
            "abs_corr_b_res68_vs_astack_iqr": float(winner["abs_corr_b_res68_vs_astack_iqr"]),
            "abs_corr_b_res68_vs_astack_iqr_ci95": winner["abs_corr_b_res68_vs_astack_iqr_ci95"],
        },
        "methods": json.loads(scores.to_json(orient="records")),
        "finding": finding,
        "next_tickets": [
            {
                "title": "S14n: event-key A/B coincidence validation for saturation transfer",
                "body": "Verify whether A-stack and B-stack ROOT event counters can be joined at event-key level across analysis runs, then rerun S14m with event-level A-stack charge instead of run-level transfer handles.",
            }
        ],
        "runtime_sec": round(time.time() - t0, 1),
    }

    repro_runs.to_csv(out_dir / "b_reproduction_counts_by_run.csv", index=False)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    astack.to_csv(out_dir / "astack_run_summary.csv", index=False)
    run_panel.to_csv(out_dir / "method_run_external_panel.csv", index=False)
    scores.to_csv(out_dir / "method_external_transfer_scores.csv", index=False)
    input_paths = [raw_path(config, "b", run) for run in configured_runs(config)] + [raw_path(config, "a", run) for run in configured_runs(config) if raw_path(config, "a", run).exists()]
    input_paths += [s14f_dir / "method_metrics.csv", s14f_dir / "per_run_acceptance.csv", config_path]
    input_rows = []
    for p in input_paths:
        try:
            display = p.relative_to(ROOT)
        except ValueError:
            display = p
        input_rows.append({"path": str(display), "bytes": int(p.stat().st_size), "sha256": sha256_file(p)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps({"command": f"/home/billy/anaconda3/bin/python scripts/s14m_1781109219_904_3a4267b9_external_astack_geometry_validation.py --config {args.config}", "git_commit": git_commit(), "platform": platform.platform(), "runtime_sec": result["runtime_sec"]}, indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, result, repro_runs, astack, run_panel, scores)


if __name__ == "__main__":
    main()
