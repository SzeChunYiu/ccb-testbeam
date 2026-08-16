from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "single_stave"
    / "adapt_geant4_events.py"
)


def test_cli_publishes_current_analyzer_contract(tmp_path: Path):
    input_path = tmp_path / "events.csv"
    output_path = tmp_path / "normalized.csv"
    metadata_path = tmp_path / "normalized.meta.json"
    pd.DataFrame(
        {
            "event": [0],
            "particle": ["proton"],
            "ke_MeV": [100.0],
            "edep_scint_MeV": [12.5],
            "n_scint_generated": [10],
            "n_wls_generated": [5],
            "n_cerenkov_generated": [0],
            "arrival_readout": [12],
            "detected_readout": [4],
        }
    ).to_csv(input_path, index=False)

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--metadata",
            str(metadata_path),
            "--run-id",
            "metadata-contract",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "ccb-single-stave-event-adapter/2"
    assert payload["version"] == "1.1.0"
    assert payload["analysis_compatibility"] == (
        "SCHEMA_AND_OPTICAL_BOOKKEEPING_COMPATIBLE"
    )
    assert "downstream_blocker" not in payload
    assert payload["downstream_analyzer_contract"] == {
        "version": "2.1.0",
        "policy": "ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL_AND_DECLARE_EXPLICIT_ENERGY_TARGET",
        "optical_generation_contract": "CURRENT_COMPONENT_SUM",
        "collection_efficiency_denominator": "n_optical_generated_total",
        "acceptance": "SOFTWARE_CONTRACT_VALIDATED_REAL_ROOT_PENDING",
    }
    assert "Immutable real ROOT" in payload["scientific_boundary"]
    assert payload["output"]["rows"] == 1
