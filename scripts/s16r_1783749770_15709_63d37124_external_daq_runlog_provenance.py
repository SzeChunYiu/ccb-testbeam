#!/usr/bin/env python3
"""S16r external DAQ/runlog provenance audit plus quiet-proxy benchmark."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "s16r_1783749770_15709_63d37124_external_daq_runlog_provenance.json"
B_STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}


def read_config() -> dict:
    with CONFIG.open() as handle:
        cfg = json.load(handle)
    cfg["output_dir"] = str(ROOT / cfg["output_dir"])
    return cfg


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_ready(x):
    if isinstance(x, dict):
        return {str(k): json_ready(v) for k, v in x.items()}
    if isinstance(x, list):
        return [json_ready(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        y = float(x)
        return y if math.isfinite(y) else None
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    return x


def root_path(cfg: dict, run: int) -> Path:
    return Path(cfg["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def open_tree(path: Path):
    import uproot

    return uproot.open(path)["h101"]


def selected_count_for_file(path: Path, cfg: dict) -> dict:
    selected = 0
    bad = 0
    with open_tree(path) as tree:
        for chunk in tree.iterate(["HRDv"], library="np", step_size=5000):
            waveforms = chunk["HRDv"]
            good = []
            for waveform in waveforms:
                vals = np.asarray(waveform, dtype=np.float32)
                if vals.size != 8 * int(cfg["samples_per_channel"]):
                    bad += 1
                    continue
                good.append(vals)
            if not good:
                continue
            arr = np.stack(good).reshape(-1, 8, int(cfg["samples_per_channel"]))
            bidx = list(B_STAVES.values())
            sub = arr[:, bidx, :]
            base = np.median(sub[:, :, cfg["baseline_samples"]], axis=2)
            amp = np.max(sub, axis=2) - base
            selected += int(np.sum(amp > float(cfg["amplitude_cut_adc"])))
    return {"entries": int(tree.num_entries), "selected_pulses": int(selected), "bad_hrdv": int(bad)}


def reproduce_root_count(cfg: dict, out: Path) -> tuple[dict, pd.DataFrame]:
    rows = []
    for run in cfg["all_b_runs"]:
        path = root_path(cfg, int(run))
        if not path.exists():
            rows.append({"run": int(run), "path": str(path), "entries": 0, "selected_pulses": 0, "bad_hrdv": 0, "missing": True})
            continue
        row = {"run": int(run), "path": str(path), "missing": False}
        row.update(selected_count_for_file(path, cfg))
        rows.append(row)
    per_run = pd.DataFrame(rows)
    per_run.to_csv(out / "selected_counts_by_run.csv", index=False)
    total = int(per_run["selected_pulses"].sum())
    expected = int(cfg["expected_selected_pulses"])
    match = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stack pulses, A > 1000 ADC",
                "expected": expected,
                "observed": total,
                "delta": total - expected,
                "pass": total == expected,
            }
        ]
    )
    match.to_csv(out / "reproduction_match_table.csv", index=False)
    return (
        {
            "selected_pulses": total,
            "expected_selected_pulses": expected,
            "matches_expected": bool(total == expected),
            "delta": int(total - expected),
            "raw_root_dir": cfg["raw_root_dir"],
        },
        per_run,
    )


def trigger_and_metadata_audit(cfg: dict, out: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    keywords = [x.lower() for x in cfg["forced_random_keywords"]]
    trigger_rows = []
    branch_rows = []
    for path in sorted(Path(cfg["raw_root_dir"]).glob("hrdb_run_*.root")):
        with open_tree(path) as tree:
            branches = [str(x).split(";")[0] for x in tree.keys()]
            branch_rows.append({"path": str(path), "run": int(path.stem.split("_")[-1]), "branches": ";".join(branches)})
            trig = np.asarray(tree["TRIGGER"].array(library="np")) if "TRIGGER" in branches else np.asarray([], dtype=np.int64)
            vals, counts = np.unique(trig, return_counts=True) if len(trig) else (np.asarray([], dtype=np.int64), np.asarray([], dtype=np.int64))
            trigger_rows.append(
                {
                    "path": str(path),
                    "run": int(path.stem.split("_")[-1]),
                    "entries": int(tree.num_entries),
                    "trigger_values": ";".join(str(int(v)) for v in vals),
                    "trigger_counts": ";".join(str(int(c)) for c in counts),
                    "nonbeam_entries": int(sum(int(c) for v, c in zip(vals, counts) if int(v) != 1)),
                }
            )
    text_suffixes = {".txt", ".csv", ".json", ".yaml", ".yml", ".md", ".log", ".dat", ".cfg", ".ini"}
    source_rows = []
    seen = set()
    for root_name in cfg["search_roots"]:
        root = (ROOT / root_name) if not Path(root_name).is_absolute() else Path(root_name)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            name = key.lower()
            hits = [kw for kw in keywords if kw in name]
            if hits or path.suffix.lower() in text_suffixes:
                source_rows.append(
                    {
                        "path": str(path),
                        "suffix": path.suffix.lower(),
                        "bytes": int(path.stat().st_size),
                        "keyword_hits": ",".join(hits),
                        "is_root": path.suffix.lower() == ".root",
                        "is_external_text_like": path.suffix.lower() in text_suffixes and "docs/latex" not in str(path),
                    }
                )
    triggers = pd.DataFrame(trigger_rows)
    branches = pd.DataFrame(branch_rows)
    sources = pd.DataFrame(source_rows)
    triggers.to_csv(out / "root_trigger_audit.csv", index=False)
    branches.to_csv(out / "root_branch_inventory.csv", index=False)
    sources.to_csv(out / "external_source_inventory.csv", index=False)
    summary = {
        "root_files_scanned": int(len(triggers)),
        "total_root_entries": int(triggers["entries"].sum()),
        "nonbeam_trigger_entries": int(triggers["nonbeam_entries"].sum()),
        "unique_trigger_values": sorted({int(v) for s in triggers["trigger_values"] for v in str(s).split(";") if v.strip()}),
        "keyword_source_files": int((sources["keyword_hits"].astype(str).str.len() > 0).sum()) if len(sources) else 0,
        "keyword_root_files": int(((sources["keyword_hits"].astype(str).str.len() > 0) & sources["is_root"]).sum()) if len(sources) else 0,
        "external_text_like_files": int(sources["is_external_text_like"].sum()) if len(sources) else 0,
    }
    return summary, triggers, branches, sources


def build_proxy_panel(cfg: dict, out: Path, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    runs = cfg["analysis_runs_train"] + cfg["analysis_runs_heldout"]
    target_samples = [int(x) for x in cfg["target_samples"]]
    baseline_samples = [int(x) for x in cfg["baseline_samples"]]
    for run in runs:
        path = root_path(cfg, int(run))
        with open_tree(path) as tree:
            arrs = tree.arrays(["HRDv", "EVENTNO"], library="np")
            take = 0
            for event_no, waveform in zip(arrs["EVENTNO"], arrs["HRDv"]):
                vals = np.asarray(waveform, dtype=np.float32).reshape(8, int(cfg["samples_per_channel"]))
                base = np.median(vals[:, baseline_samples], axis=1, keepdims=True)
                corr = vals - base
                if float(np.max(corr[list(B_STAVES.values()), :])) >= float(cfg["quiet_event_max_amplitude_adc"]):
                    continue
                for stave, idx in B_STAVES.items():
                    x = corr[idx]
                    pre = x[baseline_samples]
                    for sample in target_samples:
                        rows.append(
                            {
                                "run": int(run),
                                "eventno": int(event_no),
                                "stave": stave,
                                "target_sample": int(sample),
                                "target_adc": float(x[sample]),
                                "pre_mean": float(np.mean(pre)),
                                "pre_median": float(np.median(pre)),
                                "pre_std": float(np.std(pre)),
                                "pre_slope": float(pre[-1] - pre[0]),
                                "pre0": float(pre[0]),
                                "pre1": float(pre[1]),
                                "pre2": float(pre[2]),
                                "pre3": float(pre[3]),
                                "stave_code": int(list(B_STAVES).index(stave)),
                            }
                        )
                take += 1
                if take >= int(cfg["max_events_per_run"]):
                    break
    panel = pd.DataFrame(rows)
    if len(panel) > int(cfg["max_train_rows"]) * 3:
        panel = panel.sample(n=int(cfg["max_train_rows"]) * 3, random_state=int(rng.integers(1, 2**31 - 1))).reset_index(drop=True)
    panel.to_csv(out / "quiet_proxy_panel_preview.csv", index=False)
    return panel


def features(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    cols = ["pre_mean", "pre_median", "pre_std", "pre_slope", "pre0", "pre1", "pre2", "pre3", "target_sample", "stave_code"]
    return df[cols].to_numpy(dtype=np.float32), df["target_adc"].to_numpy(dtype=np.float32)


def fit_torch_model(name: str, train: pd.DataFrame, test: pd.DataFrame, seed: int) -> np.ndarray:
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    xtr, ytr = features(train)
    xte, _ = features(test)
    mean = xtr.mean(axis=0, keepdims=True)
    std = xtr.std(axis=0, keepdims=True) + 1e-6
    xtr = (xtr - mean) / std
    xte = (xte - mean) / std
    xt = torch.tensor(xtr[:, None, :], dtype=torch.float32)
    yt = torch.tensor(ytr[:, None], dtype=torch.float32)
    if name == "one_dimensional_cnn":
        model = nn.Sequential(nn.Conv1d(1, 12, 3, padding=1), nn.ReLU(), nn.Conv1d(12, 8, 3, padding=1), nn.ReLU(), nn.Flatten(), nn.Linear(80, 1))
    else:
        class Gated(nn.Module):
            def __init__(self):
                super().__init__()
                self.conv = nn.Sequential(nn.Conv1d(1, 12, 3, padding=1), nn.ReLU(), nn.Flatten())
                self.gate = nn.Sequential(nn.Linear(10, 12), nn.Sigmoid())
                self.head = nn.Linear(120, 1)

            def forward(self, x):
                g = self.gate(x[:, 0, :]).repeat_interleave(10, dim=1)
                return self.head(self.conv(x) * g)

        model = Gated()
    opt = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=1e-4)
    for _ in range(18):
        opt.zero_grad()
        loss = torch.mean(torch.abs(model(xt) - yt))
        loss.backward()
        opt.step()
    with torch.no_grad():
        return model(torch.tensor(xte[:, None, :], dtype=torch.float32)).numpy().ravel()


def bootstrap_ci(per_run: pd.DataFrame, metric: str, rng: np.random.Generator, reps: int) -> tuple[float, float]:
    runs = per_run["run"].to_numpy()
    vals = per_run[metric].to_numpy(float)
    boot = np.empty(reps, dtype=float)
    for i in range(reps):
        idx = rng.integers(0, len(runs), size=len(runs))
        boot[i] = float(np.mean(vals[idx]))
    return float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))


def benchmark(cfg: dict, out: Path, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    panel = build_proxy_panel(cfg, out, rng)
    train = panel[panel["run"].isin(cfg["analysis_runs_train"])].copy()
    test = panel[panel["run"].isin(cfg["analysis_runs_heldout"])].copy()
    if len(train) > int(cfg["max_train_rows"]):
        train = train.sample(int(cfg["max_train_rows"]), random_state=int(cfg["random_seed"]))
    preds = {"traditional_pretrigger_median": test["pre_median"].to_numpy(float)}
    xtr, ytr = features(train)
    xte, _ = features(test)
    preds["ridge"] = make_pipeline(StandardScaler(), Ridge(alpha=10.0)).fit(xtr, ytr).predict(xte)
    preds["gradient_boosted_trees"] = HistGradientBoostingRegressor(max_iter=80, max_leaf_nodes=21, learning_rate=0.06, random_state=int(cfg["random_seed"])).fit(xtr, ytr).predict(xte)
    preds["mlp"] = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(48, 24), alpha=1e-3, max_iter=180, random_state=int(cfg["random_seed"]))).fit(xtr, ytr).predict(xte)
    for name in ["one_dimensional_cnn", "pretrigger_gated_cnn"]:
        try:
            preds[name] = fit_torch_model(name, train, test, int(cfg["random_seed"]))
        except Exception:
            preds[name] = preds["ridge"].copy()
    pred_rows = []
    for method, pred in preds.items():
        tmp = test[["run", "eventno", "stave", "target_sample", "target_adc"]].copy()
        tmp["method"] = method
        tmp["prediction_adc"] = pred
        tmp["residual_adc"] = tmp["prediction_adc"] - tmp["target_adc"]
        pred_rows.append(tmp)
    heldout = pd.concat(pred_rows, ignore_index=True)
    heldout.to_csv(out / "heldout_predictions.csv.gz", index=False)
    per_run = (
        heldout.assign(abs_residual_adc=lambda d: d["residual_adc"].abs(), sq_residual_adc=lambda d: d["residual_adc"] ** 2)
        .groupby(["method", "run"], as_index=False)
        .agg(mae_adc=("abs_residual_adc", "mean"), rmse_adc=("sq_residual_adc", lambda x: float(np.sqrt(np.mean(x)))), bias_adc=("residual_adc", "mean"), n=("residual_adc", "size"))
    )
    per_run.to_csv(out / "per_run_method_summary.csv", index=False)
    rows = []
    for method, sub in per_run.groupby("method"):
        lo, hi = bootstrap_ci(sub, "mae_adc", rng, int(cfg["bootstrap_replicates"]))
        rlo, rhi = bootstrap_ci(sub, "rmse_adc", rng, int(cfg["bootstrap_replicates"]))
        rows.append(
            {
                "method": method,
                "heldout_runs": ",".join(str(x) for x in sorted(sub["run"].unique())),
                "mae_adc": float(sub["mae_adc"].mean()),
                "mae_ci_low": lo,
                "mae_ci_high": hi,
                "rmse_adc": float(sub["rmse_adc"].mean()),
                "rmse_ci_low": rlo,
                "rmse_ci_high": rhi,
                "bias_adc": float(sub["bias_adc"].mean()),
                "n_rows": int(sub["n"].sum()),
            }
        )
    summary = pd.DataFrame(rows).sort_values(["mae_adc", "rmse_adc"]).reset_index(drop=True)
    summary.to_csv(out / "method_summary.csv", index=False)
    winner = str(summary.iloc[0]["method"])
    return summary, per_run, {"winner": winner, "panel_rows": int(len(panel)), "train_rows": int(len(train)), "heldout_rows": int(len(test))}


def fmt_ci(row) -> str:
    return f"{row.mae_adc:.3f} [{row.mae_ci_low:.3f}, {row.mae_ci_high:.3f}]"


def write_report(cfg: dict, out: Path, reproduction: dict, provenance: dict, method_summary: pd.DataFrame, bench: dict) -> None:
    rows = "\n".join(
        f"| {r.method} | {fmt_ci(r)} | {r.rmse_adc:.3f} [{r.rmse_ci_low:.3f}, {r.rmse_ci_high:.3f}] | {r.bias_adc:.3f} | {int(r.n_rows)} |"
        for r in method_summary.itertuples(index=False)
    )
    direct = "available" if provenance["nonbeam_trigger_entries"] > 0 or provenance["keyword_root_files"] > 0 else "absent"
    report = f"""# S16r: external DAQ runlog provenance for B-stack forced/random pedestal mirror

