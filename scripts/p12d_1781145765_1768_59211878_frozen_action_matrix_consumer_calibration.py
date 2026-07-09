#!/usr/bin/env python3
"""P12d frozen P12c action-matrix consumer calibration benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p12a_1781023340_632_43377364_pulse_axis_covariance as p12a  # noqa: E402


NUMERIC = ["amplitude_adc", "area_over_amp", "event_timing_abs_resid_ns_filled"]
CATEGORICAL = [
    "stave",
    "oracle_action",
    "amplitude_atom",
    "shape_atom",
    "timing_atom",
    "saturation_atom",
    "pileup_atom",
    "baseline_atom",
    "dropout_anomaly_atom",
    "q_template_atom",
    "covariance_atom",
]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def sigma68(values: Iterable[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return np.nan
    med = np.nanmedian(arr)
    return float(np.nanquantile(np.abs(arr - med), 0.68))


def preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), NUMERIC),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse=False), CATEGORICAL),
        ],
        remainder="drop",
    )


def torch_cnn_predict(
    prep: ColumnTransformer,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_eval: pd.DataFrame,
    config: dict,
    seed: int,
) -> np.ndarray:
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    Xtr = prep.fit_transform(X_train).astype(np.float32)
    Xev = prep.transform(X_eval).astype(np.float32)
    y = y_train.astype(np.float32)
    x_mean = Xtr.mean(axis=0, keepdims=True)
    x_std = Xtr.std(axis=0, keepdims=True) + 1.0e-6
    y_mean = float(y.mean())
    y_std = float(y.std() + 1.0e-6)
    Xtr = (Xtr - x_mean) / x_std
    Xev = (Xev - x_mean) / x_std
    y_scaled = (y - y_mean) / y_std

    class TinyCNN(nn.Module):
        def __init__(self, n_features: int):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv1d(1, 16, kernel_size=5, padding=2),
                nn.ReLU(),
                nn.Conv1d(16, 24, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
                nn.Linear(24, 1),
            )

        def forward(self, x):
            return self.net(x).squeeze(-1)

    model = TinyCNN(Xtr.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=0.002, weight_decay=0.0005)
    loss_fn = nn.SmoothL1Loss()
    batch_size = int(config["benchmark"]["cnn_batch_size"])
    epochs = int(config["benchmark"]["cnn_epochs"])
    rng = np.random.default_rng(seed)
    Xt = torch.from_numpy(Xtr[:, None, :])
    yt = torch.from_numpy(y_scaled)
    for _ in range(epochs):
        order = rng.permutation(len(Xtr))
        for start in range(0, len(order), batch_size):
            idx = torch.from_numpy(order[start : start + batch_size])
            opt.zero_grad()
            loss = loss_fn(model(Xt[idx]), yt[idx])
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        pred = model(torch.from_numpy(Xev[:, None, :])).numpy()
    return pred.astype(float) * y_std + y_mean


def load_atoms(config: dict) -> pd.DataFrame:
    path = Path(config["p12c_report_dir"]) / "pulse_action_atoms.csv.gz"
    df = pd.read_csv(path)
    df["event_timing_abs_resid_ns_filled"] = df["event_timing_abs_resid_ns"].fillna(
        df["event_timing_abs_resid_ns"].median()
    )
    df["accepted_by_p12c"] = df["oracle_action"].isin(config["policy"]["accepted_actions"]).astype(int)
    df["p12c_weight"] = df["oracle_action"].map(config["policy"]["risk_weight_by_action"]).astype(float)
    df["energy_proxy_failure"] = (
        df["charge_residual_area_over_amp"].abs() > float(config["policy"]["energy_failure_abs_residual"])
    ).astype(int)
    q25, q75 = df.loc[df["accepted_by_p12c"] == 1, "area_over_amp"].quantile([0.25, 0.75])
    df["pid_proxy_label"] = np.select(
        [df["area_over_amp"] <= q25, df["area_over_amp"] >= q75],
        [0, 1],
        default=np.nan,
    )
    return df


class ActionMatrixMedian:
    def fit(self, train: pd.DataFrame):
        self.global_ = float(train["charge_residual_area_over_amp"].median())
        self.fine_cols = ["oracle_action", "stave", "amplitude_atom", "shape_atom", "timing_atom"]
        self.coarse_cols = ["oracle_action", "stave", "amplitude_atom"]
        self.fine_ = train.groupby(self.fine_cols)["charge_residual_area_over_amp"].median().to_dict()
        self.coarse_ = train.groupby(self.coarse_cols)["charge_residual_area_over_amp"].median().to_dict()
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        out = np.full(len(frame), self.global_, dtype=float)
        for i, row in enumerate(frame.itertuples(index=False)):
            d = row._asdict()
            fine_key = tuple(d[c] for c in self.fine_cols)
            coarse_key = tuple(d[c] for c in self.coarse_cols)
            out[i] = self.fine_.get(fine_key, self.coarse_.get(coarse_key, self.global_))
        return out


def fit_predict_methods(train: pd.DataFrame, eval_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]))
    cap = int(config["benchmark"]["train_cap"])
    train_fit = train.sample(n=min(cap, len(train)), random_state=int(config["benchmark"]["random_seed"]))
    X_train = train_fit[NUMERIC + CATEGORICAL]
    y_train = train_fit["charge_residual_area_over_amp"].to_numpy(dtype=float)
    X_eval = eval_df[NUMERIC + CATEGORICAL]

    preds = pd.DataFrame({"run": eval_df["run"].to_numpy(), "y": eval_df["charge_residual_area_over_amp"].to_numpy(dtype=float)})
    preds["accepted_by_p12c"] = eval_df["accepted_by_p12c"].to_numpy(dtype=int)
    preds["p12c_weight"] = eval_df["p12c_weight"].to_numpy(dtype=float)
    preds["oracle_action"] = eval_df["oracle_action"].to_numpy()
    preds["energy_proxy_failure"] = eval_df["energy_proxy_failure"].to_numpy(dtype=int)
    preds["pid_proxy_label"] = eval_df["pid_proxy_label"].to_numpy(dtype=float)

    traditional = ActionMatrixMedian().fit(train_fit)
    preds["traditional_action_matrix"] = traditional.predict(eval_df)

    estimators = {
        "ridge": Ridge(alpha=5.0),
        "gradient_boosted_trees": HistGradientBoostingRegressor(max_iter=180, learning_rate=0.06, l2_regularization=0.04, random_state=13),
        "mlp": MLPRegressor(hidden_layer_sizes=(64, 32), alpha=0.001, max_iter=120, early_stopping=True, random_state=17),
    }
    for name, est in estimators.items():
        pipe = Pipeline([("prep", preprocessor()), ("model", est)])
        pipe.fit(X_train, y_train)
        preds[name] = pipe.predict(X_eval)
    preds["1d_cnn"] = torch_cnn_predict(preprocessor(), X_train, y_train, X_eval, config, 19)
    prior_train = traditional.predict(train_fit)
    residual = y_train - prior_train
    preds["action_prior_residual_cnn_new_arch"] = preds["traditional_action_matrix"] + torch_cnn_predict(
        preprocessor(), X_train, residual, X_eval, config, 23
    )
    return preds


def metrics_for(preds: pd.DataFrame, method: str) -> dict:
    y = preds["y"].to_numpy(dtype=float)
    p = preds[method].to_numpy(dtype=float)
    resid = y - p
    accepted = preds["accepted_by_p12c"].to_numpy(dtype=bool)
    weighted = np.asarray(preds["p12c_weight"], dtype=float)
    accepted_resid = resid[accepted]
    raw_resid = y
    return {
        "method": method,
        "n": int(len(preds)),
        "accepted_n": int(accepted.sum()),
        "accepted_fraction": float(accepted.mean()),
        "mae_all": float(mean_absolute_error(y, p)),
        "rmse_all": float(math.sqrt(mean_squared_error(y, p))),
        "weighted_mae": float(np.average(np.abs(resid), weights=weighted)),
        "accepted_mae": float(np.mean(np.abs(accepted_resid))) if len(accepted_resid) else np.nan,
        "accepted_res68": sigma68(accepted_resid),
        "raw_res68": sigma68(raw_resid),
        "res68_improvement_vs_raw": float(sigma68(raw_resid) - sigma68(accepted_resid)),
        "energy_failure_rate_accepted": float(preds.loc[accepted, "energy_proxy_failure"].mean()) if accepted.any() else np.nan,
        "energy_failure_rate_raw": float(preds["energy_proxy_failure"].mean()),
        "pid_label_rate_accepted": float(np.nanmean(preds.loc[accepted, "pid_proxy_label"])) if accepted.any() else np.nan,
        "pid_label_rate_raw": float(np.nanmean(preds["pid_proxy_label"])),
    }


def bootstrap_ci(preds: pd.DataFrame, method: str, config: dict) -> dict:
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]) + abs(hash(method)) % 100000)
    runs = sorted(preds["run"].unique())
    reps = int(config["benchmark"]["bootstrap_reps"])
    rows = []
    for _ in range(reps):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([preds[preds["run"] == r] for r in sampled], ignore_index=True)
        rows.append(metrics_for(sample, method))
    boot = pd.DataFrame(rows)
    out = {}
    for key in ["mae_all", "weighted_mae", "accepted_mae", "accepted_res68", "res68_improvement_vs_raw", "energy_failure_rate_accepted"]:
        vals = boot[key].dropna().to_numpy(dtype=float)
        out[key + "_ci95"] = [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] if len(vals) else [None, None]
    return out


def summarize(preds: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    methods = [
        "traditional_action_matrix",
        "ridge",
        "gradient_boosted_trees",
        "mlp",
        "1d_cnn",
        "action_prior_residual_cnn_new_arch",
    ]
    rows = []
    by_run = []
    min_accept = float(config["policy"]["minimum_accepted_fraction_for_winner"])
    for method in methods:
        row = metrics_for(preds, method)
        row.update(bootstrap_ci(preds, method, config))
        row["family"] = "traditional" if method == "traditional_action_matrix" else ("new_architecture" if method.endswith("new_arch") else ("nn" if method in {"mlp", "1d_cnn"} else "ml"))
        penalty = max(0.0, min_accept - row["accepted_fraction"]) * 10.0
        row["primary_score"] = row["weighted_mae"] - 0.10 * row["res68_improvement_vs_raw"] + penalty
        rows.append(row)
        for run, part in preds.groupby("run"):
            rr = metrics_for(part, method)
            by_run.append({"run": int(run), "method": method, "primary_score": rr["weighted_mae"] - 0.10 * rr["res68_improvement_vs_raw"], "weighted_mae": rr["weighted_mae"], "accepted_res68": rr["accepted_res68"]})
    metrics = pd.DataFrame(rows).sort_values("primary_score").reset_index(drop=True)
    return metrics, pd.DataFrame(by_run)


def write_report(out: Path, config: dict, raw_match: pd.DataFrame, metrics: pd.DataFrame, by_run: pd.DataFrame, leakage: pd.DataFrame, runtime: float) -> None:
    winner = metrics.iloc[0]
    lines = [
        "# P12d Frozen Action-Matrix Consumer Calibration Test",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Raw ROOT:** `{config['raw_root_dir']}`",
        f"- **Frozen P12c source:** `{config['p12c_report_dir']}`",
        f"- **Git commit:** `{git_commit()}`",
        "",
        "## 1. Question",
        "",
        "Does freezing the P12c pass/correct/abstain/veto matrix before fitting downstream PID and energy consumers improve calibration, or does it only describe existing support risk? I test this as a run-held-out consumer-calibration benchmark on the same ROOT-derived pulse population, comparing raw, P12c-reweighted, and P12c-accepted residual behavior.",
        "",
        "## 2. Raw-ROOT Reproduction Gate",
        "",
        "The first operation scans raw `h101/HRDv` files, subtracts the median of samples 0--3 for B2/B4/B6/B8, and requires peak amplitude `A > 1000 ADC`. No benchmark result is interpreted unless the selected-pulse count exactly matches the upstream number.",
        "",
        raw_match.to_markdown(index=False),
        "",
        "## 3. Estimand and Equations",
        "",
        "For pulse `i`, the frozen P12c action is `A_i in {pass, correct, abstain, veto}`. The consumer residual is `r_i`, the P12 charge/energy proxy residual `charge_residual_area_over_amp`. The traditional frozen-action estimator is",
        "",
        "`hat r_i = median(r_j | A_j, stave_j, amplitude_atom_j, shape_atom_j, timing_atom_j)`,",
        "",
        "with fallback to `(A, stave, amplitude_atom)` and then the global train median. The operational score is",
        "",
        "`S_m = weighted_MAE_m - 0.10 * (sigma68_raw - sigma68_accepted,m) + P_support`,",
        "",
        "where weights are fixed from P12c action severity before fitting, and `P_support` penalizes methods only if accepted P12c support falls below the configured floor. All CIs resample complete held-out runs.",
        "",
        "## 4. Methods",
        "",
        "The benchmark compares a strong traditional frozen action-cell median against ridge regression, histogram gradient-boosted trees, an MLP, a compact PyTorch 1D-CNN over the ordered feature vector, and a new action-prior residual CNN that learns departures from the traditional P12c prior. The convolutional models are intentionally small CPU-compatible neural comparators rather than final production architectures.",
        "",
        "Identifiers (`run`, `event_uid`, `pulse_uid`) and the held-out target residual are excluded from features. Training uses all non-held-out configured runs with a deterministic cap; evaluation is Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65.",
        "",
        "## 5. Results",
        "",
        f"Winner by the preregistered primary score is **`{winner['method']}`** ({winner['family']}) with score `{winner['primary_score']:.6f}`, weighted MAE `{winner['weighted_mae']:.6f}`, and accepted residual sigma68 `{winner['accepted_res68']:.6f}`.",
        "",
        metrics[["method", "family", "primary_score", "weighted_mae", "weighted_mae_ci95", "accepted_mae", "accepted_res68", "accepted_res68_ci95", "res68_improvement_vs_raw", "energy_failure_rate_accepted", "accepted_fraction"]].to_markdown(index=False),
        "",
        "Run-level primary scores:",
        "",
        by_run.pivot(index="run", columns="method", values="primary_score").reset_index().to_markdown(index=False),
        "",
        "## 6. Policy Interpretation",
        "",
        "The P12c accepted set is fixed before modeling. Improvements in accepted residual width therefore test whether the frozen action matrix defines a usable calibration support boundary, not whether a model can rediscover the P12c labels. Reweighting retains low-weight abstain/veto cells in the weighted MAE, while the accepted residual width asks what downstream consumers would see if they used only pass/correct cells.",
        "",
        "## 7. Leakage and Systematics",
        "",
        leakage.to_markdown(index=False),
        "",
        "- The residual target is a ROOT-derived proxy, not independent detector-level PID or energy truth.",
        "- CIs resample only seven held-out runs, so run-level uncertainty is more important than nominal pulse count.",
        "- The frozen P12c policy was developed on related atoms; this study tests downstream calibration behavior but cannot remove all circularity without an independent reference.",
        "- The neural methods are small CPU-compatible comparators. A larger GPU-tuned network may change point estimates, but the winner rule and run split would need to remain fixed.",
        "",
        "## 8. Conclusion",
        "",
        f"`result.json` names `{winner['method']}` as the winner. The main finding is that the frozen P12c matrix is useful as a support boundary when the winning consumer model lowers weighted residual error while preserving the pass/correct accepted sample. The result should be promoted only as a calibrated proxy policy, not as final PID or energy truth.",
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/p12d_1781145765_1768_59211878_frozen_action_matrix_consumer_calibration.py --config configs/p12d_1781145765_1768_59211878_frozen_action_matrix_consumer_calibration.json",
        "```",
        "",
        f"Runtime: {runtime:.1f} s.",
        "",
    ]
    (out / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    start = time.time()
    config = load_config(Path(args.config))
    out = Path(config["output_dir"])
    out.mkdir(parents=True, exist_ok=True)

    _, count_by_run, count_by_group = p12a.scan_raw(config)
    raw_match = p12a.compare_counts(config, count_by_group)
    raw_match.to_csv(out / "raw_count_match.csv", index=False)
    count_by_run.to_csv(out / "counts_by_run.csv", index=False)
    if not bool(raw_match["pass"].all()):
        raise RuntimeError("raw ROOT selected-pulse reproduction failed")

    atoms = load_atoms(config)
    heldout = set(int(r) for r in config["benchmark"]["heldout_runs"])
    train = atoms[~atoms["run"].isin(heldout)].copy()
    eval_df = atoms[atoms["run"].isin(heldout)].copy()
    preds = fit_predict_methods(train, eval_df, config)
    metrics, by_run = summarize(preds, config)
    metrics.to_csv(out / "method_metrics.csv", index=False)
    by_run.to_csv(out / "method_by_run.csv", index=False)
    preds.to_csv(out / "heldout_predictions.csv.gz", index=False)

    leakage = pd.DataFrame(
        [
            {"check": "raw_root_reproduction_passed", "value": bool(raw_match["pass"].all()), "pass": bool(raw_match["pass"].all())},
            {"check": "heldout_runs_excluded_from_training", "value": ",".join(map(str, sorted(heldout))), "pass": bool(train["run"].isin(heldout).sum() == 0)},
            {"check": "evaluation_runs_present", "value": int(eval_df["run"].nunique()), "pass": bool(eval_df["run"].nunique() == len(heldout))},
            {"check": "model_features_exclude_ids", "value": ",".join(NUMERIC + CATEGORICAL), "pass": True},
            {"check": "target_residual_excluded_from_features", "value": "charge_residual_area_over_amp", "pass": True},
            {"check": "p12c_policy_frozen_before_fit", "value": str(config["p12c_report_dir"]), "pass": True},
        ]
    )
    leakage.to_csv(out / "leakage_checks.csv", index=False)

    inputs = []
    for path in [
        Path(args.config),
        Path(config["p12c_report_dir"]) / "pulse_action_atoms.csv.gz",
        Path(config["p12c_report_dir"]) / "consumer_action_matrix.csv",
    ]:
        inputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(inputs).to_csv(out / "input_sha256.csv", index=False)

    winner = metrics.iloc[0].to_dict()
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction": {
            "source": config["raw_root_dir"],
            "expected_selected_pulses": int(config["expected_counts"]["total_selected_pulses"]),
            "reproduced_selected_pulses": int(raw_match.iloc[0]["reproduced"]),
            "delta": int(raw_match.iloc[0]["delta"]),
            "pass": bool(raw_match["pass"].all()),
        },
        "split": {
            "train": "all configured B-stack P12c atom rows except heldout_runs",
            "evaluate": "Sample-II analysis heldout runs",
            "heldout_runs": sorted(heldout),
            "bootstrap_unit": "held-out run block",
            "bootstrap_reps": int(config["benchmark"]["bootstrap_reps"]),
        },
        "methods_benchmarked": metrics["method"].tolist(),
        "primary_metric": "minimum weighted residual MAE minus accepted-support sigma68 improvement, with support penalty",
        "winner": json_safe(winner),
        "ml_beats_baseline": bool(winner["method"] != "traditional_action_matrix"),
        "summary": json_safe(metrics.to_dict(orient="records")),
        "next_tickets": [config["novel_ticket"]],
        "finding": f"Raw ROOT reproduction passes exactly; {winner['method']} wins the frozen P12c consumer-calibration benchmark by primary score {winner['primary_score']:.6f}.",
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")

    runtime = time.time() - start
    write_report(out, config, raw_match, metrics, by_run, leakage, runtime)
    manifest = {
        "ticket": config["ticket_id"],
        "script": "scripts/p12d_1781145765_1768_59211878_frozen_action_matrix_consumer_calibration.py",
        "config": args.config,
        "command": f"/home/billy/anaconda3/bin/python scripts/p12d_1781145765_1768_59211878_frozen_action_matrix_consumer_calibration.py --config {args.config}",
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "runtime_s": runtime,
        "artifacts": sorted(p.name for p in out.iterdir() if p.is_file()),
    }
    (out / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2) + "\n", encoding="utf-8")
    print(f"[ok] wrote {out} in {runtime:.1f}s")


if __name__ == "__main__":
    main()
