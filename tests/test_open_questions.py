"""Open-question registry tests."""
from __future__ import annotations

from pathlib import Path

from ccb_mc_validation.reporting.open_questions import generate_open_question_registry


def test_generate_open_question_registry_writes_recursive_plan(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    registry = generate_open_question_registry(run)
    assert registry["status"] == "PASS"
    assert registry["scope"] == "open-question-registry"
    assert registry["all_questions_closed"] is False
    assert registry["open_count"] >= 1
    out = run / "reports" / "mc_validation" / "open_questions"
    assert (out / "OPEN_QUESTIONS.json").is_file()
    text = (out / "OPEN_QUESTIONS.md").read_text(encoding="utf-8")
    assert "OQ-MV4" in text
    assert "recursive" in text.lower() or "Needed evidence" in text