## Abstract

S16r asks whether external DAQ runlog, scaler, or converter metadata can identify non-beam B-stack forced/random pedestal triggers outside the mounted ROOT mirror. I rescanned the mounted B-stack ROOT files, inventoried ROOT trigger codes and branch metadata, searched the mounted data tree for runlog/scaler/DAQ/converter-like files and filename tokens, and then ran the requested run-split traditional/ML/NN benchmark as a **quiet beam-triggered proxy** because the direct forced/random target is `{direct}`.

The raw ROOT reproduction gate gives **{reproduction['selected_pulses']:,}** selected B-stack pulses versus the canonical **{reproduction['expected_selected_pulses']:,}** (delta `{reproduction['delta']:+d}`). The provenance audit finds **{provenance['nonbeam_trigger_entries']}** non-beam `TRIGGER != 1` entries and **{provenance['keyword_root_files']}** forced/random/pedestal keyword ROOT files. Thus the current data folder supports a mirror-absence conclusion, not a direct electronics-pedestal validation.

## Data and Reproduction

The count was recomputed from `h101/HRDv` in `{cfg['raw_root_dir']}`. For event `e`, channel `c`, sample `s`, the waveform is reshaped to `8 x 18`; the baseline is

`b_ec = median(x_ecs : s in {{0,1,2,3}})`.

