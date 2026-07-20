"""RunManifest builder — records the provenance of a single run.

Conforms to schemas/run_manifest.schema.json. Every run must record: git
commit, config, input hashes, environment, command, seed policy, wall-clock
window, and output hashes (see runbooks/DEFINITION_OF_DONE.md).
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from typing import Any

from .hashing import file_record

__all__ = ["RunManifest", "detect_git_commit", "default_environment"]

# Sentinel so ``git_commit=None`` (explicitly disable auto-detect) is
# distinguishable from ``git_commit`` omitted (auto-detect).
_AUTO = object()


def detect_git_commit(cwd: str | None = None) -> str | None:
    """Best-effort ``git rev-parse HEAD``. Returns 40-hex string or None."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    commit = out.stdout.strip()
    return commit or None


def _pkg_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None
    except Exception:  # pragma: no cover - defensive
        return None


def default_environment() -> dict[str, Any]:
    """Best-effort environment capture (python, platform, key pkg versions)."""
    env: dict[str, Any] = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
    }
    for pkg in ("numpy", "pandas", "scipy"):
        env[f"{pkg}_version"] = _pkg_version(pkg)
    return env


def _iso_utc() -> str:
    """Timezone-aware ISO-8601 UTC timestamp (RFC-3339, seconds precision)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class RunManifest:
    """Incrementally builds a run-manifest dict.

    git_commit defaults to auto-detection via ``git rev-parse HEAD``. Pass an
    explicit 40-hex string to override (e.g. on a machine without git), or
    pass ``git_commit=None`` to skip detection entirely (the field is then
    left unset until you assign it, and the manifest will fail schema
    validation — which is the intended signal that provenance is incomplete).
    """

    def __init__(
        self,
        task_id: str,
        command: list[str],
        *,
        git_commit: Any = _AUTO,
        host: str | None = None,
        slurm_job_id: str | None = None,
        seed_policy: str | None = None,
        cwd: str | None = None,
        dirty: bool | None = None,
    ) -> None:
        if not task_id:
            raise ValueError("task_id must be a non-empty string")
        if not command:
            raise ValueError("command must be a non-empty list of strings")
        self.task_id = task_id
        self.command = list(command)
        self.cwd = cwd if cwd is not None else os.getcwd()

        if git_commit is _AUTO:
            self.git_commit = detect_git_commit(self.cwd)
        else:
            self.git_commit = git_commit

        self.host = host if host is not None else platform.node()
        self.slurm_job_id = (
            slurm_job_id
            if slurm_job_id is not None
            else os.environ.get("SLURM_JOB_ID")
        )
        self.seed_policy = seed_policy
        self.dirty = dirty

        self.inputs: list[dict[str, Any]] = []
        self.configs: list[dict[str, Any]] = []
        self.outputs: list[dict[str, Any]] = []
        self.environment: dict[str, Any] = default_environment()

        self.started_utc: str | None = None
        self.finished_utc: str | None = None

    # -- file records -----------------------------------------------------
    def add_input(self, path: str | os.PathLike[str]) -> dict[str, Any]:
        rec = file_record(path)
        self.inputs.append(rec)
        return rec

    def add_config(self, path: str | os.PathLike[str]) -> dict[str, Any]:
        rec = file_record(path)
        self.configs.append(rec)
        return rec

    def add_output(self, path: str | os.PathLike[str]) -> dict[str, Any]:
        rec = file_record(path)
        self.outputs.append(rec)
        return rec

    # -- environment / timing --------------------------------------------
    def set_environment(self, env: dict[str, Any], *, merge: bool = True) -> None:
        if merge:
            self.environment.update(env)
        else:
            self.environment = dict(env)

    def start(self) -> str:
        self.started_utc = _iso_utc()
        return self.started_utc

    def finish(self) -> str:
        self.finished_utc = _iso_utc()
        return self.finished_utc

    # -- serialization ----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "task_id": self.task_id,
            "git_commit": self.git_commit,
            "command": list(self.command),
            "cwd": self.cwd,
            "started_utc": self.started_utc if self.started_utc else _iso_utc(),
            "inputs": list(self.inputs),
            "configs": list(self.configs),
            "outputs": list(self.outputs),
            "environment": dict(self.environment),
        }
        if self.finished_utc is not None:
            d["finished_utc"] = self.finished_utc
        if self.host is not None:
            d["host"] = self.host
        # slurm_job_id is nullable in the schema; always emit for clarity.
        d["slurm_job_id"] = self.slurm_job_id
        if self.seed_policy is not None:
            d["seed_policy"] = self.seed_policy
        if self.dirty is not None:
            d["dirty"] = self.dirty
        return d

    def write(self, path: str | os.PathLike[str]) -> str:
        p = os.fspath(path)
        parent = os.path.dirname(p)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, sort_keys=True)
            fh.write("\n")
        return p


if __name__ == "__main__":  # pragma: no cover - manual smoke
    m = RunManifest(task_id="SMOKE", command=[sys.executable, "-c", "pass"])
    m.start()
    m.finish()
    print(json.dumps(m.to_dict(), indent=2, sort_keys=True))
