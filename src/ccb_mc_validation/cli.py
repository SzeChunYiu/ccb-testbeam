"""Command-line interface for the MC validation program."""

from __future__ import annotations

import argparse
import json
import logging
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from ccb_mc_validation.config import ResolvedConfig, load_config, write_resolved_config
from ccb_mc_validation.exceptions import (
    InputNotFoundError,
    MCValidationError,
    SchemaMismatchError,
    StudyBlockedError,
    exit_code_for,
)
from ccb_mc_validation.io.root_truth import DEFAULT_TRUTH_BRANCHES, audit_truth_tree
from ccb_mc_validation.logging_config import setup_logging
from ccb_mc_validation.manifest import build_manifest_record, write_manifest
from ccb_mc_validation.schemas import StudyStatus as StudyStatusRecord
from ccb_mc_validation.studies.common import write_study_result
from ccb_mc_validation.studies.mv1_pid import run_mv1
from ccb_mc_validation.studies.mv2_energy_range import run_mv2
from ccb_mc_validation.studies.mv3_stopping_depth import run_mv3
from ccb_mc_validation.studies.mv9_synthesis import synthesize as synthesize_mv9

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = Path("configs/mc_validation/base.yaml")
AUDIT_DOC = Path("docs/mc_validation/REPOSITORY_AUDIT.md")
REGISTRY_PATH = Path("reports/mc_validation_registry.json")


