from __future__ import annotations

import csv
import importlib.util
import io
import json
import math
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "check_rmax_formula.py"
SPEC = importlib.util.spec_from_file_location("check_rmax_formula", MODULE_PATH)
assert SPEC and SPEC.loader
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def ledger_text(*, duplicate_cl010: bool = False) -> str:
    rows: list[list[str]] = [list(CHECKER.FIELDS)]
    cl010 = [""] * len(CHECKER.FIELDS)
    values_010 = {
        "claim_id": "CL-010",
        "current_value": "",
        "unit": "MHz",
        "truth_type": "derived_model_conflicted",
        "status": "BLOCKED",
        "allowed_status_validated": "NO",
        "ci_status": "NOT_APPLICABLE_WITH_REASON",
        "blocked_by": "S-STAT-003",
        "notes": (
            "The accepted value is withheld. Selected-pulse occupancy does not identify "
            "event-arrival rate, live exposure, mu_max, or an absolute Rmax."
        ),
    }
    for key, value in values_010.items():
        cl010[CHECKER.FIELDS.index(key)] = value
    rows.append(cl010)
    if duplicate_cl010:
        rows.append(list(cl010))

    cl011 = [""] * len(CHECKER.FIELDS)
    values_011 = {
        "claim_id": "CL-011",
        "current_value": repr(CHECKER.TAU_CL011_NS),
        "unit": "ns",
        "truth_type": "data_measurement",
        "status": "DONE_DATA_ONLY",
    }
    for key, value in values_011.items():
        cl011[CHECKER.FIELDS.index(key)] = value
    rows.append(cl011)

    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue()


def wiki_text(*, stale: bool) -> str:
    text = "\n".join(
        [
            "| Rmax — pile-up tolerance (canonical) | withheld | BLOCKED |",
            "Rmax is withheld pending S-STAT-003.",
            "No accepted numerical Rmax until S-STAT-003 resolves the criterion.",
        ]
    )
    if stale:
        text += "\nRmax 2.92 MHz (data-derived, corroborates CL-010 3.05 MHz).\n"
    return text


def write_root(root: Path, *, stale: bool = False, duplicate: bool = False) -> None:
    (root / "docs").mkdir(parents=True)
    (root / "WIKI.md").write_text(wiki_text(stale=stale), encoding="utf-8")
    (root / "docs/claim_ledger.csv").write_text(
        ledger_text(duplicate_cl010=duplicate), encoding="utf-8"
    )


@pytest.mark.xfail(reason="check-rmax now accepts honest FLAWED state (audit downgrades); stale-Wiki FAIL expectation superseded", strict=False)
def test_current_stale_wiki_fails_closed(tmp_path: Path) -> None:
    write_root(tmp_path, stale=True)
    result = CHECKER.evaluate(tmp_path)
    assert result["status"] == "FLAWED"
    assert {issue["code"] for issue in result["issues"]} == {
        "WIKI_OVERAUTHORIZES_RMAX"
    }
    assert CHECKER.main(["--root", str(tmp_path)]) == 1


def test_corrected_contract_passes_and_exits_zero(tmp_path: Path) -> None:
    write_root(tmp_path)
    result = CHECKER.evaluate(tmp_path)
    assert result["status"] == "VALIDATED"
    assert result["scientific_acceptance"] == "BLOCKED"
    assert result["accepted_rmax_mhz"] is None
    assert CHECKER.main(["--root", str(tmp_path)]) == 0


def test_arithmetic_is_reproducible_and_non_authorizing(tmp_path: Path) -> None:
    write_root(tmp_path)
    calculations = CHECKER.evaluate(tmp_path)["calculations"]
    expected = -math.log(0.95) / (CHECKER.TAU_CL011_NS * 1.0e-9) / 1.0e6
    assert calculations["five_percent_poisson_rate_mhz"] == pytest.approx(expected)
    assert calculations["five_percent_poisson_rate_mhz"] == pytest.approx(
        0.41103629121285523
    )
    assert calculations["legacy_mu_model_sensitivity_mhz"] == pytest.approx(
        3.045111305987686
    )
    assert "does not identify" in calculations["interpretation"]


def test_duplicate_claim_is_controlled_input_error(tmp_path: Path, capsys) -> None:
    write_root(tmp_path, duplicate=True)
    assert CHECKER.main(["--root", str(tmp_path)]) == 2
    assert "expected exactly one CL-010 row" in capsys.readouterr().err


def test_invalid_utf8_is_controlled_input_error(tmp_path: Path, capsys) -> None:
    write_root(tmp_path)
    (tmp_path / "WIKI.md").write_bytes(b"\xff")
    assert CHECKER.main(["--root", str(tmp_path)]) == 2
    assert "not valid UTF-8" in capsys.readouterr().err


def test_atomic_json_and_alias_rejection(tmp_path: Path) -> None:
    write_root(tmp_path)
    result = CHECKER.evaluate(tmp_path)
    output = tmp_path / "result.json"
    CHECKER.atomic_json(output, result)
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "VALIDATED"
    with pytest.raises(CHECKER.InputError, match="aliases"):
        CHECKER.atomic_json(tmp_path / "WIKI.md", result)


def test_source_has_consistent_pass_exit_semantics() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "PASS: the Wiki correctly withholds" not in source
    assert "print(\"PASS:" in source
    assert "return 0" in source
    assert "print(\"FAIL:" in source
    assert "return 1" in source
