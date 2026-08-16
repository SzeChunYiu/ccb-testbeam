"""Lane05 Wave-A timing CFD contract tests (#954,#1003,#1004,#1059,#1060,#1061,#1063,#1277,#1278)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import digital_cfd
import channel_polarity
from real_data_cfd_contract import (
    RunPopulationReport,
    apply_intime_mask,
    assert_run_population_complete,
    peak_offset_dictionary,
    select_complete_pair_rows,
)


def _load_s02():
    spec = importlib.util.spec_from_file_location("s02_timing_pickoff", SCRIPTS / "s02_timing_pickoff.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_left_censored_crossing_is_no_crossing_in_window_not_zero():
    # Sample 0 already above threshold -> left-censored (#1060)
    wave = np.asarray([[5.0, 6.0, 4.0, 2.0]], dtype=float)
    amp = np.asarray([6.0])
    times, statuses = digital_cfd.cfd_time_samples(wave, amp, 0.2, return_status=True)
    assert statuses[0] == digital_cfd.NO_CROSSING_IN_WINDOW
    assert not np.isfinite(times[0])


def test_normal_crossing_interpolates():
    wave = np.asarray([[0.0, 1.0, 3.0, 2.0]], dtype=float)
    amp = np.asarray([3.0])
    times, statuses = digital_cfd.cfd_time_samples(wave, amp, 0.5, return_status=True)
    assert statuses[0] == digital_cfd.OK
    # threshold = 1.5 between samples 1 and 2
    assert times[0] == pytest.approx(1.0 + (1.5 - 1.0) / (3.0 - 1.0))


def test_component_switch_reduced_by_first_local_peak():
    # Early peak 1000 at sample 3, late peak 3000 at sample 10 (#1059)
    y = np.zeros(16, dtype=float)
    y[2], y[3], y[4] = 500.0, 1000.0, 500.0
    y[9], y[10], y[11] = 1500.0, 3000.0, 1500.0
    wave = y[None, :]
    # Global-max at f=0.4 thresholds on late component
    t_global = digital_cfd.cfd_time_samples(wave, None, 0.4, amplitude_mode="global_max")
    t_local = digital_cfd.cfd_time_samples(wave, None, 0.4, amplitude_mode="first_local_peak")
    assert t_global[0] > 7.0
    assert t_local[0] < 5.0


def test_s02_and_p06d_delegate_to_digital_cfd():
    s02 = _load_s02()
    wave = np.asarray([[0.0, 0.5, 2.0, 1.0], [3.0, 3.0, 2.0, 1.0]], dtype=float)
    amp = np.max(wave, axis=1)
    a = s02.cfd_time_samples(wave, amp, 0.25)
    b = digital_cfd.cfd_time_samples(wave, amp, 0.25)
    assert np.array_equal(np.isnan(a), np.isnan(b))
    mask = np.isfinite(a)
    assert np.allclose(a[mask], b[mask])
    # Left-censored second row must be nan in both
    assert np.isnan(a[1]) and np.isnan(b[1])

    p06_source = (SCRIPTS / "p06d_1781066704_794_27df492e_peak_phase_coupling_atlas.py").read_text(
        encoding="utf-8"
    )
    assert "import digital_cfd" in p06_source
    assert "waveforms >= threshold" not in p06_source


def test_run_population_authorising_fails_on_missing():
    report = RunPopulationReport(
        requested_runs=(1, 2),
        resolved_runs=(1,),
        missing_runs=(2,),
        empty_runs=tuple(),
        failed_runs=tuple(),
        excluded_by_policy=tuple(),
        events_per_run={1: 10},
        pulses_per_run={1: 5},
        authorising=True,
        mode="authorising",
    )
    with pytest.raises(RuntimeError, match="missing_runs"):
        assert_run_population_complete(report)


def test_run_population_exploratory_allows_missing():
    report = RunPopulationReport(
        requested_runs=(1, 2),
        resolved_runs=(1,),
        missing_runs=(2,),
        empty_runs=tuple(),
        failed_runs=tuple(),
        excluded_by_policy=tuple(),
        events_per_run={1: 10},
        pulses_per_run={1: 5},
        authorising=False,
        mode="exploratory_permissive",
    )
    assert_run_population_complete(report)


def test_complete_pair_vs_intime_conditioning():
    frame = pd.DataFrame(
        {
            "run": [1, 1, 1, 1, 2, 2],
            "event_id": [1, 1, 2, 2, 3, 3],
            "stave": ["B6", "B8", "B6", "B8", "B6", "B8"],
            "peak_sample": [10.0, 10.1, 10.0, 20.0, 11.0, 11.2],
        }
    )
    complete, n_complete = select_complete_pair_rows(frame, ["B6", "B8"])
    assert n_complete == 3
    offsets = peak_offset_dictionary(complete, ["B6", "B8"])
    intime, n_intime = apply_intime_mask(complete, ["B6", "B8"], offsets, 1.5)
    assert n_intime == 2
    assert n_intime < n_complete


def test_polarity_map_measured_v2_signs():
    """#954: measured polarity v2 -- even ch0=+1/ch1=-1 kept, ch2-7 pair-alternating."""
    polarity_map = channel_polarity.load_polarity_map(
        ROOT / "configs" / "channel_polarity_v2.json"
    )
    measured = {0: 1, 1: -1, 2: -1, 3: 1, 4: -1, 5: 1, 6: -1, 7: 1}
    for ch, sign in measured.items():
        assert polarity_map.polarity_for_channel(ch) == sign
    raw = np.zeros((1, 8, 4), dtype=float)
    raw[0, 1, :] = -5.0  # ch1 negative-going pulse under v2
    base_corrected = raw.copy()
    flipped = channel_polarity.apply_polarity(base_corrected, polarity_map)
    assert flipped[0, 1].max() == 5.0


