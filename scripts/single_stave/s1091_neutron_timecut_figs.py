#!/usr/bin/env python3
"""s1091 figures — neutron timecut sensitivity ladder (#1091).

Reads the ladder ROOT files directly (same layout the analysis script uses)
and renders the report figures. Run AFTER s1091_*_neutron_timecut_ladder.py
(has produced result.json for the numbers echoed into annotations).

  fig1  paired per-event delta (adc_readout) per grid point — histogram of
        ext - pin with affected counts; the insensitivity picture.
  fig2  cumulative in-scintillator neutron Edep vs time (ext runs, log-x)
        with the 180 ns DAQ window and the 10 us pinned cut marked.
  fig3  neutron step-time spectra, wiring fixture (1 GeV p) per policy —
        the knob-bites picture (1 ns vs 10 us vs 1e9 us).
  fig4  affected-event fraction + neutron-producing-event fraction per point.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import uproot  # noqa: E402

DAQ_NS = 180.0
CUT_NS = 1e4


def load_events_cols(root: Path, cols):
    with uproot.open(root) as f:
        t = f["events"]
        ev = t["event"].array(library="np")
        out = {c: t[c].array(library="np") for c in cols}
    order = np.argsort(ev)
    return {c: v[order] for c, v in out.items()}


def load_steps(root: Path):
    with uproot.open(root) as f:
        if "neutron_steps" not in f:
            return None
        t = f["neutron_steps"]
        return {
            k: t[k].array(library="np") for k in ("event", "kind", "t_ns", "edep_MeV", "in_scint")
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ladder-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--config", required=True, type=Path)
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    R = lambda t: args.ladder_dir / f"{t}.root"  # noqa: E731

    # fig1 — paired adc deltas
    fig, ax = plt.subplots(figsize=(7, 4.5))
    fracs, nfrac = [], []
    for pt, spec in cfg["grid_points"].items():
        a = load_events_cols(R(spec["pin"]), ["adc_readout"])
        b = load_events_cols(R(spec["ext"]), ["adc_readout"])
        d = b["adc_readout"] - a["adc_readout"]
        n = len(d)
        nz = int((d != 0).sum())
        fracs.append(nz / n if n else 0.0)
        nfrac.append(int(n))
        if nz:
            ax.hist(d[d != 0], bins=60, histtype="step", label=f"{pt} ({nz}/{n})")
    ax.set_xlabel("paired Δ adc_readout (ext − pin), nonzero events")
    ax.set_ylabel("events")
    ax.set_title("fig1 — #1091 ladder: paired per-event ADC delta (seed- and thread-matched)")
    if fracs and max(fracs) > 0:
        ax.legend(title="point (affected/total)", fontsize=8)
    else:
        ax.text(
            0.5,
            0.5,
            "all paired deltas bitwise zero",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
    fig.tight_layout()
    fig.savefig(args.out / "fig1_paired_adc_delta.png", dpi=160)
    plt.close(fig)

    # fig2 — cumulative in-scint neutron Edep vs T (ext runs)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for pt, spec in cfg["grid_points"].items():
        s = load_steps(R(spec["ext"]))
        if s is None or not len(s["t_ns"]):
            continue
        m = (s["kind"] == 0) & (s["in_scint"] == 1)
        if not m.any():
            continue
        o = np.argsort(s["t_ns"][m])
        t = s["t_ns"][m][o]
        e = np.cumsum(s["edep_MeV"][m][o])
        ax.step(
            np.concatenate([[t[0]], t]),
            np.concatenate([[0], e]),
            where="post",
            label=f"{pt} (total {e[-1]:.3g} MeV)",
        )
    w = cfg["wiring"]
    sw = load_steps(R(w["ext"]))
    if sw is not None and len(sw["t_ns"]):
        m = (sw["kind"] == 0) & (sw["in_scint"] == 1)
        if m.any():
            o = np.argsort(sw["t_ns"][m])
            t = sw["t_ns"][m][o]
            e = np.cumsum(sw["edep_MeV"][m][o])
            ax.step(
                np.concatenate([[t[0]], t]),
                np.concatenate([[0], e]),
                where="post",
                label=f"wiring 1 GeV p (total {e[-1]:.3g} MeV)",
                linestyle="--",
            )
    ax.axvline(DAQ_NS, color="k", linestyle=":", linewidth=1)
    ax.axvline(CUT_NS, color="r", linestyle=":", linewidth=1)
    ax.text(DAQ_NS, ax.get_ylim()[1] * 0.9, " 180 ns DAQ", fontsize=8)
    ax.text(CUT_NS, ax.get_ylim()[1] * 0.9, " 10 µs cut", fontsize=8, color="r")
    ax.set_xscale("log")
    ax.set_xlabel("neutron step time t (ns, log)")
    ax.set_ylabel("cumulative in-scint neutron Edep (MeV)")
    ax.set_title("fig2 — #1091: what the 10 µs cut removes vs what the DAQ can see")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(args.out / "fig2_cumulative_neutron_edep.png", dpi=160)
    plt.close(fig)

    # fig3 — wiring knob: neutron step-time spectra per policy
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for key, lbl in [
        ("cut1ns", "1 ns cut (wiring)"),
        ("pin", "10 µs (pin)"),
        ("ext", "1e9 µs (ext)"),
    ]:
        s = load_steps(R(w[key]))
        if s is None or not len(s["t_ns"]):
            continue
        t = s["t_ns"][s["kind"] == 0]
        if not len(t):
            continue
        ax.hist(t, bins=np.logspace(-2, 7, 90), histtype="step", label=f"{lbl} (n={len(t)})")
    ax.axvline(1.0, color="C0", linestyle=":", linewidth=1)
    ax.axvline(CUT_NS, color="C1", linestyle=":", linewidth=1)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("neutron step time t (ns)")
    ax.set_ylabel("neutron steps")
    ax.set_title("fig3 — #1091 wiring fixture (1 GeV p): the cut knob bites")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(args.out / "fig3_wiring_time_spectra.png", dpi=160)
    plt.close(fig)

    # fig4 — affected / neutron-producing fractions per point
    labels = list(cfg["grid_points"].keys())
    x = np.arange(len(labels))
    neutron_frac = []
    for pt in labels:
        s = load_steps(R(cfg["grid_points"][pt]["ext"]))
        n_ev = json.loads(
            (
                R(cfg["grid_points"][pt]["ext"]).parent
                / (cfg["grid_points"][pt]["ext"] + ".root.meta.json")
            ).read_text()
        )["n_events"]
        if s is None or not len(s["event"]):
            neutron_frac.append(0.0)
        else:
            neutron_frac.append(len(set(s["event"][s["kind"] == 0].tolist())) / n_ev)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(
        x - 0.2,
        nfrac and [f * n for f, n in zip(fracs, nfrac)] or fracs,
        0.4,
        label="affected events (Δadc ≠ 0)",
    )
    ax.bar(
        x + 0.2, [f * n for f, n in zip(neutron_frac, nfrac)], 0.4, label="neutron-producing events"
    )
    ax.set_xticks(x, labels)
    ax.set_ylabel("events (of 2000)")
    ax.set_title("fig4 — #1091: affected vs neutron-producing events per grid point")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(args.out / "fig4_affected_fractions.png", dpi=160)
    plt.close(fig)

    print(
        json.dumps(
            {"fig1_max_frac": max(fracs) if fracs else None, "fig2_points": len(labels)}, indent=1
        )
    )


if __name__ == "__main__":
    main()
