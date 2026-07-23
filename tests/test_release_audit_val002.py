from ccb_mc_validation.reporting.release_audit import study_release_check, PASS, BLOCKED

def test_production_no_blocker_passes():
    assert study_release_check("MV1", {"status": "PRODUCTION"})["status"] == PASS

def test_blocked_by_fails_even_if_production():
    r = study_release_check("MV1", {"status": "PRODUCTION", "blocked_by": "geometry"})
    assert r["status"] == BLOCKED and "blocked_by" in r["reason"]

def test_ml_error_fails_even_if_production():
    r = study_release_check("MV2", {"status": "PRODUCTION", "_ml_error": "oops"})
    assert r["status"] == BLOCKED and "_ml_error" in r["reason"]

def test_non_production_fails():
    assert study_release_check("MV3", {"status": "NOT_RUN"})["status"] == BLOCKED
    assert study_release_check("MV3", {})["status"] == BLOCKED