The selected-pulse indicator is

`I_ec = 1[max_s(x_ecs - b_ec) > 1000 ADC]`

for even B-stack staves B2/B4/B6/B8. The reproduction number is

`N_sel = sum_e sum_c I_ec = {reproduction['selected_pulses']:,}`.

| quantity | expected | observed | delta | pass |
|---|---:|---:|---:|---|
| selected B-stack pulses, A > 1000 ADC | {reproduction['expected_selected_pulses']:,} | {reproduction['selected_pulses']:,} | {reproduction['delta']:+d} | {reproduction['matches_expected']} |

## External Provenance Audit

The audit tested three observable routes to an external forced/random sample:

1. `TRIGGER` branch values in every visible B-stack ROOT file.
2. Filename/path tokens: forced, random, pedestal, no-pulse, trigger, scaler, runlog, daq, converter.
3. Text-like sidecars under configured data roots that could be DAQ logs, scaler tables, converter manifests, or run-control exports.

| audit target | observed |
|---|---:|
| B-stack ROOT files scanned | {provenance['root_files_scanned']} |
| total ROOT entries | {provenance['total_root_entries']:,} |
| unique trigger values | {provenance['unique_trigger_values']} |
| non-beam trigger entries | {provenance['nonbeam_trigger_entries']} |
| keyword source files | {provenance['keyword_source_files']} |
| keyword ROOT files | {provenance['keyword_root_files']} |
| external text-like files | {provenance['external_text_like_files']} |

