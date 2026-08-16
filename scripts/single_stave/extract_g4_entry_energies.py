#!/usr/bin/env python3
"""
Extract empirical B-stack entry kinematics from the full CCB Geant4 truth tree.

The repository's truth schema has varied across productions. This tool uses
explicit candidate branch names, prints the selected contract, and refuses to
guess when required fields are ambiguous.

Definition:
  An entry record is the earliest Sci_bar hit for a unique
  (event, arm, track_id, layer) tuple. This approximates the particle state at
  entry to that scintillator layer. A dedicated pre-step entry branch is
  preferable and should supersede this approximation when available.

Sample mimic:
  - Sample II inclusive: a charged particle reaches B-arm layer 0.
  - Sample I mimic: B-arm layer-0 and A-arm layer-0 charged hits occur within
    --coincidence-ns.
Both flags are saved. The analyst must compare this mimic to the production
trigger implementation before using it as a final sample label.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

MASS_MEV = {
    2212: 938.27208816,
    1000010020: 1875.61294257,
    1000010030: 2808.92113298,
    1000020030: 2808.39160743,
    1000020040: 3727.3794066,
}

CANDIDATES = {
    "track": ["Sci_bar_TrackID", "SciBar_TrackID"],
    "arm": ["Sci_bar_LayerID1", "SciBar_LayerID1", "Sci_bar_ArmID"],
    "layer": ["Sci_bar_LayerID", "SciBar_LayerID"],
    "pdg": ["Sci_bar_PDG", "SciBar_PDG"],
    "time": ["Sci_bar_Time", "SciBar_Time", "Sci_bar_GlobalTime"],
    "ekin": [
        "Sci_bar_EKin", "Sci_bar_Ekin", "Sci_bar_KE",
        "Sci_bar_KineticEnergy", "SciBar_EKin"
    ],
    "px": ["Sci_bar_Px", "Sci_bar_MomX", "Sci_bar_PX", "Sci_bar_Momentum_X"],
    "py": ["Sci_bar_Py", "Sci_bar_MomY", "Sci_bar_PY", "Sci_bar_Momentum_Y"],
    "pz": ["Sci_bar_Pz", "Sci_bar_MomZ", "Sci_bar_PZ", "Sci_bar_Momentum_Z"],
    "x": ["Sci_bar_X", "Sci_bar_PosX", "Sci_bar_PositionX"],
    "y": ["Sci_bar_Y", "Sci_bar_PosY", "Sci_bar_PositionY"],
    "z": ["Sci_bar_Z", "Sci_bar_PosZ", "Sci_bar_PositionZ"],
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--tree", default="hibeam")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--b-arm-id", type=int, default=1)
    p.add_argument("--a-arm-id", type=int, default=2)
    p.add_argument("--coincidence-ns", type=float, default=15.0)
    p.add_argument("--step-size", default="200 MB")
    p.add_argument("--max-events", type=int, default=0)
    # Momentum branch unit. The deployed krakow MC stores Sci_bar_Momentum_* in
    # GeV/c (proton |p| ~0.41 -> KE ~85 MeV); assuming MeV/c gives KE~0.
    p.add_argument("--momentum-unit", choices=["MeV", "GeV"], default="MeV",
                   help="unit of the Sci_bar momentum branches (krakow MC = GeV)")
    return p.parse_args()


def sha256(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def select_branch(keys: set[str], logical: str, required: bool) -> str | None:
    found = [c for c in CANDIDATES[logical] if c in keys]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        raise SystemExit(
            f"Ambiguous {logical} branches {found}. "
            "Edit the candidate contract or add a CLI override."
        )
    if required:
        raise SystemExit(
            f"Missing {logical} branch. Candidates: {CANDIDATES[logical]}"
        )
    return None


def charge(pdg: int) -> int:
    a = abs(int(pdg))
    if a > 1_000_000_000:
        return (a // 10_000) % 1000
    return 1 if a in {11, 13, 211, 321, 2212} else 0


def kinetic_from_momentum(pdg: int, px: float, py: float, pz: float) -> float:
    mass = MASS_MEV.get(abs(int(pdg)))
    if mass is None:
        return float("nan")
    p2 = px * px + py * py + pz * pz
    return math.sqrt(max(0.0, p2 + mass * mass)) - mass


def first_index_by_time(
    track: np.ndarray,
    arm: np.ndarray,
    layer: np.ndarray,
    time: np.ndarray,
) -> list[int]:
    best: dict[tuple[int, int, int], tuple[float, int]] = {}
    for i, (tr, ar, la, ti) in enumerate(zip(track, arm, layer, time)):
        key = (int(tr), int(ar), int(la))
        t = float(ti)
        if key not in best or t < best[key][0]:
            best[key] = (t, i)
    return [value[1] for value in best.values()]


def main() -> int:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    try:
        import awkward as ak
        import uproot
    except ImportError as exc:
        raise SystemExit("This tool requires uproot and awkward") from exc

    root = uproot.open(args.input)
    if args.tree not in root:
        candidates = [k.split(";")[0] for k, obj in root.items() if hasattr(obj, "iterate")]
        raise SystemExit(f"Tree {args.tree!r} not found. Candidates: {candidates}")
    tree = root[args.tree]
    keys = set(tree.keys())

    contract = {
        "track": select_branch(keys, "track", True),
        "arm": select_branch(keys, "arm", True),
        "layer": select_branch(keys, "layer", True),
        "pdg": select_branch(keys, "pdg", True),
        "time": select_branch(keys, "time", True),
        "ekin": select_branch(keys, "ekin", False),
        "px": select_branch(keys, "px", False),
        "py": select_branch(keys, "py", False),
        "pz": select_branch(keys, "pz", False),
        "x": select_branch(keys, "x", False),
        "y": select_branch(keys, "y", False),
        "z": select_branch(keys, "z", False),
    }
    have_momentum = all(contract[k] is not None for k in ("px", "py", "pz"))
    pscale = 1000.0 if args.momentum_unit == "GeV" else 1.0  # -> MeV/c
    if contract["ekin"] is None and not have_momentum:
        raise SystemExit(
            "Need an explicit kinetic-energy branch or all three momentum components."
        )

    read_branches = sorted({v for v in contract.values() if v is not None})
    print(json.dumps({"branch_contract": contract}, indent=2))

    rows: list[dict] = []
    event_offset = 0
    entry_stop = args.max_events if args.max_events > 0 else None

    # NB: uproot's ``report=True`` (yielding (arrays, Report) pairs) is not
    # implemented in current uproot releases, so we track the global event
    # offset manually. ``event_offset`` equals the chunk's global start index
    # (report.start), preserving the original global event_id semantics.
    for arrays in tree.iterate(
        read_branches,
        step_size=args.step_size,
        entry_stop=entry_stop,
        library="ak",
    ):
        n_events = len(arrays[contract["track"]])
        for local_event in range(n_events):
            event_id = int(event_offset + local_event)
            def event_array(logical: str, dtype=float):
                b = contract[logical]
                if b is None:
                    return None
                return np.asarray(ak.to_list(arrays[b][local_event]), dtype=dtype)

            track = event_array("track", np.int64)
            arm = event_array("arm", np.int64)
            layer = event_array("layer", np.int64)
            pdg = event_array("pdg", np.int64)
            time = event_array("time", float)
            if track is None or len(track) == 0:
                continue
            lengths = {len(track), len(arm), len(layer), len(pdg), len(time)}
            if len(lengths) != 1:
                raise RuntimeError(
                    f"Jagged branch length mismatch at event {event_id}: {lengths}"
                )

            charged = np.array([charge(v) > 0 for v in pdg], dtype=bool)
            b0 = charged & (arm == args.b_arm_id) & (layer == 0)
            a0 = charged & (arm == args.a_arm_id) & (layer == 0)
            enter_b = bool(b0.any())
            enter_a = bool(a0.any())
            t_b = float(np.min(time[b0])) if enter_b else float("nan")
            t_a = float(np.min(time[a0])) if enter_a else float("nan")
            sample_i_mimic = bool(
                enter_a and enter_b and abs(t_a - t_b) < args.coincidence_ns
            )

            ekin = event_array("ekin", float)
            px = event_array("px", float)
            py = event_array("py", float)
            pz = event_array("pz", float)
            xpos = event_array("x", float)
            ypos = event_array("y", float)
            zpos = event_array("z", float)

            for i in first_index_by_time(track, arm, layer, time):
                if int(arm[i]) != args.b_arm_id or not charged[i]:
                    continue
                p = int(pdg[i])
                if ekin is not None:
                    ke = float(ekin[i])
                    ke_source = contract["ekin"]
                else:
                    ke = kinetic_from_momentum(
                        p, float(px[i]) * pscale, float(py[i]) * pscale,
                        float(pz[i]) * pscale
                    )
                    ke_source = f"computed_from_momentum_{args.momentum_unit}_c"

                p_mag = float("nan")
                ux = uy = uz = float("nan")
                if have_momentum:
                    p_mag = float(
                        math.sqrt(px[i] ** 2 + py[i] ** 2 + pz[i] ** 2)
                    ) * pscale
                    if p_mag > 0:
                        ux, uy, uz = (
                            float(px[i] / p_mag),
                            float(py[i] / p_mag),
                            float(pz[i] / p_mag),
                        )

                rows.append(
                    {
                        "file_path": str(args.input.resolve()),
                        "event_id": event_id,
                        "track_id": int(track[i]),
                        "arm_id": int(arm[i]),
                        "layer_id": int(layer[i]),
                        "particle_pdg": p,
                        "kinetic_energy_MeV": ke,
                        "kinetic_energy_source": ke_source,
                        "entry_time_ns": float(time[i]),
                        "global_x": float(xpos[i]) if xpos is not None else np.nan,
                        "global_y": float(ypos[i]) if ypos is not None else np.nan,
                        "global_z": float(zpos[i]) if zpos is not None else np.nan,
                        "momentum_MeV_c": p_mag,
                        "direction_x": ux,
                        "direction_y": uy,
                        "direction_z": uz,
                        "sample_II_inclusive_mimic": enter_b,
                        "sample_I_coincidence_mimic": sample_i_mimic,
                        "event_has_A_entry": enter_a,
                        "event_has_B_entry": enter_b,
                        "A_B_first_time_difference_ns": (
                            t_a - t_b if enter_a and enter_b else np.nan
                        ),
                    }
                )
        event_offset += n_events

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("No B-arm charged entry records were extracted.")

    if not np.isfinite(df["kinetic_energy_MeV"]).any():
        raise SystemExit("All extracted kinetic energies are non-finite.")

    try:
        df.to_parquet(args.output, index=False)
        actual_output = args.output
    except Exception:
        actual_output = args.output.with_suffix(".csv.gz")
        df.to_csv(actual_output, index=False)

    summary_rows = []
    for keys_, g in df.groupby(
        ["particle_pdg", "layer_id", "sample_I_coincidence_mimic"],
        dropna=False,
    ):
        particle, layer_id, sample_i = keys_
        x = g["kinetic_energy_MeV"].dropna().to_numpy(float)
        if len(x) == 0:
            continue
        q = np.percentile(x, [5, 16, 50, 84, 95])
        summary_rows.append(
            {
                "particle_pdg": int(particle),
                "layer_id": int(layer_id),
                "sample_I_coincidence_mimic": bool(sample_i),
                "n_entries": int(len(x)),
                "ke_p05_MeV": float(q[0]),
                "ke_p16_MeV": float(q[1]),
                "ke_median_MeV": float(q[2]),
                "ke_p84_MeV": float(q[3]),
                "ke_p95_MeV": float(q[4]),
                "ke_mean_MeV": float(np.mean(x)),
                "ke_std_MeV": float(np.std(x)),
            }
        )
    summary_path = actual_output.with_name(actual_output.stem + "_summary.csv")
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)

    meta = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input.resolve()),
        "input_sha256": sha256(args.input),
        "tree": args.tree,
        "branch_contract": contract,
        "definition": "earliest hit by (event,arm,track,layer)",
        "b_arm_id": args.b_arm_id,
        "a_arm_id": args.a_arm_id,
        "coincidence_ns": args.coincidence_ns,
        "n_rows": int(len(df)),
        "n_events_with_rows": int(df["event_id"].nunique()),
        "output": str(actual_output),
        "summary": str(summary_path),
        "caveat": (
            "Earliest Sci_bar hit approximates layer entry. Replace with a true "
            "pre-step entry branch if available. Sample flags are trigger mimics."
        ),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
    }
    meta_path = actual_output.with_name(actual_output.stem + "_metadata.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