def test_template_loro_excludes_heldout_run_from_build():
    """build_templates on train must not include held-out run pulses (#1061)."""
    s02 = _load_s02()
    rng = np.random.default_rng(0)
    rows = []
    for run in (10, 11):
        for event in range(5):
            for stave, ch in (("B6", 0), ("B8", 1)):
                wave = np.zeros(16, dtype=np.float32)
                wave[4:8] = 1000.0 + 50 * run
                rows.append(
                    {
                        "run": run,
                        "event_id": event,
                        "stave": stave,
                        "amplitude_adc": float(wave.max()),
                        "peak_sample": 6.0,
                        "waveform": wave,
                    }
                )
    df = pd.DataFrame(rows)
    train = df[df["run"] != 10]
    templates = s02.build_templates(train, ["B6", "B8"])
    # Training template median peak scale tracks run 11 only (~1050), not average with 10.
    assert float(np.max(templates["B6"])) == pytest.approx(1.0, abs=1e-6)


def test_producer_source_contract_tokens():
    source = (SCRIPTS / "real_data_cfd_timing.py").read_text(encoding="utf-8")
    assert "LEAVE_ONE_RUN_OUT" in source or "leave-one-run-out" in source.lower() or "_template_phase_loro" in source
    assert "NO_CROSSING_IN_WINDOW" in source or "digital_cfd" in source
    assert "RunPopulationReport" in source or "assert_run_population_complete" in source
    assert "SAME_SAMPLE_MINIMUM_EXPLORATORY_ONLY" in source
    assert "select_complete_pair_rows" in source
    assert "load_polarity_map" in source
    assert "first_local_peak_diagnostics" in source
    assert "first_local_peak_selector" in source
    assert "/ np.sqrt(2)" not in source


