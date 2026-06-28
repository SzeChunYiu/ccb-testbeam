#!/usr/bin/env python3
"""
mv9_synthesis_runner.py
=======================
MV9 -- synthesis runner. Scans reports/ for all completed MV study JSONs,
builds a synthesis registry + table, renders the master plot grid, and writes
reports/mc_validation_synthesis/SYNTHESIS.md.

Run AFTER the individual MV studies have produced their report JSONs.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ccb_mc_validation.studies.mv9_synthesis import (  # noqa: E402
    build_registry_from_reports,
    master_plot,
)

# narrative: study_id -> (title, the open data question it closes)
NARRATIVE = {
    "MV1": ("Particle ID (p vs d)", "Is data-only p/d separation ceiling reachable? MC sets the truth-level AUC."),
    "MV2": ("Range-energy calibration", "Is 10% absolute energy resolution unreachable, as data claimed?"),
    "MV3": ("Stopping-depth profile", "Does MC reproduce the Sample I/II deuteron enrichment in the first B layer?"),
    "MV4": ("Single-stave timing", "Does the analytic amp-timewalk sigma68~1.495 ns hold in MC?"),
    "MV5": ("Pile-up / Rmax", "Is Rmax 3.05 MHz (tau_eff=124.8ns) or the note's 4.2 MHz (90ns)?"),
    "MV6": ("Representation & anomaly ID", "What species is the ~4% early-peak anomalous class found in data P02?"),
}


def main() -> None:
    ap = argparse.ArgumentParser(description="MV9 synthesis runner")
    ap.add_argument("--reports", default=str(ROOT / "reports"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "mc_validation_synthesis"))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    registry = build_registry_from_reports(args.reports)
    studies = registry["studies"]

    (out / "synthesis_registry.json").write_text(json.dumps(registry, indent=2))

    # master plot grid
    master_png = out / "mv9_master_synthesis.png"
    try:
        master_plot(registry, args.reports, master_png)
        plot_ok = True
    except Exception as exc:  # noqa: BLE001
        plot_ok = False
        print(f"[warn] master_plot failed: {exc}")

    # SYNTHESIS.md
    n_done = sum(1 for s in studies.values() if s.get("status") == "PRODUCTION")
    lines = [
        "# MC Validation Synthesis (MV9)",
        "",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Studies discovered as PRODUCTION:** {n_done}/{len(studies)}",
        "",
        "This program runs MC-truth validation studies to *close open questions* the",
        "data-only analysis could not answer, and to confirm data-derived corrections.",
        "",
        "## Synthesis table",
        "",
        "| Study | Title | Status | Key result | Question closed |",
        "| --- | --- | --- | --- | --- |",
    ]
    for sid in sorted(studies.keys()):
        e = studies[sid]
        title, question = NARRATIVE.get(sid, (sid, ""))
        lines.append(f"| {sid} | {title} | {e.get('status')} | "
                     f"{e.get('key_result', '')} | {question} |")
    lines += ["", "## Per-study detail", ""]
    for sid in sorted(studies.keys()):
        e = studies[sid]
        title, question = NARRATIVE.get(sid, (sid, ""))
        lines.append(f"### {sid} — {title}")
        lines.append(f"- **Status:** {e.get('status')}")
        lines.append(f"- **Key result:** {e.get('key_result', 'n/a')}")
        lines.append(f"- **Open question addressed:** {question}")
        if e.get("report"):
            lines.append(f"- **Report JSON:** `{e['report']}`")
        lines.append("")
    if plot_ok:
        lines += ["## Master plot", "",
                  "![master synthesis](mv9_master_synthesis.png)", ""]

    (out / "SYNTHESIS.md").write_text("\n".join(lines))

    print(json.dumps({
        "status": "ok", "out": str(out),
        "n_production": n_done, "n_total": len(studies),
        "studies": {k: v.get("status") for k, v in studies.items()},
    }, indent=2))
    print(f"[ok] wrote {out}/SYNTHESIS.md")


if __name__ == "__main__":
    main()
