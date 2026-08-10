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

    The predicates are intentionally narrow and evidence-oriented. They identify
    the currently reviewed mechanisms; they are not a C++ parser or a proof that
    an arbitrary replacement implementation is correct.
    """

    findings = {
        "event_zero_load_gate": _contains(
            r"if\s*\(\s*event->GetEventID\(\)\s*==\s*0\s*\)\s*LoadFiles\(\)\s*;",
            text,
        ),
        "uniform_fallback_on_empty_cdf": _contains(
            r"if\s*\([^{};]*cdfTheta\.empty\(\).*?\)\s*\{\s*return\s+pi\s*\*\s*G4UniformRand\(\)\s*;\s*\}",
            text,
        ),
        "success_exit_on_input_open_failure": _contains(
            r"if\s*\(\s*!infile\.is_open\(\)\s*\)\s*\{.*?exit\(0\)\s*;",
            text,
        ),
        "unchecked_cross_section_sscanf": _contains(
            r"sscanf\s*\(\s*line\s*,\s*\"%lf\\t%lf\\t%\*f\\n\"\s*,\s*&tmpA\s*,\s*&tmpCS\s*\)\s*;",
            text,
        ),
        "empty_stopping_table_dereference_pattern": (
            "dEdx[0]*in/Ene[0]" in text or "dEdx[0] * in / Ene[0]" in text
        ),
        "explicit_instance_readiness_state": any(
            token in text
            for token in (
                "EnsureSourceReady",
                "EnsureFilesLoaded",
                "SourceState",
                "filesLoaded",
                "fFilesLoaded",
            )
        ),
    }

    blockers = [
        key
        for key in (
            "event_zero_load_gate",
            "uniform_fallback_on_empty_cdf",
            "success_exit_on_input_open_failure",
            "unchecked_cross_section_sscanf",
            "empty_stopping_table_dereference_pattern",
        )
        if findings[key]
    ]
    if not findings["explicit_instance_readiness_state"]:
        blockers.append("missing_explicit_instance_readiness_state")

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
        "verdict": "BLOCK_RUNTIME_AUTHORIZATION" if blockers else "NO_FROZEN_BLOCKER_MATCH",
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
