#!/usr/bin/env python3
"""Resumable MC-validation production pipeline orchestrator."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

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
        description="Canonical CCB MC-validation DAG orchestrator (fail-closed production semantics).",
    )
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--repo-root", type=Path, default=ROOT)
    p.add_argument("--run-id", default=None)
    p.add_argument("--profile", choices=("fixture", "smoke", "production", "full"), default=None)
    p.add_argument("--studies", default="all")
    p.add_argument("--allow-dirty", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--log-level", default="INFO")
    p.add_argument("--format", default="json")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("discover")
    inv = sub.add_parser("inventory")
    inv.add_argument("--root", type=Path, default=None)
    inv.add_argument("--include-untracked", action="store_true")
    inv.add_argument("--format", default="json")

    init = sub.add_parser("init")
    init.add_argument("--profile", choices=("fixture", "smoke", "production", "full"), default=None)

    pf = sub.add_parser("preflight")
    pf.add_argument("--allow-dirty", action="store_true")
    pf.add_argument("--all", action="store_true")
    pf.add_argument("--strict", action="store_true")

    pl = sub.add_parser("plan")
    pl.add_argument("--studies", default=None)
    pl.add_argument("--freeze", action="store_true")
    pl.add_argument("--explain", action="store_true")
    pl.add_argument("--validate-slurm", action="store_true")
    pl.add_argument("--dry-run", action="store_true")
    pl.add_argument("--output", type=Path, default=None)
    pl.add_argument("--format", default="json")

    tst = sub.add_parser("test")
    tst.add_argument("--scope", default="unit")
    tst.add_argument("--strict", action="store_true")

    fx = sub.add_parser("fixture")
    fx.add_argument("--workers", type=int, default=1)
    fx.add_argument("--shards", type=int, default=1)
    fx.add_argument("--compare-to", default=None)

    sm = sub.add_parser("smoke")
    sm.add_argument("--study", "--studies", dest="studies", default=None)
    sm.add_argument("--profile", default="smoke")
    sm.add_argument("--max-files", type=int, default=None)
    sm.add_argument("--max-events", type=int, default=None)
    sm.add_argument("--wait", action="store_true")

    sb = sub.add_parser("submit")
    sb.add_argument("--study", "--studies", dest="studies", default=None)
    sb.add_argument("--profile", default=None)

    watch = sub.add_parser("watch")
    watch.add_argument("--until-terminal", "--wait-until-terminal", action="store_true")
    watch.add_argument("--continue-independent", action="store_true")
    watch.add_argument("--poll-interval-seconds", type=int, default=60)
    sub.add_parser("monitor", parents=[watch], add_help=False)

    for name in ("collect", "status", "plot", "docs", "thesis", "release", "resume"):
        sp = sub.add_parser(name)
        if name == "status":
            sp.add_argument("--all", action="store_true")
            sp.add_argument("--verbose", action="store_true")
            sp.add_argument("--format", default="json")

    val = sub.add_parser("validate")
    val.add_argument("--scope", default="all")
    val.add_argument("--strict", action="store_true")

    qa = sub.add_parser("qa")
    qa.add_argument("--scope", default="all")
    qa.add_argument("--strict", action="store_true")

    nb = sub.add_parser("notebooks")
    nb.add_argument("--execute", action="store_true")

    allp = sub.add_parser("all")
    allp.add_argument("--studies", default=None)
    allp.add_argument("--profile", default=None)
    allp.add_argument("--backend", default="slurm")
    allp.add_argument("--wait-until-terminal", action="store_true")
    allp.add_argument("--continue-independent", action="store_true")
    allp.add_argument("--resume", action="store_true")
    return p


def _print(payload: Any) -> None:
    if isinstance(payload, str):
        print(payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    setup_logging(str(args.log_level).upper())
    try:
        repo_root = args.root if getattr(args, "root", None) else args.repo_root
        orch = PipelineOrchestrator(args.config, repo_root=repo_root, profile=getattr(args, "profile", None) or args.profile, run_id=args.run_id)
        cmd = args.command
        if cmd == "init":
            _print(orch.init(profile=args.profile))
        elif cmd in {"discover", "inventory"}:
            _print(orch.inventory(include_untracked=getattr(args, "include_untracked", True)))
        elif cmd == "preflight":
            _print(orch.preflight(allow_dirty=args.allow_dirty or getattr(args, "allow_dirty", False), strict=args.strict))
        elif cmd == "plan":
            payload = orch.plan(studies=args.studies or args.__dict__.get("studies") or "all", freeze=args.freeze)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(payload.get("dag_mermaid", "") + "\n", encoding="utf-8")
            _print(payload)
        elif cmd == "test":
            _print(orch.test(scope=args.scope, strict=args.strict))
        elif cmd == "fixture":
            _print(orch.fixture(workers=args.workers, shards=args.shards))
        elif cmd == "smoke":
            _print(orch.smoke(studies=args.studies or "all"))
        elif cmd == "submit":
            _print(orch.submit(studies=args.studies or "all", dry_run=args.dry_run))
        elif cmd in {"watch", "monitor"}:
            _print(orch.watch(until_terminal=args.until_terminal, poll_interval_seconds=args.poll_interval_seconds))
        elif cmd == "status":
            _print(orch.status(all_runs=args.all))
        elif cmd == "collect":
            _print(orch.collect())
        elif cmd == "validate":
            _print(orch.validate(scope=args.scope, strict=args.strict))
        elif cmd == "qa":
            _print(orch.qa(scope=args.scope, strict=args.strict))
        elif cmd == "plot":
            _print(orch.plot())
        elif cmd == "notebooks":
            _print(orch.notebooks(execute=args.execute))
        elif cmd == "docs":
            _print(orch.docs())
        elif cmd == "thesis":
            _print(orch.thesis())
        elif cmd == "release":
            _print(orch.release())
        elif cmd == "resume":
            _print(orch.resume())
        elif cmd == "all":
            _print(orch.all(studies=args.studies or "all", wait_until_terminal=args.wait_until_terminal, continue_independent=args.continue_independent, resume=args.resume))
        else:
            parser.error(f"unknown command {cmd}")
        return 0
    except MCValidationError as exc:
        logging.getLogger(__name__).error("%s", exc)
        return exit_code_for(exc)


if __name__ == "__main__":
    raise SystemExit(main())
