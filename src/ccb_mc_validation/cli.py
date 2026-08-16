"""Command-line interface for the CCB MC validation program."""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from ccb_mc_validation.config import ResolvedConfig, load_config, write_resolved_config
from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline
from ccb_mc_validation.exceptions import (
    InputNotFoundError,
    MCValidationError,
    SchemaMismatchError,
    StudyBlockedError,
    exit_code_for,
)
from ccb_mc_validation.io.root_truth import DEFAULT_TRUTH_BRANCHES, audit_truth_tree, load_truth_records
from ccb_mc_validation.logging_config import setup_logging
from ccb_mc_validation.manifest import build_manifest_record, write_manifest
from ccb_mc_validation.raw_root_paths import resolve_raw_root_dir
from ccb_mc_validation.studies.common import write_study_result
from ccb_mc_validation.studies.mv1_pid import run_mv1
from ccb_mc_validation.studies.mv2_energy_range import run_mv2
from ccb_mc_validation.studies.mv3_stopping_depth import run_mv3
from ccb_mc_validation.studies.mv9_synthesis import synthesize as synthesize_mv9

logger = logging.getLogger(__name__)
DEFAULT_CONFIG = Path("configs/mc_validation/base.yaml")
AUDIT_DOC = Path("docs/mc_validation/REPOSITORY_AUDIT.md")
REGISTRY_PATH = Path("reports/mc_validation_registry.json")


@dataclass
class StudyStatusRecord:
    study_id: str
    phase: str
    state: str
    blocked_by: str | None = None
    message: str = ""

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _git_value(args: Sequence[str], cwd: Path) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _synthetic_fixture_records(n: int = 6000, seed: int = 4242) -> dict[str, np.ndarray]:
    """Generate reproducible truth-like fixture-mode records."""
    rng = np.random.default_rng(seed)
    half = n // 2
    pdg = np.array([2212] * half + [1000010020] * (n - half), dtype=np.int64)
    is_proton = pdg == 2212
    edep_l0 = np.empty(n, dtype=np.float64)
    edep_l0[is_proton] = rng.uniform(0.3, 4.0, int(is_proton.sum()))
    edep_l0[~is_proton] = rng.uniform(2.0, 9.0, int((~is_proton).sum()))
    edep_l1 = edep_l0 * rng.uniform(0.4, 0.9, n)
    stop_layer = rng.integers(0, 8, size=n)
    return {
        "pdg": pdg,
        "ekin": rng.uniform(20, 80, n),
        "edep_l0": edep_l0,
        "edep_l1": edep_l1,
        "edep_tot": edep_l0 + edep_l1 + rng.uniform(0.1, 1.0, n),
        "stop_layer": stop_layer,
        "nlayers": stop_layer + 1,
        "tracklen": rng.uniform(10, 40, n),
        "event_id": np.arange(n),
    }


def cmd_audit(args: argparse.Namespace) -> int:
    repo = Path(args.repo_root).resolve()
    setup_logging("INFO")
    out_path = repo / AUDIT_DOC
    payload = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "repo": str(repo),
        "head": _git_value(["rev-parse", "HEAD"], repo),
        "branch": _git_value(["branch", "--show-current"], repo),
        "status": _git_value(["status", "--short", "--branch"], repo),
        "package_cli": "python -m ccb_mc_validation",
        "orchestrator": "scripts/mc_validation/run_pipeline.py",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "# Repository audit\n\n" + "\n".join(f"- **{k}**: `{v}`" for k, v in payload.items()) + "\n",
        encoding="utf-8",
    )
    _write_json(out_path.with_suffix(".json"), payload)
    logger.info("wrote audit report %s", out_path)
    return 0


def cmd_truth_build(args: argparse.Namespace) -> int:
    config = _require_config(args)
    setup_logging(config.logging_level)
    resolved_path = write_resolved_config(config)
    if not config.mc_root.is_file():
        raise InputNotFoundError(f"MC ROOT file not found: {config.mc_root}")
    if "SLURM_JOB_ID" not in os.environ:
        raise StudyBlockedError(
            "truth-build production ROOT inspection must run in a LUNARC batch allocation. "
            "Submit with sbatch; do not run full ROOT scans locally or on a login node."
        )
    report = audit_truth_tree(config.mc_root, tree="hibeam", required=DEFAULT_TRUTH_BRANCHES)
    if not report["ok"]:
        raise SchemaMismatchError(f"MC truth tree missing branches: {report['missing']}")
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
    return 0


