"""Neutron tracking-time cut provenance (#1091)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "audit"))
import validate_neutron_tracking_time_cut as v  # noqa: E402


def test_unconfigured_implicit_default_pass():
    contract = json.loads((REPO / "docs/contracts/NEUTRON_TRACKING_TIME_CUT.json").read_text(encoding="utf-8"))
    meta = {
        "physics_list": "QGSP_BIC",
        "neutron_tracking_time_cut_us": 10.0,
        "neutron_tracking_time_cut_status": "IMPLICIT_QGSP_BIC_REFERENCE_DEFAULT",
        "neutron_tracking_time_cut_configured": False,
    }
    assert v.validate(meta, contract)["status"] == "PASS"


def test_authorising_delayed_neutron_blocked_when_unconfigured():
    contract = json.loads((REPO / "docs/contracts/NEUTRON_TRACKING_TIME_CUT.json").read_text(encoding="utf-8"))
    meta = {
        "physics_list": "QGSP_BIC",
        "neutron_tracking_time_cut_us": 10.0,
        "neutron_tracking_time_cut_status": "IMPLICIT_QGSP_BIC_REFERENCE_DEFAULT",
        "neutron_tracking_time_cut_configured": False,
        "authorising_delayed_neutron_claim": True,
    }
    assert v.validate(meta, contract)["status"] == "BLOCKED"
