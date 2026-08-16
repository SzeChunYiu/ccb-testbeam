#!/usr/bin/env python3
"""Audit regenerated figure artifacts against the committed tree.

Replaces the former `git diff --exit-code` final gate of the
paper-grade-plots workflow. That byte gate produced two classes of false
alarm with ZERO data drift (plotted_data_sha256 unchanged):

  1. matplotlib version skew (local 3.11.1 vs CI-pinned 3.10.8) —
     SVG tick-layout and PNG bytes shift while the plotted data is identical.
  2. Platform/Pillow-wheel skew (darwin vs manylinux x86_64) — identical
     matplotlib and identical pixels, but the bundled zlib/libpng differ, so
     every PNG re-encodes (observed 11-16% size deltas, one direction).

Gate design (fail-closed on data, warn on encoding):

  GATE A  data drift (HARD, always fails):
          committed vs regenerated manifests must agree on every figure's
          plotted_data_sha256 / source_table_sha256 and on the figure id set.
          Derived TEXT docs (WIKI.md, FIGURE_GALLERY.md,
          docs/wiki_plot_manifest.csv) are pure functions of the data tables,
          so any text diff is data drift and fails unconditionally.

  GATE B  byte identity (HARD only when the toolchain stamp matches):
          binary artifacts (png/svg/pdf) and manifest.json may only differ
          when the per-figure environment stamp differs somewhere
          (matplotlib/numpy/pandas/pillow/platform). Stamp mismatch with
          identical data digests = WARNING (pass), never a failure.
          Missing stamp fields (schema /1 manifests) count as "unknown" —
          they can never satisfy gate B, only downgrade it.

  exit 0  clean, or tolerated encoding skew (warning printed)
  exit 1  real drift / unreproducible bytes (same stamp, different bytes)
  exit 2  could not check (missing or malformed manifests) — NEVER silently
          reported as clean

Usage:
  python tools/figure_registry/audit_regenerated.py [--repo-root .]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

# Derived-text outputs: pure functions of the source tables, never of the
# rendering toolchain. Any byte diff here is data drift (GATE A).
TEXT_PATHS = (
    "WIKI.md",
    "docs/FIGURE_GALLERY.md",
    "docs/wiki_plot_manifest.csv",
    "wiki/Figure-Gallery.md",
    "wiki/Home.md",
    "wiki/_Sidebar.md",
)

MANIFEST_PATH = "docs/figures/paper/manifest.json"

STAMP_KEYS = ("matplotlib", "numpy", "pandas", "pillow", "platform")

DATA_KEYS = ("plotted_data_sha256", "source_table_sha256")


def git_show(root: Path, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"HEAD:{path}"], cwd=root, capture_output=True, text=True
    )
    return proc.stdout if proc.returncode == 0 else None


def git_diff_names(root: Path, paths: tuple[str, ...]) -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", *paths],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git diff failed: {proc.stderr.strip()}")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def load_json(text: str, what: str) -> dict:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{what} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or "figures" not in payload:
        raise RuntimeError(f"{what} has no 'figures' array")
    return payload


def figures_by_id(manifest: dict) -> dict[str, dict]:
    return {fig["figure_id"]: fig for fig in manifest["figures"]}


def stamp_diffs(committed: dict, regenerated: dict) -> list[str]:
    """Toolchain stamp components that differ between the two manifests."""
    diffs: list[str] = []
    committed_stamps: dict[str, str] = {}
    regenerated_stamps: dict[str, str] = {}
    for fig in committed.get("figures", []):
        committed_stamps.update(fig.get("environment", {}))
    for fig in regenerated.get("figures", []):
        regenerated_stamps.update(fig.get("environment", {}))
    for key in STAMP_KEYS:
        old = committed_stamps.get(key, "unknown")
        new = regenerated_stamps.get(key, "unknown")
        if old != new:
            diffs.append(f"{key}: {old} -> {new}")
    return diffs


def audit(root: Path) -> tuple[int, list[str], list[str]]:
    """Return (exit_code, failures, warnings)."""
    failures: list[str] = []
    warnings: list[str] = []

    committed_text = git_show(root, MANIFEST_PATH)
    if committed_text is None:
        return 2, ["manifest.json is not committed at HEAD"], warnings
    try:
        committed = load_json(committed_text, "committed manifest")
    except RuntimeError as exc:
        return 2, [f"committed manifest unreadable: {exc}"], warnings
    reg_path = root / MANIFEST_PATH
    if not reg_path.exists():
        return 2, [f"{MANIFEST_PATH} was not regenerated"], warnings
    try:
        regenerated = load_json(reg_path.read_text(encoding="utf-8"), "regenerated manifest")
    except (RuntimeError, OSError) as exc:
        return 2, [f"regenerated manifest unreadable: {exc}"], warnings

    # GATE A — data drift.
    committed_figs = figures_by_id(committed)
    regenerated_figs = figures_by_id(regenerated)
    added = sorted(set(regenerated_figs) - set(committed_figs))
    removed = sorted(set(committed_figs) - set(regenerated_figs))
    if added:
        failures.append(f"figure ids added by regeneration: {added}")
    if removed:
        failures.append(f"figure ids removed by regeneration: {removed}")
    for fig_id in sorted(set(committed_figs) & set(regenerated_figs)):
        for key in DATA_KEYS:
            old = committed_figs[fig_id].get(key)
            new = regenerated_figs[fig_id].get(key)
            if old != new:
                failures.append(f"DATA DRIFT {fig_id}: {key} {old} -> {new}")

    changed_text = [p for p in git_diff_names(root, TEXT_PATHS) if p in TEXT_PATHS]
    if changed_text:
        failures.append(
            "DATA DRIFT in derived text docs (pure functions of the source "
            f"tables, independent of the toolchain): {changed_text}"
        )

    if failures:
        return 1, failures, warnings

    # GATE B — byte identity under a matching toolchain stamp.
    skew = stamp_diffs(committed, regenerated)
    changed_all = git_diff_names(
        root, ("docs/figures/paper", "WIKI.md", "docs/FIGURE_GALLERY.md", "docs/wiki_plot_manifest.csv")
    )
    changed_binaries = [p for p in changed_all if p.startswith("docs/figures/paper/")]
    if not changed_all:
        return 0, failures, warnings
    if skew:
        warnings.append(
            "tolerated encoding skew (plotted data identical, toolchain "
            f"stamp differs — rebuild on the CI-pinned Linux environment and "
            f"commit the artifacts): {'; '.join(skew)}; changed: {changed_binaries}"
        )
        return 0, failures, warnings
    failures.append(
        "committed artifacts are not reproducible under an IDENTICAL toolchain "
        f"stamp (data digests identical but bytes differ): {changed_all}. "
        "This is not version skew — the stamp must differ for bytes to differ."
    )
    return 1, failures, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()

    failures: list[str] = []
    try:
        code, failures, warnings = audit(root)
    except RuntimeError as exc:
        print(f"AUDIT-UNVERIFIABLE: {exc}")
        return 2

    for warning in warnings:
        print(f"AUDIT-WARNING: {warning}")
    for failure in failures:
        print(f"AUDIT-FAIL: {failure}")
    if code == 0 and not warnings:
        print("AUDIT-CLEAN: committed artifacts byte-identical to regeneration")
    elif code == 0:
        print("AUDIT-PASS-WITH-WARNING: data unchanged, encoding skew tolerated")
    elif code == 2:
        print("AUDIT-UNVERIFIABLE: manifests missing or malformed; NOT reported as clean")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
