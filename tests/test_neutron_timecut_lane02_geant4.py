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


# --- #1091 sensitivity ladder additions (2026-08-16) ---


def test_registry_wiring_policy():
    reg = json.loads(
        (REPO / "configs/transport/neutron_timecut_registry.json").read_text()
    )
    assert reg["policy_version"] == "2026.1-issue1091-ladder"
    p = reg["policies"]["wiring_test_1ns"]
    assert p["neutron_time_cut_us"] == 0.001
    assert p["status"] == "WIRING_TEST"
    assert p["claims_authorized"] is False


def test_policy_mirror_has_wiring_policy():
    t = (REPO / "geant4/single_stave/src/NeutronTimecutPolicy.cc").read_text()
    assert "wiring_test_1ns" in t
    assert "1.0e-3" in t


def test_neutron_diagnostics_surfaces():
    t = (REPO / "geant4/single_stave/src/AppConfig.cc").read_text()
    assert "--neutron-diagnostics" in t
    t2 = (REPO / "geant4/single_stave/src/RunAction.cc").read_text()
    assert "neutron_steps" in t2
    t3 = (REPO / "geant4/single_stave/src/SteppingAction.cc").read_text()
    assert "NeutronStepRecord" in t3
