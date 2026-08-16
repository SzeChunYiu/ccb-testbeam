from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "audit" / "validate_hrd_waveform_contract.py"
spec = importlib.util.spec_from_file_location("validate_hrd_waveform_contract", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_exact_8x16_preserves_event_boundaries():
    rows = [np.arange(128) + 1000 * i for i in range(9)]
    out, summary = mod.validate_and_reshape_rows(rows, n_channels=8, samples_per_channel=16)
    assert out.shape == (9, 8, 16)
    assert summary.malformed_events == 0
    for i in range(9):
        np.testing.assert_array_equal(out[i].ravel(), rows[i])


def test_reshape_compatible_8x16_batch_rejected_under_8x18_contract():
    # 9 * 128 == 8 * 144: a historical batch-level reshape can silently turn
    # nine 8x16 events into eight 8x18 pseudo-events. The per-event gate must fail.
    rows = [np.arange(128) + 1000 * i for i in range(9)]
    with pytest.raises(ValueError, match="expected 144 words/event"):
        mod.validate_and_reshape_rows(rows, n_channels=8, samples_per_channel=18)


def test_one_short_event_rejected_without_padding():
    rows = [np.arange(128), np.arange(127), np.arange(128)]
    with pytest.raises(ValueError, match="malformed 1/3"):
        mod.validate_and_reshape_rows(rows, n_channels=8, samples_per_channel=16)


def test_one_long_event_rejected_without_truncation():
    rows = [np.arange(128), np.arange(129)]
    with pytest.raises(ValueError, match="1:129"):
        mod.validate_and_reshape_rows(rows, n_channels=8, samples_per_channel=16)


def test_empty_input_has_explicit_empty_shape():
    out, summary = mod.validate_and_reshape_rows([], n_channels=8, samples_per_channel=16)
    assert out.shape == (0, 8, 16)
    assert summary.events == 0


def test_nested_non_scalar_content_rejected():
    # Each row has total size 128 but is itself 8x16. The contract accepts scalar
    # word count but requires a flat per-event word vector to prevent hidden axes.
    rows = [np.zeros((8, 16))]
    with pytest.raises(ValueError, match="do not form a 2-D scalar matrix"):
        mod.validate_and_reshape_rows(rows, n_channels=8, samples_per_channel=16)
