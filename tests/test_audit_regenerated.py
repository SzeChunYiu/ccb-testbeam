"""Validation of the regenerate-and-audit gate against every known skew class.

The audit replaces a raw `git diff --exit-code` gate that produced two
documented false-alarm classes (matplotlib version skew; darwin-vs-manylinux
Pillow/zlib PNG re-encoding), both with identical plotted_data_sha256. These
tests pin the gate's verdict for each class, including the no-alarm case:
a gate that cries wolf on a clean tree is as broken as one that misses drift.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools.figure_registry.audit_regenerated import audit, main

_STAMP = {
    "python": ">=3.11 (requires-python floor; patch version not stamped)",
    "matplotlib": "3.10.8",
    "numpy": "2.3.5",
    "pandas": "2.2.3",
    "pillow": "12.2.0",
    "platform": "linux-x86_64",
}


def _figure(env: dict[str, str]) -> dict[str, object]:
    return {
        "figure_id": "FIG-WIKI-004",
        "plotted_data_sha256": "a" * 64,
        "source_table_sha256": "a" * 64,
        "environment": dict(env),
        "outputs": {
            "png": {
                "path": "docs/figures/paper/pid_mc_validation.png",
                "sha256": "b" * 64,
                "bytes": 1000,
            }
        },
    }


def _build_repo(tmp_path: Path, env: dict[str, str], png_bytes: bytes) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "docs/figures/paper").mkdir(parents=True)
    (root / "wiki").mkdir()
    manifest = {
        "schema": "ccb-paper-grade-wiki-figures/2",
        "figure_count": 1,
        "figures": [_figure(env)],
    }
    (root / "docs/figures/paper/manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (root / "docs/figures/paper/pid_mc_validation.png").write_bytes(png_bytes)
    for text_path, text in (
        ("WIKI.md", "wiki\n"),
        ("docs/FIGURE_GALLERY.md", "gallery\n"),
        ("docs/wiki_plot_manifest.csv", "figure_id,stem\n"),
        ("wiki/Figure-Gallery.md", "gallery\n"),
        ("wiki/Home.md", "home\n"),
        ("wiki/_Sidebar.md", "sidebar\n"),
    ):
        target = root / text_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "test"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "base"],
    ):
        subprocess.run(command, cwd=root, check=True, capture_output=True)
    return root


def _rewrite_manifest(root: Path, figures: list[dict[str, object]]) -> None:
    manifest = {
        "schema": "ccb-paper-grade-wiki-figures/2",
        "figure_count": len(figures),
        "figures": figures,
    }
    (root / "docs/figures/paper/manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def test_clean_regeneration_is_silent(tmp_path: Path) -> None:
    root = _build_repo(tmp_path, _STAMP, b"png-bytes")
    code, failures, warnings = audit(root)
    assert code == 0
    assert failures == []
    assert warnings == []


def test_data_digest_drift_fails(tmp_path: Path) -> None:
    root = _build_repo(tmp_path, _STAMP, b"png-bytes")
    drifted = _figure(_STAMP)
    drifted["plotted_data_sha256"] = "c" * 64
    _rewrite_manifest(root, [drifted])
    (root / "docs/figures/paper/pid_mc_validation.png").write_bytes(b"new-png")
    code, failures, warnings = audit(root)
    assert code == 1
    assert any("DATA DRIFT" in failure for failure in failures)
    assert warnings == []


def test_figure_set_change_fails(tmp_path: Path) -> None:
    root = _build_repo(tmp_path, _STAMP, b"png-bytes")
    other = _figure(_STAMP)
    other["figure_id"] = "FIG-WIKI-099"
    _rewrite_manifest(root, [other])
    code, failures, _ = audit(root)
    assert code == 1
    assert any("figure ids removed" in failure for failure in failures)


def test_derived_text_drift_fails(tmp_path: Path) -> None:
    root = _build_repo(tmp_path, _STAMP, b"png-bytes")
    (root / "WIKI.md").write_text("wiki with changed numbers\n", encoding="utf-8")
    code, failures, _ = audit(root)
    assert code == 1
    assert any("derived text docs" in failure for failure in failures)


def test_matplotlib_version_skew_passes_with_warning(tmp_path: Path) -> None:
    # The documented false-alarm class: identical plotted_data_sha256, local
    # build at 3.11.1 vs CI-pinned 3.10.8, tick-layout bytes shift.
    root = _build_repo(tmp_path, {**_STAMP, "matplotlib": "3.11.1"}, b"png-bytes")
    _rewrite_manifest(root, [_figure(_STAMP)])
    (root / "docs/figures/paper/pid_mc_validation.png").write_bytes(b"relaid-out")
    code, failures, warnings = audit(root)
    assert code == 0
    assert failures == []
    assert len(warnings) == 1
    assert "matplotlib: 3.11.1 -> 3.10.8" in warnings[0]


def test_platform_skew_passes_with_warning(tmp_path: Path) -> None:
    # darwin vs manylinux Pillow/zlib wheels re-encode identical pixels.
    root = _build_repo(tmp_path, {**_STAMP, "platform": "darwin-arm64"}, b"png-bytes")
    _rewrite_manifest(root, [_figure(_STAMP)])
    (root / "docs/figures/paper/pid_mc_validation.png").write_bytes(b"reencoded")
    code, failures, warnings = audit(root)
    assert code == 0
    assert failures == []
    assert any("platform: darwin-arm64 -> linux-x86_64" in warning for warning in warnings)


def test_identical_stamp_with_differing_bytes_fails(tmp_path: Path) -> None:
    # Same toolchain stamp on both sides but bytes differ: not version skew,
    # not platform skew — the committed artifacts are not reproducible.
    root = _build_repo(tmp_path, _STAMP, b"png-bytes")
    (root / "docs/figures/paper/pid_mc_validation.png").write_bytes(b"mystery-bytes")
    code, failures, _ = audit(root)
    assert code == 1
    assert any("not reproducible" in failure for failure in failures)


def test_missing_regenerated_manifest_is_unverifiable_not_clean(tmp_path: Path) -> None:
    root = _build_repo(tmp_path, _STAMP, b"png-bytes")
    (root / "docs/figures/paper/manifest.json").unlink()
    code, failures, _ = audit(root)
    assert code == 2
    assert any("was not regenerated" in failure for failure in failures)


def test_malformed_committed_manifest_is_unverifiable(tmp_path: Path) -> None:
    root = _build_repo(tmp_path, _STAMP, b"png-bytes")
    (root / "docs/figures/paper/manifest.json").write_text("{not json", encoding="utf-8")
    subprocess.run(
        ["git", "add", "-A"], cwd=root, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-qm", "broken"], cwd=root, check=True, capture_output=True
    )
    (root / "docs/figures/paper/manifest.json").write_text(
        json.dumps(
            {
                "schema": "ccb-paper-grade-wiki-figures/2",
                "figure_count": 1,
                "figures": [_figure(_STAMP)],
            }
        ),
        encoding="utf-8",
    )
    code, _, _ = audit(root)
    assert code == 2


def test_cli_exit_codes(tmp_path: Path) -> None:
    root = _build_repo(tmp_path, _STAMP, b"png-bytes")
    assert main(["--repo-root", str(root)]) == 0
    (root / "docs/figures/paper/pid_mc_validation.png").write_bytes(b"x")
    assert main(["--repo-root", str(root)]) == 1
