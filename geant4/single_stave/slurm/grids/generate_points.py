#!/usr/bin/env python3
"""Generate one-knob-at-a-time SiPM sensitivity sweep grids.

Each knob is swept alone around the representative Hamamatsu S13360-3050CS
operating point (the defaults baked into ccb-sipm-core's
ModelConfig::RepresentativeS13360_3050CS and single_stave's AppConfig). The
emission is one CSV per knob plus a manifest listing every grid.

Design contract (SIPM-P2-001 + AF-036 / #984):
  * ONE knob varies per grid; all others stay at the representative default.
  * Every range bound below is justified by the device datasheet / physics and
    is ENV-OVERRIDABLE so an operator can re-grid without editing code:
       CCB_GRID_<KNOB>="v0 v1 v2 ..."   (space- or comma-separated)
    No magic numbers: every default grid cites its rationale in the header.
  * Paired multi-seed (common-random-number) design: each replicate seed is
    reused at EVERY value of a given knob. Seed-level paired differences then
    separate parameter response from finite-MC fluctuation. Stochastic
    branching knobs (PDE/crosstalk/afterpulse) may degrade pairing; that is
    reported by analyzers rather than assumed perfect.
  * Each row is self-describing so the submit driver stays knob-agnostic:
       columns = label,seed,nevents,cli_args,env_vars
    with comment metadata encoding (knob, value, replicate_seed). A companion
    JSON manifest lists the same triples explicitly.
    The submit script passes cli_args (appended to ccb_stave_sim) and exports
    env_vars (VAR=val pairs) verbatim.

Output: grids/points_<knob>.csv  for each knob, grids/MANIFEST.csv, and
        grids/PAIRED_SEED_DESIGN.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# Default events/seeds. Modest by design: this is a *sensitivity* scan (relative
# response across a knob), not a production yield campaign. Each proton event
# at 100 MeV already produces O(1e2-1e3) detected PE, so a few tens of events
# give a stable mean ADC for trend extraction. Override with the env vars below.
# ---------------------------------------------------------------------------
DEFAULT_NEVENTS = int(os.environ.get("CCB_CAMPASSIGN_NEVENTS", "60"))
SEED_BASE = int(os.environ.get("CCB_CAMPASSIGN_SEED_BASE", "1000"))
# Number of independent CRN replicates (same seed across knob values).
_N_REPS = int(os.environ.get("CCB_CAMPASSIGN_N_REPLICATES", "3"))
_RAW_REPS = os.environ.get("CCB_CAMPASSIGN_SEED_REPLICATES", "").strip()
if _RAW_REPS:
    SEED_REPLICATES: List[int] = [
        int(float(t)) for t in re.split(r"[\s,]+", _RAW_REPS) if t
    ]
else:
    SEED_REPLICATES = [SEED_BASE + r for r in range(_N_REPS)]
# Baseline beam point for every sweep (proton, 100 MeV, normal incidence, centre).
BASE_CLI = os.environ.get(
    "CCB_CAMPASSIGN_BASE_CLI",
    "--particle proton --energy 100 --hit-x 0 --hit-y 0 --theta 0 --phi 0",
)


@dataclass(frozen=True)
class Knob:
    """One sweepable parameter."""

    name: str            # short id, used in filenames / labels
    channel: str         # "cli" or "env"
    target: str          # CLI flag (e.g. "--pde-scale") or env var name
    unit: str            # human unit for plots
    rationale: str       # why this range (datasheet / physics citation)
    values: List[object]  # the swept values (float / int / str)


def _to_str(v: object) -> str:
    if isinstance(v, float):
        # Trim trailing zeros for clean labels, keep precision otherwise.
        return f"{v:g}"
    return str(v)


# ---------------------------------------------------------------------------
# Knob catalogue. Ranges span the plausible operating envelope of the
# S13360-3050CS and the stave optics; the representative default sits inside
# each grid so the slope is anchored at the nominal operating point.
# ---------------------------------------------------------------------------
def build_knobs() -> List[Knob]:
    knobs: List[Knob] = []

    def env_list(name: str, default: List[object]) -> List[object]:
        """Override a grid from $CCB_GRID_<NAME>; keep numeric type of defaults."""
        raw = os.environ.get(f"CCB_GRID_{name}")
        if not raw:
            return list(default)
        tokens = [t for t in re.split(r"[\s,]+", raw.strip()) if t]
        # Preserve int vs float by inspecting the first default element.
        if default and isinstance(default[0], int) and not isinstance(default[0], bool):
            return [int(float(t)) for t in tokens]
        # Strings (e.g. far-end modes) stay strings; everything else float.
        if default and isinstance(default[0], str):
            return tokens
        return [float(t) for t in tokens]

    knobs.append(Knob(
        "pde_scale", "cli", "--pde-scale", "x PDE table",
        "+/-40% spans the OV range + device spread (S13360-3050CS ~25-50% peak).",
        env_list("PDE_SCALE", [0.6, 0.8, 1.0, 1.2, 1.4]),
    ))
    knobs.append(Knob(
        "collection_efficiency", "cli", "--collection-efficiency", "frac",
        "Post-transport collection efficiency in [0,1]; 0.5 = poor, 1.0 = ideal.",
        env_list("COLLECTION_EFFICIENCY", [0.5, 0.7, 0.85, 0.95, 1.0]),
    ))
    knobs.append(Knob(
        "recovery_time", "env", "CCB_SIPM_RECOVERY_TIME_NS", "ns",
        "Microcell RC recovery; S13360-3050CS tens of ns, swept 5-100 ns.",
        env_list("RECOVERY_TIME", [5.0, 15.0, 30.0, 60.0, 100.0]),
    ))
    knobs.append(Knob(
        "dark_count", "env", "CCB_SIPM_DARK_COUNT_RATE_HZ", "Hz",
        "DCR: 0 (cold) to 2 MHz (hot/irradiated); nominal ~0.5 MHz/cell model.",
        env_list("DARK_COUNT", [0.0, 1.0e5, 5.0e5, 1.0e6, 2.0e6]),
    ))
    knobs.append(Knob(
        "crosstalk", "env", "CCB_SIPM_CROSSTALK_PROB", "prob",
        "Prompt crosstalk; S13360-3050CS spec ~3% typ, swept 0-15%.",
        env_list("CROSSTALK", [0.0, 0.03, 0.06, 0.10, 0.15]),
    ))
    knobs.append(Knob(
        "afterpulse", "env", "CCB_SIPM_AFTERPULSE_FAST_PROB", "prob",
        "Fast afterpulse; ~1% nominal, swept 0-8% (trap-density growth).",
        env_list("AFTERPULSE", [0.0, 0.01, 0.03, 0.05, 0.08]),
    ))
    knobs.append(Knob(
        "window_end", "env", "CCB_SIPM_WINDOW_END_NS", "ns",
        "Integration window end; 50-1000 ns (signal completeness vs dark noise).",
        env_list("WINDOW_END", [50.0, 100.0, 250.0, 500.0, 1000.0]),
    ))
    knobs.append(Knob(
        "birks_kB", "cli", "--birks-kB", "mm/MeV",
        "Birks kB; 0 = no quench, 0.126 nominal, 0.22 heavy quencher.",
        env_list("BIRKS_KB", [0.0, 0.08, 0.126, 0.17, 0.22]),
    ))
    knobs.append(Knob(
        "reflectivity", "cli", "--reflectivity-scale", "x TiO2",
        "TiO2 reflectivity scale; 0.6 degraded - 1.05 (upper tolerance).",
        env_list("REFLECTIVITY", [0.6, 0.8, 0.9, 1.0, 1.05]),
    ))
    knobs.append(Knob(
        "attenuation", "cli", "--attenuation-scale", "x attenuation len",
        "Y-11 attenuation-length scale; 0.5 high loss - 2.0 low loss.",
        env_list("ATTENUATION", [0.5, 0.75, 1.0, 1.5, 2.0]),
    ))
    knobs.append(Knob(
        "far_end", "cli", "--far-end", "mode",
        "Far-end boundary; absorb|open|mirror|instrumented (near/far split).",
        env_list("FAR_END", ["absorb", "open", "mirror", "instrumented"]),
    ))
    knobs.append(Knob(
        "sipm_n_cells", "cli", "--sipm-n-cells", "cells",
        "Microcell count for saturation; 1600-6400 (S13360-3050CS = 3600).",
        env_list("SIPM_N_CELLS", [1600, 2500, 3600, 4900, 6400]),
    ))
    return knobs


def emit(knob: Knob, outdir: Path, seed_replicates: List[int]) -> tuple[Path, list[dict]]:
    """Write grids/points_<knob>.csv with CRN replicates. Returns path + rows."""
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"points_{knob.name}.csv"
    lines = [
        f"# knob: {knob.name}",
        f"# channel: {knob.channel}  target: {knob.target}  unit: {knob.unit}",
        f"# rationale: {knob.rationale}",
        f"# base_cli: {BASE_CLI}",
        f"# default_nevents: {DEFAULT_NEVENTS}",
        f"# paired_seed_design: AF-036 / #984 common-random-number",
        f"# seed_replicates: {','.join(str(s) for s in seed_replicates)}",
        "# note: same replicate_seed is reused at every knob value (CRN pairing)",
        "# columns: label,seed,nevents,cli_args,env_vars",
        "# explicit triple encoded in label as knob=value__rep=<replicate_seed>",
        "label,seed,nevents,cli_args,env_vars",
    ]
    rows: list[dict] = []
    for replicate_seed in seed_replicates:
        for v in knob.values:
            sv = _to_str(v)
            label = f"{knob.name}={sv}__rep={replicate_seed}"
            seed = int(replicate_seed)
            cli = ""
            envv = ""
            if knob.channel == "cli":
                cli = f"{knob.target} {sv}"
            else:
                envv = f"{knob.target}={sv}"
            lines.append(f"{label},{seed},{DEFAULT_NEVENTS},{cli},{envv}")
            rows.append({
                "knob": knob.name,
                "value": v,
                "value_str": sv,
                "replicate_seed": seed,
                "seed": seed,
                "nevents": DEFAULT_NEVENTS,
                "label": label,
                "cli_args": cli,
                "env_vars": envv,
            })
    path.write_text("\n".join(lines) + "\n")
    return path, rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--outdir", "-o",
        default=str(Path(__file__).resolve().parent),
        help="directory for points_<knob>.csv (default: this dir)",
    )
    ap.add_argument(
        "--knobs", nargs="*",
        help="subset of knob names to emit (default: all)",
    )
    ap.add_argument(
        "--seed-replicates",
        default=None,
        help="comma-separated replicate seeds (overrides env)",
    )
    args = ap.parse_args()

    outdir = Path(args.outdir)
    if args.seed_replicates:
        seed_replicates = [
            int(float(t)) for t in re.split(r"[\s,]+", args.seed_replicates.strip()) if t
        ]
    else:
        seed_replicates = list(SEED_REPLICATES)
    if len(seed_replicates) < 2:
        print(
            "error: paired multi-seed design requires >=2 replicate seeds "
            f"(got {seed_replicates!r})",
            file=sys.stderr,
        )
        return 2
    if len(set(seed_replicates)) != len(seed_replicates):
        print("error: replicate seeds must be unique", file=sys.stderr)
        return 2

    knobs = build_knobs()
    if args.knobs:
        want = set(args.knobs)
        knobs = [k for k in knobs if k.name in want]
        missing = want - {k.name for k in knobs}
        if missing:
            print(f"error: unknown knob(s): {sorted(missing)}", file=sys.stderr)
            return 2

    manifest_rows = ["knob,channel,target,unit,npoints,n_replicates,rationale"]
    emitted = []
    all_triples: list[dict] = []
    for k in knobs:
        p, rows = emit(k, outdir, seed_replicates)
        emitted.append(p)
        all_triples.extend(rows)
        manifest_rows.append(
            f"{k.name},{k.channel},{k.target},{k.unit},"
            f"{len(k.values) * len(seed_replicates)},{len(seed_replicates)},"
            f'"{k.rationale}"'
        )
    (outdir / "MANIFEST.csv").write_text("\n".join(manifest_rows) + "\n")

    design = {
        "schema_version": "1.0.0",
        "contract_id": "PAIRED_MULTI_SEED_NUISANCE_SWEEP",
        "issue": "#984",
        "audit_id": "AF-036",
        "design": "common_random_number",
        "seed_replicates": seed_replicates,
        "invariant": (
            "Within each knob sweep, every value shares the same replicate_seed; "
            "uncertainty on nuisance response is estimated from seed-level paired "
            "effects, not only event-level SEM."
        ),
        "rows": all_triples,
    }
    (outdir / "PAIRED_SEED_DESIGN.json").write_text(
        json.dumps(design, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"emitted {len(emitted)} grids -> {outdir}")
    for p in emitted:
        print(f"  {p.name}")
    print("  MANIFEST.csv")
    print("  PAIRED_SEED_DESIGN.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
