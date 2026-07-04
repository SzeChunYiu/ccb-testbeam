#!/usr/bin/env python3
"""
mv6b_anomaly_with_quenching.py
==============================
MV6 honest redo (Phase 4): does the data's ~4.4% early-peak anomalous class
(P02) survive as a C12-recoil explanation once Birks quenching is included?

The original MV6 is RETRACTED (EXTERNAL_REVIEW_2026-07-02.md P5/F6.2: gain
246 with 59% saturation, NO Birks so C12 light was overstated ~10x, no
amplitude threshold, per-track whole-arm waveforms). This redo runs on the
per-stave card-driven mc02 pulse tables — one built with Birks quenching ON
(Phase 4) and the legacy twin with quenching OFF (identical card, seeds and
geometry; the ONLY difference is the quench) — and applies the DATA taxonomy:

  * selection:   net amplitude A > 1000 ADC (s00 estimator, P02 selection)
  * early-peak:  peak_sample <= 3 (P02 REPORT.md section 5: clusters 1&4,
                 ~4.4% of selected pulses, "early-peak class (peak at
                 sample 3)"; samples 0-3 are the baseline window)

Gain handling (Phase 2 update, 2026-07-04): the card gain 297 ADC/MeV is a
placeholder; the Phase-2 MV3 diagnostic grid (reports/phase2_geometry_*/
grid_table.md) found the stopping-depth discrepancy is dominated by the
UNSIMULATED two-arm coincidence trigger and prefers gain ~60 ADC/MeV
(trigger-consistent scan optimum). Both tables are built at gain 297, so the
gain-60-equivalent selection is applied by rescaling the threshold:
A_1000@g60 == A > 1000*297/60 = 4950 ADC on the native table (exact up to the
8 ADC noise). Gain 60 is the PRIMARY reporting point; 297 is kept as a
sensitivity row.

Trigger proxy (Phase 2 update): the data taxonomy sample is triggered; the MC
table is not. sample_II (charged B-entry, the B-trigger truth proxy) is the
PRIMARY population filter; 'all' and sample_I (A.B coincidence proxy) are
reported as sensitivity rows.

Honest limitation (documented): mc02 places every event at a fixed trigger
offset (peak at sample ~5-6, no trigger-phase jitter), so an MC pulse can
only be "early-peak" through noise/baseline pathologies, not through the
phase variation real data has. The decisive quenching observable is therefore
whether heavy recoils (C12/alpha) can pass A>1000 AT ALL once quenched —
if they cannot, they cannot populate the data's 4.4% class.

Outputs (in --out): result.json, REPORT.md.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from ccb_mc_validation.truth.pdg import parse_pdg, species_label

EARLY_PEAK_MAX_SAMPLE = 3   # P02 taxonomy: early-peak class peaks at sample 3
DATA_EARLY_FRAC = 0.044     # P02: clusters 1&4 = ~4.4% of selected pulses


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def bucket_of(pdg: int) -> str:
    """Species bucket: p, d, t, He3, alpha, C12, other_ion, light (e/mu/pi/gamma...)."""
    label = species_label(pdg)
    if label in ("p", "d", "t", "He3", "alpha"):
        return label
    if pdg == 1000060120:
        return "C12"
    if parse_pdg(pdg).get("kind") == "nucleus":
        return "other_ion"
    return "light"


def load_table(path: Path) -> dict[str, np.ndarray]:
    """Load the mc02 full pulse table (only the columns this study needs)."""
    want = ("stave", "amplitude_adc", "peak_sample", "pdg", "sample_I", "sample_II")
    cols: dict[str, list] = {w: [] for w in want}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
        idx = {w: header.index(w) for w in want}
        for line in handle:
            parts = line.rstrip("\n").split(",")
            cols["stave"].append(parts[idx["stave"]])
            cols["amplitude_adc"].append(float(parts[idx["amplitude_adc"]]))
            cols["peak_sample"].append(int(parts[idx["peak_sample"]]))
            cols["pdg"].append(int(parts[idx["pdg"]]))
            cols["sample_I"].append(int(parts[idx["sample_I"]]))
            cols["sample_II"].append(int(parts[idx["sample_II"]]))
    return {
        "stave": np.asarray(cols["stave"], dtype=object),
        "amplitude_adc": np.asarray(cols["amplitude_adc"], dtype=np.float64),
        "peak_sample": np.asarray(cols["peak_sample"], dtype=np.int64),
        "pdg": np.asarray(cols["pdg"], dtype=np.int64),
        "sample_I": np.asarray(cols["sample_I"], dtype=bool),
        "sample_II": np.asarray(cols["sample_II"], dtype=bool),
    }


def analyse(
    tab: dict[str, np.ndarray],
    threshold_native_adc: float,
    population: str,
) -> dict:
    """Apply the DATA taxonomy to one (table, gain-equivalent, population)."""
    if population == "all":
        pop = np.ones(tab["amplitude_adc"].size, dtype=bool)
    elif population == "sample_II":
        pop = tab["sample_II"]
    elif population == "sample_I":
        pop = tab["sample_I"]
    else:
        raise ValueError(population)

    sel = pop & (tab["amplitude_adc"] > threshold_native_adc)
    n_pop = int(pop.sum())
    n_sel = int(sel.sum())
    early = sel & (tab["peak_sample"] <= EARLY_PEAK_MAX_SAMPLE)
    n_early = int(early.sum())
    frac = n_early / n_sel if n_sel else 0.0
    ci = wilson_ci(n_early, n_sel)

    buckets = np.asarray([bucket_of(int(p)) for p in tab["pdg"]], dtype=object)

    def comp(mask: np.ndarray) -> dict:
        out: dict[str, dict] = {}
        n = int(mask.sum())
        for b in sorted(set(buckets[mask])) if n else []:
            m = mask & (buckets == b)
            amps = tab["amplitude_adc"][m]
            out[b] = {
                "n": int(m.sum()),
                "frac": float(m.sum() / n),
                "median_amplitude_adc": float(np.median(amps)),
            }
        return out

    ion = sel & np.isin(buckets, ("alpha", "C12", "other_ion", "He3", "t"))
    # C12 survival through the selection (the decisive quench observable)
    c12_pop = pop & (buckets == "C12")
    c12_sel = sel & (buckets == "C12")
    return {
        "population": population,
        "threshold_native_adc": float(threshold_native_adc),
        "n_population_rows": n_pop,
        "n_selected": n_sel,
        "n_early_peak": n_early,
        "early_peak_frac": frac,
        "early_peak_frac_ci95": list(ci),
        "data_early_peak_frac": DATA_EARLY_FRAC,
        "species_composition_selected": comp(sel),
        "species_composition_early_peak": comp(early),
        "heavy_ion_selected": {
            "n": int(ion.sum()),
            "frac_of_selected": float(ion.sum() / n_sel) if n_sel else 0.0,
        },
        "c12_rows_in_population": int(c12_pop.sum()),
        "c12_rows_passing_selection": int(c12_sel.sum()),
        "c12_selection_survival_frac": (
            float(c12_sel.sum() / c12_pop.sum()) if c12_pop.sum() else None
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quenched", required=True,
                    help="mc02 report dir (or table path) built with Birks ON")
    ap.add_argument("--unquenched", required=True,
                    help="mc02 report dir (or table path) built with Birks OFF (legacy twin)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--threshold-adc", type=float, default=1000.0)
    ap.add_argument("--gain-native", type=float, default=297.0,
                    help="card gain the tables were built with")
    ap.add_argument("--gains", type=float, nargs="+", default=[60.0, 297.0],
                    help="gain hypotheses to report (60 = Phase-2 preferred, primary)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    def table_path(arg: str) -> Path:
        p = Path(arg)
        return p if p.is_file() else p / "mc02_pulse_table.csv.gz"

    t0 = time.time()
    results: dict[str, dict] = {}
    tables = {}
    for tag, src in (("quenched", args.quenched), ("unquenched", args.unquenched)):
        path = table_path(src)
        print(f"[mv6b] loading {tag}: {path}", flush=True)
        tab = load_table(path)
        tables[tag] = str(path)
        per = {}
        for gain in args.gains:
            thr = args.threshold_adc * args.gain_native / gain
            for population in ("sample_II", "all", "sample_I"):
                key = f"gain{gain:g}_{population}"
                per[key] = analyse(tab, thr, population)
        results[tag] = per
        print(f"[mv6b] {tag}: {tab['amplitude_adc'].size} rows analysed "
              f"({time.time() - t0:.0f}s)", flush=True)

    primary_key = f"gain{args.gains[0]:g}_sample_II"
    q = results["quenched"][primary_key]
    u = results["unquenched"][primary_key]

    verdict = {
        "primary_config": primary_key,
        "early_peak_frac_quenched": q["early_peak_frac"],
        "early_peak_frac_unquenched": u["early_peak_frac"],
        "data_early_peak_frac": DATA_EARLY_FRAC,
        "c12_survival_quenched": q["c12_selection_survival_frac"],
        "c12_survival_unquenched": u["c12_selection_survival_frac"],
        "heavy_ion_frac_selected_quenched": q["heavy_ion_selected"]["frac_of_selected"],
        "heavy_ion_frac_selected_unquenched": u["heavy_ion_selected"]["frac_of_selected"],
    }

    summary = {
        "study_id": "MV6b-anomaly-with-quenching",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "script": "scripts/mv6b_anomaly_with_quenching.py",
        "inputs": tables,
        "taxonomy": {
            "selection": f"amplitude_adc > {args.threshold_adc} (gain-equivalent rescaled)",
            "early_peak": f"peak_sample <= {EARLY_PEAK_MAX_SAMPLE} (P02 section 5)",
            "data_reference": "P02: clusters 1&4 = ~4.4% early-peak/low-area",
        },
        "gain_handling": {
            "native_gain_adc_per_mev": args.gain_native,
            "gains_reported": args.gains,
            "primary_gain": args.gains[0],
            "note": (
                "Phase 2 grid prefers ~60 ADC/MeV (trigger-consistent); the "
                "gain-g selection on a gain-297 table is amplitude > 1000*297/g"
            ),
        },
        "results": results,
        "verdict": verdict,
        "caveats": [
            "MC pulses have a construction-pinned peak phase (trigger offset 50 ns, "
            "no trigger-phase jitter), so MC early-peak can only arise from "
            "noise/baseline pathologies — the decisive quench observable is C12/ion "
            "survival of the A>1000 selection, not the raw early-peak fraction",
            "gain is a placeholder either way; both hypotheses (60 preferred, 297) reported",
            "occupancy weights inherit the unsimulated-trigger defect (Phase 2)",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    # ---- REPORT.md ----------------------------------------------------------
    def pct(x: float) -> str:
        return f"{100.0 * x:.3f}%"

    lines = [
        "# MV6b — anomaly taxonomy with Birks quenching (honest MV6 redo)",
        "",
        f"Generated {summary['generated_utc']}. Inputs: quenched `{tables['quenched']}`, "
        f"unquenched twin `{tables['unquenched']}`.",
        "",
        "Question (review F6.2): can C12 recoils be the data's ~4.4% early-peak class "
        "once light quenching is included? The retracted MV6 ran unquenched (C12 light "
        "overstated ~10x) with no amplitude threshold.",
        "",
        "## Primary result (gain 60 = Phase-2 preferred, sample_II trigger proxy)",
        "",
        "| quantity | quenched (Birks ON) | unquenched (legacy twin) | data |",
        "|---|---|---|---|",
        f"| A>1000 rows | {q['n_selected']} | {u['n_selected']} | — |",
        f"| early-peak (peak_sample<=3) fraction | {pct(q['early_peak_frac'])} "
        f"[{pct(q['early_peak_frac_ci95'][0])}, {pct(q['early_peak_frac_ci95'][1])}] "
        f"| {pct(u['early_peak_frac'])} "
        f"[{pct(u['early_peak_frac_ci95'][0])}, {pct(u['early_peak_frac_ci95'][1])}] "
        f"| {pct(DATA_EARLY_FRAC)} |",
        f"| C12 rows in population | {q['c12_rows_in_population']} | {u['c12_rows_in_population']} | — |",
        f"| C12 rows passing A>1000 | {q['c12_rows_passing_selection']} | {u['c12_rows_passing_selection']} | — |",
        f"| heavy-ion fraction of A>1000 | {pct(q['heavy_ion_selected']['frac_of_selected'])} "
        f"| {pct(u['heavy_ion_selected']['frac_of_selected'])} | — |",
        "",
        "## Species composition of the A>1000 selection (primary config)",
        "",
        "| species | quenched n (frac, med amp) | unquenched n (frac, med amp) |",
        "|---|---|---|",
    ]
    all_species = sorted(
        set(q["species_composition_selected"]) | set(u["species_composition_selected"])
    )
    for b in all_species:
        cq = q["species_composition_selected"].get(b)
        cu = u["species_composition_selected"].get(b)
        fq = f"{cq['n']} ({pct(cq['frac'])}, {cq['median_amplitude_adc']:.0f})" if cq else "0"
        fu = f"{cu['n']} ({pct(cu['frac'])}, {cu['median_amplitude_adc']:.0f})" if cu else "0"
        lines.append(f"| {b} | {fq} | {fu} |")

    lines += [
        "",
        "## Early-peak species composition (primary config)",
        "",
        "| species | quenched | unquenched |",
        "|---|---|---|",
    ]
    early_species = sorted(
        set(q["species_composition_early_peak"]) | set(u["species_composition_early_peak"])
    )
    if early_species:
        for b in early_species:
            cq = q["species_composition_early_peak"].get(b)
            cu = u["species_composition_early_peak"].get(b)
            lines.append(
                f"| {b} | {cq['n'] if cq else 0} | {cu['n'] if cu else 0} |"
            )
    else:
        lines.append("| (no early-peak rows in either table) | 0 | 0 |")

    lines += [
        "",
        "## Sensitivity grid (all gain x population configs)",
        "",
        "| config | quenched: n sel / early frac / C12 sel | unquenched: n sel / early frac / C12 sel |",
        "|---|---|---|",
    ]
    for key in results["quenched"]:
        a = results["quenched"][key]
        b = results["unquenched"][key]
        lines.append(
            f"| {key} | {a['n_selected']} / {pct(a['early_peak_frac'])} / "
            f"{a['c12_rows_passing_selection']} | {b['n_selected']} / "
            f"{pct(b['early_peak_frac'])} / {b['c12_rows_passing_selection']} |"
        )

    lines += [
        "",
        "## Caveats",
        "",
    ]
    lines += [f"- {c}" for c in summary["caveats"]]
    lines += [
        "",
        "## Reproduce",
        "",
        "```",
        "python3 scripts/mv6b_anomaly_with_quenching.py \\",
        f"    --quenched {args.quenched} --unquenched {args.unquenched} --out {args.out}",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(verdict, indent=2))
    print(f"[mv6b] done in {time.time() - t0:.0f}s -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
