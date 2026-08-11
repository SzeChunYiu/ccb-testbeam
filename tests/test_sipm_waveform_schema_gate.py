"""Fail-closed gate for SiPM waveform / DAQ schema (#1009)."""
from __future__ import annotations

import json


def waveform_claims_authorised(meta: dict) -> bool:
    dig = meta.get("digitizer") or {}
    if dig.get("daq_digitizer_schema") in (None, "", "UNSET"):
        return False
    if dig.get("authorising_waveform_claims") is not True:
        return False
    if dig.get("waveform_persistence") in (None, "", "PEAK_ONLY_DISCARDED"):
        return False
    return True


def test_unset_schema_rejects_waveform_claims():
    meta = {
        "digitizer": {
            "validation_status": "OK",
            "waveform_persistence": "PEAK_ONLY_DISCARDED",
            "daq_digitizer_schema": "UNSET",
            "authorising_waveform_claims": False,
        }
    }
    assert waveform_claims_authorised(meta) is False


def test_authorising_requires_explicit_schema_and_persistence():
    meta = {
        "digitizer": {
            "validation_status": "OK",
            "waveform_persistence": "INTERNAL_AND_DAQ",
            "daq_digitizer_schema": "hrd_8x16_v1",
            "authorising_waveform_claims": True,
        }
    }
    assert waveform_claims_authorised(meta) is True


def test_json_roundtrip_example():
    raw = json.dumps(
        {
            "digitizer": {
                "waveform_persistence": "PEAK_ONLY_DISCARDED",
                "daq_digitizer_schema": "UNSET",
                "authorising_waveform_claims": False,
            }
        }
    )
    assert waveform_claims_authorised(json.loads(raw)) is False