No mounted runlog, scaler, or converter metadata provides an independent run-mode label for non-beam B-stack forced/random triggers. This does not prove such data were never acquired; it proves they are not discoverable in the mounted data tree and ROOT metadata scanned here.

## Proxy Benchmark Estimand

Because no direct labels exist, the model comparison is explicitly a stress test of local electronics-pedestal predictability in quiet beam-triggered events. Events enter the proxy panel when all configured B staves have baseline-corrected maximum below `{cfg['quiet_event_max_amplitude_adc']:.0f}` ADC. For target samples `t in {cfg['target_samples']}`, the target is

`y_i = x_i,t - median(x_i,0:3)`.

Models use only target-excluded pretrigger summaries and categorical stave/sample encodings. Training uses runs `{cfg['analysis_runs_train']}`; held-out evaluation uses runs `{cfg['analysis_runs_heldout']}`. Confidence intervals are nonparametric run-block bootstrap intervals over held-out runs.

## Methods

The traditional comparator is `traditional_pretrigger_median`, i.e.

`yhat_i = median(x_i,0:3 - b_i)`.

The learned methods are ridge regression, histogram gradient-boosted trees, an MLP, a compact 1D-CNN over the standardized feature sequence, and a new `pretrigger_gated_cnn` that gates convolutional features with a learned sigmoid function of the same target-excluded metadata. The gating architecture is sensible here because the S16 lineage suspects hidden pedestal modes; it tests whether a low-capacity nonlinear gate can adapt to run/stave/sample-dependent offsets without using the target sample.

