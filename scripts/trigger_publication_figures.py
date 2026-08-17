#!/usr/bin/env python3
"""Publication figures for issue #1045 trigger hardware-response migration.

Phase 4 corrected (per-event joint matrix) on the v3-instrumented 1M MC run.
Reads ONLY committed study JSONs (deterministic, reproducible in-repo):

  research/trigger_migration_study/phase4/joint_matrix_1m_v3.json
  research/trigger_migration_study/phase4/migration_matrix_1m_v3_aggregate_SUPERSEDED.json
  research/trigger_migration_study/phase3/hardware_scan_1m_v3.json
  research/trigger_migration_study/phase3/baseline_proxy_scan_1m_v3.json

Outputs (under reports/paper_1045_trigger_migration_<ts>/):
  result.json   - machine-readable values (figures.yaml value_key source)
  manifest.json - args/environment/inputs with sha256
  REPORT.md     - method + verdict + correction record
  figures/fig_trigger_migration_quadrants.png
  figures/fig_trigger_threshold_scan.png

Figures are copied to publication/figures/gated/ (registry source_figure path).

Governance: MC closure on the authorising corrected-source chain (CL-021
satisfied); the 1M v3 run reproduces the authorising two-arm sample (554)
exactly, proving geometry-only delta. NOT a beam-data trigger result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

STUDY = Path("research/trigger_migration_study")
JOINT = STUDY / "phase4/joint_matrix_1m_v3.json"
AGG = STUDY / "phase4/migration_matrix_1m_v3_aggregate_SUPERSEDED.json"
HW = STUDY / "phase3/hardware_scan_1m_v3.json"
PROXY = STUDY / "phase3/baseline_proxy_scan_1m_v3.json"

# colorblind-safe palette (Okabe-Ito)
BLUE, VERM, GREEN, ROSE, GREY = "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#666666"

REF_THR, REF_COINC = 1.0, 15.0
RAY_PREDICTION = 0.289
GEOM_V3_SHA = "657661c8bbae28e35bc9398e6752ed97f371e0939921770699df7d3dfb9c5eba"
GEOM_BASE_SHA = "a71c5cd7ce4cd7085f7f0236d5852f81aba0b52ff56bc2e9593f677e1e410d4e"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def binom_se(p: float, n: int) -> float:
    return math.sqrt(p * (1.0 - p) / n) if n else float("nan")


def build_result(joint: dict, agg: dict, hw: dict, proxy: dict) -> dict:
    grid = joint["grid"]
    ref = grid[str(REF_THR)][str(REF_COINC)]
    proxy_total = ref["both"] + ref["proxy_only"]
    hw_total = ref["both"] + ref["hardware_only"]
    retention = ref["both"] / proxy_total

    scan = []
    for thr_s in sorted(grid, key=float):
        r = grid[thr_s][str(REF_COINC)]
        pt = r["both"] + r["proxy_only"]
        scan.append({
            "threshold_mev": float(thr_s),
            "coinc_ns": REF_COINC,
            "both": r["both"],
            "proxy_only": r["proxy_only"],
            "hardware_only": r["hardware_only"],
            "proxy_total": pt,
            "hardware_total": r["both"] + r["hardware_only"],
            "retention": r["both"] / pt,
            "retention_se": binom_se(r["both"] / pt, pt),
        })

    # proxy pass count vs coincidence window (threshold-free by construction;
    # take the thr row matching REF_THR)
    proxy_vs_coinc = []
    for r in proxy["results"]:
        if r["threshold_mev"] == REF_THR:
            proxy_vs_coinc.append({"coinc_ns": r["coinc_ns"], "n_pass": r["n_trigger_pass"]})
    proxy_vs_coinc.sort(key=lambda d: d["coinc_ns"])

    agg_ref = agg["aggregate_migration"]["quadrants"]
    return {
        "contract": "#1045 phase 4 (corrected)",
        "n_events": joint["n_events"],
        "reference": {
            "threshold_mev": REF_THR,
            "coinc_ns": REF_COINC,
            "both": ref["both"],
            "proxy_only": ref["proxy_only"],
            "hardware_only": ref["hardware_only"],
            "proxy_total": proxy_total,
            "hardware_total": hw_total,
            "retention": retention,
            "retention_se": binom_se(retention, proxy_total),
            "hardware_purity_within_proxy": ref["both"] / hw_total,
            "ray_projection_prediction": RAY_PREDICTION,
        },
        "threshold_scan": scan,
        "species_at_reference": ref["species"],
        "proxy_vs_coincidence": proxy_vs_coinc,
        "aggregate_superseded_quadrants": {
            "both": agg_ref["both"],
            "proxy_only": agg_ref["proxy_only"],
            "hardware_only": agg_ref["hardware_only"],
            "note": "aggregate join of two scan JSONs; assumed hardware subset of "
                    "proxy; superseded by per-event joint quadrants",
        },
        "geometry": {
            "baseline_sha256": GEOM_BASE_SHA,
            "v3_sha256": GEOM_V3_SHA,
            "v3_method": "instrument baseline Trig_stack_1/2 (real T1/T2 counters, "
                         "r=99 cm) by splitting shared Trig_bar into "
                         "T1_trigger_log/T2_trigger_log",
        },
    }


def fig_quadrants(res: dict, out: Path) -> None:
    ref = res["reference"]
    sup = res["aggregate_superseded_quadrants"]
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(9.2, 3.8), constrained_layout=True
    )

    labels = ["both", "proxy_only", "hardware_only"]
    correct = [ref[k] for k in labels]
    wrong = [sup[k] for k in labels]
    x = range(len(labels))
    w = 0.36
    b1 = ax1.bar([i - w / 2 for i in x], correct, w, color=BLUE, label="per-event joint (correct)")
    b2 = ax1.bar([i + w / 2 for i in x], wrong, w, color=ROSE, alpha=0.85,
                 label="aggregate join (superseded)")
    for bars in (b1, b2):
        ax1.bar_label(bars, fontsize=8, padding=1)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(["both", "proxy-only", "hardware-only"])
    ax1.set_ylabel("events (1M MC)")
    ax1.set_title("(a) Migration quadrants @ 1.0 MeV / 15 ns", fontsize=10)
    ax1.legend(fontsize=8, frameon=False)

    scan = res["threshold_scan"]
    thr = [s["threshold_mev"] for s in scan]
    ret = [s["retention"] for s in scan]
    se = [s["retention_se"] for s in scan]
    ax2.errorbar(thr, ret, yerr=se, marker="o", color=BLUE, capsize=3,
                 label="measured retention")
    ax2.axhline(RAY_PREDICTION, color=GREEN, ls="--", lw=1.2,
                label=f"ray-projection prediction {RAY_PREDICTION:.3f}")
    ax2.set_xscale("log")
    ax2.set_xticks(thr)
    ax2.set_xticklabels([f"{t:g}" for t in thr])
    ax2.set_xlabel("threshold (MeV)")
    ax2.set_ylabel("two-arm retention")
    ax2.set_ylim(0.2, 0.4)
    ax2.set_title("(b) Retention vs threshold (coinc 15 ns)", fontsize=10)
    ax2.legend(fontsize=8, frameon=False)

    fig.suptitle(
        "T1$\\wedge$T2 hardware trigger vs two-arm proxy — 1M events, v3 geometry",
        fontsize=11,
    )
    fig.savefig(out, dpi=300)
    plt.close(fig)


def fig_threshold_scan(res: dict, hw: dict, out: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(9.2, 3.8), constrained_layout=True
    )
    coincs = sorted({r["coinc_ns"] for r in hw["results"]})
    cmap = plt.get_cmap("viridis")
    for i, c in enumerate(coincs):
        pts = sorted(
            (r for r in hw["results"] if r["coinc_ns"] == c),
            key=lambda r: r["threshold_mev"],
        )
        ax1.plot([p["threshold_mev"] for p in pts], [p["n_trigger_pass"] for p in pts],
                 marker="o", ms=3.5, color=cmap(i / max(1, len(coincs) - 1)),
                 label=f"{c:g} ns")
    ax1.set_xscale("log")
    ax1.set_xticks(sorted({r["threshold_mev"] for r in hw["results"]}))
    ax1.set_xticklabels([f"{t:g}" for t in sorted({r["threshold_mev"] for r in hw["results"]})])
    ax1.set_xlabel("threshold (MeV)")
    ax1.set_ylabel("T1$\\wedge$T2 pass count")
    ax1.set_title("(a) Hardware trigger vs threshold", fontsize=10)
    ax1.legend(fontsize=7, frameon=False, title="coincidence", title_fontsize=7)

    pvc = res["proxy_vs_coincidence"]
    ax2.plot([d["coinc_ns"] for d in pvc], [d["n_pass"] for d in pvc],
             marker="s", color=VERM, label="two-arm proxy (sample I)")
    hw15 = sorted(
        (r for r in hw["results"] if r["coinc_ns"] == REF_COINC),
        key=lambda r: r["threshold_mev"],
    )
    ax2.plot([r["threshold_mev"] for r in hw15], [r["n_trigger_pass"] for r in hw15],
             marker="o", ms=3.5, color=BLUE, label="T1$\\wedge$T2 (coinc 15 ns)")
    ax2.set_xscale("log")
    ax2.set_xlabel("coincidence window (ns) / threshold (MeV)")
    ax2.set_ylabel("pass count")
    ax2.set_title("(b) Proxy vs window; hardware flat in threshold", fontsize=10)
    ax2.legend(fontsize=8, frameon=False)

    fig.suptitle("Threshold / coincidence scan — 1M events, v3 geometry", fontsize=11)
    fig.savefig(out, dpi=300)
    plt.close(fig)


def write_report(res: dict, out_dir: Path, fig_names: list[str]) -> None:
    ref = res["reference"]
    sup = res["aggregate_superseded_quadrants"]
    lines = [
        "# Paper figure report: #1045 trigger migration (Phase 4 corrected)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Method",
        "",
        "Per-event JOINT classification of the 1M v3 MC run (real T1/T2 counters",
        "instrumented from the baseline geometry; two-arm sample reproduced at 554",
        "exactly, proving a geometry-only delta on the authorising source chain).",
        "Proxy = two-arm charged coincidence (`sample_I`); hardware = per-hit",
        "threshold + earliest-above-threshold coincidence on T1/T2 truth hits.",
        "",
        "## Verdict @ 1.0 MeV / 15 ns",
        "",
        f"- both = {ref['both']}, proxy-only = {ref['proxy_only']}, "
        f"hardware-only = {ref['hardware_only']}",
        f"- two-arm retention = {ref['both']}/{ref['proxy_total']} = "
        f"{ref['retention']:.4f} +/- {ref['retention_se']:.4f} "
        f"(binomial); ray prediction {RAY_PREDICTION}",
        f"- retention is threshold-insensitive (0.5-5 MeV flat): the loss is geometric",
        "- hardware sample is NOT a subset of the proxy sample "
        f"({ref['hardware_only']}/{ref['hardware_total']} = "
        f"{1 - ref['hardware_purity_within_proxy']:.0%} of hardware triggers lie "
        "outside the two-arm definition)",
        "",
        "## Correction record",
        "",
        "The aggregate matrix joined two scan JSONs arithmetically "
        f"(both={sup['both']}, proxy_only={sup['proxy_only']}, "
        f"hardware_only={sup['hardware_only']}) under the false assumption that a",
        "hardware pass implies proxy membership. Superseded by the per-event joint",
        "matrix (this report). See phase4/JOINT_MATRIX_CORRECTION.md.",
        "",
        "## Figures",
        "",
    ]
    lines += [f"- `{f}`" for f in fig_names]
    lines += ["", "## Governance", "",
              "MC method closure on the authorising corrected-source chain (CL-021",
              "satisfied). NOT a beam-data trigger result; no hardware-validated",
              "efficiency claim is made."]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="output report directory")
    ap.add_argument("--copy-to", default="publication/figures/gated",
                    help="directory to copy rendered PNGs into")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "figures").mkdir(exist_ok=True)

    joint = json.loads(JOINT.read_text())
    agg = json.loads(AGG.read_text())
    hw = json.loads(HW.read_text())
    proxy = json.loads(PROXY.read_text())

    res = build_result(joint, agg, hw, proxy)
    res["generated_utc"] = datetime.now(timezone.utc).isoformat()

    f1 = out_dir / "figures/fig_trigger_migration_quadrants.png"
    f2 = out_dir / "figures/fig_trigger_threshold_scan.png"
    fig_quadrants(res, f1)
    fig_threshold_scan(res, hw, f2)

    (out_dir / "result.json").write_text(json.dumps(res, indent=2) + "\n")

    inputs = []
    for p, role in ((JOINT, "joint_matrix"), (AGG, "aggregate_matrix_superseded"),
                    (HW, "hardware_scan"), (PROXY, "proxy_scan")):
        inputs.append({"path": str(p), "role": role, "sha256": sha256_file(p),
                       "bytes": p.stat().st_size})
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                text=True, check=True).stdout.strip()
    except Exception:
        commit = None
    manifest = {
        "script": "scripts/trigger_publication_figures.py",
        "command": f"scripts/trigger_publication_figures.py --out {args.out}",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "environment": {"python": platform.python_version(),
                        "matplotlib": matplotlib.__version__,
                        "platform": platform.platform()},
        "inputs": inputs,
        "figures": [f.name for f in (f1, f2)],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(res, out_dir, [str(f1.relative_to(out_dir)), str(f2.relative_to(out_dir))])

    copy_to = Path(args.copy_to)
    if copy_to.is_dir() or copy_to.parent.is_dir():
        copy_to.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f1, copy_to / f1.name)
        shutil.copy2(f2, copy_to / f2.name)

    print(f"WROTE {out_dir}")
    r = res["reference"]
    print(f"retention {r['both']}/{r['proxy_total']} = {r['retention']:.4f} "
          f"+/- {r['retention_se']:.4f} (ray {RAY_PREDICTION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
