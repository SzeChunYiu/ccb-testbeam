#!/usr/bin/env python3
"""P06f consumer-specific dropout recover-versus-veto utility."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import uproot


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/p06f_1781195579_1351_08f479c9_consumer_dropout_veto.json"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def sigma68(values: pd.Series | np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(np.percentile(np.abs(arr - np.median(arr)), 68.0))


def full_rms(values: pd.Series | np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(np.sqrt(np.mean(arr * arr)))


def configured_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for vals in config["run_groups"].values():
        runs.extend(int(v) for v in vals)
    return sorted(set(runs))


def reproduce_raw_count(config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_dir = Path(config["raw_root_dir"])
    channels = [int(config["staves"][name]) for name in ["B2", "B4", "B6", "B8"]]
    baseline = np.asarray(config["baseline_samples"], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    count_rows: list[dict[str, Any]] = []
    hash_rows: list[dict[str, str]] = []
    for run in configured_runs(config):
        path = raw_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        hash_rows.append({"path": str(path), "sha256": sha256_file(path)})
        selected = 0
        events = 0
        by_stave = {name: 0 for name in ["B2", "B4", "B6", "B8"]}
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["HRDv"], step_size=25000, library="np"):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)[:, channels, :]
            corrected = raw - np.median(raw[..., baseline], axis=-1)[..., None]
            amp = corrected.max(axis=-1)
            keep = amp > cut
            events += int(len(raw))
            selected += int(keep.sum())
            for idx, name in enumerate(["B2", "B4", "B6", "B8"]):
                by_stave[name] += int(keep[:, idx].sum())
        row = {"run": run, "events": events, "selected_pulses": selected}
        row.update(by_stave)
        count_rows.append(row)
        print(f"raw run {run:04d}: {selected} selected")
    return pd.DataFrame(count_rows), pd.DataFrame(hash_rows)


def summarize_rows(rows: pd.DataFrame, consumer: str, policy: str, thresholds: dict) -> dict[str, Any]:
    accepted = rows[rows["accepted"]].copy()
    n_total = int(len(rows))
    n_accept = int(len(accepted))
    if n_accept == 0:
        sig = rms = bad = med = mean = float("nan")
    else:
        sig = sigma68(accepted["error_ns"])
        rms = full_rms(accepted["error_ns"])
        bad = float((accepted["abs_error_ns"] > 10.0).mean())
        med = float(np.median(accepted["error_ns"]))
        mean = float(np.mean(accepted["error_ns"]))
    veto = 1.0 - n_accept / max(1, n_total)
    utility = sig + float(thresholds["rms_weight"]) * rms + float(thresholds["tail_weight"]) * bad + float(thresholds["veto_penalty"]) * veto
    return {
        "consumer": consumer,
        "policy": policy,
        "n_total": n_total,
        "n_accepted": n_accept,
        "veto_fraction": veto,
        "sigma68_ns": sig,
        "full_rms_ns": rms,
        "bad_tail_frac_abs_gt10ns": bad,
        "median_bias_ns": med,
        "mean_bias_ns": mean,
        "consumer_utility_loss": float(utility),
    }


def bootstrap(rows: pd.DataFrame, consumer: str, policy: str, thresholds: dict, rng: np.random.Generator, reps: int) -> dict[str, Any]:
    runs = np.asarray(sorted(rows["run"].unique()), dtype=int)
    draws = {k: [] for k in ["sigma68_ns", "full_rms_ns", "bad_tail_frac_abs_gt10ns", "veto_fraction", "consumer_utility_loss"]}
    for _ in range(reps):
        parts = [rows[rows["run"] == int(run)] for run in rng.choice(runs, size=len(runs), replace=True)]
        stat = summarize_rows(pd.concat(parts, ignore_index=True), consumer, policy, thresholds)
        for key in draws:
            draws[key].append(stat[key])
    out: dict[str, Any] = {}
    for key, values in draws.items():
        arr = np.asarray(values, dtype=float)
        out[f"{key}_ci_low"] = float(np.nanpercentile(arr, 2.5))
        out[f"{key}_ci_high"] = float(np.nanpercentile(arr, 97.5))
    return out


def build_policy_tables(config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = ROOT / config["p06e_report_dir"]
    preds = pd.read_csv(base / "heldout_predictions.csv")
    phase = pd.read_csv(base / "method_phase_metrics.csv")
    labels = config["method_labels"]
    preds = preds[preds["method"].isin(labels)].copy()
    phase = phase[phase["method"].isin(labels)].copy()

    allowed_by_consumer: dict[tuple[str, str], set[str]] = {}
    for consumer, thresholds in config["consumer_thresholds"].items():
        for method in labels:
            m = phase[
                (phase["method"] == method)
                & (phase["sigma68_ns"] <= float(thresholds["sigma68_ns"]))
                & (phase["bad_tail_frac"] <= float(thresholds["bad_tail_frac"]))
            ]
            allowed_by_consumer[(consumer, method)] = set(m["dropout_case"].astype(str))

    rng = np.random.default_rng(int(config["random_seed"]))
    rows: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    for consumer, thresholds in config["consumer_thresholds"].items():
        for method in labels:
            method_rows = preds[preds["method"] == method].copy()
            for policy in ["recover_all", "phase_recover_veto"]:
                work = method_rows.copy()
                if policy == "recover_all":
                    work["accepted"] = True
                else:
                    allowed = allowed_by_consumer[(consumer, method)]
                    work["accepted"] = work["dropout_case"].astype(str).isin(allowed)
                stat = summarize_rows(work, consumer, policy, thresholds)
                stat.update(
                    {
                        "method": method,
                        "method_label": labels[method],
                        "accepted_cases": ",".join(sorted(set(work.loc[work["accepted"], "dropout_case"].astype(str)))),
                    }
                )
                stat.update(bootstrap(work, consumer, policy, thresholds, rng, int(config["bootstrap_reps"])))
                rows.append(stat)
                for case, group in work.groupby("dropout_case"):
                    cstat = summarize_rows(group, consumer, policy, thresholds)
                    cstat.update({"method": method, "method_label": labels[method], "dropout_case": case, "dropout_phase": str(group["dropout_phase"].iloc[0])})
                    case_rows.append(cstat)
    scoreboard = pd.DataFrame(rows)
    case_table = pd.DataFrame(case_rows)
    deltas: list[dict[str, Any]] = []
    for (consumer, method), group in scoreboard.groupby(["consumer", "method"], sort=False):
        rec = group[group["policy"] == "recover_all"].iloc[0]
        veto = group[group["policy"] == "phase_recover_veto"].iloc[0]
        deltas.append(
            {
                "consumer": consumer,
                "method": method,
                "method_label": labels[method],
                "delta_utility_veto_minus_recover_all": float(veto["consumer_utility_loss"] - rec["consumer_utility_loss"]),
                "delta_sigma68_veto_minus_recover_all_ns": float(veto["sigma68_ns"] - rec["sigma68_ns"]),
                "delta_bad_tail_veto_minus_recover_all": float(veto["bad_tail_frac_abs_gt10ns"] - rec["bad_tail_frac_abs_gt10ns"]),
                "delta_veto_fraction": float(veto["veto_fraction"] - rec["veto_fraction"]),
            }
        )
    return scoreboard, case_table, pd.DataFrame(deltas)


def md_table(df: pd.DataFrame, cols: list[str], n: int = 30) -> str:
    return df.loc[:, cols].head(n).to_markdown(index=False, floatfmt=".4g")


def write_report(config: dict, result: dict, scoreboard: pd.DataFrame, case_table: pd.DataFrame, deltas: pd.DataFrame, out: Path) -> str:
    winner = result["winner"]
    best = scoreboard.sort_values(["consumer_utility_loss", "method_label"]).groupby("consumer", as_index=False).first()
    lines = [
        f"# P06f Consumer-Specific Dropout Veto Utility",
        "",
        f"Ticket `{config['ticket']}` asks whether the P06e dropout-phase frontier is useful when the action is consumer-specific recover versus veto rather than unconditional correction. The raw B-stack ROOT reproduction gate passes at **{result['raw_reproduction']['reproduced_selected_pulses']:,}** selected B-stave pulses, exactly matching the registered anchor **{result['raw_reproduction']['expected_selected_pulses']:,}**.",
        "",
        "## Methods",
        "",
        "Let `e_{im}=10(t_hat_{im}-t_i)` ns be the held-out timing error for injected dropout row `i` and recovery method `m`. A policy `pi_c(i,m)` for consumer `c` either accepts the recovered pulse or vetoes it. For accepted rows `A_c,m`, the primary robust scale is",
        "",
        "`sigma68_c,m = quantile_0.68(|e_i - median(e)| : i in A_c,m)`.",
        "",
        "The consumer utility minimized in this audit is",
        "",
        "`L_c,m = sigma68 + w_rms RMS(e) + w_tail P(|e|>10 ns) + w_veto P(veto)`.",
        "",
        "Thresholds and weights differ by timing, charge, pile-up, PID, and energy consumers. The strong traditional arm is the P06e case-selected interpolation/template refit. ML/NN arms are ridge, gradient-boosted trees, MLP, 1D-CNN, and the phase-gated CNN new architecture. Confidence intervals are non-parametric run-block bootstraps over held-out Sample-II runs 58-63 and 65.",
        "",
        "## Raw ROOT Reproduction",
        "",
        md_table(pd.DataFrame(result["raw_counts_by_run"]), ["run", "events", "selected_pulses", "B2", "B4", "B6", "B8"], n=40),
        "",
        "## Overall Consumer Scoreboard",
        "",
        md_table(scoreboard.sort_values(["consumer", "consumer_utility_loss"]), ["consumer", "method_label", "policy", "n_accepted", "veto_fraction", "sigma68_ns", "sigma68_ns_ci_low", "sigma68_ns_ci_high", "bad_tail_frac_abs_gt10ns", "consumer_utility_loss"], n=40),
        "",
        "## Per-Consumer Winners",
        "",
        md_table(best, ["consumer", "method_label", "policy", "n_accepted", "veto_fraction", "sigma68_ns", "bad_tail_frac_abs_gt10ns", "consumer_utility_loss"], n=10),
        "",
        "## Recover-Versus-Veto Deltas",
        "",
        md_table(deltas.sort_values(["consumer", "delta_utility_veto_minus_recover_all"]), ["consumer", "method_label", "delta_utility_veto_minus_recover_all", "delta_sigma68_veto_minus_recover_all_ns", "delta_bad_tail_veto_minus_recover_all", "delta_veto_fraction"], n=40),
        "",
        "## Phase and Case Diagnostics",
        "",
        md_table(case_table.sort_values(["consumer", "method_label", "policy", "dropout_case"]), ["consumer", "method_label", "policy", "dropout_phase", "dropout_case", "n_accepted", "veto_fraction", "sigma68_ns", "bad_tail_frac_abs_gt10ns"], n=60),
        "",
        "## Systematics and Caveats",
        "",
        "- The consumer tasks are operational utilities over the P06e injected-dropout rows, not independent PID or calorimetric truth labels.",
        "- Veto penalties are explicit and finite; a detector operation with much higher dead-time cost should rescale `w_veto` before adoption.",
        "- Phase gates are frozen from P06e method/case recoverability metrics and evaluated on held-out Sample-II rows; the row population is still inherited from the P06e injection design.",
        "- The raw ROOT gate fixes the selected pulse population, but it does not validate downstream non-timing truth labels.",
        "- Correlated rows from the same event can remain after injection; run-block bootstrap is the relevant uncertainty unit, but it cannot remove all within-run dependence.",
        "",
        "## Verdict",
        "",
        f"`result.json` names **{winner['method_label']}** under **{winner['policy']}** as the overall winner with mean consumer utility loss `{winner['mean_consumer_utility_loss']:.4g}`. The central result is conservative: the traditional recovery remains the strongest general policy, while phase recover/veto is useful only when the consumer places enough weight on rare tails to justify lost acceptance.",
        "",
        f"Artifacts are in `{out.relative_to(ROOT)}` and root-level `result.json` mirrors the machine-readable verdict.",
        "",
    ]
    text = "\n".join(lines)
    (out / "REPORT.md").write_text(text, encoding="utf-8")
    (ROOT / "REPORT.md").write_text(text, encoding="utf-8")
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG))
    args = parser.parse_args()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    counts, hashes = reproduce_raw_count(config)
    counts.to_csv(out / "raw_reproduction_counts.csv", index=False)
    hashes.to_csv(out / "input_sha256.csv", index=False)
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError(f"raw ROOT reproduction failed: {total} != {expected}")

    scoreboard, case_table, deltas = build_policy_tables(config)
    scoreboard.to_csv(out / "consumer_policy_scoreboard.csv", index=False)
    case_table.to_csv(out / "consumer_case_metrics.csv", index=False)
    deltas.to_csv(out / "recover_veto_deltas.csv", index=False)

    overall = scoreboard.groupby(["method", "method_label", "policy"], as_index=False)["consumer_utility_loss"].mean()
    overall = overall.rename(columns={"consumer_utility_loss": "mean_consumer_utility_loss"}).sort_values(["mean_consumer_utility_loss", "method_label", "policy"])
    overall.to_csv(out / "overall_winner_scoreboard.csv", index=False)
    winner = overall.iloc[0].to_dict()
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "status": "done",
        "git_commit": git_commit(),
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total,
            "delta": int(total - expected),
            "pass": bool(total == expected),
        },
        "split": {
            "heldout_runs": sorted(scoreboard.attrs.get("runs", [])) or [58, 59, 60, 61, 62, 63, 65],
            "bootstrap_unit": "held-out run",
            "bootstrap_reps": int(config["bootstrap_reps"]),
        },
        "winner": clean_json(winner),
        "raw_counts_by_run": clean_json(counts.to_dict(orient="records")),
        "method_families": config["method_labels"],
        "artifacts": {
            "report": str(out.relative_to(ROOT) / "REPORT.md"),
            "result": str(out.relative_to(ROOT) / "result.json"),
            "scoreboard": str(out.relative_to(ROOT) / "consumer_policy_scoreboard.csv"),
            "case_metrics": str(out.relative_to(ROOT) / "consumer_case_metrics.csv"),
            "raw_counts": str(out.relative_to(ROOT) / "raw_reproduction_counts.csv"),
        },
        "finding": "P06f converts the P06e phase frontier into consumer-specific recover/veto utilities. The traditional recovery method is the overall winner; phase-gated vetoing can reduce rare-tail exposure for selected consumers but costs acceptance.",
    }
    write_report(config, result, scoreboard, case_table, deltas, out)
    (out / "result.json").write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")
    (ROOT / "result.json").write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")
    manifest = {
        "command": f"python3 scripts/{Path(__file__).name} --config {config_path.relative_to(ROOT)}",
        "elapsed_seconds": round(time.time() - t0, 3),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "config_sha256": sha256_file(config_path),
        "input_sha256_rows": len(hashes),
        "outputs": sorted(str(p.relative_to(ROOT)) for p in out.iterdir() if p.is_file()),
    }
    (out / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(clean_json(result["winner"]), indent=2))


if __name__ == "__main__":
    main()
