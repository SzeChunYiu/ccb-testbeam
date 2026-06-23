"""S00 selected-pulse contract reader/writer stubs with truth columns."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ccb_mc_validation.io.artifact_store import atomic_write

# Truth columns use the ``truth_`` prefix so they can ride alongside S00 pulse
# columns without name collisions in downstream pandas joins.
TRUTH_PULSE_COLUMNS: tuple[str, ...] = (
    "truth_pdg",
    "truth_species",
    "truth_ekin_mev",
    "truth_edep_l0_mev",
    "truth_edep_tot_mev",
    "truth_stop_layer",
    "truth_sample_I",
    "truth_sample_II",
)

S00_BASE_COLUMNS: tuple[str, ...] = (
    "run",
    "event_id",
    "stave",
    "amplitude_adc",
    "time_ns",
)


def read_pulse_table(path: Path | str) -> pd.DataFrame:
    """Read an S00-compatible pulse table (CSV or CSV.GZ)."""
    path = Path(path)
    if path.suffix == ".gz":
        return pd.read_csv(path, compression="gzip")
    return pd.read_csv(path)


def write_pulse_table(path: Path | str, frame: pd.DataFrame) -> None:
    """Write a pulse table atomically, preserving S00 + truth columns."""
    path = Path(path)

    def _write(tmp: Path) -> None:
        if path.suffix == ".gz" or str(path).endswith(".csv.gz"):
            frame.to_csv(tmp, index=False, compression="gzip")
        else:
            frame.to_csv(tmp, index=False)

    atomic_write(path, _write)


def attach_truth_columns(
    pulses: pd.DataFrame,
    truth_by_event: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """Join truth fields onto an S00 pulse table by ``event_id``."""
    out = pulses.copy()
    for col in TRUTH_PULSE_COLUMNS:
        out[col] = np.nan if col not in ("truth_sample_I", "truth_sample_II") else False
    for idx, row in out.iterrows():
        ev = str(row.get("event_id", ""))
        truth = truth_by_event.get(ev)
        if truth is None:
            continue
        out.at[idx, "truth_pdg"] = truth.get("pdg", np.nan)
        out.at[idx, "truth_species"] = truth.get("species", "")
        out.at[idx, "truth_ekin_mev"] = truth.get("ekin", np.nan)
        out.at[idx, "truth_edep_l0_mev"] = truth.get("edep_l0", np.nan)
        out.at[idx, "truth_edep_tot_mev"] = truth.get("edep_tot", np.nan)
        out.at[idx, "truth_stop_layer"] = truth.get("stop_layer", np.nan)
        out.at[idx, "truth_sample_I"] = bool(truth.get("sample_I", False))
        out.at[idx, "truth_sample_II"] = bool(truth.get("sample_II", False))
    return out
