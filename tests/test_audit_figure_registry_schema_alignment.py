from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "tools"
    / "audit"
    / "audit_figure_registry_schema_alignment.py"
)
SPEC = importlib.util.spec_from_file_location("figure_registry_schema_audit", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_current_like(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "registry.py"
    source.write_text(
        '''ALLOWED_STATUSES = frozenset(
    {"VALIDATED", "PRELIMINARY", "TENSION",
     "EXTERNAL_BLOCKER", "ILLUSTRATIVE"}
)
ALLOWED_KINDS = frozenset({"quantitative", "illustrative"})
def validate_registry(entries):
    problems = []
    for e in entries:
        if not e.result:
            problems.append("missing required 'result' path")
    return problems
''',
        encoding="utf-8",
    )
    registry = tmp_path / "figures.yaml"
    registry.write_text(
        '''TIMING-MC:
  result: metrics.json
  status: MC_METHOD_CLOSURE
  kind: quantitative
  caption: MC closure.
S00-COUNT:
  result: report.csv
  status: VALIDATED
  kind: figure_sourced
  caption: Data count.
SCH-01:
  source_figure: geometry.png
  status: ILLUSTRATIVE
  kind: illustrative
  caption: Schematic.
''',
        encoding="utf-8",
    )
    test = tmp_path / "test_registry.py"
    test.write_text(
        '''def test_allowed_statuses_frozen():
    assert ALLOWED_STATUSES == frozenset(
        {"VALIDATED", "PRELIMINARY", "TENSION",
         "EXTERNAL_BLOCKER", "ILLUSTRATIVE"}
    )
''',
        encoding="utf-8",
    )
    return source, registry, test


def write_corrected(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "registry.py"
    statuses = {
        "VALIDATED",
        "SIMULATION_RESULT",
        "MC_METHOD_CLOSURE",
        "PARTIAL",
        "GATED",
        "TENSION",
        "BLOCKED",
        "SUPERSEDED",
        "EXTERNAL_BLOCKER",
        "ILLUSTRATIVE",
    }
    source.write_text(
        "ALLOWED_STATUSES = frozenset("
        f"{statuses!r})\n"
        "ALLOWED_KINDS = frozenset({'quantitative', 'illustrative', 'figure_sourced'})\n"
        "def validate_registry(entries):\n"
        "    problems = []\n"
        "    for e in entries:\n"
        "        if e.kind == 'quantitative' and not e.result:\n"
        "            problems.append(\"missing required 'result' path\")\n"
        "    return problems\n",
        encoding="utf-8",
    )
    registry = tmp_path / "figures.yaml"
    registry.write_text(
        '''TIMING-MC:
  result: metrics.json
  status: MC_METHOD_CLOSURE
  kind: quantitative
  caption: MC closure.
S00-COUNT:
  result: report.csv
  status: VALIDATED
  kind: figure_sourced
  caption: Data count.
SCH-01:
  source_figure: geometry.png
  status: ILLUSTRATIVE
  kind: illustrative
  caption: Schematic.
''',
        encoding="utf-8",
    )
    test = tmp_path / "test_registry.py"
    test.write_text(
        f"def test_allowed_statuses_frozen():\n"
        f"    assert ALLOWED_STATUSES == frozenset({statuses!r})\n",
        encoding="utf-8",
    )
    return source, registry, test


def test_current_like_contract_fails_closed(tmp_path: Path) -> None:
    source, registry, test = write_current_like(tmp_path)
    status, payload = MODULE.audit(source, registry, test)
    assert status == 1
    codes = {item["code"] for item in payload["issues"]}
    assert "REGISTRY_STATUS_UNSUPPORTED" in codes
    assert "REGISTRY_KIND_UNSUPPORTED" in codes
    assert "ILLUSTRATIVE_RESULT_FALSE_REQUIREMENT" in codes
    assert "TEST_FREEZES_OBSOLETE_STATUS_SET" in codes


def test_corrected_contract_validates(tmp_path: Path) -> None:
    source, registry, test = write_corrected(tmp_path)
    status, payload = MODULE.audit(source, registry, test)
    assert status == 0
    assert payload["status"] == "VALIDATED"
    assert payload["issues"] == []


def test_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    source, registry, test = write_current_like(tmp_path)
    registry.write_bytes(b"valid:\n  status: VALIDATED\n\xff")
    status, payload = MODULE.audit(source, registry, test)
    assert status == 2
    assert payload["status"] == "INPUT_ERROR"


def test_output_alias_is_rejected(tmp_path: Path) -> None:
    source, registry, test = write_current_like(tmp_path)
    status, payload = MODULE.audit(source, registry, test, registry)
    assert status == 2
    assert payload["issues"][0]["code"] == "OUTPUT_ALIASES_INPUT"


def test_atomic_json_publication(tmp_path: Path) -> None:
    source, registry, test = write_current_like(tmp_path)
    output = tmp_path / "evidence.json"
    status, payload = MODULE.audit(source, registry, test, output)
    assert status == 1
    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert not list(tmp_path.glob(".evidence.json.*"))
