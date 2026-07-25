"""Shared helpers for CCB single-stave campaign + VIS-MC plotters."""
from __future__ import annotations
import os, re, glob, json
from dataclasses import dataclass
from typing import Iterable
import numpy as np
import uproot

I885 = "/projects/hep/fs10/shared/nnbar/billy/ccb-runs/i885_v1"
BIRKS = "/projects/hep/fs10/shared/nnbar/billy/ccb-runs/an3/sys_birks_smoke2"
SIPM = "/projects/hep/fs10/shared/nnbar/billy/ccb-runs/sipm-p2-001"
KRAKOW = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root"

@dataclass
class RunMeta:
    path: str
    particle: str
    ke_MeV: float
    x_mm: float
    seed: int
    meta: dict

def parse_i885(filename: str) -> RunMeta | None:
    b = os.path.basename(filename)
    m = re.match(r"stave_(\w+?)_(\d+)MeV_x([\-\d.]+)_s(\d+)\.root", b)
    if not m:
        return None
    particle, ke, x, seed = m.group(1), int(m.group(2)), float(m.group(3)), int(m.group(4))
    meta = {}
    mf = filename + ".meta.json"
    if os.path.exists(mf):
        try:
            meta = json.load(open(mf))
        except Exception:
            pass
    return RunMeta(filename, particle, ke, x, seed, meta)

def iter_i885() -> list[RunMeta]:
    out = []
    for f in sorted(glob.glob(os.path.join(I885, "stave_*.root"))):
        r = parse_i885(f)
        if r:
            out.append(r)
    return out

def parse_birks(filename: str) -> RunMeta | None:
    b = os.path.basename(filename)
    m = re.match(r"sys_birks_kB(\d+)_s(\d+)\.root", b)
    if not m:
        return None
    kb = int(m.group(1)) / 1000.0  # kB code in mdeg of mm/MeV; e.g. 0100 -> 0.100
    meta = {}
    mf = filename + ".meta.json"
    if os.path.exists(mf):
        try:
            meta = json.load(open(mf))
        except Exception:
            pass
    # Birks smoke uses 100 MeV protons; KE from meta if present
    ke = float(meta.get("kinetic_energy_MeV", 100.0))
    seed = int(m.group(2))
    return RunMeta(filename, "proton", ke, 0.0, seed, meta)

def iter_birks() -> list[RunMeta]:
    out = []
    for f in sorted(glob.glob(os.path.join(BIRKS, "sys_birks_kB*.root"))):
        r = parse_birks(f)
        if r:
            out.append(r)
    return out

def load_events(path: str) -> dict[str, np.ndarray]:
    with uproot.open(path) as fh:
        tree = fh["events"]
        return tree.arrays(library="np")

def load_photons(path: str) -> dict[str, np.ndarray]:
    with uproot.open(path) as fh:
        tree = fh["photons"]
        return tree.arrays(library="np")

def sipm_subdirs() -> list[str]:
    out = []
    for d in sorted(os.listdir(SIPM)):
        if os.path.isdir(os.path.join(SIPM, d)):
            out.append(d)
    return out

def load_sipm_knob(sub: str) -> dict:
    """Load all root files for one SiPM knob subdir + meta JSON."""
    rows = []
    for f in sorted(glob.glob(os.path.join(SIPM, sub, "*.root"))):
        try:
            ev = load_events(f)
        except Exception:
            continue
        meta = {}
        mf = f + ".meta.json"
        if os.path.exists(mf):
            try: meta = json.load(open(mf))
            except Exception: pass
        rows.append({"path": f, "events": ev, "meta": meta})
    return {"sub": sub, "rows": rows}

# Minimal NIST PSTAR polystyrene reference (MeV, stopping_mm) — published NIST values
# for polystyrene (C8H8)n, density 1.06 g/cm^3. Stopping power in MeV cm^2/g.
# Reference: https://physics.nist.gov/PhysRefData/Star/Text/PSTAR.html
PSTAR_POLYSTYRENE = [
    # (KE MeV, mass_stopping_power MeV*cm^2/g)
    (1.0,   259.0),
    (1.5,   196.0),
    (2.0,   159.0),
    (3.0,   117.0),
    (5.0,    81.7),
    (8.0,    58.4),
    (10.0,   50.5),
    (15.0,   40.0),
    (20.0,   33.7),
    (25.0,   29.6),
    (30.0,   26.7),
    (40.0,   22.6),
    (50.0,   19.8),
    (60.0,   17.8),
    (80.0,   14.9),
    (100.0,  12.9),
    (120.0,  11.4),
    (150.0,   9.74),
    (180.0,   8.51),
    (200.0,   7.83),
]
POLYSTYRENE_DENSITY_G_PER_CM3 = 1.06  # g/cm^3

def pstar_dEdx_MeV_per_mm(ke_MeV: np.ndarray) -> np.ndarray:
    """Interpolate PSTAR mass stopping power -> MeV/mm at given KE."""
    src = np.array(PSTAR_POLYSTYRENE)
    log_ke_src = np.log(src[:, 0])
    log_sp_src = np.log(src[:, 1])
    out = np.interp(np.log(np.clip(ke_MeV, src[:, 0].min(), src[:, 0].max())),
                    log_ke_src, log_sp_src)
    mass_sp = np.exp(out)  # MeV*cm^2/g
    return mass_sp * POLYSTYRENE_DENSITY_G_PER_CM3 / 10.0  # MeV/mm

def ccb_style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.figsize": (8.0, 5.5),
        "figure.dpi": 130,
        "savefig.dpi": 130,
        "savefig.bbox": "tight",
        "font.size": 10,
        "axes.grid": True,
        "grid.alpha": 0.35,
        "axes.axisbelow": True,
        "legend.frameon": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
    return plt
