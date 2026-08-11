from pathlib import Path

import pytest

from tools.audit.validate_mc_ci_trigger_scope import validate_trigger_scope

WORKFLOW = Path(".github/workflows/mc_validation_ci.yml")


def test_repository_workflow_routes_geant4_and_never_filters_prs() -> None:
    result = validate_trigger_scope(WORKFLOW)
    assert result["status"] == "PASS"
    assert result["required_job"] == "test"
    assert result["push"]["pattern_present"] is True
    assert result["pull_request"]["unfiltered"] is True


def test_missing_push_geant4_route_fails_closed(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        """name: test
on:
  push:
    paths: ["src/**"]
  pull_request: {}
jobs:
  test:
    runs-on: ubuntu-latest
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="push.*geant4"):
        validate_trigger_scope(workflow)


def test_required_pull_request_path_filter_fails_closed(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        """name: test
on:
  push:
    paths: ["geant4/**"]
  pull_request:
    paths: ["geant4/**"]
jobs:
  test:
    runs-on: ubuntu-latest
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must not use.*paths"):
        validate_trigger_scope(workflow)


def test_missing_required_test_job_fails_closed(tmp_path: Path) -> None:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        """name: test
on:
  push:
    paths: ["geant4/**"]
  pull_request: {}
jobs:
  other:
    runs-on: ubuntu-latest
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="required workflow job"):
        validate_trigger_scope(workflow)
