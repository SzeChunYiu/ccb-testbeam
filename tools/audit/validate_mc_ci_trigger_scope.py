#!/usr/bin/env python3
"""Fail closed when required MC Validation CI can skip a pull request.

The protected branch requires job ``test``. GitHub documents that a workflow
skipped by path filtering leaves its associated required check pending, so the
pull-request event must not be path-filtered. Push routing remains scoped but
must include the material ``geant4/**`` subtree.

This validator checks workflow routing only. It does not claim that the
workflow compiles Geant4 or authorises detector/source physics.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "ccb_mc_ci_trigger_scope_v2"
REQUIRED_PUSH_PATTERN = "geant4/**"
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

    push_cfg = on.get("push")
    if not isinstance(push_cfg, dict):
        raise ValueError("workflow must define 'push' routing")
    push_paths = push_cfg.get("paths")
    if not isinstance(push_paths, list):
        raise ValueError("workflow 'push' must define a paths list")
    normalized_push = [str(item) for item in push_paths]
    if REQUIRED_PUSH_PATTERN not in normalized_push:
        raise ValueError(
            f"workflow 'push' does not route {REQUIRED_PUSH_PATTERN!r} to validation"
        )

    if "pull_request" not in on:
        raise ValueError("workflow must define 'pull_request' routing")
    pull_request_cfg = on.get("pull_request")
    if pull_request_cfg is None:
        pull_request_cfg = {}
    if not isinstance(pull_request_cfg, dict):
        raise ValueError("workflow 'pull_request' configuration must be a mapping or null")
    for forbidden_filter in ("paths", "paths-ignore"):
        if forbidden_filter in pull_request_cfg:
            raise ValueError(
                "required pull_request workflow must not use "
                f"{forbidden_filter!r}; skipped required checks remain pending"
            )

    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or REQUIRED_JOB not in jobs:
        raise ValueError(f"required workflow job {REQUIRED_JOB!r} is missing")

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "workflow": str(path),
        "required_job": REQUIRED_JOB,
        "push": {
            "required_pattern": REQUIRED_PUSH_PATTERN,
            "pattern_present": True,
            "path_count": len(normalized_push),
        },
        "pull_request": {
            "unfiltered": True,
        },
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
