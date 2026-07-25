"""Shared helpers for CCB single-stave campaign and VIS-MC plotters."""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import uproot

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.audit.validate_pstar_component_sum import (  # noqa: E402
    PstarComponentError,
    TOOL_VERSION as PSTAR_VALIDATOR_VERSION,
    read_validated_pstar_table,
)

I885 = "/projects/hep/fs10/shared/nnbar/billy/ccb-runs/i885_v1"
BIRKS = "/projects/hep/fs10/shared/nnbar/billy/ccb-runs/an3/sys_birks_smoke2"
SIPM = "/projects/hep/fs10/shared/nnbar/billy/ccb-runs/sipm-p2-001"
KRAKOW = (
    "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/"
    "geant4/data/output_krakow_1M.root"
)
PSTAR_REFERENCE = (
    REPO_ROOT / "data" / "reference" / "stopping_power" / "pstar_polystyrene.csv"
)
POLYSTYRENE_DENSITY_G_PER_CM3 = 1.060
PSTAR_INTERPOLATION = "LOG_LINEAR_IN_ENERGY_AND_TOTAL_MASS_STOPPING_POWER"
PSTAR_RANGE_POLICY = "FAIL_CLOSED_OUTSIDE_VALIDATED_REFERENCE_DOMAIN"


@dataclass
class RunMeta:
    path: str
    particle: str
    ke_MeV: float
    x_mm: float
    seed: int
    meta: dict


def parse_i885(filename: str) -> RunMeta | None:
    basename = os.path.basename(filename)
    match = re.match(r"stave_(\w+?)_(\d+)MeV_x([\-\d.]+)_s(\d+)\.root", basename)
    if not match:
        return None
    particle = match.group(1)
    ke = int(match.group(2))
    x_position = float(match.group(3))
    seed = int(match.group(4))
    metadata = {}
    metadata_path = filename + ".meta.json"
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, encoding="utf-8") as handle:
                metadata = json.load(handle)
        except (OSError, json.JSONDecodeError):
            pass
    return RunMeta(filename, particle, ke, x_position, seed, metadata)


def iter_i885() -> list[RunMeta]:
    runs = []
    for filename in sorted(glob.glob(os.path.join(I885, "stave_*.root"))):
        run = parse_i885(filename)
        if run:
            runs.append(run)
    return runs


def parse_birks(filename: str) -> RunMeta | None:
    basename = os.path.basename(filename)
    match = re.match(r"sys_birks_kB(\d+)_s(\d+)\.root", basename)
    if not match:
        return None
    metadata = {}
    metadata_path = filename + ".meta.json"
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, encoding="utf-8") as handle:
                metadata = json.load(handle)
        except (OSError, json.JSONDecodeError):
            pass
    ke = float(metadata.get("kinetic_energy_MeV", 100.0))
    return RunMeta(filename, "proton", ke, 0.0, int(match.group(2)), metadata)


def iter_birks() -> list[RunMeta]:
    runs = []
    pattern = os.path.join(BIRKS, "sys_birks_kB*.root")
    for filename in sorted(glob.glob(pattern)):
        run = parse_birks(filename)
        if run:
            runs.append(run)
    return runs


def load_events(path: str) -> dict[str, np.ndarray]:
    with uproot.open(path) as handle:
        return handle["events"].arrays(library="np")


def load_photons(path: str) -> dict[str, np.ndarray]:
    with uproot.open(path) as handle:
        return handle["photons"].arrays(library="np")


def sipm_subdirs() -> list[str]:
    return [
        directory
        for directory in sorted(os.listdir(SIPM))
        if os.path.isdir(os.path.join(SIPM, directory))
    ]


def load_sipm_knob(subdirectory: str) -> dict:
    rows = []
    for filename in sorted(glob.glob(os.path.join(SIPM, subdirectory, "*.root"))):
        try:
            events = load_events(filename)
        except Exception:
            continue
        metadata = {}
        metadata_path = filename + ".meta.json"
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, encoding="utf-8") as handle:
                    metadata = json.load(handle)
            except (OSError, json.JSONDecodeError):
                pass
        rows.append({"path": filename, "events": events, "meta": metadata})
    return {"sub": subdirectory, "rows": rows}


@lru_cache(maxsize=4)
def _validated_pstar(reference_path: str) -> tuple[np.ndarray, dict[str, object]]:
    path = Path(reference_path)
    try:
        rows, provenance = read_validated_pstar_table(path)
    except PstarComponentError as exc:
        raise ValueError(f"invalid canonical PSTAR reference {path}: {exc}") from exc
    return np.asarray(rows, dtype=float), provenance


def pstar_reference_provenance(
    reference_path: Path = PSTAR_REFERENCE,
) -> dict[str, object]:
    """Return exact canonical-reference provenance used by campaign plotters."""
    rows, provenance = _validated_pstar(str(Path(reference_path)))
    result = dict(provenance)
    result.update(
        {
            "reference_path": str(Path(reference_path)),
            "reference_validator_version": PSTAR_VALIDATOR_VERSION,
            "reference_rows_loaded": int(rows.shape[0]),
            "density_g_cm3": POLYSTYRENE_DENSITY_G_PER_CM3,
            "interpolation": PSTAR_INTERPOLATION,
            "range_policy": PSTAR_RANGE_POLICY,
            "stopping_power_column": "total_MeV_cm2_g",
        }
    )
    return result


def pstar_dEdx_MeV_per_mm(
    ke_MeV: np.ndarray,
    reference_path: Path = PSTAR_REFERENCE,
) -> np.ndarray:
    """Interpolate validated PSTAR total mass stopping power into MeV/mm."""
    query = np.asarray(ke_MeV, dtype=float)
    if query.ndim == 0:
        query = query.reshape(1)
    if not np.isfinite(query).all() or (query <= 0).any():
        raise ValueError("PSTAR lookup energies must be finite and positive")
    rows, _ = _validated_pstar(str(Path(reference_path)))
    energy = rows[:, 0]
    total_mass_stopping = rows[:, 3]
    if query.min() < energy.min() or query.max() > energy.max():
        raise ValueError(
            "PSTAR lookup outside validated energy range "
            f"[{energy.min()}, {energy.max()}] MeV"
        )
    interpolated = np.exp(
        np.interp(np.log(query), np.log(energy), np.log(total_mass_stopping))
    )
    return interpolated * POLYSTYRENE_DENSITY_G_PER_CM3 / 10.0


def ccb_style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
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
        }
    )
    return plt
