from __future__ import annotations

from pathlib import Path

import pytest

from ccb_mc_validation.raw_root_paths import (
    ENV_RAW_ROOT_DIR,
    default_raw_root_candidates,
    resolve_raw_root_dir,
)


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_resolve_prefers_canonical_before_repo_alias(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical" / "root" / "root"
    alias = tmp_path / "repo" / "data" / "extracted" / "root" / "root"
    _touch(canonical / "hrdb_run_0058.root")
    _touch(alias / "hrdb_run_0065.root")

    resolution = resolve_raw_root_dir(
        candidates=[
            (canonical, "canonical-worker-mount"),
            (alias, "repo-relative-alias"),
        ]
    )

    assert resolution.raw_root_dir == str(canonical)
    assert resolution.source == "canonical-worker-mount"
    assert resolution.probes[0].n_hrdb == 1


def test_resolve_falls_back_to_repo_alias(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    alias = tmp_path / "repo" / "data" / "extracted" / "root" / "root"
    _touch(alias / "hrdb_run_0058.root")

    resolution = resolve_raw_root_dir(
        candidates=[
            (missing, "canonical-worker-mount"),
            (alias, "repo-relative-alias"),
        ]
    )

    assert resolution.raw_root_dir == str(alias)
    assert [probe.usable for probe in resolution.probes] == [False, True]


def test_resolve_requires_b_stack_root_files(tmp_path: Path) -> None:
    only_a = tmp_path / "only-a"
    _touch(only_a / "hrda_run_0058.root")

    with pytest.raises(FileNotFoundError, match="no usable B-stack raw ROOT directory"):
        resolve_raw_root_dir(candidates=[(only_a, "candidate")])


def test_env_candidate_is_first(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_dir = tmp_path / "env" / "root" / "root"
    monkeypatch.setenv(ENV_RAW_ROOT_DIR, str(env_dir))

    candidates = default_raw_root_candidates(repo_root=tmp_path / "repo")

    assert candidates[0] == (env_dir, f"env:{ENV_RAW_ROOT_DIR}")
