#!/usr/bin/env python3
"""Synchronize public C12 wording with the authoritative MC-only evidence state."""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path

REPLACEMENTS: dict[str, tuple[tuple[str, str], ...]] = {
    "README.md": (
        (
            "| Pile-up tolerance | **R_max ≈ 3.05 MHz** (corrected from 4.22 MHz) | "
            "CL-010 — VALIDATED (MV5 release BLOCKED) |",
            "| Pile-up tolerance | **Withheld pending S-STAT-003** | "
            "CL-010 — BLOCKED |",
        ),
        (
            "| C12-like anomaly in truth-labelled MC | **283 / 87,555 tracks "
            "(0.32%)**; ~55% C12 within the selected MC class | CL-022 — "
            "TRUTH_LEVEL_MC_ONLY (real-data identity unvalidated) |",
            "| Early-peak morphology rate in truth-labelled MC | **283 / 87,555 "
            "tracks (0.323%; Wilson 95% CI 0.288–0.363%)**; C12 labels are "
            "**156 / 283 (55.1%)** within that selected MC class | CL-022 — "
            "TRUTH_LEVEL_MC_ONLY (real-data identity unvalidated) |",
        ),
    ),
    "WIKI.md": (
        (
            "| C12 anomaly fraction | 0.32% | — | — | MC-identified | "
            "**VALIDATED** |",
            "| C12-like anomaly fraction in truth-labelled MC | 283 / 87,555 "
            "tracks (0.32%) | — | — | MC truth only | "
            "**TRUTH_LEVEL_MC_ONLY** |",
        ),
        (
            "| C12 anomaly fraction | 0.32% of tracks | "
            "**VALIDATED** (MC-identified, MV6) |",
            "| C12-like anomaly fraction in truth-labelled MC | 283 / 87,555 "
            "tracks (0.32%) | **TRUTH_LEVEL_MC_ONLY** "
            "(MV6; transfer to data unvalidated) |",
        ),
        (
            "| MV6 | C12 anomaly | **VALIDATED** | Efficiency study |",
            "| MV6 | C12-like anomaly in truth-labelled MC | "
            "**TRUTH_LEVEL_MC_ONLY** | Matched data/MC closure and "
            "efficiency study |",
        ),
        (
            "### Veto Impact (Conservative Estimate)\n"
            "At 99% efficiency, 5% false-positive: events retained = 99.68%, "
            "background passed = 0.016%.",
            "### Veto Impact\n"
            "No data-veto performance is claimed. Efficiency, false-positive "
            "rate, and retained-event fraction require the preregistered matched "
            "data/MC closure and independent data sidebands.",
        ),
    ),
    "docs/academic_chapters/09_anomaly_id.md": (
        (
            "# Chapter 9: Anomaly Identification — C12 Nuclear Recoils",
            "# Chapter 9: C12-Like Anomaly in Truth-Labelled Monte Carlo",
        ),
        (
            "> **ACCEPTED by nature-reviewer (3/3).** All standard fixes applied.",
            "> **Evidence-status correction:** the C12 interpretation is "
            "demonstrated in truth-labelled Monte Carlo only; transfer to real "
            "beam data remains unvalidated.",
        ),
        (
            "Unsupervised clustering of pulse waveform embeddings discovered an "
            "anomalous class comprising 0.32% of tracks, characterised by early "
            "peaking (sample 1-2 instead of sample 5) and near-zero integrated "
            "pulse area. Monte Carlo truth identification (Study MV6) determined "
            "the dominant species as carbon-12 nuclear recoils (55% of anomalies) "
            "produced by proton scattering off carbon nuclei in the CD2 target. "
            "The C12 ions, with kinetic energies of 1-4 MeV, deposit all energy "
            "in the first 1-5 micrometres of scintillator, producing a waveform "
            "confined to ADC samples 0-1. The Birks quenching factor for these "
            "heavily ionising particles is approximately 6.7e-4, reducing the "
            "light output by a factor of approximately 1500 relative to a "
            "minimum-ionising proton. The anomaly contributes a negligible "
            "systematic uncertainty of 0.1% to deuteron counts after applying a "
            "Gaussian Mixture Model morphology cut. This chapter provides the "
            "complete algorithmic, physical, and methodological account of the "
            "discovery.",
            "In a truth-labelled Monte Carlo sample, unsupervised clustering "
            "selected 283 of 87,555 tracks (0.32%) with early-peaking, "
            "near-zero-area waveforms. Within that simulated selected class, "
            "approximately 55% of tracks were labelled carbon-12. These "
            "observations support carbon-12 recoil as a candidate simulated "
            "mechanism for the morphology, but they do not identify the related "
            "real-data anomaly because no event-level species truth or "
            "independently validated proxy has been demonstrated for data. "
            "Reported ranges, quenching estimates, veto efficiency, "
            "false-positive rate, retained-event fraction, and deuteron "
            "systematic impact therefore remain hypotheses or simulation-only "
            "quantities until the preregistered matched data/MC closure is "
            "executed. This chapter documents the algorithm and MC "
            "interpretation while preserving that evidence boundary.",
        ),
    ),
}


