#!/usr/bin/env python3
"""Deterministic audit of ScatteringGenerator source-readiness semantics.

This is a source-contract falsifier for issue #1182. It does not execute Geant4
and must not be interpreted as generator or detector validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "geant4/src_patch/ScatteringGenerator.cc"
AUDIT_ID = "ARU-MC-CS-WORKER-INIT-001"


def _contains(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.DOTALL) is not None


def audit_source_text(text: str) -> dict[str, Any]:
    """Return deterministic source-level readiness findings.

    The predicates are intentionally narrow and evidence-oriented. They freeze
    specific mechanisms reviewed under #1182; they are not a C++ parser and do
    not substitute for compiled Geant4 tests.
    """

    event_zero = _contains(
        r"if\s*\(\s*event->GetEventID\(\)\s*==\s*0\s*\)\s*LoadFiles\(\)\s*;",
        text,
    )
    per_event_ready = _contains(
        r"void\s+ScatteringGenerator::GeneratePrimaryVertex\s*\([^)]*\)\s*\{.*?EnsureSourceReady\(\)\s*;",
        text,
    )
    hidden_uniform = _contains(
        r"if\s*\([^{};]*cdfTheta\.empty\(\).*?\)\s*\{\s*return\s+pi\s*\*\s*G4UniformRand\(\)\s*;\s*\}",
        text,
    )
    explicit_uniform = _contains(
        r"SourceState::UNCONFIGURED_UNIFORM.*?return\s+pi\s*\*\s*G4UniformRand\(\)\s*;",
        text,
    )
    success_exit = _contains(
        r"if\s*\(\s*!infile\.is_open\(\)\s*\)\s*\{.*?exit\(0\)\s*;",
        text,
    )
    unchecked_sscanf = _contains(
        r"sscanf\s*\(\s*line\s*,\s*\"%lf\\t%lf\\t%\*f\\n\"\s*,\s*&tmpA\s*,\s*&tmpCS\s*\)\s*;",
        text,
    )
    stopping_deref = (
        "dEdx[0]*in/Ene[0]" in text or "dEdx[0] * in / Ene[0]" in text
    )
    stopping_guard = _contains(
        r"Ene\.size\(\)\s*<\s*2.*?dEdx\.size\(\)\s*!=\s*Ene\.size\(\).*?FatalSourceError",
        text,
    )
    explicit_state = all(
        token in text
        for token in (
            "SourceState::UNINITIALIZED",
            "SourceState::UNCONFIGURED_UNIFORM",
            "SourceState::CONFIGURED_READY",
            "SourceState::FATAL",
            "EnsureSourceReady",
        )
    )
    identity_guard = all(
        token in text
        for token in (
            "fDEdxFile != fLoadedDEdxFile",
            "fCSFile != fLoadedCSFile",
            "CCB_SOURCE_RECONFIGURED",
        )
    )
    transactional = all(
        token in text
        for token in (
            "Ene.swap(nextEne)",
            "dEdx.swap(nextDEdx)",
            "ang.swap(nextAng)",
            "sigma.swap(nextSigma)",
            "cdfTheta.swap(nextTheta)",
            "cdfVal.swap(nextVal)",
            "cdfPdf.swap(nextPdf)",
        )
    )
    configured_cdf_fatal = all(
        token in text
        for token in (
            "CCB_CS_SAMPLE_NOT_READY",
            "CCB_CS_CDF_STATE",
            "FatalSourceError",
        )
    )
    checked_numeric_parser = all(
        token in text
        for token in (
            "std::istringstream row(line)",
            "row >> tmpE >> tmpDEdx",
            "row >> tmpA >> tmpCS",
        )
    )
    fatal_non_success = "FatalException" in text and "std::abort()" in text

    findings = {
        "event_zero_load_gate": event_zero,
        "per_event_instance_readiness_call": per_event_ready,
        "uniform_fallback_on_empty_cdf": hidden_uniform,
        "uniform_sampling_is_explicit_state": explicit_uniform,
        "success_exit_on_input_open_failure": success_exit,
        "fatal_exception_with_abort_fallback": fatal_non_success,
        "unchecked_cross_section_sscanf": unchecked_sscanf,
        "checked_numeric_row_parser": checked_numeric_parser,
        "empty_stopping_table_dereference_pattern": stopping_deref,
        "stopping_table_cardinality_guard": stopping_guard,
        "explicit_instance_readiness_state": explicit_state,
        "configuration_identity_guard": identity_guard,
        "transactional_table_publication": transactional,
        "configured_cdf_state_is_fatal_not_uniform": configured_cdf_fatal,
    }

    blockers: list[str] = []
    if event_zero:
        blockers.append("event_zero_load_gate")
    if not per_event_ready:
        blockers.append("missing_per_event_instance_readiness_call")
    if hidden_uniform:
        blockers.append("uniform_fallback_on_empty_cdf")
    if not explicit_uniform:
        blockers.append("missing_explicit_uniform_state")
    if success_exit:
        blockers.append("success_exit_on_input_open_failure")
    if not fatal_non_success:
        blockers.append("missing_non_success_fatal_semantics")
    if unchecked_sscanf:
        blockers.append("unchecked_cross_section_sscanf")
    if not checked_numeric_parser:
        blockers.append("missing_checked_numeric_row_parser")
    if stopping_deref and not stopping_guard:
        blockers.append("unguarded_empty_stopping_table_dereference")
    if not explicit_state:
        blockers.append("missing_explicit_instance_readiness_state")
    if not identity_guard:
        blockers.append("missing_configuration_identity_guard")
    if not transactional:
        blockers.append("missing_transactional_table_publication")
    if not configured_cdf_fatal:
        blockers.append("configured_cdf_failure_not_proven_fatal")

    return {
        "audit_id": AUDIT_ID,
        "scope": "STATIC_SOURCE_CONTRACT_ONLY_NONAUTHORISING",
        "runtime_thread_mode": "UNRESOLVED_REQUIRES_EXACT_EXECUTABLE_PROVENANCE",
        "required_state_machine": [
            "UNINITIALIZED",
            "UNCONFIGURED_UNIFORM",
            "CONFIGURED_READY",
            "FATAL",
        ],
        "findings": findings,
        "blockers": blockers,
        "verdict": (
            "BLOCK_RUNTIME_AUTHORIZATION"
            if blockers
            else "STATIC_CONTRACT_IMPLEMENTED_COMPILED_VALIDATION_REQUIRED"
        ),
    }


def audit_source(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    text = data.decode("utf-8")
    result = audit_source_text(text)
    result["source"] = {
        "path": str(path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = audit_source(args.source)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
