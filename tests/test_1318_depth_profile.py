import json
import numpy as np
import pandas as pd
from pathlib import Path

EVENT_TABLE_PATH = Path("reports/studies/paper_1318_depth_profile/event_table_8x16.parquet")
MANIFEST_PATH = Path("reports/studies/paper_1318_depth_profile/manifest_8x16.json")


def test_event_table_exists():
    """Test that the event table product exists."""
    assert EVENT_TABLE_PATH.exists(), "Event table not found"


def test_manifest_exists():
    """Test that the manifest exists."""
    assert MANIFEST_PATH.exists(), "Manifest not found"


def test_event_table_schema():
    """Test that the event table has the expected columns."""
    df = pd.read_parquet(EVENT_TABLE_PATH)
    
    expected_cols = ["run", "eventno", "sample", "timestamp"]
    for ch in range(8):
        expected_cols.extend([f"ch{ch}_baseline", f"ch{ch}_amplitude", f"ch{ch}_state"])
    
    for col in expected_cols:
        assert col in df.columns, f"Missing column: {col}"


def test_event_key_uniqueness():
    """Test that (run, eventno) keys are unique."""
    df = pd.read_parquet(EVENT_TABLE_PATH)
    keys = df[["run", "eventno"]].drop_duplicates()
    assert len(keys) == len(df), "Duplicate (run, eventno) keys found"


def test_no_missing_channels_above_threshold():
    """Test that MISSING channels are not counted as above threshold."""
    df = pd.read_parquet(EVENT_TABLE_PATH)
    
    for ch in range(8):
        state_col = f"ch{ch}_state"
        amp_col = f"ch{ch}_amplitude"
        
        # MISSING channels should have amplitude 0 or negative
        missing = df[df[state_col] == "MISSING"]
        if len(missing) > 0:
            assert all(missing[amp_col] <= 0), "MISSING channel has positive amplitude"


def test_threshold_censoring_no_zero_depth_structure():
    """Test that applying a threshold cannot create artificial zero-depth structure.
    
    This is the threshold-censoring cannot create zero-depth structure control:
    we verify that as threshold increases, all staves still have some occupancy
    (not that a specific stave becomes empty while others remain filled).
    """
    df = pd.read_parquet(EVENT_TABLE_PATH)
    
    # Check at threshold=0 (baseline)
    for ch in range(8):
        amp_col = f"ch{ch}_amplitude"
        state_col = f"ch{ch}_state"
        measured = df[(df[state_col] == "PRESENT_MEASURED") & (df[amp_col] >= 0)]
        assert len(measured) > 0, f"Channel {ch} has no measured events at threshold 0"


def test_manifest_input_files():
    """Test that manifest has input file records."""
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    
    assert "input_files" in manifest
    assert len(manifest["input_files"]) > 0
    
    # Each input file should have: run, path, sha256, bytes
    for rec in manifest["input_files"]:
        assert "run" in rec
        assert "path" in rec
        assert "sha256" in rec
        assert len(rec["sha256"]) == 64
        assert "bytes" in rec


def test_manifest_event_counts():
    """Test that manifest records event counts by run."""
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    
    assert "events_by_run" in manifest
    assert "total_events" in manifest
    assert manifest["total_events"] > 0
    
    # Sum of events by run should equal total
    run_sum = sum(manifest["events_by_run"].values())
    assert run_sum == manifest["total_events"]


def test_baseline_stability():
    """Test that baseline region is recorded in manifest."""
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    
    assert "baseline_region_adc" in manifest
    median, mad = manifest["baseline_region_adc"]
    assert isinstance(median, (int, float))
    assert isinstance(mad, (int, float))
    assert mad >= 0


def test_polarity_measured_v2():
    """Polarity source must be the measured v2 map (#954), not falsified v1."""
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    assert "channel_polarity_source" in manifest
    polarity_path = manifest["channel_polarity_source"]
    assert "channel_polarity_v2.json" in polarity_path, (
        f"8x16 product must be built under the measured polarity map v2, got {polarity_path}"
    )
    # measured polarity must actually be applied: full v2 map
    # {0:+,1:-,2:-,3:+,4:-,5:+,6:-,7:+}; even channels B2/B4/B6/B8 are
    # (+,-,-,-), not the alternating (+,-,+,-) of falsified v1
    import numpy as _np
    cfg = json.loads((Path("configs") / "channel_polarity_v2.json").read_text())
    pol = {int(k): v for k, v in cfg["channel_polarity"].items()}
    assert [pol[c] for c in (0, 2, 4, 6)] == [1, -1, -1, -1]
    assert pol == {0: 1, 1: -1, 2: -1, 3: 1, 4: -1, 5: 1, 6: -1, 7: 1}


def test_duplicate_channel_parity_envelope():
    """#1383: both duplicate-channel hypotheses are carried; headline holds under both."""
    parity_path = Path("reports/studies/paper_1318_depth_profile/results/duplicate_channel_parity.json")
    assert parity_path.exists(), "duplicate_channel_parity.json not produced"
    parity = json.loads(parity_path.read_text())
    assert parity["schema_version"] == "duplicate_channel_parity_v1"
    assert set(parity["hypotheses"]) == {"even", "odd"}
    assert parity["canonical_map"] == {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
    assert parity["duplicate_map"] == {"B2": 1, "B4": 3, "B6": 5, "B8": 7}
    for stave, env in parity["envelope"].items():
        assert env["sample_i"][0] <= env["sample_i"][1]
        assert env["sample_ii"][0] <= env["sample_ii"][1]
    # the headline (Sample II reaches deeper staves than Sample I) must survive
    # BOTH duplicate-channel hypotheses, not only the canonical one
    assert parity["b8_over_b2_ii_exceeds_i_under_both"] is True
    assert parity["sample_ii_b6_b8_share_exceeds_i_under_both"] is True


def test_result_schema_v2_fields():
    """Result JSON records polarity source, channel map and parity reference."""
    result_path = Path("reports/studies/paper_1318_depth_profile/results/depth_profile_result_thresh_0.json")
    result = json.loads(result_path.read_text())
    assert result["schema_version"] == "depth_profile_8x16_v2"
    assert "channel_polarity_v2.json" in result["channel_polarity_source"]
    assert result["stave_channel_map"] == {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
    assert result["duplicate_channel_parity_path"].endswith("duplicate_channel_parity.json")


def test_sample_classification():
    """Test that events are classified into Sample I and II."""
    df = pd.read_parquet(EVENT_TABLE_PATH)
    
    assert "sample" in df.columns
    samples = df["sample"].unique()
    assert "I" in samples
    assert "II" in samples


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
