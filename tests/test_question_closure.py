"""Question closure plan tests."""
from __future__ import annotations

from pathlib import Path

from ccb_mc_validation.reporting.question_closure import generate_question_closure_plan


def test_generate_question_closure_plan_writes_dag_and_steps(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    plan = generate_question_closure_plan(run)
    assert plan["status"] == "PASS"
    assert plan["scope"] == "open-question-closure-plan"
    assert plan["all_steps_closed"] is False
    assert plan["step_count"] >= 7
    assert "flowchart TD" in plan["dag_mermaid"]
    out = run / "reports" / "mc_validation" / "open_questions"
    assert (out / "OPEN_QUESTION_CLOSURE_PLAN.json").is_file()
    text = (out / "OPEN_QUESTION_CLOSURE_PLAN.md").read_text(encoding="utf-8")
    assert "produce_mv4_timing_artifact" in text
    assert "terminal condition" in text.lower()
