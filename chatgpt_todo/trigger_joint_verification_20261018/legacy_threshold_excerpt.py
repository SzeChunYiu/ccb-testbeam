"""Named function bodies transcribed from a connector-read pinned source.

Origin scripts/trigger_threshold_scan.py@223280d03a86d74d1656b70528fc17eb4f87984e
Full source blob 6edc498d53df882ddc17377b7453a953ef8ca67c.
Imports injected; this is NOT the full module/CLI/ROOT or hardware execution.
"""
from typing import Dict, Optional
import numpy as np


def classify_event_hardware_response(
    t1_edep: np.ndarray,
    t1_time: np.ndarray,
    t2_edep: np.ndarray,
    t2_time: np.ndarray,
    threshold_mev: float,
    coinc_ns: float,
) -> Dict[str, bool]:
    t1_pass = (t1_edep >= threshold_mev).any() if len(t1_edep) > 0 else False
    t2_pass = (t2_edep >= threshold_mev).any() if len(t2_edep) > 0 else False
    if t1_pass and t2_pass:
        t1_earliest = float(t1_time[t1_edep >= threshold_mev].min())
        t2_earliest = float(t2_time[t2_edep >= threshold_mev].min())
        if np.isfinite(t1_earliest) and np.isfinite(t2_earliest):
            coinc = abs(t1_earliest - t2_earliest) < coinc_ns
        else:
            coinc = False
    else:
        coinc = False
    return {"t1_above_threshold": t1_pass,
            "t2_above_threshold": t2_pass, "coincidence": coinc}


def get_primary_species(pdg_array: np.ndarray) -> Optional[int]:
    if len(pdg_array) == 0:
        return None
    CHARGED_PDG = {
        2212, 1000010020, 1000010030, 1000020030, 1000020040,
        11, -11, 13, -13, 211, -211, 321, -321,
        1000060120, 1000060130, 1000060140,
    }
    for p in pdg_array:
        if int(p) in CHARGED_PDG:
            return int(p)
    return None
