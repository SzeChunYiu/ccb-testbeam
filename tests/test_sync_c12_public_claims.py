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
