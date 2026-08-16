from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.audit.classify_ci_failure_log import FailureLogError, classify

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "audit" / "classify_ci_failure_log.py"


def write_log(path: Path, failed: list[tuple[str, str]], passed: int = 4) -> None:
    lines = [f"FAILED {nodeid} - {message}" for nodeid, message in failed]
    lines.append(f"{len(failed)} failed, {passed} passed, 0 skipped, 0 warnings in 1.00s")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_single_log_is_classified_without_preexisting_claim(tmp_path: Path) -> None:
    log = tmp_path / "pytest.log"
    write_log(
        log,
        [
            (
                "tests/test_compare_stopping_power_deuteron_proxy.py::test_proxy",
                "KeyError: 'energy_deposit_basis'",
            ),
            (
                "tests/test_wiki_claim_front_door_current.py::test_wiki",
                "WikiCanonicalResultsError: canonical results table was not found",
            ),
        ],
    )
    result = classify(
        log,
        candidate_test_prefixes=("tests/test_mv3_chi2_producer_contract.py",),
    )
    assert result["status"] == "VALIDATED"
    assert result["candidate"]["family_counts"] == {
        "stopping_power_compare": 1,
        "wiki_claim_binding": 1,
    }
    assert result["direct_candidate_test_failure_count"] == 0
    assert result["causal_attribution"]["mode"] == "UNRESOLVED_SINGLE_RUN"
    assert "cannot establish" in result["causal_attribution"]["statement"]


def test_paired_logs_identify_introduced_resolved_and_persistent(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.log"
    candidate = tmp_path / "candidate.log"
    write_log(
        baseline,
        [
            ("tests/test_old.py::test_old", "AssertionError"),
            ("tests/test_shared.py::test_shared", "AssertionError"),
        ],
    )
    write_log(
        candidate,
        [
            ("tests/test_shared.py::test_shared", "AssertionError"),
            ("tests/test_new.py::test_new", "AssertionError"),
        ],
    )
    result = classify(candidate, baseline_log=baseline)
    attribution = result["causal_attribution"]
    assert attribution["mode"] == "PAIRED_BASELINE_COMPARISON"
    assert attribution["introduced"] == ["tests/test_new.py::test_new"]
    assert attribution["resolved"] == ["tests/test_old.py::test_old"]
    assert attribution["persistent"] == ["tests/test_shared.py::test_shared"]


def test_parametrized_nodeid_with_spaces_is_preserved(tmp_path: Path) -> None:
    log = tmp_path / "pytest.log"
    nodeid = "tests/test_ref.py::test_invalid[value with spaces]"
    write_log(log, [(nodeid, "Failed: DID NOT RAISE")])
    result = classify(log)
    assert result["candidate"]["failures"][0]["nodeid"] == nodeid


def test_duplicate_failed_nodeids_fail_closed(tmp_path: Path) -> None:
    log = tmp_path / "pytest.log"
    write_log(
        log,
        [
            ("tests/test_a.py::test_x", "AssertionError"),
            ("tests/test_a.py::test_x", "AssertionError"),
        ],
    )
    with pytest.raises(FailureLogError, match="duplicate FAILED node IDs"):
        classify(log)


def test_summary_count_mismatch_fails_closed(tmp_path: Path) -> None:
    log = tmp_path / "pytest.log"
    log.write_text(
        "FAILED tests/test_a.py::test_x - AssertionError\n"
        "2 failed, 4 passed, 0 skipped, 0 warnings in 1.00s\n",
        encoding="utf-8",
    )
    with pytest.raises(FailureLogError, match="disagrees"):
        classify(log)


def test_invalid_utf8_returns_controlled_status(tmp_path: Path) -> None:
    log = tmp_path / "pytest.log"
    log.write_bytes(b"FAILED x - y\n\xff")
    process = subprocess.run(
        [sys.executable, str(SCRIPT), str(log)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 2
    assert "not valid UTF-8" in process.stdout


def test_atomic_json_and_alias_rejection(tmp_path: Path) -> None:
    log = tmp_path / "pytest.log"
    output = tmp_path / "result.json"
    write_log(log, [("tests/test_a.py::test_x", "AssertionError")])
    process = subprocess.run(
        [sys.executable, str(SCRIPT), str(log), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 0
    assert json.loads(output.read_text())["candidate"]["failure_count"] == 1
    assert not list(tmp_path.glob(".result.json.*.tmp"))

    alias = subprocess.run(
        [sys.executable, str(SCRIPT), str(log), "--output", str(log)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert alias.returncode == 2
    assert "aliases an input" in alias.stdout
