"""Wave D Lane 02: Geant4 UI/macro ApplyCommand must fail closed (#998)."""

from __future__ import annotations

from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "geant4/single_stave/src/main.cc"


def test_main_cc_requires_applycommand_status() -> None:
    text = MAIN.read_text(encoding="utf-8")
    assert "apply_required" in text
    assert "ApplyCommand(command)" in text
    assert "Geant4 UI command failed with status" in text
    assert "return 4" in text
    macro_idx = text.index("cfg.macro.empty()")
    end_idx = text.index("CCB_STAVE_END")
    fail_idx = text.index("if (!macro_ok)")
    assert macro_idx < fail_idx < end_idx
    assert "delete runManager" in text[fail_idx:end_idx]


def test_batch_verbose_commands_are_required() -> None:
    text = MAIN.read_text(encoding="utf-8")
    for cmd in ("/run/verbose 0", "/event/verbose 0", "/tracking/verbose 0"):
        assert cmd in text
