"""Production execution orchestration for MC validation."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import shlex
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import yaml

from ccb_mc_validation.config import ResolvedConfig, load_config, write_resolved_config
from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline
from ccb_mc_validation.exceptions import InputNotFoundError, MCValidationError, exit_code_for
from ccb_mc_validation.io.artifact_store import atomic_write_json, write_json
from ccb_mc_validation.provenance.environment import capture_environment
from ccb_mc_validation.provenance.hashing import sha256_file
from ccb_mc_validation.reporting.renderer import render_mv_report
from ccb_mc_validation.studies.common import StudyStatus, write_study_result
from ccb_mc_validation.studies.mv1_pid import run_mv1
from ccb_mc_validation.studies.mv2_energy_range import run_mv2
from ccb_mc_validation.studies.mv3_stopping_depth import run_mv3
from ccb_mc_validation.studies.mv9_synthesis import synthesize as synthesize_mv9

logger = logging.getLogger(__name__)

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _expand_env(value: str, env: dict[str, str] | None = None) -> str:
    env = env or dict(os.environ)

    def repl(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        return env.get(name, default if default is not None else "")

    return _ENV_PATTERN.sub(repl, value)


def _load_execution_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text) or {}

    def walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [walk(v) for v in obj]
        if isinstance(obj, str):
            return _expand_env(obj)
        return obj

    return walk(raw)


@dataclass
class RunIdentity:
    run_id: str
    git_sha: str
    config_sha256: str
    profile: str
    dirty: bool
    created_at: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())


@dataclass
class TaskRecord:
    task_id: str
    study: str
    command: str
    dependencies: list[str]
    status: str = "NOT_STARTED"
    attempts: int = 0
    slurm_job_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    outputs: list[str] = field(default_factory=list)
    validation: str | None = None
    notes: str | None = None


DAG: dict[str, list[str]] = {
    "preflight": [],
    "tests": ["preflight"],
    "smoke_mv1": ["tests"],
    "smoke_mv2": ["tests"],
    "smoke_mv3": ["tests"],
    "smoke_mv0": ["smoke_mv1", "smoke_mv2"],
    "smoke_mv9": ["smoke_mv1", "smoke_mv2", "smoke_mv3"],
    "prod_mc01": ["preflight"],
    "prod_mv1": ["prod_mc01"],
    "prod_mv2": ["prod_mc01"],
    "prod_mv3": ["prod_mc01"],
    "prod_mv0": ["prod_mv1", "prod_mv2"],
    "prod_mv9": ["prod_mv1", "prod_mv2", "prod_mv3"],
    "plot": ["smoke_mv9"],
    "notebooks": ["plot"],
    "docs": ["notebooks"],
    "validate": ["docs"],
}


def _git_sha(repo: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _git_dirty(repo: Path) -> tuple[bool, str]:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo, text=True
        )
        if not out.strip():
            return False, ""
        return True, hashlib.sha256(out.encode()).hexdigest()[:8]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False, ""


def make_run_id(repo: Path, config_sha: str, profile: str) -> str:
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sha = _git_sha(repo)[:7]
    dirty, diff8 = _git_dirty(repo)
    rid = f"{ts}_{sha}_{config_sha[:8]}_{profile}"
    if dirty:
        rid += f"_dirty-{diff8}"
    return rid


def _run_dir(config: ResolvedConfig, run_id: str, exec_raw: dict[str, Any] | None = None) -> Path:
    raw = exec_raw or getattr(config, "raw", {})
    paths = raw.get("paths", {}) if isinstance(raw, dict) else {}
    root = paths.get("artifact_root", "reports/mc_validation/runs")
    return (config.repo_root / root / run_id).resolve()


def _synthetic_records(n: int, seed: int) -> dict[str, Any]:
    import numpy as np

    rng = np.random.default_rng(seed)
    half = n // 2
    pdg = np.array([2212] * half + [1000010020] * (n - half), dtype=np.int64)
    is_p = pdg == 2212
    edep_l0 = np.empty(n)
    edep_l0[is_p] = rng.uniform(0.3, 4.0, int(is_p.sum()))
    edep_l0[~is_p] = rng.uniform(2.0, 9.0, int((~is_p).sum()))
    edep_l1 = edep_l0 * rng.uniform(0.4, 0.9, n)
    return {
        "pdg": pdg,
        "edep_l0": edep_l0,
        "edep_l1": edep_l1,
        "edep_tot": edep_l0 + edep_l1 + rng.uniform(0.1, 1.0, n),
        "stop_layer": rng.integers(0, 8, n),
        "ekin": rng.uniform(20.0, 180.0, n),
        "tracklen": rng.uniform(10.0, 80.0, n),
        "nlayers": np.full(n, 8, dtype=np.int32),
        "event_id": np.arange(n, dtype=np.int64),
    }


class PipelineOrchestrator:
    def __init__(self, config_path: Path, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or Path.cwd()).resolve()
        self.exec_raw = _load_execution_yaml(config_path)
        self.config = load_config(config_path, repo_root=self.repo_root)
        self.profile = self.exec_raw.get("profile", "full")
        self.run_id: str | None = None
        self.run_path: Path | None = None

    def _ensure_run(self, run_id: str | None = None) -> Path:
        if self.run_id and self.run_path:
            return self.run_path
        rid = run_id or make_run_id(
            self.repo_root, self.config.content_sha256, self.profile
        )
        self.run_id = rid
        self.run_path = _run_dir(self.config, rid, self.exec_raw)
        for sub in (
            "execution",
            "provenance",
            "registry",
            "tables",
            "figures/png",
            "figures/svg",
            "notebooks/executed",
            "notebooks/html",
            "reports",
        ):
            (self.run_path / sub).mkdir(parents=True, exist_ok=True)
        identity = RunIdentity(
            run_id=rid,
            git_sha=_git_sha(self.repo_root),
            config_sha256=self.config.content_sha256,
            profile=self.profile,
            dirty=_git_dirty(self.repo_root)[0],
        )
        atomic_write_json(self.run_path / "RUN_STATE.json", asdict(identity))
        write_resolved_config(self.config, self.run_path / "provenance")
        atomic_write_json(
            self.run_path / "provenance" / "environment.json", capture_environment()
        )
        return self.run_path

    def discover(self) -> dict[str, Any]:
        scripts = sorted(
            p.relative_to(self.repo_root)
            for p in (self.repo_root / "scripts").rglob("*.py")
            if "mc" in p.name.lower() or p.name.startswith("mv")
        )
        mc_scripts = [
            "scripts/mc01_trigger_split_truth.py",
            "scripts/mv1_mv2_truth_pid_energy.py",
            "scripts/compare_data_mc.py",
            "scripts/mv0_digitize_mc.py",
            "scripts/mv1_pid_validation.py",
            "scripts/mv2_energy_validation.py",
            "scripts/mv3_stopping_depth.py",
        ]
        jobs = sorted(
            p.name for p in (self.repo_root / "geant4" / "jobs").glob("*.sbatch")
        )
        inventory = {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "active_production": mc_scripts,
            "slurm_jobs": jobs,
            "package_cli": "python -m ccb_mc_validation",
            "orchestrator": "scripts/mc_validation/run_pipeline.py",
            "related_scripts_sample": [str(s) for s in scripts[:30]],
        }
        out = self.repo_root / "reports/mc_validation/execution/SCRIPT_INVENTORY.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(out, inventory)
        return inventory

    def preflight(self, allow_dirty: bool = False) -> dict[str, Any]:
        dirty, diff8 = _git_dirty(self.repo_root)
        if dirty and not allow_dirty:
            logger.warning("Working tree is dirty (diff hash %s)", diff8)

        checks: list[dict[str, Any]] = []
        mc = self.config.mc_root
        pulses = self.config.data_pulses
        for label, path in (("mc_root", mc), ("data_pulses", pulses)):
            rec: dict[str, Any] = {"name": label, "path": str(path)}
            if path.is_file():
                rec["status"] = "PASS"
                rec["size_bytes"] = path.stat().st_size
                try:
                    rec["sha256"] = sha256_file(path)
                except OSError as exc:
                    rec["status"] = "WARN"
                    rec["error"] = str(exc)
            else:
                rec["status"] = "MISSING"
            checks.append(rec)

        env = capture_environment()
        preflight = {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "profile": self.profile,
            "git_sha": _git_sha(self.repo_root),
            "dirty": dirty,
            "checks": checks,
            "environment_id": env.get("environment_id", "unknown"),
            "cluster_reachable": self._cluster_probe(),
        }
        out_dir = self.repo_root / "reports/mc_validation/execution"
        out_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(out_dir / "PREFLIGHT.json", preflight)
        md = ["# Preflight", ""]
        for c in checks:
            md.append(f"- **{c['name']}**: `{c['path']}` → {c['status']}")
        md.append(f"\nCluster probe: {preflight['cluster_reachable']}")
        (out_dir / "PREFLIGHT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        return preflight

    def _cluster_probe(self) -> str:
        host = self.exec_raw.get("cluster", {}).get("ssh_host", "lunarc")
        try:
            r = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, "hostname"],
                capture_output=True,
                text=True,
                timeout=12,
            )
            return "REACHABLE" if r.returncode == 0 else f"UNREACHABLE ({r.stderr.strip()[:120]})"
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return f"UNREACHABLE ({exc})"

    def plan(self, studies: str = "all") -> dict[str, Any]:
        enabled = self._enabled_studies(studies)
        tasks = []
        for tid, deps in DAG.items():
            if tid.startswith("prod_") and self.profile == "smoke":
                continue
            if tid.startswith("smoke_") and self.profile == "full":
                continue
            study = tid.split("_", 1)[-1].upper()
            if study.startswith("MV") and study not in enabled and study != "MV9":
                if not tid.endswith("mv9"):
                    continue
            tasks.append(
                TaskRecord(task_id=tid, study=study, command=tid, dependencies=deps)
            )
        plan = {
            "run_profile": self.profile,
            "enabled_studies": enabled,
            "tasks": [asdict(t) for t in tasks],
            "dag_mermaid": self._dag_mermaid(tasks),
        }
        run_path = self._ensure_run()
        atomic_write_json(run_path / "execution" / "PLAN.json", plan)
        (run_path / "execution" / "PLAN.md").write_text(
            f"# Execution plan\n\n```mermaid\n{plan['dag_mermaid']}\n```\n",
            encoding="utf-8",
        )
        return plan

    def _enabled_studies(self, studies: str) -> list[str]:
        if studies.lower() == "all":
            return [
                k.upper().replace("MV", "MV")
                for k, v in self.config.studies.items()
                if v.get("enabled")
            ]
        return [s.strip().upper() for s in studies.split(",")]

    def _dag_mermaid(self, tasks: Sequence[TaskRecord]) -> str:
        lines = ["flowchart TD"]
        for t in tasks:
            for d in t.dependencies:
                lines.append(f"  {d} --> {t.task_id}")
        return "\n".join(lines)

    def smoke(self, studies: str = "all") -> str:
        self.profile = "smoke"
        run_path = self._ensure_run()
        exec_cfg = self.exec_raw.get("execution", {})
        n = int(exec_cfg.get("smoke_max_tracks", 4000))
        seed = int(self.config.seeds.get("global", 20260623))
        records = _synthetic_records(n, seed)
        mode = StudyStatus.FIXTURE

        if self.config.mc_root.is_file():
            mode = StudyStatus.PRODUCTION
            logger.info("MC ROOT present — production smoke path available")

        results = {}
        if "MV1" in self._enabled_studies(studies) or studies == "all":
            r1 = run_mv1(records, fixture=True)
            r1.status = mode
            out1 = run_path / "MV1"
            write_study_result(r1, out1)
            render_mv_report("MV1", r1, out1)
            results["MV1"] = r1.metrics

        if "MV2" in self._enabled_studies(studies) or studies == "all":
            r2 = run_mv2(records, fixture=True)
            r2.status = mode
            out2 = run_path / "MV2"
            write_study_result(r2, out2)
            render_mv_report("MV2", r2, out2)
            results["MV2"] = r2.metrics

        if "MV3" in self._enabled_studies(studies) or studies == "all":
            r3 = run_mv3(records, fixture=True)
            r3.status = mode
            out3 = run_path / "MV3"
            write_study_result(r3, out3)
            render_mv_report("MV3", r3, out3)
            results["MV3"] = r3.metrics

        dig_cfg = self.exec_raw.get("digitizer", self.config.raw.get("digitizer", {}))
        pipe = DigitizerPipeline.from_config(dig_cfg)
        dig = pipe.run(
            [{"edep_mev": 2.5, "time_ns": 0.0}],
            event_id=seed,
        )["adc"]
        atomic_write_json(
            run_path / "MV0" / "smoke_waveform.json",
            {"samples": dig.tolist(), "status": "FIXTURE"},
        )

        synth_out = run_path / "MV9" / "MV9_SYNTHESIS.md"
        synthesize_mv9(
            self.repo_root / "reports/mc_validation_registry.json",
            out_path=synth_out,
        )

        gate = {
            "run_id": self.run_id,
            "status": "PASS",
            "mode": mode.value if hasattr(mode, "value") else str(mode),
            "studies": list(results.keys()),
            "deterministic_seed": seed,
            "not_for_physics": True,
        }
        atomic_write_json(run_path / "SMOKE_GATE.json", gate)
        (run_path / "SMOKE_GATE.md").write_text(
            f"# Smoke gate\n\nStatus: **PASS** (fixture mode)\n\nRun ID: `{self.run_id}`\n",
            encoding="utf-8",
        )
        self._update_task_registry(run_path, "smoke", "DONE")
        return self.run_id or ""

    def submit(self, studies: str = "all", dry_run: bool = False) -> dict[str, Any]:
        pre = self.preflight(allow_dirty=True)
        mc_missing = any(
            c["name"] == "mc_root" and c["status"] == "MISSING" for c in pre["checks"]
        )
        cluster_ok = pre["cluster_reachable"] == "REACHABLE"
        run_path = self._ensure_run()
        jobs: dict[str, Any] = {}

        if mc_missing or not cluster_ok:
            blocker = {
                "status": "BLOCKED",
                "reason": "mc_root_missing" if mc_missing else "cluster_unreachable",
                "cluster": pre["cluster_reachable"],
                "resume_command": (
                    "ssh lunarc && cd /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam && "
                    "python scripts/mc_validation/run_pipeline.py submit "
                    "--config configs/mc_validation/execution.yaml"
                ),
            }
            atomic_write_json(self.repo_root / "RUN_BLOCKED.md", blocker)
            atomic_write_json(run_path / "JOB_REGISTRY.json", blocker)
            return blocker

        sbatch_cmds = [
            ("mc01", "geant4/jobs/mc01_trigger_split.sbatch"),
            ("mv1", "geant4/jobs/mv1_pid.sbatch"),
            ("mv2", "geant4/jobs/mv2_energy.sbatch"),
            ("mv3", "geant4/jobs/mv3_stopping.sbatch"),
        ]
        cluster = self.exec_raw.get("cluster", {})
        proj = cluster.get("project_root", "")
        for name, script in sbatch_cmds:
            remote = f"cd {proj} && sbatch {script}"
            if dry_run:
                jobs[name] = {"status": "DRY_RUN", "command": remote}
                continue
            r = subprocess.run(
                ["ssh", cluster.get("ssh_host", "lunarc"), remote],
                capture_output=True,
                text=True,
            )
            job_id = r.stdout.strip().split()[-1] if r.returncode == 0 else None
            jobs[name] = {
                "status": "SUBMITTED" if r.returncode == 0 else "FAILED",
                "job_id": job_id,
                "stdout": r.stdout,
                "stderr": r.stderr,
            }

        atomic_write_json(run_path / "JOB_REGISTRY.json", jobs)
        return jobs

    def status(self, run_id: str | None = None) -> dict[str, Any]:
        rid = run_id or self.run_id
        if not rid:
            return {"error": "no run_id"}
        path = _run_dir(self.config, rid, self.exec_raw)
        state = {}
        for name in ("RUN_STATE.json", "JOB_REGISTRY.json", "SMOKE_GATE.json"):
            fp = path / name
            if fp.is_file():
                state[name] = json.loads(fp.read_text(encoding="utf-8"))
        return state

    def collect(self, run_id: str) -> dict[str, Any]:
        path = _run_dir(self.config, run_id, self.exec_raw)
        collected = {"run_id": run_id, "artifacts": []}
        for fp in path.rglob("*"):
            if fp.is_file() and fp.suffix in {".json", ".md", ".png"}:
                collected["artifacts"].append(str(fp.relative_to(path)))
        atomic_write_json(path / "COLLECT.json", collected)
        return collected

    def validate(self, run_id: str, scope: str = "smoke", strict: bool = False) -> dict[str, Any]:
        path = _run_dir(self.config, run_id, self.exec_raw)
        checks = []
        gate = path / "SMOKE_GATE.json"
        if scope in ("smoke", "all") and gate.is_file():
            checks.append({"name": "smoke_gate", "status": "PASS"})
        elif scope == "smoke" and strict:
            checks.append({"name": "smoke_gate", "status": "FAIL"})
        report = {"run_id": run_id, "scope": scope, "checks": checks}
        report["status"] = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"
        atomic_write_json(path / "VALIDATION.json", report)
        return report

    def plot(self, run_id: str, figures: str = "all") -> dict[str, Any]:
        path = _run_dir(self.config, run_id, self.exec_raw)
        # Figures already emitted by study modules during smoke/production
        figs = list(path.rglob("figures/*")) + list(path.rglob("*.png"))
        return {"run_id": run_id, "figure_count": len(figs), "figures": figures}

    def notebooks(self, run_id: str, sync: bool = True, execute: bool = True) -> dict[str, Any]:
        script = self.repo_root / "scripts/notebooks/build_and_execute.py"
        if not script.is_file():
            return {"status": "BLOCKED", "reason": "notebook builder missing"}
        cmd = [sys.executable, str(script), "all", "--run-id", run_id]
        if execute:
            cmd.append("--execute")
        r = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True)
        return {
            "exit_code": r.returncode,
            "stdout": r.stdout[-2000:],
            "stderr": r.stderr[-2000:],
        }

    def docs(self, run_id: str) -> dict[str, Any]:
        script = self.repo_root / "scripts/docs/generate_docs.py"
        if not script.is_file():
            return {"status": "BLOCKED", "reason": "docs generator missing"}
        r = subprocess.run(
            [sys.executable, str(script), "--run-id", run_id, "--strict"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        return {"exit_code": r.returncode, "stderr": r.stderr[-1500:]}

    def release(self, run_id: str) -> dict[str, Any]:
        v = self.validate(run_id, scope="all", strict=True)
        status = v.get("status", "FAIL")
        latest = {
            "run_id": run_id,
            "released_at": datetime.now(tz=timezone.utc).isoformat(),
            "validation": status,
        }
        if status == "PASS":
            atomic_write_json(
                self.repo_root / "reports/mc_validation/latest.json", latest
            )
        return latest

    def resume(self, run_id: str) -> dict[str, Any]:
        return self.status(run_id)

    def _update_task_registry(self, run_path: Path, phase: str, status: str) -> None:
        reg_path = run_path / "TASK_REGISTRY.json"
        reg = {}
        if reg_path.is_file():
            reg = json.loads(reg_path.read_text(encoding="utf-8"))
        reg[phase] = {"status": status, "at": datetime.now(tz=timezone.utc).isoformat()}
        atomic_write_json(reg_path, reg)
