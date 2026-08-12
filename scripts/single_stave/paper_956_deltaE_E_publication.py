#!/usr/bin/env python3
"""Publication producer for issue #956 / PAPER-A05 corrected ΔE–E.

Implements the supervisor contract (#618):
  DATA:     ΔE = A(B2);  E = A(B4)+A(B6)+A(B8)  [ADC amplitude proxies]
  MC 4-readout: ΔE = Edep(B2); E = Edep(B4)+Edep(B6)+Edep(B8)
  MC full:      ΔE = Edep(B2); E = sum(all downstream physical B layers)

Outputs land under ``reports/paper_956_deltaE_E_<stamp>/`` with full provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.single_stave import _deltaE_E_core as core
from scripts.single_stave.deltaE_E_data_bridge import build_event_table

# Verified analysis run groups (S03e / paper configs).
SAMPLE_I_RUNS = set(range(44, 58))   # 44-57 analysis
SAMPLE_II_RUNS = set(list(range(58, 64)) + [65])

SAT_ADC = 7000.0
S00_CUT_ADC = 1000.0
DEFAULT_DATA_THRESHOLDS = (500.0, 750.0, 1000.0, 1500.0)
DEFAULT_STOP_THRESHOLDS = (0.05, 0.15, 0.30)
COINC_NS = 15.0
B_ARM = 1
NB_LAYERS = 8
READOUT_PRIMARY = (1, 3, 5, 7)   # B2,B4,B6,B8 = LayerID 1,3,5,7 (#869)
READOUT_ALT = (0, 2, 4, 6)

PDG_NAME = {2212: "p", 1000010020: "d", 1000010030: "t", 1000020040: "alpha"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def species_label(pdg: int) -> str:
    return PDG_NAME.get(int(pdg), "other")


def is_charged(pdg: int) -> bool:
    pdg = int(pdg)
    a = abs(pdg)
    if a > 1_000_000_000:
        return ((a // 10_000) % 1000) > 0
    return a in (2212, 11, 13, 211, 321)


def wmedian(x: np.ndarray, w: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    w = np.asarray(w, dtype=float)
    if x.size == 0:
        return float("nan")
    sw = w.sum()
    if not np.isfinite(sw) or sw <= 0:
        return float(np.median(x))
    o = np.argsort(x)
    xs, ws = x[o], w[o]
    cw = np.cumsum(ws) / sw
    return float(np.interp(0.5, cw, xs))


def wcorr(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    w = np.asarray(w, dtype=float)
    if x.size < 2:
        return float("nan")
    sw = w.sum()
    if sw <= 0:
        return float(np.corrcoef(x, y)[0, 1])
    mx = np.sum(w * x) / sw
    my = np.sum(w * y) / sw
    cx, cy = x - mx, y - my
    cov = np.sum(w * cx * cy) / sw
    vx = np.sum(w * cx * cx) / sw
    vy = np.sum(w * cy * cy) / sw
    den = np.sqrt(vx * vy)
    return float(cov / den) if den > 0 else float("nan")


def run_block_bootstrap(
    df: pd.DataFrame,
    stat_fn,
    *,
    n_boot: int = 200,
    seed: int,
) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    runs = df["run_id"].unique()
    if len(runs) < 2:
        point = stat_fn(df)
        return {"point": point, "p16": point, "p84": point, "n_runs": int(len(runs))}
    stats = []
    for _ in range(n_boot):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        sub = pd.concat([df[df["run_id"] == r] for r in chosen], ignore_index=True)
        stats.append(stat_fn(sub))
    arr = np.asarray(stats, dtype=float)
    return {
        "point": float(stat_fn(df)),
        "p16": float(np.percentile(arr, 16)),
        "p84": float(np.percentile(arr, 84)),
        "n_runs": int(len(runs)),
        "n_bootstrap": n_boot,
    }


def build_data_wide_table(
    pulse_path: Path,
    *,
    source_file_id: str,
    analysis_only: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    pulses = pd.read_csv(pulse_path)
    if analysis_only:
        pulses = pulses[pulses["group"].str.endswith("_analysis")].copy()
    pulses["sample_token"] = np.where(
        pulses["group"].str.startswith("sample_i_"), "I",
        np.where(pulses["group"].str.startswith("sample_ii_"), "II", ""),
    )
    wide, bridge_meta = build_event_table(
        pulses,
        source_file_id=source_file_id,
        threshold_adc=S00_CUT_ADC,
        amplitude_column="amplitude_adc",
        amplitude_convention="net",
    )
    wide = wide.rename(columns={"run": "run_id", "evt": "event_id"})
    for layer in core.DATA_LAYERS:
        col = f"amp_{layer}"
        wide[f"saturation_{layer}"] = wide[col] >= SAT_ADC
        wide[f"threshold_pass_{layer}"] = wide[col] > S00_CUT_ADC
    wide["sample"] = wide["run_id"].map(
        lambda r: "I" if int(r) in SAMPLE_I_RUNS
        else ("II" if int(r) in SAMPLE_II_RUNS else "")
    )
    wide["trigger_definition"] = np.where(
        wide["sample"] == "I", "hardware_coincidence_analysis",
        np.where(wide["sample"] == "II", "hardware_B_only_analysis", "other"),
    )
    # Event anchor: any selected B-stack pulse (issue #1040).
    anchor = (
        pulses.groupby(["run", "evt"], dropna=False)
        .agg(sample_token=("sample_token", "first"))
        .reset_index()
        .rename(columns={"run": "run_id", "evt": "event_id"})
    )
    wide = wide.merge(anchor, on=["run_id", "event_id"], how="inner")
    wide["sample"] = wide["sample_token"].replace("", np.nan)
    wide = wide.drop(columns=["sample_token"], errors="ignore")
    wide = wide[wide["sample"].isin(["I", "II"])].copy()
    meta = {
        "bridge": bridge_meta,
        "missing_layer_policy": core.MISSING_LAYER_POLICY if hasattr(core, "MISSING_LAYER_POLICY") else "ZERO_AFTER_KEY_VALIDATION",
        "saturation_threshold_adc": SAT_ADC,
        "s00_selection_cut_adc": S00_CUT_ADC,
        "composite_key": list(core.KEY_COLS),
        "n_events": int(len(wide)),
        "runs_sample_I": sorted(int(r) for r in wide.loc[wide["sample"] == "I", "run_id"].unique()),
        "runs_sample_II": sorted(int(r) for r in wide.loc[wide["sample"] == "II", "run_id"].unique()),
    }
    return wide, meta


def _layer_edep_per_event(
    arm: Any, layer: Any, edep: Any, weights: Any, event_count: int
) -> dict[int, np.ndarray]:
    import awkward as ak

    out: dict[int, np.ndarray] = {}
    for lid in range(NB_LAYERS):
        mask = (arm == B_ARM) & (layer == lid)
        vals = ak.to_numpy(ak.sum(edep[mask], axis=1)).astype(float)
        if vals.shape != (event_count,):
            raise RuntimeError(f"layer {lid} edep shape mismatch")
        out[lid] = vals
    return out


def build_mc_wide_table(
    mc_path: Path,
    *,
    source_file_id: str,
    coinc_ns: float = COINC_NS,
    entry_stop: int | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    import awkward as ak
    import uproot

    f = uproot.open(mc_path)
    tree = f["hibeam"]
    branches = [
        "Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_PDG",
        "Sci_bar_EDep", "Sci_bar_Time", "PrimaryWeight",
    ]
    arrays = tree.arrays(branches, entry_stop=entry_stop, library="ak")
    n_evt = len(arrays["PrimaryWeight"])
    w_evt = ak.to_numpy(ak.firsts(arrays["PrimaryWeight"], axis=1)).astype(float)
    if not np.all(np.isfinite(w_evt)) or np.any(w_evt < 0) or w_evt.sum() <= 0:
        raise RuntimeError("invalid PrimaryWeight vector")

    arm = arrays["Sci_bar_LayerID1"]
    lay = arrays["Sci_bar_LayerID"]
    ed = arrays["Sci_bar_EDep"]
    tm = arrays["Sci_bar_Time"]
    pdg = arrays["Sci_bar_PDG"]

    per_layer = _layer_edep_per_event(arm, lay, ed, w_evt, n_evt)

    rows: list[dict[str, Any]] = []
    n_enterB = n_coinc = 0
    for i in range(n_evt):
        l = ak.to_numpy(lay[i])
        l1 = ak.to_numpy(arm[i])
        pd_i = ak.to_numpy(pdg[i])
        ed_i = ak.to_numpy(ed[i])
        t_i = ak.to_numpy(tm[i])
        if l.size == 0:
            continue
        charged = np.array([is_charged(p) for p in pd_i], dtype=bool)
        isB = l1 == B_ARM
        isA = l1 == 2
        firstB = isB & (l == 0) & charged
        firstA = isA & (l == 0) & charged
        enterB = bool(firstB.any())
        enterA = bool(firstA.any())
        tB = float(t_i[firstB].min()) if enterB else float("nan")
        tA = float(t_i[firstA].min()) if enterA else float("nan")
        if enterB:
            n_enterB += 1
        coinc = enterB and enterA and abs(tA - tB) < coinc_ns
        if coinc:
            n_coinc += 1
        belongs: list[str] = []
        if enterB:
            belongs.append("II")
        if coinc:
            belongs.append("I")
        if not belongs:
            continue

        # Species: largest B2 (layer 0) deposit PDG.
        b2_mask = isB & charged & (l == 0)
        b2_by_pdg: dict[int, float] = {}
        for li, ei, pi in zip(l[b2_mask], ed_i[b2_mask], pd_i[b2_mask]):
            b2_by_pdg[int(pi)] = b2_by_pdg.get(int(pi), 0.0) + float(ei)
        primary_pdg = max(b2_by_pdg, key=b2_by_pdg.get) if b2_by_pdg else int(pd_i[charged][0])

        edeps = {lid: float(per_layer[lid][i]) for lid in range(NB_LAYERS)}
        # Canonical readout-channel columns (#869): LayerID 1,3,5,7 -> B2,B4,B6,B8.
        edep_cols = {f"edep_B{lid}": edeps.get(lid, 0.0) for lid in range(NB_LAYERS)}
        edep_cols["edep_B2"] = edeps.get(READOUT_PRIMARY[0], 0.0)
        edep_cols["edep_B4"] = edeps.get(READOUT_PRIMARY[1], 0.0)
        edep_cols["edep_B6"] = edeps.get(READOUT_PRIMARY[2], 0.0)
        edep_cols["edep_B8"] = edeps.get(READOUT_PRIMARY[3], 0.0)

        sample_token = ";".join(sorted(set(belongs), key=lambda s: (s != "I", s)))
        edeps = {lid: float(per_layer[lid][i]) for lid in range(NB_LAYERS)}
        # Canonical readout-channel columns (#869): LayerID 1,3,5,7 -> B2,B4,B6,B8.
        edep_cols = {f"edep_B{lid}": edeps.get(lid, 0.0) for lid in range(NB_LAYERS)}
        edep_cols["edep_B2"] = edeps.get(READOUT_PRIMARY[0], 0.0)
        edep_cols["edep_B4"] = edeps.get(READOUT_PRIMARY[1], 0.0)
        edep_cols["edep_B6"] = edeps.get(READOUT_PRIMARY[2], 0.0)
        edep_cols["edep_B8"] = edeps.get(READOUT_PRIMARY[3], 0.0)

        row = {
            "source_file_id": source_file_id,
            "run_id": 0,
            "event_id": i,
            "sample": sample_token,
            "trigger_definition": "MC_TRIGGER_PROXY",
            "PrimaryWeight": float(w_evt[i]),
            "truth_pdg": int(primary_pdg),
            "truth_species": species_label(primary_pdg),
            **edep_cols,
        }
        rows.append(row)

    mc = pd.DataFrame(rows)
    meta = {
        "mc_trigger_proxy": True,
        "coincidence_window_ns": coinc_ns,
        "readout_mapping_primary": list(READOUT_PRIMARY),
        "readout_mapping_alt": list(READOUT_ALT),
        "n_mc_source_events": int(n_evt),
        "n_enter_B": int(n_enterB),
        "n_coincidence_sample_I": int(n_coinc),
        "n_rows": int(len(mc)),
        "weight_diagnostics": core.mc_weight_diagnostics(mc["PrimaryWeight"].to_numpy()),
    }
    return mc, meta


def _hexbin_panel(
    ax: plt.Axes,
    x: np.ndarray,
    y: np.ndarray,
    w: np.ndarray | None,
    *,
    xlabel: str,
    ylabel: str,
    title: str,
    cmap: str = "viridis",
    gridsize: int = 45,
    xlim: tuple[float, float] | None = None,
    ylim: tuple[float, float] | None = None,
    vline_sat: float | None = None,
) -> None:
    if w is None:
        hb = ax.hexbin(x, y, gridsize=gridsize, mincnt=1, bins="log", cmap=cmap)
    else:
        hb = ax.hexbin(
            x, y, C=w, reduce_C_function=np.sum, gridsize=gridsize,
            mincnt=1, bins="log", cmap=cmap,
        )
    plt.colorbar(hb, ax=ax, label="log count" if w is None else "log Σw")
    if vline_sat is not None:
        ax.axvline(vline_sat, color="darkorange", ls="--", lw=1.2)
        ax.text(vline_sat, ax.get_ylim()[1] * 0.95, " B2 sat", color="darkorange", fontsize=8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)


def summarize_sample(
    df: pd.DataFrame,
    *,
    delta_col: str,
    e_col: str,
    weight_col: str | None,
    sample: str,
    is_data: bool,
    seed: int,
) -> dict[str, Any]:
    sub = core.select_sample(df, sample).copy()
    de = sub[delta_col].to_numpy(dtype=float)
    ee = sub[e_col].to_numpy(dtype=float)
    w = np.ones(len(sub)) if weight_col is None else sub[weight_col].to_numpy(dtype=float)
    mask = np.isfinite(de) & np.isfinite(ee) & (de + ee > 0)
    de, ee, w = de[mask], ee[mask], w[mask]
    sub = sub.iloc[np.flatnonzero(mask)].copy()

    def _corr(frame: pd.DataFrame) -> float:
        return wcorr(
            frame[delta_col].to_numpy(dtype=float),
            frame[e_col].to_numpy(dtype=float),
            np.ones(len(frame)) if weight_col is None else frame[weight_col].to_numpy(dtype=float),
        )

    out: dict[str, Any] = {
        "sample": sample,
        "side": "DATA" if is_data else "MC",
        "n_events": int(len(sub)),
        "deltaE_median": wmedian(de, w),
        "E_median": wmedian(ee, w),
        "deltaE_p16": float(np.percentile(de, 16)) if de.size else None,
        "deltaE_p84": float(np.percentile(de, 84)) if de.size else None,
        "E_p16": float(np.percentile(ee, 16)) if ee.size else None,
        "E_p84": float(np.percentile(ee, 84)) if ee.size else None,
        "pearson_r": wcorr(de, ee, w),
        "missing_channel_policy": "downstream absent layers filled with 0 after composite-key validation",
    }
    if is_data:
        sat = sub["saturation_B2"].to_numpy(dtype=bool) if "saturation_B2" in sub else de >= SAT_ADC
        out["frac_B2_saturated"] = float(sat.mean()) if sat.size else None
        out["n_B2_saturated"] = int(sat.sum())
        out["corr_bootstrap"] = run_block_bootstrap(sub, _corr, seed=seed)
        out["corr_no_sat"] = wcorr(de[~sat], ee[~sat], w[~sat]) if (~sat).sum() > 10 else None
    else:
        out["weight_diagnostics"] = core.mc_weight_diagnostics(w)
    return out


def make_publication_figures(
    data: pd.DataFrame,
    mc: pd.DataFrame,
    out: Path,
    *,
    seed: int,
) -> list[dict[str, str]]:
    figdir = out / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, str]] = []

    # Shared data axis ranges (Sample I and II identical).
    dsub = data[data["sample"].isin(["I", "II"])].copy()
    dsub = core.derive_data_columns(dsub)
    xmax = float(np.percentile(dsub["E_data_adc"], 99.5)) * 1.05
    ymax = float(np.percentile(dsub["deltaE_data_adc"], 99.5)) * 1.05
    xlim = (0, max(xmax, 1000))
    ylim = (0, max(ymax, 1000))

    # Figure 7 — DATA ΔE–E per sample.
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), sharex=True, sharey=True)
    for ax, sample, label in zip(axes, ("I", "II"), ("Sample I", "Sample II")):
        sub = core.select_sample(dsub, sample)
        _hexbin_panel(
            ax,
            sub["E_data_adc"].to_numpy(),
            sub["deltaE_data_adc"].to_numpy(),
            None,
            xlabel="E = A(B4)+A(B6)+A(B8) [ADC]",
            ylabel="ΔE = A(B2) [ADC]",
            title=f"DATA {label} — amplitude ΔE–E\n(not calibrated energy)",
            xlim=xlim,
            ylim=ylim,
            vline_sat=SAT_ADC,
        )
    fig.suptitle("Figure 7: DATA amplitude ΔE–E (issue #618)", fontsize=12, fontweight="bold")
    fig.tight_layout()
    p7 = figdir / "fig07_data_deltaE_E_per_sample"
    fig.savefig(p7.with_suffix(".png"), dpi=200)
    fig.savefig(p7.with_suffix(".pdf"))
    plt.close(fig)
    records.append({"figure_id": "FIG-07", "path": str(p7.with_suffix(".png"))})

    # Figure 8 — MC 4-readout vs full downstream.
    mc = core.prepare_mc_side(mc)
    emax = float(np.percentile(mc["E_mc_full_mev"], 99.5)) * 1.05
    demax = float(np.percentile(mc["deltaE_mc_mev"], 99.5)) * 1.05
    mxlim = (0, max(emax, 1))
    mylim = (0, max(demax, 1))

    for sample, slabel in (("I", "Sample I"), ("II", "Sample II")):
        sub = core.select_sample(mc, sample)
        fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), sharex=True, sharey=True)
        for ax, ecol, etitle in zip(
            axes,
            ("E_mc_4layer_mev", "E_mc_full_mev"),
            ("data-matched B4+B6+B8", "full downstream B layers"),
        ):
            _hexbin_panel(
                ax,
                sub[ecol].to_numpy(),
                sub["deltaE_mc_mev"].to_numpy(),
                sub["PrimaryWeight"].to_numpy(),
                xlabel=f"E = {etitle} [MeV]",
                ylabel="ΔE = Edep(B2) [MeV]",
                title=f"MC {slabel} — {etitle}\n(MC_TRIGGER_PROXY; weighted)",
                xlim=mxlim,
                ylim=mylim,
            )
        fig.suptitle(f"Figure 8: MC ΔE–E — {slabel}", fontsize=12, fontweight="bold")
        fig.tight_layout()
        p8 = figdir / f"fig08_mc_deltaE_E_{sample}"
        fig.savefig(p8.with_suffix(".png"), dpi=200)
        fig.savefig(p8.with_suffix(".pdf"))
        plt.close(fig)
        records.append({"figure_id": f"FIG-08-{sample}", "path": str(p8.with_suffix(".png"))})

    # Segmentation readout-phase nuisance (PAPER-A10 ablation).
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    for ax, layers, tag in zip(axes, (READOUT_PRIMARY, READOUT_ALT), ("1/3/5/7", "0/2/4/6")):
        de = mc[f"edep_B{layers[0]}"].to_numpy()
        ee = sum(mc[f"edep_B{layers[i]}"].to_numpy() for i in range(1, 4))
        w = mc["PrimaryWeight"].to_numpy()
        _hexbin_panel(
            ax, ee, de, w,
            xlabel="E downstream sum [MeV]",
            ylabel="ΔE upstream [MeV]",
            title=f"MC readout phase {tag}\n(all samples; weighted)",
        )
    fig.suptitle("Segmentation nuisance: readout-layer phase", fontsize=12, fontweight="bold")
    fig.tight_layout()
    pseg = figdir / "fig_segmentation_readout_phase"
    fig.savefig(pseg.with_suffix(".png"), dpi=200)
    fig.savefig(pseg.with_suffix(".pdf"))
    plt.close(fig)
    records.append({"figure_id": "FIG-SEG", "path": str(pseg.with_suffix(".png"))})

    # B2–B4 two-channel diagnostic (NOT ΔE–E).
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), sharex=True, sharey=True)
    for ax, sample, label in zip(axes, ("I", "II"), ("Sample I", "Sample II")):
        sub = core.select_sample(dsub, sample)
        sub = sub[(sub["amp_B2"] > 0) & (sub["amp_B4"] > 0)]
        _hexbin_panel(
            ax,
            sub["amp_B4"].to_numpy(),
            sub["amp_B2"].to_numpy(),
            None,
            xlabel="A(B4) [ADC]",
            ylabel="A(B2) [ADC]",
            title=f"{label}: B2–B4 diagnostic only\n(not ΔE–E)",
        )
    fig.suptitle("Two-channel B2–B4 correlation diagnostic (issue #618)", fontsize=12)
    fig.tight_layout()
    pb2b4 = figdir / "fig_b2_b4_two_channel_diagnostic"
    fig.savefig(pb2b4.with_suffix(".png"), dpi=200)
    fig.savefig(pb2b4.with_suffix(".pdf"))
    plt.close(fig)
    records.append({"figure_id": "FIG-B2B4", "path": str(pb2b4.with_suffix(".png"))})

    return records


def _write_table(df: pd.DataFrame, base: Path) -> Path:
    try:
        path = base.with_suffix(".parquet")
        df.to_parquet(path, index=False)
        return path
    except Exception:
        path = base.with_suffix(".csv.gz")
        df.to_csv(path, index=False, compression="gzip")
        return path


def write_tables_and_manifest(
    out: Path,
    *,
    data: pd.DataFrame,
    mc: pd.DataFrame,
    summaries: dict[str, Any],
    inputs: list[dict[str, Any]],
    args: argparse.Namespace,
) -> None:
    tabdir = out / "tables"
    tabdir.mkdir(parents=True, exist_ok=True)
    data_path = _write_table(data, out / "deltaE_E_events_data")
    mc_path = _write_table(mc, out / "deltaE_E_events_mc")
    with (out / "result.json").open("w", encoding="utf-8") as fh:
        json.dump(core._json_safe(summaries), fh, indent=2, sort_keys=True)
    with (tabdir / "sample_summary.json").open("w", encoding="utf-8") as fh:
        json.dump(core._json_safe(summaries.get("per_sample", {})), fh, indent=2, sort_keys=True)

    outputs = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            outputs.append({
                "path": str(p.relative_to(out)),
                "bytes": p.stat().st_size,
                "sha256": sha256_file(p),
            })
    manifest = {
        "producer": "scripts/single_stave/paper_956_deltaE_E_publication.py",
        "issue": "#956 / PAPER-A05",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "command": " ".join(sys.argv),
        "args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "inputs": inputs,
        "outputs": outputs,
        "schema": {
            "data_deltaE": "A(B2) ADC",
            "data_E": "A(B4)+A(B6)+A(B8) ADC",
            "mc_deltaE": "Edep(B2) MeV",
            "mc_E_4layer": "Edep(B4)+Edep(B6)+Edep(B8) MeV",
            "mc_E_full": "sum downstream physical B-layer Edep MeV",
            "composite_key": list(core.KEY_COLS),
        },
    }
    with (out / "manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(core._json_safe(manifest), fh, indent=2, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Publication ΔE–E producer (#956)")
    ap.add_argument("--pulse-table", type=Path, required=True)
    ap.add_argument("--mc-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--source-file-id", default=None)
    ap.add_argument("--mc-source-id", default=None)
    ap.add_argument("--coinc-ns", type=float, default=COINC_NS)
    ap.add_argument("--seed", type=int, default=20260812)
    ap.add_argument("--mc-entry-stop", type=int, default=0, help="0 = all MC events")
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    pulse_id = args.source_file_id or f"pulse_{sha256_file(args.pulse_table)[:12]}"
    mc_id = args.mc_source_id or args.mc_root.name

    inputs = [
        {
            "role": "data_pulse_table",
            "path": str(args.pulse_table.resolve()),
            "bytes": args.pulse_table.stat().st_size,
            "sha256": sha256_file(args.pulse_table),
        },
        {
            "role": "mc_root",
            "path": str(args.mc_root.resolve()),
            "bytes": args.mc_root.stat().st_size,
            "sha256": sha256_file(args.mc_root),
        },
    ]

    data, data_meta = build_data_wide_table(args.pulse_table, source_file_id=pulse_id)
    entry_stop = None if args.mc_entry_stop <= 0 else args.mc_entry_stop
    mc, mc_meta = build_mc_wide_table(
        args.mc_root, source_file_id=mc_id, coinc_ns=args.coinc_ns, entry_stop=entry_stop,
    )

    data_prep = core.prepare_data_side(data)
    mc_prep = core.prepare_mc_side(mc)

    per_sample: dict[str, Any] = {}
    for sample in ("I", "II"):
        per_sample[f"data_{sample}"] = summarize_sample(
            data_prep, delta_col="deltaE_data_adc", e_col="E_data_adc",
            weight_col=None, sample=sample, is_data=True, seed=args.seed + (1 if sample == "I" else 2),
        )
        per_sample[f"mc4_{sample}"] = summarize_sample(
            mc_prep, delta_col="deltaE_mc_mev", e_col="E_mc_4layer_mev",
            weight_col="PrimaryWeight", sample=sample, is_data=False, seed=args.seed,
        )
        per_sample[f"mcfull_{sample}"] = summarize_sample(
            mc_prep, delta_col="deltaE_mc_mev", e_col="E_mc_full_mev",
            weight_col="PrimaryWeight", sample=sample, is_data=False, seed=args.seed,
        )

    # B2–B4 diagnostic (both samples combined for headline n).
    b2b4 = data_prep[(data_prep["amp_B2"] > 0) & (data_prep["amp_B4"] > 0)].copy()
    per_sample["b2_b4_diagnostic"] = {
        "n_events": int(len(b2b4)),
        "pearson_r": float(np.corrcoef(b2b4["amp_B2"], b2b4["amp_B4"])[0, 1]),
        "median_B2_adc": float(b2b4["amp_B2"].median()),
        "median_B4_adc": float(b2b4["amp_B4"].median()),
        "label": "two-channel diagnostic; NOT ΔE–E",
        "corr_bootstrap": run_block_bootstrap(
            b2b4.assign(run_id=b2b4["run_id"]),
            lambda f: float(np.corrcoef(f["amp_B2"], f["amp_B4"])[0, 1]),
            seed=args.seed + 99,
        ),
    }

    bundle = core.analyze(
        data, mc,
        DEFAULT_STOP_THRESHOLDS,
        DEFAULT_DATA_THRESHOLDS,
        "all",
        args.seed,
    )

    summaries = {
        "study_id": "PAPER-956-DELTAE-E",
        "issue": "#956",
        "contract": "#618",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "data_meta": data_meta,
        "mc_meta": mc_meta,
        "per_sample": per_sample,
        "core_result": bundle["result"],
        "run_groups_verified": {
            "sample_I_analysis": sorted(SAMPLE_I_RUNS),
            "sample_II_analysis": sorted(SAMPLE_II_RUNS),
        },
    }

    fig_records = make_publication_figures(data_prep, mc, args.out, seed=args.seed)
    summaries["figures"] = fig_records
    write_tables_and_manifest(
        args.out, data=data_prep, mc=mc_prep, summaries=summaries, inputs=inputs, args=args,
    )
    print(json.dumps({
        "status": bundle["result"]["status"],
        "out": str(args.out),
        "n_data": int(len(data_prep)),
        "n_mc": int(len(mc_prep)),
        "per_sample": per_sample,
    }, indent=2))
    return 0 if bundle["result"]["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