def _run_tier1_study(
    config: ResolvedConfig,
    study_key: str,
    runner: Callable[..., object],
    *,
    extra_checks: Callable[[ResolvedConfig], None] | None = None,
    fixture: bool = False,
) -> int:
    if not _study_enabled(config, study_key):
        raise StudyBlockedError(f"{study_key.upper()} disabled in config")
    if extra_checks is not None:
        extra_checks(config)
    write_resolved_config(config)
    if fixture:
        logger.warning("running %s in explicit fixture mode; result is not physics evidence", study_key.upper())
        records = _synthetic_fixture_records(seed=int(config.seeds.get("global", 4242)))
        result = runner(records, config.raw, fixture=True)
    else:
        if not config.mc_root.is_file():
            raise InputNotFoundError(
                f"MC ROOT file not found for production {study_key.upper()}: {config.mc_root}. "
                "Use --fixture only for deterministic software tests; fixture output is never production evidence."
            )
        if "SLURM_JOB_ID" not in os.environ:
            raise StudyBlockedError(
                f"{study_key.upper()} heavy production task must run in a LUNARC batch allocation. "
                f"Submit with: sbatch --parsable geant4/jobs/mc_validation_pipeline.sbatch {study_key}"
            )
        max_events_raw = os.environ.get("CCB_MAX_ROOT_EVENTS", "100000")
        max_events = int(max_events_raw) if max_events_raw else 100000
        records = load_truth_records(
            config.mc_root,
            tree=str(config.raw.get("tree", "hibeam")),
            max_events=max_events,
            coinc_ns=float(config.coincidence_ns),
        )
        result = runner(records, config.raw, fixture=False)
    out_dir = config.study_output_dir(study_key)
    path = write_study_result(result, out_dir)
    logger.info("%s wrote %s", study_key.upper(), path)
    return 0


def cmd_mv1(args: argparse.Namespace) -> int:
    config = _require_config(args)
    setup_logging(config.logging_level)
    return _run_tier1_study(config, "mv1", run_mv1, fixture=getattr(args, "fixture", False))


def cmd_mv2(args: argparse.Namespace) -> int:
    config = _require_config(args)
    setup_logging(config.logging_level)

    def _checks(cfg: ResolvedConfig) -> None:
        if cfg.units.get("energy") != "MeV":
            raise SchemaMismatchError("MV2 expects energy unit MeV")

    return _run_tier1_study(config, "mv2", run_mv2, extra_checks=_checks, fixture=getattr(args, "fixture", False))


def cmd_mv3(args: argparse.Namespace) -> int:
    config = _require_config(args)
    setup_logging(config.logging_level)
    return _run_tier1_study(config, "mv3", run_mv3, fixture=getattr(args, "fixture", False))


def cmd_mv0_digitize(args: argparse.Namespace) -> int:
    config = _require_config(args)
    setup_logging(config.logging_level)
    out_dir = config.study_output_dir("mv0")
    out_dir.mkdir(parents=True, exist_ok=True)
    status = StudyStatusRecord(
        study_id="MV0",
        phase="C",
        state="fixture" if getattr(args, "fixture", False) else "blocked",
        blocked_by=None if getattr(args, "fixture", False) else "real pulse train/validation/held-out calibration",
        message="Fixture waveform only; not production evidence" if getattr(args, "fixture", False) else "Requires calibrated real pulse data and SLURM production path",
    )
    pipe = DigitizerPipeline.from_config(config.raw.get("digitizer", {}))
    waveform = pipe.run([{"edep_mev": 0.0, "time_ns": 0.0}, {"edep_mev": 0.0, "time_ns": 5.0}], event_id=int(config.seeds.get("global", 4242)))
    _write_json(
        out_dir / "digitizer_status.json",
        {
            "status": status.as_dict(),
            "waveform": {"adc": waveform["adc"].tolist(), "n_hits": waveform["n_hits"], "not_for_physics": True},
            "units": config.units,
            "data_pulses": str(config.data_pulses),
            "data_pulses_present": config.data_pulses.is_file(),
        },
    )
    return 0


def _blocked_mv(study_id: str, blocked_by: str = "MV0") -> Callable[[argparse.Namespace], int]:
    def _cmd(args: argparse.Namespace) -> int:
        config = _require_config(args)
        setup_logging(config.logging_level)
        raise StudyBlockedError(f"{study_id} blocked until {blocked_by} digitizer calibration complete")

    return _cmd



