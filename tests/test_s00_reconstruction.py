"""Unit and regression tests for the S00 reconstruction pipeline.

This closes a documented open item (docs/09_open_questions.md, "Infrastructure":
"No unit/regression tests on the reconstruction pipeline"). Everything in this
file exercises pure functions from scripts/01_build_pulse_table_from_root.py --
the canonical S00 baseline/amplitude/selection-gate implementation that every
downstream study in this repository depends on -- with hand-computed expected
outputs. None of it requires the raw ROOT data (which is not present in this
checkout; see DATA.md), so these tests run anywhere, including CI.

Two things are deliberately NOT tested here, because they need the real data:
  - The end-to-end scan_raw()/sorted_crosscheck() functions (require raw ROOT
    files under data/extracted/, which are outside git).
  - The canonical S00 result itself (640,737 selected pulses) as measured from
    raw data -- that is reproduced by running scripts/01_build_pulse_table_from_root.py
    directly, not by a unit test. What IS tested here is that the checked-in
    configs/s00_reproduction.yaml `expected_counts` block is *internally
    consistent* (its own subtotals sum correctly), so a future accidental edit
    to that config cannot silently desynchronize the numbers every downstream
    report and the wiki cite.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "01_build_pulse_table_from_root.py"
CONFIG_PATH = REPO_ROOT / "configs" / "s00_reproduction.yaml"


def _load_s00_module():
    """Import scripts/01_build_pulse_table_from_root.py by path.

    The filename starts with a digit, so it cannot be imported with a normal
    `import` statement; this uses importlib to load it as a standalone module
    without requiring scripts/ to be turned into a package.
    """
    spec = importlib.util.spec_from_file_location("s00_build_pulse_table", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture(scope="module")
def s00():
    if not SCRIPT_PATH.exists():
        pytest.skip(f"{SCRIPT_PATH} not found")
    return _load_s00_module()


@pytest.fixture(scope="module")
def s00_config():
    if not CONFIG_PATH.exists():
        pytest.skip(f"{CONFIG_PATH} not found")
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


# --------------------------------------------------------------------------
# pulse_quantities(): baseline, amplitude, peak_sample, area
# --------------------------------------------------------------------------


def test_pulse_quantities_flat_pretrigger_and_symmetric_peak(s00):
    """A single event, single stave, hand-constructed 8-sample waveform.

    Samples: [100, 100, 100, 100, 300, 500, 300, 100]
    Baseline (median of indices 0-3) = median(100,100,100,100) = 100.
    Corrected: [0, 0, 0, 0, 200, 400, 200, 0]
    Amplitude = max(corrected) = 400, at index 5.
    Area = sum(corrected) = 0+0+0+0+200+400+200+0 = 800.
    """
    waveforms = np.array([[[100, 100, 100, 100, 300, 500, 300, 100]]], dtype=float)  # (event=1, stave=1, sample=8)
    baseline, amplitude, peak_sample, area = s00.pulse_quantities(waveforms, [0, 1, 2, 3])

    assert baseline.shape == (1, 1)
    np.testing.assert_allclose(baseline, [[100.0]])
    np.testing.assert_allclose(amplitude, [[400.0]])
    assert peak_sample[0, 0] == 5
    np.testing.assert_allclose(area, [[800.0]])


def test_pulse_quantities_baseline_uses_median_not_mean(s00):
    """One outlier pretrigger sample must not drag the baseline via a mean.

    Pretrigger samples [90, 92, 91, 500] (500 is a pretrigger contamination
    outlier). median([90,92,91,500]) = 91.5, NOT mean([90,92,91,500])=193.25.
    This is exactly the distinction documented in the wiki's pedestal
    chapter (median-of-4, not mean-of-4) and in S16's baseline-estimator
    comparison -- get this wrong and every downstream amplitude is biased.
    """
    waveforms = np.array([[[90, 92, 91, 500, 91, 91, 1091, 91]]], dtype=float)
    baseline, amplitude, _, _ = s00.pulse_quantities(waveforms, [0, 1, 2, 3])
    np.testing.assert_allclose(baseline, [[91.5]])
    np.testing.assert_allclose(amplitude, [[1091.0 - 91.5]])


def test_pulse_quantities_multi_stave_multi_event_shapes(s00):
    """Vectorized over (event, stave, sample); each (event, stave) pair is
    independent -- one stave's pulse must not leak into another's baseline
    or amplitude."""
    n_events, n_staves, n_samples = 3, 4, 18
    rng = np.random.default_rng(0)
    waveforms = rng.uniform(80, 120, size=(n_events, n_staves, n_samples))
    # Inject a clean, known pulse into (event=1, stave=2) only.
    waveforms[1, 2, :4] = 100.0
    waveforms[1, 2, 4] = 100.0 + 5000.0

    baseline, amplitude, peak_sample, area = s00.pulse_quantities(waveforms, [0, 1, 2, 3])

    assert baseline.shape == (n_events, n_staves)
    assert amplitude.shape == (n_events, n_staves)
    np.testing.assert_allclose(baseline[1, 2], 100.0)
    np.testing.assert_allclose(amplitude[1, 2], 5000.0)
    assert peak_sample[1, 2] == 4
    # Other (event, stave) pairs must be unaffected by the injected pulse.
    assert amplitude[0, 0] < 200  # nowhere near the 5000 ADC injected pulse
    assert amplitude[2, 3] < 200


def test_pulse_quantities_negative_dip_does_not_become_the_amplitude(s00):
    """A pulse with a negative undershoot must not let the undershoot win
    argmax; amplitude is defined as max(corrected), not max(abs(corrected))."""
    waveforms = np.array([[[100, 100, 100, 100, 100, 250, 100, 40]]], dtype=float)
    baseline, amplitude, peak_sample, _ = s00.pulse_quantities(waveforms, [0, 1, 2, 3])
    np.testing.assert_allclose(baseline, [[100.0]])
    np.testing.assert_allclose(amplitude, [[150.0]])  # the +150 peak, not the -60 undershoot
    assert peak_sample[0, 0] == 5


def test_pulse_quantities_selection_gate_boundary(s00):
    """The S00 selection rule is amplitude > cut (strict), not >=. Verify the
    exact boundary the whole 640,737-pulse count depends on."""
    cut = 1000.0
    waveforms = np.array(
        [
            [[100, 100, 100, 100, 100, 1100, 100, 100]],  # amplitude exactly 1000 -> NOT selected
            [[100, 100, 100, 100, 100, 1100.01, 100, 100]],  # amplitude 1000.01 -> selected
        ],
        dtype=float,
    )
    _, amplitude, _, _ = s00.pulse_quantities(waveforms, [0, 1, 2, 3])
    selected = amplitude > cut
    assert bool(selected[0, 0]) is False
    assert bool(selected[1, 0]) is True


# --------------------------------------------------------------------------
# HRD waveform width contract (Issue #952)
# --------------------------------------------------------------------------


def test_hrd_waveform_contract_rejects_8x16_batch_under_8x18_config(s00):
    """The 9×128 == 8×144 trap: nine 8x16 events (128 words each) can be
    batch-reshaped into eight 8x18 pseudo-events (144 words each). The
    per-event scalar-width gate must reject this, and the error message
    must reference the #952 contract violation. (#952)"""
    rows = [np.arange(128) + 1000 * i for i in range(9)]
    with pytest.raises(ValueError, match=r"HRD waveform contract violation: expected 144 words/event"):
        s00.validate_and_reshape_rows(rows, n_channels=8, samples_per_channel=18)


