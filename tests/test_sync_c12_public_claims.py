from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_c12_public_claims.py"
SPEC = importlib.util.spec_from_file_location("sync_c12_public_claims", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def test_applies_all_replacements_and_is_idempotent() -> None:
    for label, pairs in sync.REPLACEMENTS.items():
        source = "\n".join(old for old, _ in pairs)
        updated, changed = sync.synchronize_text(label, source)
        assert changed == len(pairs)
        assert all(new in updated for _, new in pairs)

        second_pass, second_changed = sync.synchronize_text(label, updated)
        assert second_pass == updated
        assert second_changed == 0


def test_rejects_ambiguous_duplicate_snippet() -> None:
    label = "WIKI.md"
    old, _ = sync.REPLACEMENTS[label][0]
    try:
        sync.synchronize_text(label, f"{old}\n{old}")
    except ValueError as exc:
        assert "old=2" in str(exc)
    else:
        raise AssertionError("duplicate source snippet was not rejected")


def test_rejects_partially_synchronized_file() -> None:
    label = "WIKI.md"
    pairs = sync.REPLACEMENTS[label]
    partial = "\n".join([pairs[0][1], *(old for old, _ in pairs[1:])])
    try:
        sync.synchronize_text(label, partial)
    except ValueError as exc:
        assert "partially synchronized file" in str(exc)
    else:
        raise AssertionError("partially synchronized file was not rejected")


def test_check_mode_rejects_unsynchronized_files(tmp_path: Path) -> None:
    label = "WIKI.md"
    path = tmp_path / label
    path.write_text(
        "\n".join(old for old, _ in sync.REPLACEMENTS[label]), encoding="utf-8"
    )
    try:
        sync.synchronize_file(tmp_path, label, check=True)
    except RuntimeError as exc:
        assert "requires 4 synchronization change(s)" in str(exc)
    else:
        raise AssertionError("check mode accepted an unsynchronized file")


def test_check_mode_accepts_synchronized_files(tmp_path: Path) -> None:
    for label, pairs in sync.REPLACEMENTS.items():
        path = tmp_path / label
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(new for _, new in pairs), encoding="utf-8")
        assert sync.synchronize_file(tmp_path, label, check=True) == 0


def test_readme_replacements_are_scientifically_qualified() -> None:
    pairs = sync.REPLACEMENTS["README.md"]
    source = "\n".join(old for old, _ in pairs)
    updated, changed = sync.synchronize_text("README.md", source)
    assert changed == 2
    assert "Withheld pending S-STAT-003" in updated
    assert "CL-010 — BLOCKED" in updated
    assert "Early-peak morphology rate" in updated
    assert "Wilson 95% CI 0.288–0.363%" in updated
    assert "156 / 283 (55.1%)" in updated
    assert "real-data identity unvalidated" in updated
    assert "R_max ≈ 3.05 MHz" not in updated
    assert "~55% C12" not in updated


def test_current_readme_state_is_idempotent() -> None:
    current = "\n".join(new for _, new in sync.REPLACEMENTS["README.md"])
    updated, changed = sync.synchronize_text("README.md", current)
    assert changed == 0
    assert updated == current


def test_selected_paths_defaults_to_all_in_repository_order() -> None:
    assert sync.selected_paths(None) == tuple(sync.REPLACEMENTS)
    assert sync.selected_paths([]) == tuple(sync.REPLACEMENTS)


def test_selected_paths_filters_and_deduplicates_in_repository_order() -> None:
    selected = sync.selected_paths(["WIKI.md", "README.md", "WIKI.md"])
    assert selected == ("README.md", "WIKI.md")


def test_selected_paths_rejects_unknown_paths() -> None:
    try:
        sync.selected_paths(["docs/unknown.md"])
    except ValueError as exc:
        assert "unknown path(s): docs/unknown.md" in str(exc)
        assert "WIKI.md" in str(exc)
    else:
        raise AssertionError("unknown path was not rejected")


def test_unified_diff_is_reviewable_and_stable() -> None:
    label = "WIKI.md"
    source = "\n".join(old for old, _ in sync.REPLACEMENTS[label]) + "\n"
    updated, changed = sync.synchronize_text(label, source)
    diff = sync.unified_diff(label, source, updated)
    assert changed == 4
    assert diff.startswith("--- a/WIKI.md\n+++ b/WIKI.md\n")
    assert "-" + sync.REPLACEMENTS[label][0][0] in diff
    assert "+" + sync.REPLACEMENTS[label][0][1] in diff


def test_diff_mode_does_not_modify_file(tmp_path: Path, capsys) -> None:
    label = "WIKI.md"
    source = "\n".join(old for old, _ in sync.REPLACEMENTS[label]) + "\n"
    path = tmp_path / label
    path.write_text(source, encoding="utf-8")
    changed = sync.synchronize_file(tmp_path, label, check=False, show_diff=True)
    captured = capsys.readouterr().out
    assert changed == 4
    assert captured.startswith("--- a/WIKI.md\n+++ b/WIKI.md\n")
    assert path.read_text(encoding="utf-8") == source


def test_multi_file_write_is_atomic_on_validation_failure(tmp_path: Path) -> None:
    first = "README.md"
    second = "WIKI.md"
    first_source = "\n".join(old for old, _ in sync.REPLACEMENTS[first])
    second_pairs = sync.REPLACEMENTS[second]
    ambiguous_second = "\n".join(
        [second_pairs[0][0], second_pairs[0][0], *(old for old, _ in second_pairs[1:])]
    )

    (tmp_path / first).write_text(first_source, encoding="utf-8")
    (tmp_path / second).write_text(ambiguous_second, encoding="utf-8")

    try:
        sync.synchronize_paths(tmp_path, (first, second), check=False, show_diff=False)
    except ValueError as exc:
        assert "old=2" in str(exc)
    else:
        raise AssertionError("ambiguous later file was not rejected")

    assert (tmp_path / first).read_text(encoding="utf-8") == first_source


def test_multi_file_check_reports_all_pending_files(tmp_path: Path) -> None:
    paths = ("README.md", "WIKI.md")
    for label in paths:
        (tmp_path / label).write_text(
            "\n".join(old for old, _ in sync.REPLACEMENTS[label]),
            encoding="utf-8",
        )

    try:
        sync.synchronize_paths(tmp_path, paths, check=True)
    except RuntimeError as exc:
        message = str(exc)
        assert "README.md requires 2 synchronization change(s)" in message
        assert "WIKI.md requires 4 synchronization change(s)" in message
    else:
        raise AssertionError("check mode accepted unsynchronized files")
