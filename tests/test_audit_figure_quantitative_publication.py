from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.audit.audit_figure_quantitative_publication import (
    _atomic_write_json,
    audit_source,
    behavioral_controls,
)


CURRENT_LIKE = '''\
def _emit_quantitative(entry, result_snapshot, out_dir):
    fig, axis = plt.subplots(figsize=(6.0, 4.0), dpi=150)
    axis.errorbar([0], [1.0], yerr=[0.1], fmt="o", capsize=4)
    figure_path = out_dir / f"{entry.id}.png"
    fig.savefig(figure_path)
    plt.close(fig)
    figure_snapshot = _read_file_snapshot(
        figure_path, entry_id=entry.id, label="rendered figure"
    )
    return figure_path, figure_snapshot
'''


CORRECTED = '''\
def _emit_quantitative(entry, result_snapshot, out_dir):
    fig, axis = plt.subplots(figsize=(6.0, 4.0), dpi=150)
    figure_path = out_dir / f"{entry.id}.png"
    temporary = out_dir / f".{entry.id}.render.png.tmp"
    try:
        fig.savefig(temporary, format="png")
        rendered = _read_file_snapshot(
            temporary, entry_id=entry.id, label="temporary rendered figure"
        )
        _atomic_publish_snapshot(
            figure_path, rendered, entry_id=entry.id, label="quantitative figure"
        )
    finally:
        plt.close(fig)
        temporary.unlink(missing_ok=True)
    return figure_path, rendered
'''


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_current_like_source_is_flawed(tmp_path: Path) -> None:
    result = audit_source(_write(tmp_path / "current.py", CURRENT_LIKE))
    assert result["status"] == "FLAWED"
    assert {finding["code"] for finding in result["findings"]} == {
        "QUANTITATIVE_RENDER_WRITES_FINAL_PATH_DIRECTLY",
        "QUANTITATIVE_FIGURE_HAS_NO_ATOMIC_PUBLICATION_BOUNDARY",
        "QUANTITATIVE_FIGURE_NOT_CLOSED_ON_RENDER_FAILURE",
    }


def test_corrected_contract_is_validated(tmp_path: Path) -> None:
    result = audit_source(_write(tmp_path / "corrected.py", CORRECTED))
    assert result["status"] == "VALIDATED"
    assert result["finding_count"] == 0


def test_behavioral_control_proves_target_preservation() -> None:
    controls = behavioral_controls()
    assert not controls["former_direct_target_failure"]["previous_target_preserved"]
    assert controls["corrected_temporary_failure"]["previous_target_preserved"]
    assert controls["corrected_temporary_failure"]["temporary_files_remaining"] == 0
    assert controls["corrected_atomic_success"]["published_matches_replacement"]


def test_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    source = tmp_path / "bad.py"
    source.write_bytes(b"\xff\xfe")
    command = [
        sys.executable,
        "-m",
        "tools.audit.audit_figure_quantitative_publication",
        str(source),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == 2
    assert "INPUT_ERROR" in completed.stderr


def test_output_alias_is_rejected(tmp_path: Path) -> None:
    source = _write(tmp_path / "source.py", CURRENT_LIKE)
    original = source.read_bytes()
    command = [
        sys.executable,
        "-m",
        "tools.audit.audit_figure_quantitative_publication",
        str(source),
        "--output",
        str(source),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == 2
    assert source.read_bytes() == original


def test_atomic_json_failure_preserves_previous_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "evidence.json"
    previous = b'{"previous": true}\n'
    output.write_bytes(previous)

    def fail_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected replace failure"):
        _atomic_write_json(output, {"new": True})
    assert output.read_bytes() == previous
    assert not list(tmp_path.glob(".evidence.json.*.tmp"))


def test_atomic_json_success_is_parseable(tmp_path: Path) -> None:
    output = tmp_path / "evidence.json"
    metadata = _atomic_write_json(output, {"status": "VALIDATED"})
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "VALIDATED"
    assert metadata["bytes"] == output.stat().st_size