def test_hrd_waveform_contract_passes_8x18_batch(s00):
    """When every event has exactly 144 words (8x18), the per-event gate must
    pass and the output shape must be (N, 8, 18). (#952)"""
    rows = [np.arange(144) + 1000 * i for i in range(5)]
    out, summary = s00.validate_and_reshape_rows(rows, n_channels=8, samples_per_channel=18)
    assert out.shape == (5, 8, 18)
    assert summary.malformed_events == 0


# --------------------------------------------------------------------------
# compare_expected(): pass/fail bookkeeping
# --------------------------------------------------------------------------


def test_compare_expected_flags_exact_match_as_pass(s00):
    import pandas as pd

    config = {
        "expected_counts": {
            "total_selected_pulses": 10,
            "groups": {
                "g1": {"events": 5, "pulses": 10, "staves": {"B2": 7, "B4": 3}},
            },
        }
    }
    counts_by_group = pd.DataFrame(
        [{"group": "g1", "events_total": 5, "events_with_selected": 5, "selected_pulses": 10, "B2": 7, "B4": 3}]
    )
    result = s00.compare_expected(config, counts_by_group)
    assert bool(result["pass"].all())
    assert (result["delta"] == 0).all()


def test_compare_expected_flags_mismatch_as_fail(s00):
    import pandas as pd

    config = {
        "expected_counts": {
            "total_selected_pulses": 10,
            "groups": {"g1": {"pulses": 10}},
        }
    }
    counts_by_group = pd.DataFrame([{"group": "g1", "selected_pulses": 9}])
    result = s00.compare_expected(config, counts_by_group)
    assert not bool(result["pass"].all())
    row = result[result["quantity"] == "g1 selected pulses"].iloc[0]
    assert row["delta"] == -1


# --------------------------------------------------------------------------
# Config self-consistency (catches accidental edits to s00_reproduction.yaml)
# --------------------------------------------------------------------------


def test_expected_counts_groups_sum_to_total(s00_config):
    """The four run-group pulse counts must sum to the headline 640,737.
    This is the exact number cited throughout PROJECT_REPORT.md,
    FINDINGS_SYNTHESIS.md, docs/ANALYSIS_REPORT.md, and the wiki -- if this
    config is ever hand-edited and the arithmetic breaks, every one of those
    documents becomes silently wrong. This test is the tripwire."""
    expected = s00_config["expected_counts"]
    group_total = sum(group["pulses"] for group in expected["groups"].values())
    assert group_total == expected["total_selected_pulses"] == 640737


def test_expected_counts_sample_ii_stave_breakdown_sums_correctly(s00_config):
    """Sample II analysis per-stave counts (B2/B4/B6/B8) must sum to that
    group's total pulse count -- the exact numbers quoted in README.md's
    'At a glance' table and reports/S00.../REPORT.md."""
    group = s00_config["expected_counts"]["groups"]["sample_ii_analysis"]
    stave_total = sum(group["staves"].values())
    assert stave_total == group["pulses"] == 125096
    assert group["staves"] == {"B2": 88213, "B4": 21229, "B6": 11148, "B8": 4506}


def test_expected_counts_sample_i_analysis_stave_breakdown_sums_correctly(s00_config):
    group = s00_config["expected_counts"]["groups"]["sample_i_analysis"]
    stave_total = sum(group["staves"].values())
    assert stave_total == group["pulses"] == 252266
    assert group["staves"]["B2"] == 241422


def test_baseline_samples_and_amplitude_cut_match_documented_gate(s00_config):
    """Pin the exact S00 gate parameters (median of samples 0-3, cut>1000 ADC)
    that every wiki chapter and report describes in prose, so a silent config
    change would be caught here rather than only discovered by a human
    re-reading the docs against the code."""
    assert s00_config["baseline_samples"] == [0, 1, 2, 3]
    assert s00_config["amplitude_cut_adc"] == 1000.0
    assert s00_config["staves"] == {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
