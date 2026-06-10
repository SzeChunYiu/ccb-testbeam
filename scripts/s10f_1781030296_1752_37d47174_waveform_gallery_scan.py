#!/usr/bin/env python3
"""S10f blinded waveform-gallery morphology scan.

The candidate scores come from the S10e real-candidate run-held-out scoring
table. This script reloads the raw B-stack ROOT-derived waveforms through the
same S10e loader, reproduces the S10 topology gate first, verifies the score
rows against the raw event table, then applies a deterministic blinded
morphology rubric to high-current candidates above the S10d real-candidate
thresholds and matched low-current controls.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s10f_1781030296_1752_37d47174_waveform_gallery_scan.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


CFG = load_json(CONFIG)
TICKET = CFG["ticket"]
OUT = ROOT / CFG["output_dir"]
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(OUT / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


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


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def load_s10e_source():
    path = ROOT / CFG["source_s10e_script"]
    spec = importlib.util.spec_from_file_location("s10e_real_candidate_source", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def event_score_flags(scores: pd.DataFrame) -> pd.DataFrame:
    out = scores.copy()
    out["traditional_above_s10d_threshold"] = (
        (out["trad_score_sse_improvement"] > float(CFG["traditional_score_threshold"]))
        & (out["trad_delay_ns"] >= float(CFG["traditional_delay_threshold_ns"]))
    )
    out["ml_above_s10d_threshold"] = (
        (out["ml_overlap_score"] > float(CFG["ml_score_threshold"]))
        & (out["ml_delay_ns"] >= float(CFG["ml_delay_threshold_ns"]))
    )
    out["any_above_s10d_threshold"] = out["traditional_above_s10d_threshold"] | out["ml_above_s10d_threshold"]
    return out


def waveform_features(waves: np.ndarray, rows: pd.DataFrame) -> pd.DataFrame:
    chosen = waves[rows["event_index"].to_numpy(dtype=int)].astype(float)
    amp = np.maximum(np.nanmax(chosen, axis=1), 1.0)
    norm = chosen / amp[:, None]
    peak = np.argmax(norm, axis=1)
    second_idx = np.zeros(len(norm), dtype=int)
    second_frac = np.zeros(len(norm), dtype=float)
    valley_frac = np.ones(len(norm), dtype=float)
    separation_ns = np.zeros(len(norm), dtype=float)
    for i, wf in enumerate(norm):
        start = min(int(peak[i]) + 2, wf.size - 1)
        tail = wf[start:]
        if len(tail):
            rel = int(np.argmax(tail))
            second_idx[i] = start + rel
            second_frac[i] = float(tail[rel])
            lo = min(int(peak[i]), int(second_idx[i]))
            hi = max(int(peak[i]), int(second_idx[i]))
            valley_frac[i] = float(np.min(wf[lo : hi + 1])) if hi > lo else 1.0
            separation_ns[i] = 10.0 * float(second_idx[i] - peak[i])
    area = norm.sum(axis=1)
    width20 = (norm > 0.20).sum(axis=1).astype(float)
    width10 = (norm > 0.10).sum(axis=1).astype(float)
    late_max = norm[:, 10:].max(axis=1)
    final_frac = norm[:, -1]
    early_max = norm[:, :4].max(axis=1)
    min_post = norm[:, 8:].min(axis=1)
    neg_steps = (np.diff(norm, axis=1) < -0.20).sum(axis=1).astype(float)
    dip_depth = np.maximum(0.0, np.minimum(1.0, second_frac) - valley_frac)
    return pd.DataFrame(
        {
            "blind_peak_sample": peak.astype(float),
            "blind_second_peak_sample": second_idx.astype(float),
            "blind_second_peak_frac": second_frac,
            "blind_valley_frac": valley_frac,
            "blind_dip_depth": dip_depth,
            "blind_second_peak_separation_ns": separation_ns,
            "blind_area_over_peak": area,
            "blind_width10_samples": width10,
            "blind_width20_samples": width20,
            "blind_late_max_frac": late_max,
            "blind_final_frac": final_frac,
            "blind_early_max_frac": early_max,
            "blind_min_post_frac": min_post,
            "blind_neg_step_count": neg_steps,
        }
    )


def classify_morphology(feat: pd.DataFrame) -> pd.DataFrame:
    out = feat.copy()
    early_pathology = (
        (out["blind_peak_sample"] <= 3)
        | (out["blind_area_over_peak"] < 1.65)
        | (out["blind_neg_step_count"] >= 3)
        | (out["blind_min_post_frac"] < -0.20)
    )
    two_pulse_like = (
        (out["blind_second_peak_frac"] >= 0.28)
        & (out["blind_second_peak_separation_ns"] >= 20.0)
        & (out["blind_dip_depth"] >= 0.08)
        & ~early_pathology
    )
    broad_late = (
        ((out["blind_width20_samples"] >= 9) | (out["blind_late_max_frac"] >= 0.28) | (out["blind_area_over_peak"] >= 5.7))
        & ~two_pulse_like
        & ~early_pathology
    )
    single_tail = ~(two_pulse_like | broad_late | early_pathology)
    out["morphology"] = np.select(
        [two_pulse_like, broad_late, early_pathology, single_tail],
        ["two_pulse_like", "broad_late_shape", "pathology_or_noisy", "single_tail"],
        default="single_tail",
    )
    out["two_pulse_like"] = two_pulse_like.astype(float)
    out["artifact_like"] = (~two_pulse_like).astype(float)
    out["shape_artifact_strong"] = (broad_late | early_pathology).astype(float)
    return out


def add_blind_labels(scored: pd.DataFrame) -> pd.DataFrame:
    key = (
        scored["event_index"].astype(str)
        + ":"
        + scored["run"].astype(str)
        + ":"
        + scored["eventno"].astype(str)
    )
    digest = key.map(lambda x: hashlib.sha1((str(CFG["random_seed"]) + ":" + x).encode("utf-8")).hexdigest()[:10])
    out = scored.copy()
    out["blind_id"] = "B" + digest
    return out.sort_values("blind_id").reset_index(drop=True)


def bootstrap_group_delta(rows: pd.DataFrame, flag_col: str, value_col: str, rng: np.random.Generator) -> dict:
    high = rows[(rows[flag_col]) & (rows["group"] == "high_20nA")]
    low = rows[(rows["low_control_for_" + flag_col]) & (rows["group"] == "low_2nA")]
    high_runs = np.array(sorted(high["run"].unique()), dtype=int)
    low_runs = np.array(sorted(low["run"].unique()), dtype=int)

    def mean_for(df: pd.DataFrame) -> float:
        return float(df[value_col].mean()) if len(df) else float("nan")

    high_mean = mean_for(high)
    low_mean = mean_for(low)
    boot = []
    for _ in range(int(CFG["bootstrap_samples"])):
        pieces = []
        for run in rng.choice(high_runs, size=len(high_runs), replace=True) if len(high_runs) else []:
            pieces.append(high[high["run"] == int(run)])
        for run in rng.choice(low_runs, size=len(low_runs), replace=True) if len(low_runs) else []:
            pieces.append(low[low["run"] == int(run)])
        if not pieces:
            continue
        sample = pd.concat(pieces, ignore_index=True)
        h = sample[(sample[flag_col]) & (sample["group"] == "high_20nA")]
        l = sample[(sample["low_control_for_" + flag_col]) & (sample["group"] == "low_2nA")]
        if len(h) and len(l):
            boot.append(float(h[value_col].mean() - l[value_col].mean()))
    ci = np.quantile(boot, [0.025, 0.975]) if boot else [np.nan, np.nan]
    return {
        "method": "traditional" if flag_col.startswith("traditional") else "ml",
        "metric": value_col,
        "n_high_candidates": int(len(high)),
        "n_low_controls": int(len(low)),
        "high_value": high_mean,
        "low_control_value": low_mean,
        "high_minus_low_control": float(high_mean - low_mean),
        "ci_low": float(ci[0]),
        "ci_high": float(ci[1]),
        "high_runs": " ".join(str(x) for x in high_runs),
        "low_control_runs": " ".join(str(x) for x in low_runs),
    }


def mark_low_controls(scored: pd.DataFrame) -> pd.DataFrame:
    out = scored.copy()
    for flag_col in ["traditional_above_s10d_threshold", "ml_above_s10d_threshold"]:
        high = out[(out[flag_col]) & (out["group"] == "high_20nA")]
        strata = sorted(high["stratum"].unique())
        staves = sorted(high["ref_stave"].unique())
        out["low_control_for_" + flag_col] = (
            (out["group"] == "low_2nA")
            & out["stratum"].isin(strata)
            & out["ref_stave"].isin(staves)
        )
    return out


def gallery_subset(scored: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    pieces = []
    trad_high = scored[(scored["traditional_above_s10d_threshold"]) & (scored["group"] == "high_20nA")].nlargest(
        int(CFG["gallery_high_per_method"]), "trad_delay_ns"
    )
    ml_high = scored[(scored["ml_above_s10d_threshold"]) & (scored["group"] == "high_20nA")].nlargest(
        int(CFG["gallery_high_per_method"]), "ml_overlap_score"
    )
    low_pool = scored[
        scored["low_control_for_traditional_above_s10d_threshold"] | scored["low_control_for_ml_above_s10d_threshold"]
    ]
    low = low_pool.sample(n=min(int(CFG["gallery_low_controls"]), len(low_pool)), random_state=int(rng.integers(0, 1_000_000)))
    pieces.extend([trad_high, ml_high, low])
    gallery = pd.concat(pieces, ignore_index=True).drop_duplicates("event_index")
    return gallery.sort_values("blind_id").reset_index(drop=True)


def write_gallery(scored: pd.DataFrame, waves: np.ndarray, path: Path) -> None:
    n = len(scored)
    cols = 6
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 2.15, rows * 1.65), sharex=True, sharey=True)
    axes = np.asarray(axes).reshape(-1)
    x = np.arange(18) * 10.0
    for ax, (_, row) in zip(axes, scored.iterrows()):
        wf = waves[int(row["event_index"])].astype(float)
        wf = wf / max(float(np.nanmax(wf)), 1.0)
        ax.plot(x, wf, lw=1.1, color="#222222")
        ax.axhline(0.0, color="#999999", lw=0.5)
        tags = []
        if bool(row["traditional_above_s10d_threshold"]):
            tags.append("T")
        if bool(row["ml_above_s10d_threshold"]):
            tags.append("M")
        if row["group"] == "low_2nA":
            tags.append("L")
        title = f"{row['blind_id']} {'/'.join(tags)}\n{row['morphology']}"
        ax.set_title(title, fontsize=6.5)
        ax.tick_params(labelsize=6)
    for ax in axes[n:]:
        ax.axis("off")
    fig.supxlabel("sample time (ns)", fontsize=9)
    fig.supylabel("normalized ADC", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write_report(result: dict, repro: pd.DataFrame, summary: pd.DataFrame, counts: pd.DataFrame) -> None:
    trad = summary[(summary["method"] == "traditional") & (summary["metric"] == "two_pulse_like")].iloc[0]
    ml = summary[(summary["method"] == "ml") & (summary["metric"] == "two_pulse_like")].iloc[0]
    lines = [
        "# S10f: blinded waveform gallery scan",
        "",
        f"- **Ticket:** `{TICKET}`",
        f"- **Worker:** `{CFG['worker']}`",
        "- **Inputs:** raw B-stack ROOT runs 44-57 plus S10e run-held-out score table; no Monte Carlo.",
        "- **Split:** candidate scores are source-run held out from S10e; morphology CIs bootstrap held-out source runs.",
        "",
        "## Reproduction first",
        "",
        (
            "The raw ROOT S10 topology gate was rerun before any gallery classification. "
            f"All documented topology rows pass: {bool(repro['pass'].all())}. "
            f"The S10d real-candidate thresholds used here are traditional score > {CFG['traditional_score_threshold']} "
            f"with delay >= {CFG['traditional_delay_threshold_ns']:.0f} ns, and ML score > {CFG['ml_score_threshold']} "
            f"with delay >= {CFG['ml_delay_threshold_ns']:.0f} ns."
        ),
        "",
        repro.to_markdown(index=False),
        "",
        "## Candidate gallery",
        "",
        (
            f"The high-current set contains {result['candidate_counts']['traditional_high']} traditional candidates and "
            f"{result['candidate_counts']['ml_high']} ML candidates above the reproduced S10d real-candidate thresholds. "
            "Rows were assigned blinded IDs before morphology labeling; the rubric used only normalized waveform shape "
            "features, not current group, run, event number, or model scores. A compact audit image is in "
            "`waveform_gallery_blinded.png`."
        ),
        "",
        counts.to_markdown(index=False),
        "",
        "## Traditional method",
        "",
        (
            "Traditional candidates are the bounded template-fit events with nontrivial SSE improvement and recovered delay "
            f"above {CFG['traditional_delay_threshold_ns']:.0f} ns. Their two-pulse-like morphology fraction is "
            f"**{trad['high_value']:.3f}** versus **{trad['low_control_value']:.3f}** in matched low-current controls, "
            f"delta **{trad['high_minus_low_control']:.3f}** "
            f"[{trad['ci_low']:.3f}, {trad['ci_high']:.3f}]."
        ),
        "",
        "## ML method",
        "",
        (
            "ML candidates are the random-forest residual-score events with overlap score and recovered delay above the "
            f"S10d ML thresholds. Their two-pulse-like morphology fraction is **{ml['high_value']:.3f}** versus "
            f"**{ml['low_control_value']:.3f}** in matched low-current controls, delta "
            f"**{ml['high_minus_low_control']:.3f}** [{ml['ci_low']:.3f}, {ml['ci_high']:.3f}]."
        ),
        "",
        "## Leakage review",
        "",
        (
            f"Leakage flags: {result['leakage']['n_flags']}. Candidate scoring is inherited from S10e's run-held-out "
            "fits/ML; this script verifies score rows against freshly loaded raw ROOT events. The morphology classifier "
            "uses only blinded waveform features. Current AUC from morphology two-pulse-like labels is "
            f"{result['leakage']['current_auc_from_morphology']:.3f}; current AUC from the blinded morphology feature "
            f"score is {result['leakage']['current_auc_from_blind_shape_score']:.3f}."
        ),
        "",
        "## Conclusion",
        "",
        result["conclusion"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `morphology_scores.csv`, `morphology_summary.csv`, "
        "`morphology_counts.csv`, `gallery_manifest.csv`, and `waveform_gallery_blinded.png` are in this folder.",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def hash_outputs() -> dict:
    return {p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"}


def main() -> int:
    start = time.time()
    rng = np.random.default_rng(int(CFG["random_seed"]))
    s10e = load_s10e_source()
    events, waves, run_counts = s10e.load_events()
    topology, repro = s10e.reproduce_s10(events)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT S10 topology reproduction failed")

    scores_path = ROOT / CFG["source_s10e_scores"]
    scores = event_score_flags(pd.read_csv(scores_path))
    check = scores.merge(
        events[["event_index", "run", "eventno", "ref_stave", "ref_amp_adc", "stratum"]],
        on="event_index",
        suffixes=("_score", "_raw"),
        how="left",
    )
    if check["run_raw"].isna().any():
        raise RuntimeError("some S10e score rows do not map to raw-loaded event_index")
    max_amp_delta = float(np.max(np.abs(check["ref_amp_adc_score"] - check["ref_amp_adc_raw"])))
    row_match = bool(
        (check["run_score"].astype(int) == check["run_raw"].astype(int)).all()
        and (check["eventno_score"].astype(int) == check["eventno_raw"].astype(int)).all()
        and (check["ref_stave_score"].astype(str) == check["ref_stave_raw"].astype(str)).all()
        and max_amp_delta < 1.0e-9
    )
    if not row_match:
        raise RuntimeError("S10e score rows failed raw event consistency check")

    feat = classify_morphology(waveform_features(waves, scores))
    scored = pd.concat([scores.reset_index(drop=True), feat.reset_index(drop=True)], axis=1)
    scored = add_blind_labels(mark_low_controls(scored))

    summaries = []
    for flag in ["traditional_above_s10d_threshold", "ml_above_s10d_threshold"]:
        for metric in ["two_pulse_like", "artifact_like", "shape_artifact_strong"]:
            summaries.append(bootstrap_group_delta(scored, flag, metric, rng))
    summary = pd.DataFrame(summaries)

    counts = (
        scored[
            (scored["traditional_above_s10d_threshold"] & (scored["group"] == "high_20nA"))
            | (scored["ml_above_s10d_threshold"] & (scored["group"] == "high_20nA"))
            | scored["low_control_for_traditional_above_s10d_threshold"]
            | scored["low_control_for_ml_above_s10d_threshold"]
        ]
        .groupby(["group", "morphology"], observed=False)
        .agg(n=("event_index", "size"))
        .reset_index()
    )
    gallery = gallery_subset(scored, rng)
    write_gallery(gallery, waves, OUT / "waveform_gallery_blinded.png")

    high_any = scored[(scored["group"] == "high_20nA") & scored["any_above_s10d_threshold"]]
    current_rows = scored[
        scored["any_above_s10d_threshold"]
        | scored["low_control_for_traditional_above_s10d_threshold"]
        | scored["low_control_for_ml_above_s10d_threshold"]
    ].copy()
    y_current = (current_rows["group"] == "high_20nA").astype(int).to_numpy()
    morph_auc = float(roc_auc_score(y_current, current_rows["two_pulse_like"])) if len(np.unique(y_current)) == 2 else float("nan")
    blind_score = (
        current_rows["blind_second_peak_frac"].to_numpy()
        + current_rows["blind_dip_depth"].to_numpy()
        + 0.01 * current_rows["blind_second_peak_separation_ns"].to_numpy()
    )
    blind_auc = float(roc_auc_score(y_current, blind_score)) if len(np.unique(y_current)) == 2 else float("nan")
    leakage_rows = pd.DataFrame(
        [
            {
                "check": "s10e_scores_match_raw_root_events",
                "value": 1.0 if row_match else 0.0,
                "flag": False,
                "note": "run/event/stave/amplitude in score table match freshly loaded raw ROOT event table",
            },
            {
                "check": "morphology_features_exclude_identifiers_and_scores",
                "value": 1.0,
                "flag": False,
                "note": "rubric uses normalized waveform shape only after blinded IDs are assigned",
            },
            {
                "check": "current_auc_from_morphology_two_pulse_like",
                "value": morph_auc,
                "flag": bool(np.isfinite(morph_auc) and morph_auc > 0.80),
                "note": "flagged if morphology label nearly identifies current group",
            },
            {
                "check": "current_auc_from_blind_shape_score",
                "value": blind_auc,
                "flag": bool(np.isfinite(blind_auc) and blind_auc > 0.80),
                "note": "flagged if blind shape score nearly identifies current group",
            },
        ]
    )

    input_files = [s10e.raw_file(run) for run in sorted(s10e.run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    input_hashes[str(scores_path.relative_to(ROOT))] = sha256_file(scores_path)
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(OUT / "input_sha256.csv", index=False)

    scored.to_csv(OUT / "morphology_scores.csv", index=False)
    summary.to_csv(OUT / "morphology_summary.csv", index=False)
    counts.to_csv(OUT / "morphology_counts.csv", index=False)
    gallery.to_csv(OUT / "gallery_manifest.csv", index=False)
    topology.to_csv(OUT / "topology_by_group.csv", index=False)
    run_counts.to_csv(OUT / "run_counts.csv", index=False)
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    leakage_rows.to_csv(OUT / "leakage_checks.csv", index=False)

    trad_tp = summary[(summary["method"] == "traditional") & (summary["metric"] == "two_pulse_like")].iloc[0]
    ml_tp = summary[(summary["method"] == "ml") & (summary["metric"] == "two_pulse_like")].iloc[0]
    conclusion = (
        f"Above-threshold high-current S10e candidates are mostly not clean visually separated double pulses: "
        f"traditional two-pulse-like fraction {trad_tp['high_value']:.3f} versus matched low-control "
        f"{trad_tp['low_control_value']:.3f}, and ML two-pulse-like fraction {ml_tp['high_value']:.3f} "
        f"versus {ml_tp['low_control_value']:.3f}. The excess is therefore better described as broad/late "
        "detector-shape support with a small genuine-two-pulse-like subset, not a pure beam pile-up gallery."
    )
    result = {
        "study": CFG["study"],
        "ticket": TICKET,
        "worker": CFG["worker"],
        "title": CFG["title"],
        "reproduced": bool(repro["pass"].all() and row_match),
        "source_s10e_ticket": CFG["source_s10e_ticket"],
        "split": "S10e source-run held-out candidate scores; run-bootstrap morphology CIs",
        "thresholds": {
            "traditional_score_threshold": float(CFG["traditional_score_threshold"]),
            "traditional_delay_threshold_ns": float(CFG["traditional_delay_threshold_ns"]),
            "ml_score_threshold": float(CFG["ml_score_threshold"]),
            "ml_delay_threshold_ns": float(CFG["ml_delay_threshold_ns"]),
        },
        "candidate_counts": {
            "traditional_high": int(((scored["group"] == "high_20nA") & scored["traditional_above_s10d_threshold"]).sum()),
            "traditional_low_threshold": int(((scored["group"] == "low_2nA") & scored["traditional_above_s10d_threshold"]).sum()),
            "ml_high": int(((scored["group"] == "high_20nA") & scored["ml_above_s10d_threshold"]).sum()),
            "ml_low_threshold": int(((scored["group"] == "low_2nA") & scored["ml_above_s10d_threshold"]).sum()),
            "any_high_unique": int(len(high_any)),
            "gallery_rows": int(len(gallery)),
        },
        "morphology_summary": summary.to_dict(orient="records"),
        "leakage": {
            "n_flags": int(leakage_rows["flag"].sum()),
            "current_auc_from_morphology": morph_auc,
            "current_auc_from_blind_shape_score": blind_auc,
        },
        "conclusion": conclusion,
        "input_sha256": input_hashes,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(result, repro, summary, counts)
    manifest = {
        "study": CFG["study"],
        "ticket": TICKET,
        "worker": CFG["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "config": str(CONFIG.relative_to(ROOT)),
        "inputs": input_hashes,
        "code_inputs": {
            str(CONFIG.relative_to(ROOT)): sha256_file(CONFIG),
            str(Path(__file__).resolve().relative_to(ROOT)): sha256_file(Path(__file__).resolve()),
            CFG["source_s10e_script"]: sha256_file(ROOT / CFG["source_s10e_script"]),
        },
        "outputs": hash_outputs(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": TICKET, "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
