from __future__ import annotations

from pathlib import Path

import pytest

from tools.audit.validate_gitlink_submodule_contract import (
    ContractError,
    audit,
    evaluate_contract,
    parse_gitmodules_text,
    parse_index_records,
)

ROOT = Path(__file__).resolve().parents[1]
REAL_SUBMODULE = "geant4/single_stave/sipm"


def test_parse_index_records_selects_only_gitlinks() -> None:
    raw = (
        b"100644 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 0\tordinary.txt\0"
        b"160000 bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb 0\tdep\0"
    )
    assert parse_index_records(raw) == {
        "dep": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    }


def test_orphan_gitlink_fails_contract() -> None:
    result = evaluate_contract(
        {"orphan": "a" * 40},
        set(),
        worktrees_ignored=True,
    )
    assert result["ok"] is False
    assert result["issues"] == [{"code": "ORPHAN_GITLINK", "paths": ["orphan"]}]


def test_configured_submodule_without_gitlink_fails_contract() -> None:
    result = evaluate_contract(
        {},
        {REAL_SUBMODULE},
        worktrees_ignored=True,
    )
    assert result["ok"] is False
    assert result["issues"] == [
        {
            "code": "CONFIGURED_SUBMODULE_NOT_GITLINK",
            "paths": [REAL_SUBMODULE],
        }
    ]


def test_unignored_local_worktree_path_fails_contract() -> None:
    result = evaluate_contract(
        {REAL_SUBMODULE: "a" * 40},
        {REAL_SUBMODULE},
        worktrees_ignored=False,
    )
    assert result["ok"] is False
    assert result["issues"] == [
        {
            "code": "LOCAL_WORKTREE_PATH_NOT_IGNORED",
            "path": ".claude/worktrees/",
        }
    ]


def test_duplicate_gitmodules_paths_are_rejected() -> None:
    text = """
[submodule "one"]
    path = dep
    url = https://example.invalid/one.git
[submodule "two"]
    path = dep
    url = https://example.invalid/two.git
"""
    with pytest.raises(ContractError, match="duplicate submodule path"):
        parse_gitmodules_text(text)


def test_malformed_index_record_is_rejected() -> None:
    with pytest.raises(ContractError, match="malformed git ls-files"):
        parse_index_records(b"not-a-valid-record\0")


def test_repository_gitlinks_equal_configured_submodules() -> None:
    result = audit(ROOT)
    assert result["ok"] is True, result["issues"]
    assert result["configured_submodule_paths"] == [REAL_SUBMODULE]
    assert [entry["path"] for entry in result["tracked_gitlinks"]] == [REAL_SUBMODULE]
    assert result["local_worktrees_ignored"] is True