def cmd_synthesize(args: argparse.Namespace) -> int:
    config = _require_config(args)
    setup_logging(config.logging_level)
    out_dir = config.study_output_dir("mv9")
    out_dir.mkdir(parents=True, exist_ok=True)

    result_paths = {
        "MV1": config.study_output_dir("mv1") / "study_result.json",
        "MV2": config.study_output_dir("mv2") / "study_result.json",
        "MV3": config.study_output_dir("mv3") / "study_result.json",
    }
    rows: list[dict[str, object]] = []
    lines = ["# MV9 — MC Validation Synthesis", "", "Current-run study verdicts from `reports/mc_validation/*/study_result.json`.", ""]
    lines.extend(["| Study | Status | Support / key metric |", "|---|---|---|"])
    for study, path in result_paths.items():
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            metrics = payload.get("metrics", {}) if isinstance(payload, dict) else {}
            key_metric = ""
            for key in ("hgb_auc", "logreg_auc", "proton_ekin_recon_res68", "n_tracks"):
                if key in metrics:
                    key_metric = f"{key}={metrics[key]}"
                    break
            rows.append({"study_id": study, "state": payload.get("status", "UNKNOWN"), "path": str(path), "key_metric": key_metric})
            lines.append(f"| {study} | {payload.get('status', 'UNKNOWN')} | {key_metric} |")
        else:
            rows.append({"study_id": study, "state": "BLOCKED", "path": str(path), "message": "missing study_result.json"})
            lines.append(f"| {study} | BLOCKED | missing `{path}` |")
    for study in ("MV4", "MV5", "MV6", "MV7", "MV8"):
        rows.append({"study_id": study, "state": "BLOCKED", "blocked_by": "MV0", "message": "requires calibrated digitized MC"})
        lines.append(f"| {study} | BLOCKED | requires calibrated digitized MC |")
    _write_json(out_dir / "synthesis_scaffold.json", {"studies": rows})
    lines.extend([
        "",
        "## Interpretation guardrails",
        "",
        "- These rows summarize the current checked-out report artifacts only.",
        "- Bounded or reduced-statistics production runs are not final thesis conclusions until strict validation, uncertainty, figures, and final audit pass.",
        "- MV4–MV8 remain blocked until calibrated MV0 digitized MC is available.",
    ])
    (out_dir / "MV9_SYNTHESIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


def cmd_raw_root_probe(args: argparse.Namespace) -> int:
    repo = Path(args.repo_root).resolve()
    resolution = resolve_raw_root_dir(repo_root=repo)
    text = resolution.to_json()
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0



def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path MC validation YAML config")
    parser.add_argument("--repo-root", default=None, help="Repository root for relative config paths")
    parser.add_argument("--fixture", action="store_true", help="Run deterministic synthetic fixture only; never production evidence")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ccb-mc-validation", description="MC validation CLI for CCB HiBeam testbeam analysis")
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit", help="Generate docs/mc_validation/REPOSITORY_AUDIT.md")
    audit.add_argument("--repo-root", default=".", help="Repository root")
    audit.set_defaults(handler=cmd_audit)
    raw_probe = sub.add_parser("raw-root-probe", help="Resolve and probe the raw ROOT input directory")
    raw_probe.add_argument("--repo-root", default=".", help="Repository root")
    raw_probe.add_argument("--output", default=None, help="Optional JSON path for probe evidence")
    raw_probe.set_defaults(handler=cmd_raw_root_probe)
    truth = sub.add_parser("truth-build", help="Inspect MC truth schema manifest")
    _add_common_args(truth); truth.set_defaults(handler=cmd_truth_build)
    for name, handler, help_text in (
        ("mv1", cmd_mv1, "Run MV1 PID validation"),
        ("mv2", cmd_mv2, "Run MV2 energy/range validation"),
        ("mv3", cmd_mv3, "Run MV3 stopping-depth validation"),
        ("mv0", cmd_mv0_digitize, "Run MV0 digitizer fixture/status"),
        ("synthesize", cmd_synthesize, "Build MV9 synthesis scaffold/report"),
    ):
        sp = sub.add_parser(name, help=help_text)
        _add_common_args(sp)
        sp.set_defaults(handler=handler)
    for mv in ("mv4", "mv5", "mv6", "mv7", "mv8"):
        sp = sub.add_parser(mv, help=f"{mv.upper()} blocked placeholder")
        _add_common_args(sp)
        sp.set_defaults(handler=_blocked_mv(mv.upper()))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except MCValidationError as exc:
        logger.error("%s", exc)
        return exit_code_for(exc)


if __name__ == "__main__":
    raise SystemExit(main())
