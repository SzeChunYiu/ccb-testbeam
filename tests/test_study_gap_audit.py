"""Study implementation gap audit tests."""
from __future__ import annotations

from pathlib import Path

from ccb_mc_validation.reporting.study_gap_audit import generate_study_gap_audit


def test_generate_study_gap_audit_writes_fail_closed_readiness_map(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()

    audit = generate_study_gap_audit(run)

    assert audit["status"] == "PASS"
    assert audit["scope"] == "study-implementation-gap-audit"
    assert audit["all_study_implementations_ready"] is False
    assert audit["blocked_count"] == 5
    by_study = {gap["study"]: gap for gap in audit["studies"]}
    assert by_study["MV4"]["status"] == "BLOCKED"
    assert by_study["MV8"]["required_next_artifact"].endswith("MV8_DYNAMIC_RANGE_SCAN.json")

    out = run / "reports" / "mc_validation" / "open_questions"
    assert (out / "STUDY_IMPLEMENTATION_GAP_AUDIT.json").is_file()
    md = (out / "STUDY_IMPLEMENTATION_GAP_AUDIT.md").read_text(encoding="utf-8")
    assert "Study implementation gap audit" in md
    assert "not physics evidence" in md
