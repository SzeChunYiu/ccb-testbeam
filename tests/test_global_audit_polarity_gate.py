from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from sipm_waveC_gates import polarity_authorisation_report  # noqa: E402


def test_duplicate_readout_convention_is_not_authorising() -> None:
    report = polarity_authorisation_report("LOCKED_FROM_DUPLICATE_READOUT_CONVENTION")
    assert report["authorising_waveform_amplitude_claims"] is False
    assert report["blocked_reasons"]


def test_gated_v1_map_is_not_authorising() -> None:
    payload = json.loads((ROOT / "configs/channel_polarity_v1.json").read_text())
    assert payload["status"] == "GATED_FROM_DUPLICATE_READOUT_CONVENTION"
    assert payload["provenance"]["authorising_for_even_b_staves"] is False
    assert payload["provenance"]["authorising_for_odd_duplicates"] is False
    report = polarity_authorisation_report(payload["status"])
    assert report["authorising_waveform_amplitude_claims"] is False


def test_only_independently_measured_status_authorises() -> None:
    report = polarity_authorisation_report("LOCKED_FROM_MEASUREMENT")
    assert report["authorising_waveform_amplitude_claims"] is True
    assert report["blocked_reasons"] == []