def synchronize_text(path_label: str, text: str) -> tuple[str, int]:
    """Apply exact replacements, rejecting ambiguous or partially synchronized inputs."""
    replacements = REPLACEMENTS[path_label]
    states: list[str] = []
    for old, new in replacements:
        old_count = text.count(old)
        new_count = text.count(new)
        if old_count == 1 and new_count == 0:
            states.append("old")
        elif old_count == 0 and new_count == 1:
            states.append("new")
        else:
            raise ValueError(
                f"{path_label}: expected exactly one old or one new snippet; "
                f"found old={old_count}, new={new_count}"
            )

    if len(set(states)) > 1:
        raise ValueError(f"{path_label}: partially synchronized file; states={states}")

    if states[0] == "new":
        return text, 0

    result = text
    for old, new in replacements:
        result = result.replace(old, new)
    return result, len(replacements)


def unified_diff(relative_path: str, original: str, updated: str) -> str:
    """Return a stable unified diff for review without modifying the file."""
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
        )
    )


def synchronize_file(
    root: Path, relative_path: str, *, check: bool, show_diff: bool = False
) -> int:
    path = root / relative_path
    original = path.read_text(encoding="utf-8")
    updated, changed = synchronize_text(relative_path, original)
    if show_diff and changed:
        print(unified_diff(relative_path, original, updated), end="")
    if check:
        if changed:
            raise RuntimeError(f"{relative_path} requires {changed} synchronization change(s)")
    elif changed and not show_diff:
        path.write_text(updated, encoding="utf-8")
    return changed


def synchronize_paths(
    root: Path,
    relative_paths: tuple[str, ...],
    *,
    check: bool,
    show_diff: bool = False,
) -> int:
    """Validate every selected file before producing output or writing any file."""
    prepared: list[tuple[str, Path, str, str, int]] = []
    for relative_path in relative_paths:
        path = root / relative_path
        original = path.read_text(encoding="utf-8")
        updated, changed = synchronize_text(relative_path, original)
        prepared.append((relative_path, path, original, updated, changed))

    if show_diff:
        for relative_path, _, original, updated, changed in prepared:
            if changed:
                print(unified_diff(relative_path, original, updated), end="")

    if check:
        pending = [
            f"{relative_path} requires {changed} synchronization change(s)"
            for relative_path, _, _, _, changed in prepared
            if changed
        ]
        if pending:
            raise RuntimeError("; ".join(pending))
    elif not show_diff:
        for _, path, _, updated, changed in prepared:
            if changed:
                path.write_text(updated, encoding="utf-8")

    return sum(changed for _, _, _, _, changed in prepared)


def selected_paths(requested: list[str] | None) -> tuple[str, ...]:
    """Return validated paths in deterministic repository order."""
    if not requested:
        return tuple(REPLACEMENTS)

    unknown = sorted(set(requested) - set(REPLACEMENTS))
    if unknown:
        allowed = ", ".join(REPLACEMENTS)
        raise ValueError(f"unknown path(s): {', '.join(unknown)}; allowed: {allowed}")

    requested_set = set(requested)
    return tuple(path for path in REPLACEMENTS if path in requested_set)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--diff",
        action="store_true",
        help="print a unified diff without modifying files",
    )
    parser.add_argument(
        "--path",
        action="append",
        choices=tuple(REPLACEMENTS),
        help="process only this repository-relative path; repeat for multiple files",
    )
    args = parser.parse_args()

    if args.check and args.diff:
        parser.error("--check and --diff are mutually exclusive")

    paths = selected_paths(args.path)
    total = synchronize_paths(
        args.root, paths, check=args.check, show_diff=args.diff
    )
    mode = "diffed" if args.diff else "checked" if args.check else "updated"
    print(f"{mode} {len(paths)} files; replacements={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
