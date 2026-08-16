"""Raw ROOT path resolution for portable beam-data audits."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

CANONICAL_RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
LEGACY_RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")
REPO_RELATIVE_RAW_ROOT_DIR = Path("data/extracted/root/root")
ENV_RAW_ROOT_DIR = "CCB_RAW_ROOT_DIR"


@dataclass(frozen=True)
class RawRootProbe:
    """Result of checking one candidate raw ROOT directory."""

    path: str
    exists: bool
    is_dir: bool
    n_hrda: int
    n_hrdb: int
    n_total: int
    usable: bool
    role: str


@dataclass(frozen=True)
class RawRootResolution:
    """Resolved raw ROOT directory plus all probe evidence."""

    raw_root_dir: str
    source: str
    probes: list[RawRootProbe]

    def as_dict(self) -> dict[str, object]:
        return {
            "raw_root_dir": self.raw_root_dir,
            "source": self.source,
            "probes": [asdict(probe) for probe in self.probes],
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


def default_raw_root_candidates(repo_root: Path | None = None) -> list[tuple[Path, str]]:
    """Return raw ROOT candidates in preferred resolution order.

    The worker-visible canonical mount is checked before repo-relative and
    legacy aliases so stale local symlinks cannot silently win.
    """

    candidates: list[tuple[Path, str]] = []
    env_value = os.environ.get(ENV_RAW_ROOT_DIR)
    if env_value:
        candidates.append((Path(env_value), f"env:{ENV_RAW_ROOT_DIR}"))
    candidates.append((CANONICAL_RAW_ROOT_DIR, "canonical-worker-mount"))
    if repo_root is not None:
        candidates.append((repo_root / REPO_RELATIVE_RAW_ROOT_DIR, "repo-relative-alias"))
    candidates.append((LEGACY_RAW_ROOT_DIR, "legacy-absolute-alias"))
    return candidates


def probe_raw_root_dir(path: Path, *, role: str = "candidate") -> RawRootProbe:
    """Inspect a candidate directory without opening ROOT payload bytes."""

    exists = path.exists()
    is_dir = path.is_dir()
    n_hrda = len(list(path.glob("hrda_run_*.root"))) if is_dir else 0
    n_hrdb = len(list(path.glob("hrdb_run_*.root"))) if is_dir else 0
    n_total = n_hrda + n_hrdb
    return RawRootProbe(
        path=str(path),
        exists=exists,
        is_dir=is_dir,
        n_hrda=n_hrda,
        n_hrdb=n_hrdb,
        n_total=n_total,
        usable=is_dir and n_hrdb > 0,
        role=role,
    )


def resolve_raw_root_dir(
    repo_root: Path | None = None,
    candidates: Iterable[tuple[Path, str] | Path] | None = None,
) -> RawRootResolution:
    """Resolve the first usable raw ROOT directory and retain probe evidence."""

    raw_candidates = (
        candidates if candidates is not None else default_raw_root_candidates(repo_root)
    )
    probes: list[RawRootProbe] = []
    for item in raw_candidates:
        if isinstance(item, tuple):
            path, role = item
        else:
            path, role = item, "candidate"
        probe = probe_raw_root_dir(path, role=role)
        probes.append(probe)
        if probe.usable:
            return RawRootResolution(raw_root_dir=probe.path, source=probe.role, probes=probes)
    tried = ", ".join(probe.path for probe in probes) or "<none>"
    raise FileNotFoundError(f"no usable B-stack raw ROOT directory found; tried: {tried}")
