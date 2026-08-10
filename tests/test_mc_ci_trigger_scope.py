from pathlib import Path

import pytest

from tools.audit.validate_mc_ci_trigger_scope import validate_trigger_scope


WORKFLOW = Path(".github/workflows/mc_validation_ci.yml")


def test_repository_workflow_routes_geant4_to_required_test() -> None:
    result = validate_trigger_scope(WORKFLOW)
    assert result["status"] == "PASS"
    assert result["required_job"] == "test"
    assert result["events"]["push"]["pattern_present"] is True
    assert result["events"]["pull_request"]["pattern_present"] is True


def test_missing_pull_request_geant4_route_fails_closed(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        """name: test\non:\n  push:\n    paths: [\"geant4/**\"]\n  pull_request:\n    paths: [\"src/**\"]\njobs:\n  test:\n    runs-on: ubuntu-latest\n""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="pull_request.*geant4"):
        validate_trigger_scope(workflow)


def test_missing_required_test_job_fails_closed(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        """name: test\non:\n  push:\n    paths: [\"geant4/**\"]\n  pull_request:\n    paths: [\"geant4/**\"]\njobs:\n  other:\n    runs-on: ubuntu-latest\n""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="required workflow job"):
        validate_trigger_scope(workflow)
