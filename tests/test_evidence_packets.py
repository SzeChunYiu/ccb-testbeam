"""Open-question evidence packet tests."""
from __future__ import annotations

from pathlib import Path

from ccb_mc_validation.reporting.evidence_packets import generate_evidence_packets


def test_generate_evidence_packets_writes_fail_closed_packet_templates(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()

    packets = generate_evidence_packets(run)

    assert packets["status"] == "PASS"
    assert packets["scope"] == "open-question-evidence-packets"
    assert packets["all_packets_closed"] is False
    assert packets["packet_count"] == 7
    assert packets["open_packet_count"] == 7

    by_id = {packet["question_id"]: packet for packet in packets["packets"]}
    assert by_id["OQ-MV4"]["packet_status"] == "BLOCKED"
    assert "reports/mc_validation/leakage/MV4_TRUTH_BOUNDARY_AUDIT.json" in by_id["OQ-MV4"]["required_artifacts"]
    assert by_id["OQ-MV4"]["execution_hint"] == "CCB_RUN_ID=<run_id> sbatch --parsable geant4/jobs/mc_validation_pipeline.sbatch"
    assert "MV4 packet cannot close" in by_id["OQ-MV4"]["implementation_blocker"]
    assert "--studies" not in by_id["OQ-MV4"]["execution_hint"]
    assert "QA release audit rerun after artifact generation" in by_id["OQ-MV4"]["validation_gates"]

    out = run / "reports" / "mc_validation" / "open_questions"
    assert (out / "EVIDENCE_PACKETS.json").is_file()
    md = (out / "EVIDENCE_PACKETS.md").read_text(encoding="utf-8")
    assert "Open-question evidence packets" in md
    assert "OQ-MV8" in md
    assert "Implementation blocker" in md
    assert "BLOCKED" in md
