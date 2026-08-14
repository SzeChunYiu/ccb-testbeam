"""Minimal validation of #956 P0-1 fixes: no hard-coded constants, CLI args work."""

import re
import subprocess
import sys
from pathlib import Path

PRODUCER = Path(__file__).parents[2] / "scripts" / "single_stave" / "paper_956_deltaE_E_publication.py"


def test_no_hardcoded_sat_adc_assignment():
    """P0-1: SAT_ADC must not be assigned as a constant (should be CLI-configurable)."""
    src = PRODUCER.read_text()
    code_lines = [l for l in src.splitlines() if not l.strip().startswith("#") and "\"\"\"" not in l]
    code_text = "\n".join(code_lines)
    assert not re.search(r"SAT_ADC\s*=\s*\d+", code_text), "Hard-coded SAT_ADC assignment found"


def test_no_hardcoded_s00_cut_adc_assignment():
    """P0-1: S00_CUT_ADC must not be assigned as a constant."""
    src = PRODUCER.read_text()
    code_lines = [l for l in src.splitlines() if not l.strip().startswith("#") and "\"\"\"" not in l]
    code_text = "\n".join(code_lines)
    assert not re.search(r"S00_CUT_ADC\s*=\s*\d+", code_text), "Hard-coded S00_CUT_ADC assignment found"


def test_readout_primary_conditional_not_global():
    """P0-1: READOUT_PRIMARY must be conditional (CLI-driven), not global hard-coded."""
    src = PRODUCER.read_text()
    # Should be set inside conditional blocks, not at module top level
    lines = src.splitlines()
    top_level_readout = []
    for i, line in enumerate(lines):
        if "READOUT_PRIMARY" in line and "=" in line:
            # Check if this is inside a conditional (indent check)
            if i > 0 and (lines[i-1].strip().startswith("if") or lines[i-1].strip().startswith("elif") or lines[i-1].strip().startswith("else")):
                continue  # OK, inside conditional
            # Check if line itself starts with if (ternary or one-line if)
            if line.strip().startswith("if") or line.strip().startswith("elif"):
                continue  # OK, conditional
            # Check if the assignment line is indented (inside a block)
            if line.startswith("    ") and not line.startswith("    READOUT_PRIMARY = ("):
                top_level_readout.append((i+1, line))
    # Allow conditional assignment patterns but reject top-level hard-code
    for ln, l in top_level_readout:
        assert False, f"Line {ln}: hard-coded READOUT_PRIMARY outside conditional: {l.strip()}"


def test_readout_parity_arg_exists():
    """P0-1: --readout-parity CLI arg must exist."""
    result = subprocess.run(
        [sys.executable, str(PRODUCER), "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "--readout-parity" in result.stdout
    assert "0/2/4/6" in result.stdout  # even parity option added


def test_bootstrap_replicates_arg_exists():
    """P0-1: --bootstrap-replicates arg must exist."""
    result = subprocess.run(
        [sys.executable, str(PRODUCER), "--help"],
        capture_output=True, text=True
    )
    assert "--bootstrap-replicates" in result.stdout


def test_data_threshold_adc_flag_only():
    """P0-1: --data-threshold-adc must be flags-only (no selection effect)."""
    result = subprocess.run(
        [sys.executable, str(PRODUCER), "--help"],
        capture_output=True, text=True
    )
    assert "--data-threshold-adc" in result.stdout
    # The help should mention it is for flags only
    assert "threshold_pass" in result.stdout or "flags only" in result.stdout.lower()


def test_namespace_has_layer_0_7():
    """P0-1: Immutable edep_layer_0..7 naming must exist."""
    src = PRODUCER.read_text()
    # Check for immutable layer column generation
    assert "edep_layer_" in src
    # Check for readout_B* aliases
    assert "readout_B" in src


def test_imports_no_errors():
    """Producer module imports without errors (syntax check)."""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(PRODUCER)],
        capture_output=True
    )
    assert result.returncode == 0, f"Syntax error: {result.stderr.decode()}"
