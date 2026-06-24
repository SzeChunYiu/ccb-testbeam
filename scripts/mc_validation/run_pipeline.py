#!/usr/bin/env python3
"""Resumable MC-validation production pipeline orchestrator."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ccb_mc_validation.exceptions import MCValidationError, exit_code_for
from ccb_mc_validation.execution.pipeline import PipelineOrchestrator
from ccb_mc_validation.logging_config import setup_logging

DEFAULT_CONFIG = ROOT / "configs/mc_validation/execution.yaml"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_pipeline",
        description="MC validation production DAG: discover, smoke, submit, collect, plot, notebooks, docs",
    )
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--repo-root", type=Path, default=ROOT)
    p.add_argument("--run-id", default=None)
    p.add_argument("--profile", choices=("smoke", "full"), default=None)
    p.add_argument("--studies", default="all")
    p.add_argument("--allow-dirty", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--log-level", default="INFO")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("discover")
    pf = sub.add_parser("preflight")
    pf.add_argument("--allow-dirty", action="store_true")
    pl = sub.add_parser("plan")
    pl.add_argument("--studies", default="all")
    sm = sub.add_parser("smoke")
    sm.add_argument("--studies", default="all")
    sb = sub.add_parser("submit")
    sb.add_argument("--studies", default="all")
    for name in ("watch", "collect", "plot", "notebooks", "docs", "release", "status", "resume"):
        sp = sub.add_parser(name)
        sp.add_argument("--run-id", required=(name != "status"))
    val = sub.add_parser("validate")
    val.add_argument("--run-id", required=True)
    val.add_argument("--scope", default="smoke")
    val.add_argument("--strict", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    setup_logging(level=args.log_level)
    orch = PipelineOrchestrator(args.config, repo_root=args.repo_root)
    if args.profile:
        orch.profile = args.profile
    try:
        if args.command == "discover":
            orch.discover()
            return 0
        if args.command == "preflight":
            orch.preflight(allow_dirty=args.allow_dirty)
            return 0
        if args.command == "plan":
            orch.plan(studies=args.studies)
            return 0
        if args.command == "smoke":
            smoke_cfg = ROOT / "configs/mc_validation/smoke.yaml"
            orch = PipelineOrchestrator(smoke_cfg, repo_root=args.repo_root)
            orch.profile = "smoke"
            rid = orch.smoke(studies=args.studies)
            print(rid)
            return 0
        if args.command == "submit":
            orch.submit(studies=args.studies, dry_run=args.dry_run)
            return 0
        if args.command in ("status", "resume"):
            print(orch.status(args.run_id))
            return 0
        if not args.run_id and args.command not in ("discover", "preflight", "plan", "smoke", "submit"):
            logging.error("--run-id required for %s", args.command)
            return 2
        if args.command == "collect":
            print(orch.collect(args.run_id))
            return 0
        if args.command == "validate":
            print(orch.validate(args.run_id, scope=args.scope, strict=args.strict))
            return 0
        if args.command == "plot":
            print(orch.plot(args.run_id))
            return 0
        if args.command == "notebooks":
            r = orch.notebooks(args.run_id, execute=args.execute)
            return r.get("exit_code", 1)
        if args.command == "docs":
            r = orch.docs(args.run_id)
            return r.get("exit_code", 1)
        if args.command == "release":
            print(orch.release(args.run_id))
            return 0
        logging.error("command %s not fully implemented", args.command)
        return 2
    except MCValidationError as exc:
        logging.error("%s", exc)
        return exit_code_for(exc)


if __name__ == "__main__":
    raise SystemExit(main())
