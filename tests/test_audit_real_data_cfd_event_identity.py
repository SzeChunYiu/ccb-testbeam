from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tools.audit import audit_real_data_cfd_event_identity as audit

CURRENT_LIKE = '''
import pandas as pd

def load_waveforms():
    return pd.DataFrame({"run": [], "event_id": [], "stave": []})

def select_in_time(df, staves, tol):
    df = df.copy()
    df["peak_al"] = df["peak_sample"]
    pk = df.pivot(index="event_id", columns="stave", values="peak_al")
    keep = pk.dropna().index
    return df[df["event_id"].isin(keep)].copy()

def pair_analysis(df):
    return df.pivot(index="event_id", columns="stave", values="tcorr").dropna()

def make_figures(df):
    return df.pivot(index="event_id", columns="stave", values="tcorr").dropna()
'''

CORRECTED = '''
import pandas as pd

EVENT_KEY = ["run", "event_id"]

def load_waveforms():
    return pd.DataFrame({"run": [], "event_id": [], "stave": []})

def select_in_time(df, staves, tol):
    pk = df.pivot(index=EVENT_KEY, columns="stave", values="peak_al")
    keep = pk.dropna().reset_index()[EVENT_KEY]
    return df.merge(keep, on=EVENT_KEY, how="inner", validate="many_to_one")

def pair_analysis(df):
    return df.pivot(index=EVENT_KEY, columns="stave", values="tcorr").dropna()

def make_figures(df):
    return df.pivot(index=EVENT_KEY, columns="stave", values="tcorr").dropna()
'''


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_current_like_source_fails_closed(tmp_path: Path) -> None:
    result = audit.audit_source(write(tmp_path / "current.py", CURRENT_LIKE))
    codes = [finding["code"] for finding in result["findings"]]
    assert result["status"] == "FLAWED"
    assert codes.count("RUN_DROPPED_FROM_PIVOT_KEY") == 3
    assert "RUN_DROPPED_FROM_SELECTION_FILTER" in codes
    assert "SYNTHETIC_FALSE_CROSS_RUN_PAIR" in codes
    assert "RUN_LOCAL_EVENT_ID_COLLISION_CAN_ABORT" in codes


def test_corrected_composite_contract_validates(tmp_path: Path) -> None:
    result = audit.audit_source(write(tmp_path / "corrected.py", CORRECTED))
    assert result["status"] == "VALIDATED"
    assert result["finding_count"] == 0


def test_behavioral_controls_reproduce_false_pair_and_duplicate_failure() -> None:
    controls = audit.behavioral_controls()
    false_pair = controls["false_cross_run_pair"]
    duplicate = controls["duplicate_event_id"]
    assert false_pair["current_event_id_only_pair_count"] == 1
    assert false_pair["composite_key_pair_count"] == 0
    assert duplicate["current_event_id_only_outcome"] == "ValueError"
    assert duplicate["composite_key_pair_count"] == 2


def test_invalid_utf8_is_controlled(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "bad.py"
    source.write_bytes(b"print(1)\xff")
    status = audit.main([str(source)])
    assert status == 2
    assert "strict UTF-8" in capsys.readouterr().err


def test_output_alias_is_rejected_without_modifying_source(tmp_path: Path) -> None:
    source = write(tmp_path / "source.py", CURRENT_LIKE)
    before = source.read_bytes()
    status = audit.main([str(source), "--output", str(source)])
    assert status == 2
    assert source.read_bytes() == before


def test_atomic_publication_preserves_previous_output_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "result.json"
    output.write_text('{"old": true}\n', encoding="utf-8")

    def fail_replace(source: os.PathLike[str], destination: os.PathLike[str]) -> None:
        raise OSError("injected replacement failure")

    monkeypatch.setattr(audit.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected replacement failure"):
        audit._atomic_write_json(output, {"new": True})
    assert json.loads(output.read_text(encoding="utf-8")) == {"old": True}
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []
