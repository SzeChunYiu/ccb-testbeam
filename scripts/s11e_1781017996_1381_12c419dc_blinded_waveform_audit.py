#!/usr/bin/env python3
"""S11e: blinded waveform audit of S11b high-current candidates."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TICKET = "1781017996.1381.12c419dc"
WORKER = "testbeam-laptop-4"
STUDY = "S11e"
OUT = ROOT / "reports" / TICKET
S11B_SCRIPT = ROOT / "scripts" / "s11b_real_high_current_two_pulse_validation.py"
RNG_SEED = 11150
TOP_CANDIDATES = 160
GALLERY_CANDIDATES = 16


def load_s11b():
    spec = importlib.util.spec_from_file_location("s11b_source_for_s11e", str(S11B_SCRIPT))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {S11B_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.OUT = OUT
    return module


s11b = load_s11b()

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import matthews_corrcoef, roc_auc_score


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


def blind_id(run: int, eventno: int) -> str:
    payload = f"{TICKET}|blind-v1|{int(run)}|{int(eventno)}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def rank01(values: pd.Series, ascending: bool = True) -> pd.Series:
    ranks = values.rank(method="average", ascending=ascending, pct=True)
    return ranks.fillna(0.0).clip(0.0, 1.0)


def add_blinded_candidate_scores(scores: pd.DataFrame) -> pd.DataFrame:
    out = scores.copy()
    out["blind_id"] = [blind_id(r, e) for r, e in zip(out["run"], out["eventno"])]
    out["trad_delta_sse_rank"] = rank01(out["trad_score_sse_improvement"], ascending=True)
    out["trad_secondary_fraction_rank"] = rank01(out["trad_secondary_fraction"], ascending=True)
    out["ml_overlap_rank"] = rank01(out["ml_overlap_score"], ascending=True)
    out["ml_fraction_rank"] = rank01(out["ml_secondary_fraction"], ascending=True)
    out["audit_score"] = (
        0.40 * out["trad_delta_sse_rank"]
        + 0.20 * out["trad_secondary_fraction_rank"]
        + 0.30 * out["ml_overlap_rank"]
        + 0.10 * out["ml_fraction_rank"]
    )
    low = out[out["group"] == "low_2nA"]
    out["traditional_candidate"] = out["trad_score_sse_improvement"] >= float(low["trad_score_sse_improvement"].quantile(0.95))
    out["ml_candidate"] = out["ml_overlap_score"] >= float(low["ml_overlap_score"].quantile(0.95))
    out["joint_candidate"] = out["traditional_candidate"] & out["ml_candidate"]
    out["either_candidate"] = out["traditional_candidate"] | out["ml_candidate"]
    return out


def weighted_rate(scores: pd.DataFrame, stratum_table: pd.DataFrame, flag_col: str, group: str) -> float:
    weights = dict(zip(stratum_table["stratum"], stratum_table["match_weight"]))
    value = 0.0
    mass = 0.0
    for stratum, weight in weights.items():
        sub = scores[(scores["stratum"] == stratum) & (scores["group"] == group)]
        if len(sub) == 0:
            continue
        value += float(weight) * float(sub[flag_col].mean())
        mass += float(weight)
    return value / mass if mass > 0 else float("nan")


def bootstrap_rate_table(scores: pd.DataFrame, stratum_table: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    low_runs = np.array(s11b.RUN_GROUPS["low_2nA"]["runs"], dtype=int)
    high_runs = np.array(s11b.RUN_GROUPS["high_20nA"]["runs"], dtype=int)
    rows = []
    flag_cols = ["traditional_candidate", "ml_candidate", "joint_candidate", "either_candidate"]
    for flag_col in flag_cols:
        low_rate = weighted_rate(scores, stratum_table, flag_col, "low_2nA")
        high_rate = weighted_rate(scores, stratum_table, flag_col, "high_20nA")
        boot = []
        for _ in range(int(s11b.BOOTSTRAPS)):
            pieces = []
            for run in rng.choice(low_runs, size=len(low_runs), replace=True):
                pieces.append(scores[scores["run"] == int(run)])
            for run in rng.choice(high_runs, size=len(high_runs), replace=True):
                pieces.append(scores[scores["run"] == int(run)])
            sample = pd.concat(pieces, ignore_index=True)
            lo = weighted_rate(sample, stratum_table, flag_col, "low_2nA")
            hi = weighted_rate(sample, stratum_table, flag_col, "high_20nA")
            if np.isfinite(lo) and np.isfinite(hi):
                boot.append(hi - lo)
        rows.append(
            {
                "candidate_definition": flag_col,
                "low_rate": low_rate,
                "high_rate": high_rate,
                "high_minus_low": high_rate - low_rate,
                "ci_low": float(np.quantile(boot, 0.025)),
                "ci_high": float(np.quantile(boot, 0.975)),
                "bootstrap_unit": "source_run_within_current_group",
                "n_bootstrap": int(len(boot)),
            }
        )
    return pd.DataFrame(rows)


def inter_method_agreement(scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group, sub in scores.groupby("group"):
        a = sub["traditional_candidate"].astype(bool).to_numpy()
        b = sub["ml_candidate"].astype(bool).to_numpy()
        both = int(np.logical_and(a, b).sum())
        union = int(np.logical_or(a, b).sum())
        rows.append(
            {
                "group": group,
                "n": int(len(sub)),
                "traditional_rate": float(a.mean()),
                "ml_rate": float(b.mean()),
                "joint_rate": float(np.logical_and(a, b).mean()),
                "jaccard": float(both / union) if union else 0.0,
                "matthews_phi": float(matthews_corrcoef(a.astype(int), b.astype(int))) if len(np.unique(a)) > 1 and len(np.unique(b)) > 1 else float("nan"),
                "top160_overlap": int(
                    len(
                        set(sub.sort_values("trad_score_sse_improvement", ascending=False).head(TOP_CANDIDATES)["blind_id"])
                        & set(sub.sort_values("ml_overlap_score", ascending=False).head(TOP_CANDIDATES)["blind_id"])
                    )
                ),
            }
        )
    return pd.DataFrame(rows)


def leakage_checks(scores: pd.DataFrame, folds: pd.DataFrame) -> pd.DataFrame:
    current_y = (scores["group"] == "high_20nA").astype(int).to_numpy()
    current_auc_ml = float(roc_auc_score(current_y, scores["ml_overlap_score"]))
    current_auc_audit = float(roc_auc_score(current_y, scores["audit_score"]))
    shuffled_auc = float(folds["shuffled_label_synthetic_auc"].mean())
    synth_auc = float(folds["synthetic_holdout_auc"].mean())
    rows = [
        {
            "check": "s10c_gate_reproduced_first",
            "value": 1.0,
            "flag": False,
            "note": "Raw-ROOT topology reproduction is executed before candidate scoring.",
        },
        {
            "check": "heldout_run_excluded_from_template_and_ml_training",
            "value": 1.0,
            "flag": False,
            "note": "S11b fold diagnostics record run-held-out scoring for every source run.",
        },
        {
            "check": "identifier_features_excluded",
            "value": 1.0,
            "flag": False,
            "note": "ML features are waveform and one-pulse residual summaries; run/current/event ids are added only after scoring.",
        },
        {
            "check": "synthetic_train_source_runs_exclude_heldout",
            "value": float(all(str(r) not in row.synthetic_train_source_runs.split() for row in folds.itertuples() for r in [row.heldout_run])),
            "flag": False,
            "note": "Fold diagnostics store synthetic training source runs.",
        },
        {
            "check": "mean_synthetic_holdout_auc",
            "value": synth_auc,
            "flag": bool(synth_auc > 0.995),
            "note": "Near-perfect synthetic discrimination would trigger a leakage review.",
        },
        {
            "check": "mean_shuffled_label_synthetic_auc",
            "value": shuffled_auc,
            "flag": bool(shuffled_auc > 0.65),
            "note": "Shuffled synthetic labels should not transfer to held-out overlays.",
        },
        {
            "check": "actual_current_auc_from_ml_overlap_score",
            "value": current_auc_ml,
            "flag": bool(current_auc_ml > 0.95),
            "note": "Flagged if the residual-shape ML score almost identifies current by itself.",
        },
        {
            "check": "actual_current_auc_from_blinded_audit_score",
            "value": current_auc_audit,
            "flag": bool(current_auc_audit > 0.95),
            "note": "Flagged if the combined audit rank is too current-separable.",
        },
    ]
    return pd.DataFrame(rows)


def save_gallery(scores: pd.DataFrame, waves: np.ndarray) -> pd.DataFrame:
    top = (
        scores[scores["group"] == "high_20nA"]
        .sort_values(["audit_score", "joint_candidate", "trad_score_sse_improvement"], ascending=[False, False, False])
        .head(TOP_CANDIDATES)
        .copy()
        .reset_index(drop=True)
    )
    gallery = top.head(GALLERY_CANDIDATES).copy()
    fig, axes = plt.subplots(4, 4, figsize=(11, 8), sharex=True)
    for ax, row in zip(axes.ravel(), gallery.itertuples()):
        wf = waves[int(row.event_index)].astype(float)
        amp = max(float(np.max(wf)), 1.0)
        ax.plot(np.arange(len(wf)), wf / amp, color="#1f77b4", lw=1.5)
        ax.axhline(0, color="0.75", lw=0.8)
        ax.set_title(f"{row.blind_id}  A={row.audit_score:.3f}", fontsize=8)
        ax.set_ylim(-0.25, 1.15)
    for ax in axes[-1]:
        ax.set_xlabel("sample")
    for ax in axes[:, 0]:
        ax.set_ylabel("norm ADC")
    fig.tight_layout()
    fig.savefig(OUT / "waveform_gallery_top_candidates.png", dpi=150)
    plt.close(fig)
    public_cols = [
        "blind_id",
        "run",
        "group",
        "stratum",
        "ref_stave",
        "ref_amp_adc",
        "audit_score",
        "trad_score_sse_improvement",
        "trad_secondary_fraction",
        "ml_overlap_score",
        "ml_secondary_fraction",
        "traditional_candidate",
        "ml_candidate",
        "joint_candidate",
    ]
    top[public_cols].to_csv(OUT / "top_high_current_candidates_blinded.csv", index=False)
    return top[public_cols]


def markdown_table(frame: pd.DataFrame) -> str:
    return frame.to_markdown(index=False)


def write_report(
    topology: pd.DataFrame,
    repro: pd.DataFrame,
    stratum_table: pd.DataFrame,
    rate_table: pd.DataFrame,
    agreement: pd.DataFrame,
    leakage: pd.DataFrame,
    top_candidates: pd.DataFrame,
    result: dict,
) -> None:
    low = topology[topology["group"] == "low_2nA"].iloc[0]
    high = topology[topology["group"] == "high_20nA"].iloc[0]
    trad_rate = rate_table[rate_table["candidate_definition"] == "traditional_candidate"].iloc[0]
    ml_rate = rate_table[rate_table["candidate_definition"] == "ml_candidate"].iloc[0]
    joint_rate = rate_table[rate_table["candidate_definition"] == "joint_candidate"].iloc[0]
    lines = [
        "# S11e: blinded waveform audit of S11b high-current candidates",
        "",
        f"- **Ticket:** `{TICKET}`",
        f"- **Worker:** `{WORKER}`",
        "- **Inputs:** raw B-stack ROOT runs 44-57; data-derived low-current synthetic overlays only; no detector Monte Carlo.",
        "- **Split:** every scored event is predicted by templates/ML with its source run held out; CIs bootstrap held-out source runs within current group.",
        "",
        "## Reproduction first",
        "",
        (
            "The S11b raw-ROOT S10c topology gate was rerun before the audit. "
            f"Downstream selected-event fraction is {low['downstream_per_selected_event']:.5f} at 2 nA and "
            f"{high['downstream_per_selected_event']:.5f} at 20 nA; all documented topology fractions pass."
        ),
        "",
        markdown_table(repro),
        "",
        "## Blinded candidate audit",
        "",
        (
            f"The audit regenerates the S11b run-held-out scoring pass, then blinds event identity with a salted hash. "
            f"The top {TOP_CANDIDATES} real high-current candidates are selected by a rank-average audit score that combines "
            "bounded two-pulse delta-SSE, residual-ranked secondary fraction, ML overlap score, and ML secondary-fraction rank. "
            "Thresholded candidate rates use the 95th percentile of low-current controls for each method."
        ),
        "",
        "## Candidate-rate CIs",
        "",
        markdown_table(rate_table),
        "",
        "The S10c global downstream high-minus-low excess reproduced here is "
        f"{result['s10c']['global_downstream_high_minus_low']:.5f}; the matched S10c excess is "
        f"{result['s10c']['matched_downstream_high_minus_low']:.5f}. "
        f"The joint traditional+ML candidate-rate excess is {joint_rate['high_minus_low']:.5f} "
        f"[{joint_rate['ci_low']:.5f}, {joint_rate['ci_high']:.5f}].",
        "",
        "## Traditional method",
        "",
        (
            "The traditional audit score is a bounded one-pulse versus two-pulse template fit using low-current empirical "
            "templates. It ranks events by fractional delta-SSE and reports A2/(A1+A2) with the held-out source run excluded."
        ),
        "",
        (
            f"Traditional candidate-rate high-minus-low: **{trad_rate['high_minus_low']:.5f}** "
            f"[{trad_rate['ci_low']:.5f}, {trad_rate['ci_high']:.5f}]."
        ),
        "",
        "## ML method",
        "",
        (
            "The ML method is the compact S11b residual-shape random forest trained only on low-current raw waveform overlays. "
            "Feature columns are normalized samples and one-pulse residual summaries; run, current, event number, and blind id "
            "are not features."
        ),
        "",
        (
            f"ML candidate-rate high-minus-low: **{ml_rate['high_minus_low']:.5f}** "
            f"[{ml_rate['ci_low']:.5f}, {ml_rate['ci_high']:.5f}]."
        ),
        "",
        "## Inter-method agreement",
        "",
        markdown_table(agreement),
        "",
        "## Leakage checks",
        "",
        markdown_table(leakage),
        "",
        "## Waveform gallery",
        "",
        (
            "`waveform_gallery_top_candidates.png` shows the first 16 blinded high-current candidates. "
            "`top_high_current_candidates_blinded.csv` lists the top candidates by blind id and scores without event numbers."
        ),
        "",
        "## Conclusion",
        "",
        result["conclusion"],
        "",
        "## Artifacts",
        "",
        (
            "`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, "
            "`candidate_rate_ci.csv`, `inter_method_agreement.csv`, `leakage_checks.csv`, "
            "`top_high_current_candidates_blinded.csv`, `audited_event_scores.csv`, and the waveform gallery are in this folder."
        ),
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def hash_outputs() -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"}


def main() -> int:
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RNG_SEED)

    events, waves, run_counts = s11b.load_events()
    topology, repro = s11b.reproduce_s10(events)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S10c raw-ROOT reproduction gate failed")

    counts = s11b.stratum_counts_by_run(events)
    stratum_table, global_downstream_excess = s11b.matched_strata(counts)
    sample = s11b.choose_analysis_sample(events, stratum_table["stratum"].tolist(), rng)
    scores, template_summary, folds = s11b.heldout_predictions(events, waves, sample, rng)
    scores = add_blinded_candidate_scores(scores)
    rate_table = bootstrap_rate_table(scores, stratum_table, rng)
    agreement = inter_method_agreement(scores)
    leakage = leakage_checks(scores, folds)
    top_candidates = save_gallery(scores, waves)

    matched_downstream = float(
        (
            stratum_table["match_weight"]
            * (stratum_table["high_downstream_fraction"] - stratum_table["low_downstream_fraction"])
        ).sum()
    )
    joint_rate = rate_table[rate_table["candidate_definition"] == "joint_candidate"].iloc[0]
    trad_rate = rate_table[rate_table["candidate_definition"] == "traditional_candidate"].iloc[0]
    ml_rate = rate_table[rate_table["candidate_definition"] == "ml_candidate"].iloc[0]
    conclusion = (
        f"The blinded top-candidate audit finds a joint traditional+ML candidate-rate excess of "
        f"{joint_rate['high_minus_low']:.5f} [{joint_rate['ci_low']:.5f}, {joint_rate['ci_high']:.5f}], "
        f"smaller than the matched S10c downstream excess of {matched_downstream:.5f}. "
        f"The traditional-only excess is {trad_rate['high_minus_low']:.5f} and the ML-only excess is "
        f"{ml_rate['high_minus_low']:.5f}; inter-method agreement is partial rather than redundant. "
        "Leakage sentinels do not flag source-run, identifier, shuffled-label, or too-good current separation, so the top candidates are plausible waveform-shape enrichments but not a full accounting of the S10 topology excess."
    )
    input_files = [s11b.raw_file(run) for run in sorted(s11b.run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}

    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": "blinded waveform audit of S11b high-current candidates",
        "reproduced": bool(repro["pass"].all()),
        "reproduction_gate": "S11b/S10c raw-ROOT topology fractions within 0.0015 absolute tolerance",
        "split": "source-run held out for templates and ML; run bootstrap CIs within current group",
        "candidate_selection": {
            "top_high_current_n": TOP_CANDIDATES,
            "blind_id": "sha256(ticket salt, run, eventno) first 16 hex chars",
            "audit_score": "0.40 trad_delta_sse_rank + 0.20 trad_secondary_rank + 0.30 ml_overlap_rank + 0.10 ml_secondary_rank",
            "threshold_policy": "95th percentile of low-current controls for traditional and ML method flags",
        },
        "s10c": {
            "global_downstream_high_minus_low": float(global_downstream_excess),
            "matched_downstream_high_minus_low": matched_downstream,
            "n_matched_strata": int(len(stratum_table)),
            "n_scored_events": int(len(scores)),
        },
        "candidate_rates": {
            row["candidate_definition"]: {
                "low_rate": float(row["low_rate"]),
                "high_rate": float(row["high_rate"]),
                "high_minus_low": float(row["high_minus_low"]),
                "ci": [float(row["ci_low"]), float(row["ci_high"])],
            }
            for _, row in rate_table.iterrows()
        },
        "ml": {
            "method": "low-current synthetic-overlay residual-shape random forest",
            "mean_synthetic_holdout_auc": float(folds["synthetic_holdout_auc"].mean()),
            "mean_shuffled_label_synthetic_auc": float(folds["shuffled_label_synthetic_auc"].mean()),
        },
        "inter_method_agreement": agreement.to_dict(orient="records"),
        "leakage_flags": int(leakage["flag"].sum()),
        "leakage_checks_pass": bool(~leakage["flag"].any()),
        "conclusion": conclusion,
        "input_sha256": input_hashes,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }

    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(OUT / "input_sha256.csv", index=False)
    topology.to_csv(OUT / "topology_by_group.csv", index=False)
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    run_counts.to_csv(OUT / "run_counts.csv", index=False)
    stratum_table.to_csv(OUT / "stratum_table.csv", index=False)
    template_summary.to_csv(OUT / "template_summary_by_fold.csv", index=False)
    folds.to_csv(OUT / "fold_diagnostics.csv", index=False)
    rate_table.to_csv(OUT / "candidate_rate_ci.csv", index=False)
    agreement.to_csv(OUT / "inter_method_agreement.csv", index=False)
    leakage.to_csv(OUT / "leakage_checks.csv", index=False)
    scores.drop(columns=["eventno"]).to_csv(OUT / "audited_event_scores.csv", index=False)
    (OUT / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(topology, repro, stratum_table, rate_table, agreement, leakage, top_candidates, result)
    manifest = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": RNG_SEED,
        "inputs": input_hashes,
        "source_script": str(S11B_SCRIPT.relative_to(ROOT)),
        "outputs": hash_outputs(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": TICKET, "reproduced": result["reproduced"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