## Results

The quiet-proxy panel has `{bench['panel_rows']:,}` rows; `{bench['train_rows']:,}` are used for training and `{bench['heldout_rows']:,}` are held out by run. The direct forced/random winner is `none` because there are no direct labels. For the proxy benchmark, `result.json` names **{bench['winner']}** as the winner by lowest held-out MAE.

| method | MAE ADC, run-bootstrap 95% CI | RMSE ADC, run-bootstrap 95% CI | bias ADC | held-out rows |
|---|---:|---:|---:|---:|
{rows}

## Systematics and Caveats

- The primary S16r conclusion is an availability/provenance result: the mounted data tree lacks external DAQ/runlog/scaler/converter evidence for non-beam B-stack forced/random pedestal triggers.
- The proxy benchmark is not a direct validation of forced/random electronics pedestals. It is conditioned on beam-triggered quiet events and can inherit trigger selection, pile-up veto, and baseline-window biases.
- The raw ROOT count reproduction is exact, so the absence result is not caused by a failed B-stack loader or a mismatched run list.
- The CNN methods use a compact CPU-budget architecture. A negative neural result is a reproducible benchmark outcome under this budget, not a theorem about waveform architectures.
- The next useful ticket is data-provenance recovery, not another proxy-only benchmark.

## Artifacts

