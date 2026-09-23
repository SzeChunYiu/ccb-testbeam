#!/usr/bin/env python3
"""Guard evidence-class boundaries in paper/hardware_bom.csv."""
from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BOM = ROOT / "paper/hardware_bom.csv"

EXPECTED = {
    "waveform_samples_per_channel_raw": ("16", "RETRACTED_TRUNCATED_STAGING"),
    "waveform_samples_per_channel_historical": ("18", "GATED_DATA_PRODUCT"),
    "waveform_channels_per_event": ("8", "GATED_DATA_PRODUCT"),
    "pulse_selection_threshold": ("1000", "ANALYSIS_CONFIG"),
    "Sample_I_calibration_runs": ("31-37,39-42", "ANALYSIS_CONFIG"),
    "Sample_I_analysis_runs": ("44-57", "ANALYSIS_CONFIG"),
    "Sample_II_calibration_runs": ("64", "ANALYSIS_CONFIG"),
    "Sample_II_analysis_runs": ("58-63,65", "ANALYSIS_CONFIG"),
}


def main() -> int:
    with BOM.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    by_component = {row["component"]: row for row in rows}
    errors: list[str] = []
    for component, (value, status) in EXPECTED.items():
        row = by_component.get(component)
        if row is None:
            errors.append(f"missing BOM row {component}")
            continue
        if row.get("value") != value:
            errors.append(f"{component}.value={row.get('value')!r}, expected {value!r}")
        if row.get("status") != status:
            errors.append(f"{component}.status={row.get('status')!r}, expected {status!r}")
    raw = by_component.get("waveform_samples_per_channel_raw", {})
    if raw.get("status") == "MEASURED":
        errors.append("known-truncated 8x16 staging waveform must never be restored to MEASURED")
    if "truncated" not in (raw.get("notes") or "").lower():
        errors.append("8x16 staging row must retain explicit truncation warning")
    hardware = by_component.get("hardware_evidence_report", {})
    if "conflicts resolved" in (hardware.get("notes") or "").lower():
        errors.append("hardware evidence report must not claim unresolved external conflicts are resolved")

    if errors:
        print("HARDWARE_BOM_EVIDENCE_CLASSES: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("HARDWARE_BOM_EVIDENCE_CLASSES: PASS")
    print("Known truncated/data-analysis quantities cannot masquerade as measured hardware facts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
