from __future__ import annotations
import json
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
import sys; sys.path.insert(0, str(REPO / "tools/audit")); import validate_neutron_tracking_time_cut as v

def test_lane02_appconfig_flag():
    t = (REPO / "geant4/single_stave/src/AppConfig.cc").read_text()
    assert "--neutron-timecut-policy-id" in t

def test_lane02_main_ui():
    t = (REPO / "geant4/single_stave/src/main.cc").read_text()
    assert "/physics_engine/neutron/timeLimit" in t

def test_lane02_configured_contract():
    c = json.loads((REPO / "docs/contracts/NEUTRON_TRACKING_TIME_CUT.json").read_text())
    m = {"physics_list": "QGSP_BIC", "neutron_tracking_time_cut_us": 10.0, "neutron_tracking_time_cut_status": "PINNED_REFERENCE_DEFAULT", "neutron_tracking_time_cut_configured": True}
    assert v.validate(m, c)["status"] == "PASS"