def _git_value(args: Sequence[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unknown"


def _require_config(args: argparse.Namespace) -> ResolvedConfig:
    config_path = Path(args.config).resolve()
    repo_root = Path(args.repo_root).resolve() if getattr(args, "repo_root", None) else None
    return load_config(config_path, repo_root=repo_root)


def _study_enabled(config: ResolvedConfig, study_key: str) -> bool:
    return bool(config.studies.get(study_key, {}).get("enabled", False))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _synthetic_fixture_records(n: int = 6000, seed: int = 4242) -> dict[str, np.ndarray]:
    """Generate reproducible truth-like records for fixture-mode study runs."""
    rng = np.random.default_rng(seed)
    half = n // 2
    pdg = np.array([2212] * half + [1000010020] * (n - half), dtype=np.int64)
    is_proton = pdg == 2212
    edep_l0 = np.empty(n, dtype=np.float64)
    edep_l0[is_proton] = rng.uniform(0.3, 4.0, int(is_proton.sum()))
    edep_l0[~is_proton] = rng.uniform(2.0, 9.0, int((~is_proton).sum()))
    edep_l1 = edep_l0 * rng.uniform(0.4, 0.9, n)
    edep_tot = edep_l0 + edep_l1 + rng.uniform(0.1, 1.0, n)
    stop_layer = rng.integers(0, 8, size=n)
    ekin = rng.uniform(20.0, 180.0, n)
    tracklen = stop_layer.astype(np.float64) * rng.uniform(8.0, 12.0, n)
    return {
        "pdg": pdg,
        "edep_l0": edep_l0,
        "edep_l1": edep_l1,
        "edep_tot": edep_tot,
        "stop_layer": stop_layer,
        "ekin": ekin,
        "tracklen": tracklen,
        "nlayers": np.full(n, 8, dtype=np.int32),
        "event_id": np.arange(n, dtype=np.int64),
    }


def cmd_audit(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root or ".").resolve()
    branch = _git_value(["branch", "--show-current"], repo_root)
    head = _git_value(["rev-parse", "HEAD"], repo_root)
    python_version = platform.python_version()
    generated_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    config_path = repo_root / DEFAULT_CONFIG
    package_src = repo_root / "src" / "ccb_mc_validation"
    mc_root = repo_root / "geant4" / "data" / "output_krakow_1M.root"
    data_pulses = repo_root / "data" / "tables" / "s00_selected_b_pulses.csv.gz"

    lines = [
        "# MC Validation Repository Audit",
        "",
        f"Generated: {generated_at}",
        "",
        "## Environment",
        "",
        f"- Repository path: `{repo_root}`",
        f"- Git branch: `{branch}`",
        f"- Git HEAD: `{head}`",
        f"- Python version: `{python_version}`",
        "",
        "## Package layout",
        "",
        f"- MC validation package present: `{package_src.is_dir()}`",
        f"- Base config present: `{config_path.is_file()}` (`{DEFAULT_CONFIG}`)",
        "",
        "## Key inputs",
        "",
        f"- MC ROOT (`geant4/data/output_krakow_1M.root`): `{mc_root.is_file()}`",
        f"- Data pulse table (`data/tables/s00_selected_b_pulses.csv.gz`): `{data_pulses.is_file()}`",
        "",
        "## Phase A-B scope",
        "",
        "This audit confirms repository scaffolding for the MC validation program:",
        "packaging, strict config loading, unit helpers, schema records, CLI wiring,",
        "and Tier-1 study entry points (MV1–MV3) plus truth-build inspection.",
        "",
        "Tier-2 studies MV4–MV8 remain blocked until MV0 digitizer calibration lands.",
        "",
    ]

    out_path = repo_root / AUDIT_DOC
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("wrote audit report to %s", out_path)
    return 0


def cmd_truth_build(args: argparse.Namespace) -> int:
    config = _require_config(args)
    setup_logging(config.logging_level)
    resolved_path = write_resolved_config(config)
    logger.info("wrote resolved config to %s", resolved_path)

    if not config.mc_root.is_file():
        raise InputNotFoundError(f"MC ROOT file not found: {config.mc_root}")

    report = audit_truth_tree(config.mc_root, tree="hibeam", required=DEFAULT_TRUTH_BRANCHES)
    if not report["ok"]:
        raise SchemaMismatchError(
            f"MC truth tree missing branches: {report['missing']}"
        )

    out_dir = config.study_output_dir("mv0")
    out_dir.mkdir(parents=True, exist_ok=True)
    schema_path = out_dir / "truth_schema.json"
    _write_json(schema_path, report)

    manifest = build_manifest_record(
        study_id="truth-build",
        ticket="phase-a-b",
        config_path=config.source_path,
        out_dir=out_dir,
        inputs={"mc_root": config.mc_root},
        outputs=[schema_path.name, resolved_path.name],
    )
    write_manifest(out_dir, manifest)
    logger.info("truth-build complete; schema written to %s", schema_path)
    return 0


def _run_tier1_study(
    config: ResolvedConfig,
    study_key: str,
    runner: Callable[..., object],
    *,
    extra_checks: Callable[[ResolvedConfig], None] | None = None,
) -> int:
    if not _study_enabled(config, study_key):
        raise StudyBlockedError(f"{study_key.upper()} is disabled in config")

    if extra_checks is not None:
        extra_checks(config)

    write_resolved_config(config)
    fixture = not config.mc_root.is_file()
    if fixture:
        logger.warning("MC ROOT missing; running %s in fixture mode", study_key.upper())

    records = _synthetic_fixture_records(seed=int(config.seeds.get("global", 4242)))
    result = runner(records, config.raw, fixture=fixture)
    out_dir = config.study_output_dir(study_key)
    path = write_study_result(result, out_dir)
    logger.info("%s wrote %s", study_key.upper(), path)
    return 0


def cmd_mv1(args: argparse.Namespace) -> int:
    config = _require_config(args)
    setup_logging(config.logging_level)
    return _run_tier1_study(config, "mv1", run_mv1)


def cmd_mv2(args: argparse.Namespace) -> int:
    config = _require_config(args)
    setup_logging(config.logging_level)

    def _check(cfg: ResolvedConfig) -> None:
        if not cfg.data_pulses.is_file():
            raise InputNotFoundError(f"MV2 requires data pulse table: {cfg.data_pulses}")

    return _run_tier1_study(config, "mv2", run_mv2, extra_checks=_check)


def cmd_mv3(args: argparse.Namespace) -> int:
    config = _require_config(args)
    setup_logging(config.logging_level)
    return _run_tier1_study(config, "mv3", run_mv3)


def cmd_mv0_digitize(args: argparse.Namespace) -> int:
    config = _require_config(args)
    setup_logging(config.logging_level)
    write_resolved_config(config)

    samples = int(config.waveform["adc_samples"])
    spacing = float(config.waveform["sample_spacing_ns"])
    if samples <= 0 or spacing <= 0:
        raise SchemaMismatchError("waveform adc_samples and sample_spacing_ns must be positive")

    out_dir = config.study_output_dir("mv0")
    status = StudyStatusRecord(
        study_id="MV0",
        phase="A-B",
        state="scaffold",
        message="Digitizer parameters resolved; calibration deferred to Phase C",
    )
    _write_json(
        out_dir / "digitizer_scaffold.json",
        {
            "status": status.as_dict(),
            "waveform": config.waveform,
            "units": config.units,
            "data_pulses": str(config.data_pulses),
            "data_pulses_present": config.data_pulses.is_file(),
        },
    )
    logger.info("MV0 digitizer scaffold written to %s", out_dir)
    return 0


def _blocked_mv(study_id: str, blocked_by: str = "MV0") -> Callable[[argparse.Namespace], int]:
    def _cmd(args: argparse.Namespace) -> int:
        config = _require_config(args)
        setup_logging(config.logging_level)
        raise StudyBlockedError(
            f"{study_id} is blocked until {blocked_by} digitizer calibration is complete"
        )

    return _cmd


def cmd_synthesize(args: argparse.Namespace) -> int:
    config = _require_config(args)
    setup_logging(config.logging_level)
    out_dir = config.study_output_dir("mv9")
    out_dir.mkdir(parents=True, exist_ok=True)

    tier1 = {"mv1", "mv2", "mv3"}
    tier2 = {"mv4", "mv5", "mv6", "mv7", "mv8"}
    rows: list[dict[str, object]] = []
    for key in ("mv1", "mv2", "mv3", "mv0", *sorted(tier2)):
        label = f"MV{key[2:]}"
        enabled = _study_enabled(config, key)
        blocked = key in tier2
        state = "blocked" if blocked else ("ready" if enabled else "disabled")
        rows.append(
            StudyStatusRecord(
                study_id=label,
                phase="A-B" if not blocked else "blocked",
                state=state,
                blocked_by="MV0" if blocked else None,
                message="Tier-1 scaffold" if key in tier1 else "",
            ).as_dict()
        )

    scaffold_path = out_dir / "synthesis_scaffold.json"
    _write_json(scaffold_path, {"studies": rows})

    registry_path = config.repo_root / REGISTRY_PATH
    if registry_path.is_file():
        report_path = out_dir / "MV9_SYNTHESIS.md"
        synthesize_mv9(registry_path, report_path)
        logger.info("MV9 synthesis report written to %s", report_path)
    else:
        logger.info("registry not found at %s; wrote scaffold only", registry_path)

    return 0


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to MC validation YAML config",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root for relative config paths",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ccb-mc-validation",
        description="MC validation program CLI for CCB HiBeam testbeam analysis",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Generate docs/mc_validation/REPOSITORY_AUDIT.md")
    audit.add_argument("--repo-root", default=".", help="Repository root")
    audit.set_defaults(handler=cmd_audit)

    truth = sub.add_parser("truth-build", help="Inspect MC truth schema and write manifest")
    _add_common_args(truth)
    truth.set_defaults(handler=cmd_truth_build)

    mv1 = sub.add_parser("mv1", help="Run MV1 PID study (fixture mode if MC ROOT absent)")
    _add_common_args(mv1)
    mv1.set_defaults(handler=cmd_mv1)

    mv2 = sub.add_parser("mv2", help="Run MV2 energy calibration study")
    _add_common_args(mv2)
    mv2.set_defaults(handler=cmd_mv2)

    mv3 = sub.add_parser("mv3", help="Run MV3 stopping-depth study")
    _add_common_args(mv3)
    mv3.set_defaults(handler=cmd_mv3)

    mv0 = sub.add_parser("mv0-digitize", help="Resolve MV0 digitizer scaffold parameters")
    _add_common_args(mv0)
    mv0.set_defaults(handler=cmd_mv0_digitize)

    for mv_id in ("mv4", "mv5", "mv6", "mv7", "mv8"):
        label = f"MV{mv_id[2:]}"
        blocked = sub.add_parser(mv_id, help=f"{label} study (blocked until MV0 digitizer)")
        _add_common_args(blocked)
        blocked.set_defaults(handler=_blocked_mv(label))

    synth = sub.add_parser("synthesize", help="Write MV9 synthesis scaffold from config")
    _add_common_args(synth)
    synth.set_defaults(handler=cmd_synthesize)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return int(args.handler(args))
    except MCValidationError as exc:
        if not logging.getLogger().handlers:
            setup_logging("ERROR")
        logging.getLogger(__name__).error("%s", exc.message)
        return exit_code_for(exc)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
