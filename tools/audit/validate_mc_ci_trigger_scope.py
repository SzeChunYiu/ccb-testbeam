#!/usr/bin/env python3
"""Fail closed when MC Validation CI does not route Geant4 changes to required test.

This validator checks workflow routing only.  It does not claim that the
workflow compiles Geant4 or authorises detector/source physics.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "ccb_mc_ci_trigger_scope_v1"
REQUIRED_EVENTS = ("push", "pull_request")
REQUIRED_PATTERN = "geant4/**"
REQUIRED_JOB = "test"


def _load_workflow(path: Path) -> dict[str, Any]:
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if not isinstance(data, dict):
        raise ValueError("workflow root must be a mapping")
    return data


def validate_trigger_scope(path: Path) -> dict[str, Any]:
    workflow = _load_workflow(path)
    on = workflow.get("on")
    if not isinstance(on, dict):
        raise ValueError("workflow must define mapping-valued 'on'")

    event_evidence: dict[str, dict[str, Any]] = {}
    for event in REQUIRED_EVENTS:
        event_cfg = on.get(event)
        if not isinstance(event_cfg, dict):
            raise ValueError(f"workflow must define '{event}' routing")
        paths = event_cfg.get("paths")
        if not isinstance(paths, list):
            raise ValueError(f"workflow '{event}' must define a paths list")
        normalized = [str(item) for item in paths]
        if REQUIRED_PATTERN not in normalized:
            raise ValueError(
                f"workflow '{event}' does not route {REQUIRED_PATTERN!r} to validation"
            )
        event_evidence[event] = {
            "required_pattern": REQUIRED_PATTERN,
            "pattern_present": True,
            "path_count": len(normalized),
        }

    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or REQUIRED_JOB not in jobs:
        raise ValueError(f"required workflow job {REQUIRED_JOB!r} is missing")

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "workflow": str(path),
        "required_job": REQUIRED_JOB,
        "events": event_evidence,
        "scientific_scope": "ROUTING_PRECONDITION_ONLY_NOT_COMPILED_GEANT4_VALIDATION",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workflow", type=Path)
    args = parser.parse_args()
    try:
        result = validate_trigger_scope(args.workflow)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "BLOCKED",
                    "workflow": str(args.workflow),
                    "error": str(exc),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