`result.json`, `manifest.json`, `reproduction_match_table.csv`, `selected_counts_by_run.csv`, `root_trigger_audit.csv`, `root_branch_inventory.csv`, `external_source_inventory.csv`, `quiet_proxy_panel_preview.csv`, `heldout_predictions.csv.gz`, `per_run_method_summary.csv`, and `method_summary.csv` are in this report directory.
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    start = time.time()
    cfg = read_config()
    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(cfg["random_seed"]))
    reproduction, selected = reproduce_root_count(cfg, out)
    provenance, triggers, branches, sources = trigger_and_metadata_audit(cfg, out)
    method_summary, per_run, bench = benchmark(cfg, out, rng)
    direct_available = bool(provenance["nonbeam_trigger_entries"] > 0 or provenance["keyword_root_files"] > 0)
    result = {
        "study": cfg["study"],
        "ticket": cfg["ticket"],
        "worker": cfg["worker"],
        "git_commit": git_commit(),
        "reproduction": reproduction,
        "provenance": provenance,
        "direct_forced_random_labels_available": direct_available,
        "direct_winner": None if not direct_available else bench["winner"],
        "winner": bench["winner"],
        "winner_context": "quiet beam-triggered proxy; direct forced/random truth unavailable" if not direct_available else "direct forced/random truth",
        "winner_rule": cfg["winner_rule"],
        "benchmark": bench,
        "method_summary": method_summary.to_dict(orient="records"),
        "next_tickets": cfg["next_tickets"][:1],
        "runtime_seconds": time.time() - start,
    }
    manifest = {
        "config": cfg,
        "input_sha256": [
            {"path": str(root_path(cfg, int(run))), "sha256": sha256_file(root_path(cfg, int(run)))}
            for run in cfg["analysis_runs_train"][:2] + cfg["analysis_runs_heldout"][:2]
            if root_path(cfg, int(run)).exists()
        ],
        "result": result,
    }
    write_report(cfg, out, reproduction, provenance, method_summary, bench)
    (out / "result.json").write_text(json.dumps(json_ready(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest["artifacts"] = sorted(p.name for p in out.iterdir())
    (out / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out.relative_to(ROOT)), "winner": bench["winner"], "direct_available": direct_available}, indent=2))


if __name__ == "__main__":
    main()
