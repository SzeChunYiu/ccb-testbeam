"""Wave D Lane 01: authorising reads cannot use mutable generation paths (#1149)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ccb_mc_validation.s00_authorising_read import forbid_generation_path_for_authorising_read


def test_forbid_generation_path(tmp_path: Path) -> None:
    root = tmp_path / "generations"
    target = root / "g1" / "data.csv"
    target.parent.mkdir(parents=True)
    target.write_text("a\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="#1149|authorising_artifact_snapshot"):
        forbid_generation_path_for_authorising_read(target, root)


def test_outside_generation_root_allowed(tmp_path: Path) -> None:
    root = tmp_path / "generations"
    root.mkdir()
    other = tmp_path / "scratch" / "snap.csv"
    other.parent.mkdir()
    other.write_text("a\n", encoding="utf-8")
    forbid_generation_path_for_authorising_read(other, root)
