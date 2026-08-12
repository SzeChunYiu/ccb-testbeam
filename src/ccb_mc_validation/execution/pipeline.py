"""Canonical fail-closed execution orchestration for MC validation."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import platform
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
from ccb_mc_validation.io.artifact_store import atomic_write_json
from ccb_mc_validation.provenance.environment import capture_environment
from ccb_mc_validation.provenance.hashing import sha256_file
from ccb_mc_validation.reporting.run_summary import generate_run_summary
from ccb_mc_validation.reporting.figure_manifest import generate_summary_figure_manifest
from ccb_mc_validation.reporting.visual_review import generate_summary_visual_review
from ccb_mc_validation.reporting.notebook_summary import generate_notebook_exports
from ccb_mc_validation.reporting.artifact_reports import generate_artifact_reports
from ccb_mc_validation.reporting.release_audit import generate_release_audit
from ccb_mc_validation.reporting.claim_ledger import generate_claim_ledger
from ccb_mc_validation.reporting.thesis_draft import generate_thesis_draft
from ccb_mc_validation.reporting.publication_index import generate_publication_index
from ccb_mc_validation.reporting.reference_registry import generate_reference_registry
from ccb_mc_validation.reporting.notation_registry import generate_notation_registry
from ccb_mc_validation.reporting.open_questions import generate_open_question_registry
from ccb_mc_validation.reporting.question_closure import generate_question_closure_plan
from ccb_mc_validation.reporting.evidence_packets import generate_evidence_packets
from ccb_mc_validation.reporting.study_gap_audit import generate_study_gap_audit
from ccb_mc_validation.reporting.wiki_export import generate_wiki_export
from ccb_mc_validation.studies.common import StudyStatus, write_study_result
from ccb_mc_validation.studies.mv1_pid import run_mv1
from ccb_mc_validation.studies.mv2_energy_range import run_mv2
from ccb_mc_validation.studies.mv3_stopping_depth import run_mv3
from ccb_mc_validation.studies.mv9_synthesis import synthesize as synthesize_mv9

logger = logging.getLogger(__name__)

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _expand_env(value: str) -> str:
    def repl(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        return os.environ.get(name, default if default is not None else "")
    return _ENV_PATTERN.sub(repl, value)

STATUS_FIXTURE = "FIXTURE"
STATUS_SMOKE = "SMOKE"
STATUS_PRODUCTION = "PRODUCTION"
STATUS_BLOCKED = "BLOCKED"
STATUS_FAILED = "FAILED"
STATUS_STALE = "STALE"
STATUS_SUBMITTED = "SUBMITTED"
STATUS_DONE = "DONE"

CANONICAL_STUDIES = [
    "truth_audit",
    "MV0",
    "MV1",
    "MV2",
    "MV3",
    "MV4",
    "MV5",
    "MV6",
    "MV7",
    "MV8",
    "MV9",
]

DAG: dict[str, list[str]] = {
    "discover": [],
    "preflight": ["discover"],
    "tests": ["preflight"],
    "fixture": ["tests"],
    "smoke_truth_audit": ["fixture"],
    "smoke_MV1": ["fixture"],
    "smoke_MV2": ["fixture"],
    "smoke_MV3": ["fixture"],
    "smoke_MV0": ["smoke_MV1", "smoke_MV2"],
    "smoke_MV4": ["smoke_MV0"],
    "smoke_MV5": ["smoke_MV0"],
    "smoke_MV6": ["smoke_MV0"],
    "smoke_MV7": ["smoke_MV0"],
    "smoke_MV8": ["smoke_MV0"],
    "smoke_MV9": ["smoke_MV1", "smoke_MV2", "smoke_MV3", "smoke_MV4", "smoke_MV5", "smoke_MV6", "smoke_MV7", "smoke_MV8"],
    "prod_truth_audit": ["preflight"],
    "prod_GEANT4_optional": ["preflight"],
    "prod_MV1": ["prod_truth_audit"],
    "prod_MV2": ["prod_truth_audit"],
    "prod_MV3": ["prod_truth_audit"],
    "prod_MV0": ["prod_truth_audit"],
    "prod_MV4": ["prod_MV0"],
    "prod_MV5": ["prod_MV0"],
    "prod_MV6": ["prod_MV0"],
    "prod_MV7": ["prod_MV0"],
    "prod_MV8": ["prod_MV0"],
    "prod_systematics": ["prod_MV1", "prod_MV2", "prod_MV3", "prod_MV4", "prod_MV5", "prod_MV6", "prod_MV7", "prod_MV8"],
    "prod_MV9": ["prod_systematics"],
    "figures": ["prod_MV9"],
    "notebooks": ["figures"],
    "docs": ["notebooks"],
    "thesis": ["docs"],
    "validate": ["thesis"],
    "release": ["validate"],
}


def _release_blocker_digest(run_root: Path, publication: dict[str, Any]) -> dict[str, Any]:
    """Summarize why release is blocked without hiding the full audit artifacts."""

    audit_path = run_root / "QA_RELEASE_AUDIT.json"
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.is_file() else {}
    except json.JSONDecodeError:
        audit = {}
    blocked_checks = [
        {
            "name": check.get("name"),
            "reason": check.get("reason") or check.get("status"),
        }
        for check in audit.get("checks", [])
        if check.get("status") != "PASS"
    ]
    return {
        "release_ready": bool(publication.get("release_ready")),
        "publication_status": publication.get("status"),
        "missing_publication_links": publication.get("missing", []),
        "blocked_check_count": len(blocked_checks),
        "top_blocked_checks": blocked_checks[:12],
        "audit_path": str(audit_path),
    }


@dataclass(frozen=True)
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
    dependencies: list[str] = field(default_factory=list)
    status: str = "PLANNED"
    attempts: int = 0
    job_id: str | None = None
    exit_code: str | None = None
    reason: str | None = None
    log: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())


def _load_execution_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return raw if isinstance(raw, dict) else {}


def _git_sha(repo: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _git_dirty(repo: Path) -> tuple[bool, str]:
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True)
        if not out.strip():
            return False, ""
        return True, hashlib.sha256(out.encode()).hexdigest()[:8]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False, "unknown"


def make_run_id(repo: Path, config_sha: str, profile: str) -> str:
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sha = _git_sha(repo)[:7]
    dirty, diff8 = _git_dirty(repo)
    rid = f"{ts}_{sha}_{config_sha[:8]}_{profile}"
    if dirty:
        rid += f"_dirty-{diff8}"
    return rid


def _profile_alias(profile: str | None) -> str:
    if profile in (None, ""):
        return "production"
    if profile == "full":
        return "production"
    return profile


def _synthetic_records(n: int, seed: int) -> dict[str, Any]:
    import numpy as np

    rng = np.random.default_rng(seed)
    half = n // 2
    pdg = np.array([2212] * half + [1000010020] * (n - half), dtype=np.int64)
    is_p = pdg == 2212
    edep_l0 = np.empty(n, dtype=np.float64)
    edep_l0[is_p] = rng.uniform(0.3, 4.0, int(is_p.sum()))
    edep_l0[~is_p] = rng.uniform(2.0, 9.0, int((~is_p).sum()))
    edep_l1 = edep_l0 * rng.uniform(0.4, 0.9, n)
    stop_layer = rng.integers(0, 8, size=n)
    return {
        "pdg": pdg,
        "edep_l0": edep_l0,
        "edep_l1": edep_l1,
        "edep_tot": edep_l0 + edep_l1 + rng.uniform(0.1, 1.0, n),
        "stop_layer": stop_layer,
        "nlayers": stop_layer + 1,
        "tracklen": rng.uniform(10, 40, n),
        "ekin": rng.uniform(20, 80, n),
        "event_id": np.arange(n),
    }


class PipelineOrchestrator:
    def __init__(self, config_path: Path, repo_root: Path | None = None, profile: str | None = None, run_id: str | None = None) -> None:
        self.repo_root = (repo_root or Path.cwd()).resolve()
        self.config_path = Path(config_path).resolve()
        self.exec_raw = _load_execution_yaml(self.config_path)
        self.config: ResolvedConfig = load_config(self.config_path, repo_root=self.repo_root)
        self.profile = _profile_alias(profile or self.exec_raw.get("profile", "production"))
        self.run_id: str | None = run_id
        self.run_path: Path | None = None
        if run_id:
            self.run_path = self._run_dir(run_id)

    def _artifact_root(self) -> Path:
        paths = self.exec_raw.get("paths", {}) if isinstance(self.exec_raw, dict) else {}
        root = paths.get("artifact_root") or os.environ.get("CCB_ARTIFACT_ROOT") or "reports/mc_validation/runs"
        root = _expand_env(str(root))
        return (self.repo_root / root).resolve() if not Path(root).is_absolute() else Path(root).resolve()

    def _run_dir(self, run_id: str) -> Path:
        return self._artifact_root() / run_id

    def init(self, profile: str | None = None) -> str:
        if profile:
            self.profile = _profile_alias(profile)
        run_path = self._ensure_run()
        self._event("init", STATUS_DONE, {"run_id": self.run_id})
        return str(self.run_id)

    def _ensure_run(self, run_id: str | None = None) -> Path:
        if run_id:
            self.run_id = run_id
            self.run_path = self._run_dir(run_id)
        if self.run_id is None:
            self.run_id = make_run_id(self.repo_root, self.config.content_sha256, self.profile)
            self.run_path = self._run_dir(self.run_id)
        assert self.run_path is not None
        for sub in ("execution", "provenance", "registry", "tables", "figures/png", "figures/svg", "notebooks/executed", "notebooks/html", "reports", "blockers"):
            (self.run_path / sub).mkdir(parents=True, exist_ok=True)
        identity = RunIdentity(
            run_id=self.run_id,
            git_sha=_git_sha(self.repo_root),
            config_sha256=self.config.content_sha256,
            profile=self.profile,
            dirty=_git_dirty(self.repo_root)[0],
        )
        state_path = self.run_path / "RUN_STATE.json"
        if not state_path.exists():
            atomic_write_json(state_path, asdict(identity))
            write_resolved_config(self.config, self.run_path / "provenance")
            atomic_write_json(self.run_path / "provenance" / "environment.json", capture_environment())
        return self.run_path

    def _event(self, action: str, status: str, payload: dict[str, Any] | None = None) -> None:
        run_path = self._ensure_run()
        event = {"time": datetime.now(tz=timezone.utc).isoformat(), "action": action, "status": status, **(payload or {})}
        with (run_path / "execution" / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")

    def inventory(self, include_untracked: bool = True) -> dict[str, Any]:
        return self.discover(include_untracked=include_untracked)

    def discover(self, include_untracked: bool = True) -> dict[str, Any]:
        run_path = self._ensure_run()
        py_files = sorted(str(p.relative_to(self.repo_root)) for p in self.repo_root.rglob("*.py") if ".git" not in p.parts and ".venv" not in p.parts)
        md_files = sorted(str(p.relative_to(self.repo_root)) for p in self.repo_root.rglob("*.md") if ".git" not in p.parts and ".venv" not in p.parts)
        slurm_files = sorted(str(p.relative_to(self.repo_root)) for p in self.repo_root.rglob("*") if p.suffix in {".slurm", ".sbatch"})
        inventory = {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "run_id": self.run_id,
            "git_sha": _git_sha(self.repo_root),
            "include_untracked": include_untracked,
            "package_cli": "python -m ccb_mc_validation",
            "orchestrator": "scripts/mc_validation/run_pipeline.py",
            "counts": {"python": len(py_files), "markdown": len(md_files), "slurm": len(slurm_files)},
            "python_files": py_files,
            "markdown_files": md_files,
            "slurm_files": slurm_files,
        }
        atomic_write_json(run_path / "execution" / "SCRIPT_INVENTORY.json", inventory)
        self._event("discover", STATUS_DONE, {"python_files": len(py_files), "markdown_files": len(md_files)})
        return inventory

    def preflight(self, allow_dirty: bool = False, strict: bool = False) -> dict[str, Any]:
        run_path = self._ensure_run()
        dirty, diff8 = _git_dirty(self.repo_root)
        checks: list[dict[str, Any]] = []
        checks.append({"name": "git_dirty", "status": "PASS" if (not dirty or allow_dirty) else "FAIL", "dirty": dirty, "diff_hash": diff8})
        for label, path in (("mc_root", self.config.mc_root), ("data_pulses", self.config.data_pulses)):
            rec: dict[str, Any] = {"name": label, "path": str(path)}
            if path.is_file():
                rec.update({"status": "PASS", "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
            else:
                rec["status"] = "MISSING"
            checks.append(rec)
        cluster = self._cluster_probe()
        checks.append({"name": "lunarc_socket", "status": "PASS" if cluster == "REACHABLE" else "BLOCKED", "detail": cluster})
        if any(c["status"] == "FAIL" for c in checks) or (dirty and not allow_dirty):
            status = "FAIL"
        elif any(c["status"] != "PASS" for c in checks):
            status = "BLOCKED"
        else:
            status = "PASS"
        if strict and any(c["status"] != "PASS" for c in checks):
            status = "FAIL"
        preflight = {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "run_id": self.run_id,
            "profile": self.profile,
            "git_sha": _git_sha(self.repo_root),
            "checks": checks,
            "status": status,
        }
        atomic_write_json(run_path / "execution" / "PREFLIGHT.json", preflight)
        (run_path / "execution" / "PREFLIGHT.md").write_text(
            "# Preflight\n\n" + "\n".join(f"- {c['name']}: {c['status']} {c.get('path', c.get('detail', ''))}" for c in checks) + "\n",
            encoding="utf-8",
        )
        self._event("preflight", status, {"cluster": cluster})
        return preflight

    def _running_on_lunarc(self) -> bool:
        """True when this process is already on a LUNARC node (no nested ssh)."""
        markers = (
            Path("/projects/hep/fs10"),
            Path("/home/s/scyiu"),
        )
        if any(p.exists() for p in markers):
            return True
        host = (self.exec_raw.get("cluster", {}) or {}).get("ssh_host", "lunarc") if isinstance(self.exec_raw, dict) else "lunarc"
        try:
            import socket
            return host in socket.gethostname() or "lunarc" in socket.gethostname().lower()
        except OSError:
            return False

    def _slurm_cmd(self, remote_command: str) -> list[str]:
        """Run sacct/sbatch directly on-cluster; ssh only from off-cluster hosts."""
        if self._running_on_lunarc():
            return ["bash", "-lc", remote_command]
        host = (self.exec_raw.get("cluster", {}) or {}).get("ssh_host", "lunarc") if isinstance(self.exec_raw, dict) else "lunarc"
        return ["ssh", "-o", "BatchMode=yes", host, remote_command]

    def _cluster_probe(self) -> str:
        if self._running_on_lunarc():
            return "REACHABLE"
        host = self.exec_raw.get("cluster", {}).get("ssh_host", "lunarc") if isinstance(self.exec_raw, dict) else "lunarc"
        try:
            check = subprocess.run(["ssh", "-O", "check", host], capture_output=True, text=True, timeout=8)
            if check.returncode != 0:
                return f"UNREACHABLE (no active ssh control socket for {host})"
            ping = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, "hostname"], capture_output=True, text=True, timeout=12)
            return "REACHABLE" if ping.returncode == 0 else f"UNREACHABLE ({ping.stderr.strip()[:160]})"
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return f"UNREACHABLE ({exc})"

    def plan(self, studies: str = "all", freeze: bool = False) -> dict[str, Any]:
        run_path = self._ensure_run()
        enabled = self._enabled_studies(studies)
        tasks: list[TaskRecord] = []
        for tid, deps in DAG.items():
            study = tid.split("_", 1)[-1]
            if study.upper().startswith("MV") and study.upper() not in enabled:
                continue
            if self.profile == "smoke" and tid.startswith("prod_"):
                continue
            tasks.append(TaskRecord(task_id=tid, study=study, command=self._command_for_task(tid), dependencies=deps))
        plan = {
            "run_id": self.run_id,
            "profile": self.profile,
            "enabled_studies": enabled,
            "frozen": freeze,
            "tasks": [asdict(t) for t in tasks],
            "dag_mermaid": self._dag_mermaid(tasks),
        }
        atomic_write_json(run_path / "execution" / "PLAN.json", plan)
        (run_path / "execution" / "PLAN.md").write_text("# Execution plan\n\n```mermaid\n" + plan["dag_mermaid"] + "\n```\n", encoding="utf-8")
        self._write_task_registry(tasks)
        self._event("plan", STATUS_DONE, {"tasks": len(tasks)})
        return plan

    def _command_for_task(self, task_id: str) -> str:
        if task_id.startswith("prod_") or task_id in {"figures", "notebooks", "thesis"}:
            return f"sbatch --parsable geant4/jobs/mc_validation_pipeline.sbatch {task_id}"
        return f"python scripts/mc_validation/run_pipeline.py --run-id {self.run_id or '<RUN_ID>'} {task_id.split('_')[0]}"

    def _enabled_studies(self, studies: str) -> list[str]:
        if studies.lower() in {"all", "all-core"}:
            return CANONICAL_STUDIES[:]
        return [s.strip().upper() for s in studies.split(",") if s.strip()]

    def _dag_mermaid(self, tasks: Sequence[TaskRecord]) -> str:
        ids = {t.task_id for t in tasks}
        lines = ["flowchart TD"]
        for t in tasks:
            if not t.dependencies:
                lines.append(f"  {t.task_id}")
            for dep in t.dependencies:
                if dep in ids:
                    lines.append(f"  {dep} --> {t.task_id}")
        return "\n".join(lines)

    def _write_task_registry(self, tasks: Sequence[TaskRecord]) -> None:
        run_path = self._ensure_run()
        atomic_write_json(run_path / "registry" / "TASK_REGISTRY.json", [asdict(t) for t in tasks])

    def test(self, scope: str = "unit", strict: bool = False) -> dict[str, Any]:
        run_path = self._ensure_run()
        cmd = [sys.executable, "-m", "pytest", "-q"]
        if scope == "integration":
            cmd.append("tests/integration")
        elif scope == "all":
            cmd.append("tests/")
        else:  # "unit" (default) -- exclude integration
            cmd += ["tests/", "--ignore=tests/integration"]
        if strict:
            cmd += ["-x", "--strict-markers"]
        started = datetime.now(tz=timezone.utc).isoformat()
        proc = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True)
        log_path = run_path / "execution" / "pytest.log"
        log_path.write_text(proc.stdout + proc.stderr, encoding="utf-8")
        result = {"command": cmd, "scope": scope, "started_at": started, "finished_at": datetime.now(tz=timezone.utc).isoformat(), "returncode": proc.returncode, "log": str(log_path), "status": "PASS" if proc.returncode == 0 else "FAIL"}
        atomic_write_json(run_path / "execution" / "TEST.json", result)
        self._event("test", result["status"], {"returncode": proc.returncode})
        return result

    def fixture(self, workers: int = 1, shards: int = 1) -> str:
        return self.smoke(studies="MV0,MV1,MV2,MV3,MV9", fixture=True, workers=workers, shards=shards)

    @staticmethod
    def _aggregate_smoke_status(results: dict[str, Any]) -> str:
        """FAIL-closed gate: PASS only if every study result is PASS (and at least one ran)."""
        if not results:
            return "FAIL"
        return "PASS" if all(r.get("status") == "PASS" for r in results.values()) else "FAIL"

    def smoke(self, studies: str = "all", fixture: bool = True, workers: int = 1, shards: int = 1) -> str:
        run_path = self._ensure_run()
        seed = int(self.config.seeds.get("global", 424242))
        records = _synthetic_records(1000, seed)
        results: dict[str, Any] = {}
        enabled = self._enabled_studies(studies)
        if "MV1" in enabled:
            r = run_mv1(records, fixture=True); write_study_result(r, run_path / "MV1"); results["MV1"] = r.to_dict()
        if "MV2" in enabled:
            r = run_mv2(records, fixture=True); write_study_result(r, run_path / "MV2"); results["MV2"] = r.to_dict()
        if "MV3" in enabled:
            r = run_mv3(records, fixture=True, data_profiles=None); write_study_result(r, run_path / "MV3"); results["MV3"] = r.to_dict()
        if "MV0" in enabled:
            pipe = DigitizerPipeline.from_config(self.exec_raw.get("digitizer", self.config.raw.get("digitizer", {})))
            dig = pipe.run([{"edep_mev": 2.5, "time_ns": 0.0}], event_id=seed)["adc"]
            atomic_write_json(run_path / "MV0" / "smoke_waveform.json", {"samples": dig.tolist(), "status": STATUS_FIXTURE, "not_for_physics": True})
            results["MV0"] = {"status": STATUS_FIXTURE, "n_samples": int(len(dig))}
        for mv in ("MV4", "MV5", "MV6", "MV7", "MV8"):
            if mv in enabled:
                blocker = {"status": STATUS_BLOCKED, "reason": "requires calibrated MV0 and truth-labelled digitized MC; production implementation must run under SLURM", "not_for_physics": True}
                atomic_write_json(run_path / mv / "BLOCKED.json", blocker)
                results[mv] = blocker
        if "MV9" in enabled:
            synth_out = run_path / "MV9" / "MV9_SYNTHESIS.md"
            try:
                synthesize_mv9(self.repo_root / "reports/mc_validation_registry.json", out_path=synth_out)
            except Exception as exc:  # keep smoke gate honest but non-fatal for missing registry
                synth_out.write_text(f"# MV9 synthesis\n\nBLOCKED: {exc}\n", encoding="utf-8")
            results["MV9"] = {"status": STATUS_SMOKE, "artifact": str(synth_out)}
        gate_status = self._aggregate_smoke_status(results)
        gate = {"run_id": self.run_id, "status": gate_status, "mode": STATUS_FIXTURE if fixture else STATUS_SMOKE, "studies": results, "workers": workers, "shards": shards, "not_for_physics": True}
        atomic_write_json(run_path / "SMOKE_GATE.json", gate)
        (run_path / "SMOKE_GATE.md").write_text(f"# Smoke gate\n\nStatus: **{gate_status}** ({gate['mode']}; not for physics)\n\nRun ID: `{self.run_id}`\n", encoding="utf-8")
        self._event("smoke", "PASS", {"studies": list(results)})
        return str(self.run_id)

    def submit(self, studies: str = "all", dry_run: bool = False) -> dict[str, Any]:
        run_path = self._ensure_run()
        pre = self.preflight(allow_dirty=True)
        cluster_ok = any(c["name"] == "lunarc_socket" and c["status"] == "PASS" for c in pre["checks"])
        mc_ok = any(c["name"] == "mc_root" and c["status"] == "PASS" for c in pre["checks"])
        jobs: dict[str, Any] = {}
        if not cluster_ok or not mc_ok:
            blocker = {
                "status": STATUS_BLOCKED,
                "reason": "lunarc_unreachable" if not cluster_ok else "mc_root_missing",
                "cluster_reachable": cluster_ok,
                "mc_root_present": mc_ok,
                "resume_command": f"python scripts/mc_validation/run_pipeline.py --run-id {self.run_id} --profile production submit --studies {studies}",
                "heavy_compute_policy": "No production MV/GEANT4/full ROOT/notebook work may run locally or on a LUNARC login node.",
            }
            atomic_write_json(run_path / "blockers" / "PRODUCTION_SUBMIT_BLOCKED.json", blocker)
            self._write_production_status_report(run_path, status=STATUS_BLOCKED, reason=blocker["reason"], resume_command=blocker["resume_command"], extra={"cluster_reachable": cluster_ok, "mc_root_present": mc_ok})
            self._event("submit", STATUS_BLOCKED, blocker)
            return blocker
        if dry_run:
            result = {"status": "DRY_RUN", "message": "Cluster and inputs available; sbatch submission suppressed."}
            atomic_write_json(run_path / "execution" / "SUBMIT_DRY_RUN.json", result)
            return result
        # Submit canonical batch driver; actual heavy worker must enforce SLURM_JOB_ID.
        cmd = ["ssh", "lunarc", f"cd {self.exec_raw.get('cluster', {}).get('project_root', '/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam')} && sbatch --parsable geant4/jobs/mc_validation_pipeline.sbatch {self.run_id} {studies}"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        job_id = proc.stdout.strip().splitlines()[-1] if proc.returncode == 0 and proc.stdout.strip() else None
        status = STATUS_SUBMITTED if proc.returncode == 0 else STATUS_FAILED
        jobs["all-core"] = {"status": status, "job_id": job_id, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "command": cmd}
        atomic_write_json(run_path / "execution" / "JOB_REGISTRY.json", jobs)
        self._event("submit", status, {"job_id": job_id})
        return {"status": status, "jobs": jobs}

    def watch(self, run_id: str | None = None, until_terminal: bool = False, poll_interval_seconds: int = 60) -> dict[str, Any]:
        path = self._ensure_run(run_id)
        registry_path = path / "execution" / "JOB_REGISTRY.json"
        if not registry_path.is_file():
            result = {"status": STATUS_BLOCKED, "reason": "no submitted jobs", "run_id": self.run_id}
            atomic_write_json(path / "execution" / "WATCH.json", result)
            return result
        jobs = json.loads(registry_path.read_text(encoding="utf-8"))
        for rec in jobs.values():
            jid = rec.get("job_id")
            if jid:
                rec["sacct_probe"] = self._sacct(jid)
        result = {"status": "UPDATED", "jobs": jobs, "until_terminal": until_terminal}
        atomic_write_json(path / "execution" / "WATCH.json", result)
        return result

    monitor = watch

    def _sacct(self, job_id: str) -> dict[str, Any]:
        try:
            cmd = self._slurm_cmd(f"sacct -X -j {job_id} --format=JobID,State,ExitCode -P")
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "command": cmd}
        except Exception as exc:
            return {"returncode": -1, "error": str(exc)}

    def status(self, run_id: str | None = None, all_runs: bool = False) -> dict[str, Any]:
        if all_runs:
            runs = sorted(p.name for p in self._artifact_root().glob("*") if p.is_dir()) if self._artifact_root().exists() else []
            return {"artifact_root": str(self._artifact_root()), "runs": runs}
        path = self._ensure_run(run_id)
        state = json.loads((path / "RUN_STATE.json").read_text(encoding="utf-8")) if (path / "RUN_STATE.json").is_file() else {"run_id": self.run_id}
        blockers = sorted(str(p.relative_to(path)) for p in (path / "blockers").glob("*.json")) if (path / "blockers").exists() else []
        return {"run": state, "blockers": blockers, "path": str(path)}

    def collect(self, run_id: str | None = None) -> dict[str, Any]:
        path = self._ensure_run(run_id)
        artifacts: list[str] = []
        for pattern in ("**/SMOKE_GATE.json", "**/JOB_REGISTRY.json", "**/WATCH.json", "**/*SUMMARY*.json", "**/MV*/**/*.json"):
            for p in path.glob(pattern):
                if p.is_file():
                    artifacts.append(str(p.relative_to(path)))
        registry_path = path / "execution" / "JOB_REGISTRY.json"
        jobs = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {}
        completed = False
        for rec in jobs.values() if isinstance(jobs, dict) else []:
            probe = rec.get("sacct_probe") or {}
            stdout = str(probe.get("stdout") or "")
            if "COMPLETED" in stdout:
                completed = True
        smoke = path / "SMOKE_GATE.json"
        if smoke.is_file() and not jobs:
            payload = json.loads(smoke.read_text(encoding="utf-8"))
            result = {
                "status": payload.get("status", STATUS_SMOKE),
                "mode": "smoke_collect",
                "run_id": self.run_id,
                "artifacts": sorted(set(artifacts)),
                "not_for_physics": True,
                "dag_ready": True,
            }
            atomic_write_json(path / "execution" / "COLLECT.json", result)
            self._event("collect", result["status"], {"artifacts": len(result["artifacts"])})
            return result
        if not completed and not artifacts:
            result = {"status": STATUS_BLOCKED, "reason": "No completed LUNARC production jobs to collect", "run_id": self.run_id}
            atomic_write_json(path / "execution" / "COLLECT.json", result)
            self._write_production_status_report(path, status=STATUS_BLOCKED, reason=result["reason"])
            return result
        result = {
            "status": STATUS_DONE if completed else STATUS_SMOKE,
            "run_id": self.run_id,
            "jobs": jobs,
            "artifacts": sorted(set(artifacts)),
            "not_for_physics": not completed,
            "dag_ready": True,
        }
        atomic_write_json(path / "execution" / "COLLECT.json", result)
        self._event("collect", result["status"], {"artifacts": len(result["artifacts"])})
        return result

    
    def validate(self, run_id: str | None = None, scope: str = "all", strict: bool = False) -> dict[str, Any]:
        path = self._ensure_run(run_id)
        checks: list[dict[str, Any]] = []

        def add(name: str, ok: bool, **extra: Any) -> None:
            checks.append({"name": name, "status": "PASS" if ok else ("FAIL" if strict else STATUS_BLOCKED), **extra})

        job_state_path = path / "JOB_STATE.json"
        if job_state_path.is_file():
            job_state = json.loads(job_state_path.read_text(encoding="utf-8"))
            add(
                "job_state_completed",
                job_state.get("state") == "COMPLETED" and job_state.get("exit_code") == "0:0",
                job_id=job_state.get("job_id"),
                state=job_state.get("state"),
                exit_code=job_state.get("exit_code"),
            )
        else:
            job_state = {}
            add("job_state_completed", False, reason="missing JOB_STATE.json")

        preflight_path = path / "execution" / "PREFLIGHT.json"
        if preflight_path.is_file():
            preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
            input_checks = {c.get("name"): c for c in preflight.get("checks", []) if isinstance(c, dict)}
            add("preflight_mc_root", input_checks.get("mc_root", {}).get("status") == "PASS", path=input_checks.get("mc_root", {}).get("path"), sha256=input_checks.get("mc_root", {}).get("sha256"))
            add("preflight_data_pulses", input_checks.get("data_pulses", {}).get("status") == "PASS", path=input_checks.get("data_pulses", {}).get("path"), sha256=input_checks.get("data_pulses", {}).get("sha256"))
        else:
            preflight = {}
            add("preflight_present", False, reason="missing execution/PREFLIGHT.json")

        study_metrics: dict[str, Any] = {}
        required_studies = {
            "MV1": path / "reports" / "mc_validation" / "mv1_pid" / "study_result.json",
            "MV2": path / "reports" / "mc_validation" / "mv2_energy" / "study_result.json",
            "MV3": path / "reports" / "mc_validation" / "mv3_stopping_depth" / "study_result.json",
        }
        for study, result_path in required_studies.items():
            if not result_path.is_file():
                add(f"{study}_study_result", False, reason=f"missing {result_path.relative_to(path)}")
                continue
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            metrics = payload.get("metrics", {}) if isinstance(payload, dict) else {}
            cutflow = payload.get("cutflow", {}) if isinstance(payload, dict) else {}
            ok = payload.get("status") == STATUS_PRODUCTION and int(cutflow.get("n_tracks", 0)) > 0
            add(f"{study}_study_result", ok, study_status=payload.get("status"), n_tracks=cutflow.get("n_tracks"), path=str(result_path.relative_to(path)))
            study_metrics[study] = {"status": payload.get("status"), "metrics": metrics, "cutflow": cutflow}

        mv9_path = path / "reports" / "mc_validation" / "mv9_synthesis" / "MV9_SYNTHESIS.md"
        if mv9_path.is_file():
            mv9_text = mv9_path.read_text(encoding="utf-8")
            add("MV9_synthesis", "| MV1 | PRODUCTION |" in mv9_text and "MV4 | BLOCKED" in mv9_text, path=str(mv9_path.relative_to(path)))
        else:
            add("MV9_synthesis", False, reason="missing MV9 synthesis")

        logs = list((path / "logs").glob("ccb_mc_validation_*.out")) if (path / "logs").is_dir() else []
        add("slurm_logs_present", bool(logs), count=len(logs))

        if scope in {"all", "release"}:
            fixture_leak = self._fixture_release_leak(path)
            add("fixture_not_released", not fixture_leak, matches=fixture_leak)

        status = "PASS" if all(c["status"] == "PASS" for c in checks) else ("FAIL" if strict else STATUS_BLOCKED)
        report = {
            "run_id": self.run_id,
            "scope": scope,
            "strict": strict,
            "status": status,
            "job_state": job_state,
            "study_metrics": study_metrics,
            "checks": checks,
        }
        atomic_write_json(path / "VALIDATION.json", report)
        summary_lines = [
            "# MC Validation Artifact Validation Summary",
            "",
            f"- **Run ID:** `{self.run_id}`",
            f"- **Status:** **{status}**",
            f"- **Job ID:** `{job_state.get('job_id', 'unknown')}`",
            f"- **Job state:** `{job_state.get('state', 'unknown')}` / `{job_state.get('exit_code', 'unknown')}`",
            "",
            "## Checks",
            "",
        ]
        summary_lines.extend(f"- {c['name']}: `{c['status']}`" for c in checks)
        summary_lines.extend(["", "## Study support", ""])
        for study, rec in study_metrics.items():
            cutflow = rec.get("cutflow", {})
            metrics = rec.get("metrics", {})
            key_bits = []
            for key in ("hgb_auc", "hgb_purity_at_90eff", "proton_ekin_recon_res68", "deuteron_ekin_recon_res68"):
                if key in metrics:
                    key_bits.append(f"{key}={metrics[key]}")
            summary_lines.append(f"- {study}: `{rec.get('status')}`, n_tracks={cutflow.get('n_tracks')}, " + ", ".join(key_bits))
        summary_lines.extend([
            "",
            "## Release guardrail",
            "",
            "This validation confirms artifact consistency for MV1-MV3 and MV9 only. It does not complete figures, notebooks, thesis, uncertainty/systematic arrays, or final release audit.",
        ])
        (path / "VALIDATION_SUMMARY.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
        (path / "FINAL_AUDIT.md").write_text("# Final audit\n\n" + "\n".join(f"- {c['name']}: {c['status']}" for c in checks) + f"\n\nStatus: **{status}**\n", encoding="utf-8")
        if status != "PASS":
            self._write_production_status_report(path, status=status, reason="validation gates not satisfied", extra={"validation_checks": checks})
        return report


    def _fixture_release_leak(self, path: Path) -> list[str]:
        matches: list[str] = []
        for p in [self.repo_root / "README.md", self.repo_root / "PROJECT_REPORT.md", self.repo_root / "FINDINGS_SYNTHESIS.md"]:
            if p.is_file() and "FIXTURE" in p.read_text(encoding="utf-8", errors="ignore"):
                matches.append(str(p.relative_to(self.repo_root)))
        return matches

    def qa(self, run_id: str | None = None, scope: str = "all", strict: bool = False) -> dict[str, Any]:
        path = self._ensure_run(run_id)
        validation = self.validate(run_id=run_id, scope=scope, strict=strict)
        audit = generate_release_audit(path)
        claims = generate_claim_ledger(path)
        audit = generate_release_audit(path, include_claim_ledger=True)
        return {"status": audit["status"], "validation": validation, "release_audit": audit, "claim_ledger": claims}

    def plot(self, run_id: str | None = None) -> dict[str, Any]:
        path = self._ensure_run(run_id)
        val_path = path / "VALIDATION.json"
        if val_path.is_file():
            # Fail-closed (VAL-003): plots require a PASSING validation, not just a file.
            try:
                _val = json.loads(val_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                _val = {}
            if _val.get("status") != "PASS":
                result = {"status": STATUS_BLOCKED, "reason": f"plotting gated on VALIDATION.status==PASS (got {_val.get('status')!r})"}
                atomic_write_json(path / "figures" / "PLOT_BLOCKED.json", result)
                self._write_production_status_report(path, status=STATUS_BLOCKED, reason=result["reason"])
                return result
            artifacts = generate_run_summary(path)
            figure_manifest = generate_summary_figure_manifest(path)
            visual_review = generate_summary_visual_review(path)
            result = {"status": "PASS", "run_id": self.run_id, "artifacts": artifacts, "figures": figure_manifest, "visual_review": visual_review, "scope": "summary"}
            atomic_write_json(path / "figures" / "PLOT_SUMMARY.json", result)
            return result
        result = {"status": STATUS_BLOCKED, "reason": "Full figure suite requires completed production artifacts and LUNARC batch rendering"}
        atomic_write_json(path / "figures" / "PLOT_BLOCKED.json", result)
        self._write_production_status_report(path, status=STATUS_BLOCKED, reason=result["reason"])
        return result

    def notebooks(self, run_id: str | None = None, execute: bool = False) -> dict[str, Any]:
        path = self._ensure_run(run_id)
        if execute:
            result = {
                "status": STATUS_BLOCKED,
                "execute": execute,
                "reason": "Full-data notebook execution must be submitted as a LUNARC sbatch job; artifact-only export is available without --execute.",
                "sbatch_required": True,
            }
            atomic_write_json(path / "notebooks" / "NOTEBOOKS_BLOCKED.json", result)
            self._write_production_status_report(path, status=STATUS_BLOCKED, reason=result["reason"], extra={"notebook_execute_requested": execute})
            return result
        try:
            manifest = generate_notebook_exports(path)
        except (FileNotFoundError, ValueError) as exc:
            result = {"status": STATUS_BLOCKED, "execute": execute, "reason": str(exc)}
            atomic_write_json(path / "notebooks" / "NOTEBOOKS_BLOCKED.json", result)
            self._write_production_status_report(path, status=STATUS_BLOCKED, reason=result["reason"], extra={"notebook_execute_requested": execute})
            return result
        self._event("notebooks", manifest["status"], {"scope": manifest["scope"], "full_suite": manifest["full_notebook_suite_status"]})
        return manifest

    def docs(self, run_id: str | None = None) -> dict[str, Any]:
        path = self._ensure_run(run_id)
        try:
            manifest = generate_artifact_reports(path)
        except (FileNotFoundError, ValueError) as exc:
            result = {"status": STATUS_BLOCKED, "reason": str(exc)}
            atomic_write_json(path / "reports" / "DOCS_BLOCKED.json", result)
            self._write_production_status_report(path, status=STATUS_BLOCKED, reason=result["reason"])
            return result
        self._event("docs", manifest["status"], {"scope": manifest["scope"], "full_suite": manifest["full_report_suite_status"]})
        return manifest

    def thesis(self, run_id: str | None = None) -> dict[str, Any]:
        path = self._ensure_run(run_id)
        try:
            manifest = generate_thesis_draft(path)
        except (FileNotFoundError, ValueError) as exc:
            result = {"status": STATUS_BLOCKED, "reason": str(exc)}
            atomic_write_json(path / "reports" / "THESIS_BLOCKED.json", result)
            self._write_production_status_report(path, status=STATUS_BLOCKED, reason=result["reason"])
            return result
        self._event("thesis", manifest["status"], {"scope": manifest["scope"], "final_thesis_status": manifest["final_thesis_status"]})
        return manifest

    def _write_production_status_report(
        self,
        path: Path,
        *,
        status: str,
        reason: str,
        resume_command: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state_path = path / "RUN_STATE.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {"run_id": self.run_id}
        smoke_path = path / "SMOKE_GATE.json"
        smoke = json.loads(smoke_path.read_text(encoding="utf-8")) if smoke_path.is_file() else None
        job_path = path / "execution" / "JOB_REGISTRY.json"
        jobs = json.loads(job_path.read_text(encoding="utf-8")) if job_path.is_file() else {}
        blockers = sorted(str(p.relative_to(path)) for p in (path / "blockers").glob("*.json")) if (path / "blockers").exists() else []
        payload: dict[str, Any] = {
            "run_id": state.get("run_id", self.run_id),
            "git_sha": state.get("git_sha", _git_sha(self.repo_root)),
            "profile": state.get("profile", self.profile),
            "status": status,
            "reason": reason,
            "resume_command": resume_command or f"python scripts/mc_validation/run_pipeline.py --run-id {self.run_id} --profile production submit --studies all",
            "blockers": blockers,
            "job_count": len(jobs),
            "smoke_gate": smoke,
            "production_claims_allowed": False,
            "heavy_compute_policy": "Production GEANT4, full ROOT scans, digitization, ML training, systematic/bootstrap arrays, and full-data notebooks must run only via LUNARC sbatch on compute nodes.",
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        if extra:
            payload.update(extra)
        report_dir = path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(report_dir / "PRODUCTION_STATUS.json", payload)
        lines = [
            "# MC Validation Production Status",
            "",
            f"- **Run ID:** `{payload['run_id']}`",
            f"- **Git SHA:** `{payload['git_sha']}`",
            f"- **Profile:** `{payload['profile']}`",
            f"- **Status:** **{payload['status']}**",
            f"- **Reason:** {payload['reason']}",
            f"- **Production claims allowed:** `{payload['production_claims_allowed']}`",
            "",
            "## Resume command",
            "",
            "```bash",
            str(payload["resume_command"]),
            "```",
            "",
            "## Heavy-compute policy",
            "",
            payload["heavy_compute_policy"],
            "",
            "## Blockers",
            "",
        ]
        if blockers:
            lines.extend(f"- `{b}`" for b in blockers)
        else:
            lines.append("- None recorded.")
        lines.extend(["", "## Smoke/fixture evidence", ""])
        if smoke:
            lines.extend([
                f"- Smoke status: `{smoke.get('status')}`",
                f"- Mode: `{smoke.get('mode')}`",
                "- Fixture/smoke outputs are wiring evidence only and are not physics results.",
            ])
        else:
            lines.append("- No smoke gate recorded for this run.")
        lines.extend(["", "## LUNARC job registry", ""])
        if jobs:
            for name, rec in jobs.items():
                lines.append(f"- `{name}`: status `{rec.get('status')}`, job `{rec.get('job_id')}`")
        else:
            lines.append("- No production SLURM jobs submitted for this run.")
        (report_dir / "PRODUCTION_STATUS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return payload

    def release(self, run_id: str | None = None) -> dict[str, Any]:
        path = self._ensure_run(run_id)
        try:
            generate_reference_registry(path)
            generate_notation_registry(path)
            generate_open_question_registry(path)
            generate_question_closure_plan(path)
            generate_evidence_packets(path)
            generate_study_gap_audit(path)
            manifest = generate_publication_index(path)
            wiki = generate_wiki_export(path)
            # Wiki export needs the publication manifest, while the final
            # publication index should expose generated wiki pages such as the
            # claim-evidence matrix. Regenerate once after wiki export so the
            # final manifest is the reader-facing linked draft index.
            manifest = generate_publication_index(path)
            manifest["wiki"] = wiki
        except (FileNotFoundError, ValueError) as exc:
            result = {"status": STATUS_BLOCKED, "reason": str(exc)}
            atomic_write_json(path / "release_BLOCKED.json", result)
            return result
        if manifest["status"] == "PASS":
            latest = {"run_id": self.run_id, "released_at": datetime.now(tz=timezone.utc).isoformat(), "validation": "PASS", "publication_manifest": manifest["index_html"]}
            atomic_write_json(self.repo_root / "reports/mc_validation/latest.json", latest)
        else:
            atomic_write_json(
                path / "release_BLOCKED.json",
                {
                    "status": STATUS_BLOCKED,
                    "publication": manifest,
                    "blocker_digest": _release_blocker_digest(path, manifest),
                },
            )
        self._event("release", manifest["status"], {"scope": manifest["scope"], "release_ready": manifest["release_ready"]})
        return manifest

    def resume(self, run_id: str | None = None) -> dict[str, Any]:
        path = self._ensure_run(run_id)
        status = self.status(self.run_id)
        self._event("resume", "READY", {"path": str(path)})
        return status

    def all(self, studies: str = "all", wait_until_terminal: bool = False, continue_independent: bool = True, resume: bool = True) -> dict[str, Any]:
        self.plan(studies=studies, freeze=True)
        submit = self.submit(studies=studies)
        watch = self.watch(until_terminal=wait_until_terminal) if submit.get("status") == STATUS_SUBMITTED else {"status": STATUS_BLOCKED, "reason": "submit did not start"}
        return {"submit": submit, "watch": watch, "continue_independent": continue_independent, "resume": resume}