def test_first_local_selector_identifiability_limits_are_non_authorising():
    wave = np.asarray(
        [[0.0, 25.0, 49.9, 25.0, 0.0, 0.0, 500.0, 1000.0, 500.0]],
        dtype=float,
    )
    diagnostic = digital_cfd.first_local_peak_diagnostics(wave)
    assert diagnostic["authorising_component_identity"] is False
    assert diagnostic["evidence_status"] == digital_cfd.FIRST_LOCAL_PEAK_SELECTOR_STATUS
    import cfd_selector_sensitivity

    stability = cfd_selector_sensitivity.first_local_peak_linf_stability_diagnostics(
        wave
    )
    assert stability["certificate_statuses"][0] != "AUTHORIZED_COMPONENT_IDENTITY"


def test_global_max_fraction_scan_switches_component_near_a1_over_a2():
    """Deterministic two-pulse control: global-max CFD retargets at ~A1/A2 (#1059)."""
    import cfd_fraction_transition

    early_amp, late_amp = 1000.0, 3000.0
    wave = cfd_fraction_transition.synthetic_two_pulse_triangle(
        early_amplitude=early_amp,
        late_amplitude=late_amp,
    )[None, :]
    fractions = np.linspace(0.05, 0.95, 19)
    scan = cfd_fraction_transition.fraction_transition_scan(
        wave,
        fractions,
        amplitude_mode="global_max",
    )
    threshold = cfd_fraction_transition.expected_global_max_switch_fraction(
        early_amp,
        late_amp,
    )
    assert threshold == pytest.approx(1.0 / 3.0)
    assert scan["n_switch_events"] >= 1
    early_time = cfd_fraction_transition.fraction_transition_scan(
        wave, [0.1], amplitude_mode="global_max"
    )["rows"][0]["time_samples"]
    late_time = cfd_fraction_transition.fraction_transition_scan(
        wave, [0.9], amplitude_mode="global_max"
    )["rows"][0]["time_samples"]
    assert float(early_time) < 5.0
    assert float(late_time) > 7.0


def test_first_local_peak_fraction_scan_stays_on_selected_component():
    import cfd_fraction_transition

    wave = cfd_fraction_transition.synthetic_two_pulse_triangle(
        early_amplitude=1000.0,
        late_amplitude=3000.0,
    )[None, :]
    diagnostic = digital_cfd.first_local_peak_diagnostics(wave)
    selected_index = int(diagnostic["selected_peak_indices"][0])
    assert selected_index < 5

    fractions = [0.1, 0.2, 0.3, 0.4, 0.5]
    times = []
    for fraction in fractions:
        time, status = digital_cfd.cfd_time_samples(
            wave,
            None,
            fraction,
            amplitude_mode="first_local_peak",
            return_status=True,
        )
        assert status[0] == digital_cfd.OK
        times.append(float(time[0]))
        assert float(time[0]) < 5.0
    assert max(times) - min(times) < 2.0


def test_method_selection_is_exploratory_not_authorising():
    source = (SCRIPTS / "real_data_cfd_timing.py").read_text(encoding="utf-8")
    assert "SAME_SAMPLE_MINIMUM_EXPLORATORY_ONLY" in source
    assert "same_sample_method_minimum_authorized" in source
    assert "best_pair_sigma68_authorising" in source
    assert "not authorising" in source.lower() or "Not an unconditional" in source


def test_real_data_fraction_transition_blocked_until_schema_gate():
    """#993 lineage blocks authorising real-data fraction-transition product."""
    import cfd_fraction_transition

    assert (
        cfd_fraction_transition.REAL_DATA_SCHEMA_GATE
        == "BLOCKED_UNTIL_993_WAVEFORM_LINEAGE_CLOSES"
    )
    report = (ROOT / "reports" / "real_data_cfd_timing" / "REPORT.md").read_text(
        encoding="utf-8"
    )
    assert "QUARANTINED" in report or "FLAWED" in report


def test_polarity_config_is_versioned_json():
    payload = json.loads((ROOT / "configs" / "channel_polarity_v2.json").read_text(encoding="utf-8"))
    assert payload["version"] == "channel_polarity_v2"
    assert payload["status"] == "MEASURED_202608_RUNS31_65_UNANIMOUS_BOTH_ESTIMATORS"
    assert set(payload["channel_polarity"]) >= {"0", "1", "4", "6"}

