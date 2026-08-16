#!/usr/bin/env python3
"""Unit tests for trigger_threshold_scan.py using synthetic T1/T2 branches.

Tests fabricate ROOT trees with known ground truth patterns:
- Pure hits (both T1 and T2 above threshold, in-time)
- Off-time hits (above threshold but outside coincidence window)
- Sub-threshold hits (below threshold)
- Edge-of-window hits (exactly at coincidence boundary)
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# Try to import test dependencies
try:
    import numpy as np
except ImportError as e:
    print(f"Missing numpy: {e}", file=sys.stderr)
    sys.exit(2)

# Try to import uproot for tree creation
try:
    import uproot
except ImportError as e:
    print(f"Missing uproot: {e}", file=sys.stderr)
    sys.exit(2)


def create_synthetic_tree(
    output_path: str,
    events: list[dict],
    hrd_branches: bool = False,
) -> None:
    """Create a synthetic ROOT tree with T1/T2 trigger branches.

    Branch names follow the real Phase 2 sensitive-detector schema
    (T1_trigger_log_EDep etc., as verified against
    output_krakow_phase2_10k.root).

    Args:
        output_path: Path to write ROOT file
        events: List of event dicts, each with T1_EDep, T1_Time, T2_EDep,
            T2_Time arrays; with hrd_branches=True additionally
            Sci_bar_LayerID, Sci_bar_LayerID1, Sci_bar_PDG, Sci_bar_Time.
    """
    data = {
        "T1_trigger_log_EDep": [],
        "T1_trigger_log_Time": [],
        "T2_trigger_log_EDep": [],
        "T2_trigger_log_Time": [],
    }

    for event in events:
        data["T1_trigger_log_EDep"].append(event["T1_EDep"])
        data["T1_trigger_log_Time"].append(event["T1_Time"])
        data["T2_trigger_log_EDep"].append(event["T2_EDep"])
        data["T2_trigger_log_Time"].append(event["T2_Time"])

    if hrd_branches:
        data["Sci_bar_LayerID"] = []
        data["Sci_bar_LayerID1"] = []
        data["Sci_bar_PDG"] = []
        data["Sci_bar_Time"] = []
        for event in events:
            data["Sci_bar_LayerID"].append(event["Sci_bar_LayerID"])
            data["Sci_bar_LayerID1"].append(event["Sci_bar_LayerID1"])
            data["Sci_bar_PDG"].append(event["Sci_bar_PDG"])
            data["Sci_bar_Time"].append(event["Sci_bar_Time"])

    with uproot.recreate(output_path) as f:
        f.mktree("hibeam", data)


def test_pure_hits():
    """Test event with both T1 and T2 above threshold, in-time coincidence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root_file = Path(tmpdir) / "test.root"
        
        # Create 100 events: all should pass (1 MeV in both, time diff = 5 ns)
        events = []
        for i in range(100):
            events.append({
                "T1_EDep": np.array([1.0], dtype=np.float32),
                "T1_Time": np.array([0.0], dtype=np.float32),
                "T2_EDep": np.array([1.0], dtype=np.float32),
                "T2_Time": np.array([5.0], dtype=np.float32),
            })
        
        create_synthetic_tree(str(root_file), events)
        
        # Run scan
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                "scripts/trigger_threshold_scan.py",
                "--input", str(root_file),
                "--output", "test_output.json",
                "--repo-root", tmpdir,
                "--thresholds", "0.5",
                "--coincidence-windows", "10",
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0, f"Scan failed: {result.stderr}"
        
        # Check results
        output_file = Path(tmpdir) / "test_output.json"
        assert output_file.exists(), "Output file not created"
        
        with open(output_file) as f:
            data = json.load(f)
        
        assert len(data["results"]) == 1, "Expected 1 scan configuration"
        result = data["results"][0]
        
        # All 100 events should pass
        assert result["n_events"] == 100, f"Expected 100 events, got {result[n_events]}"
        assert result["n_trigger_pass"] == 100, f"Expected 100 pass, got {result[n_trigger_pass]}"
        assert abs(result["efficiency"] - 1.0) < 1e-6, f"Expected efficiency 1.0, got {result[efficiency]}"
        
        print("test_pure_hits: PASS")


def test_off_time_hits():
    """Test event with above-threshold hits outside coincidence window."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root_file = Path(tmpdir) / "test.root"
        
        # Create 100 events: all should fail (1 MeV in both, time diff = 25 ns > 20 ns window)
        events = []
        for i in range(100):
            events.append({
                "T1_EDep": np.array([1.0], dtype=np.float32),
                "T1_Time": np.array([0.0], dtype=np.float32),
                "T2_EDep": np.array([1.0], dtype=np.float32),
                "T2_Time": np.array([25.0], dtype=np.float32),
            })
        
        create_synthetic_tree(str(root_file), events)
        
        # Run scan with 20 ns coincidence window
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                "scripts/trigger_threshold_scan.py",
                "--input", str(root_file),
                "--output", "test_output.json",
                "--repo-root", tmpdir,
                "--thresholds", "0.5",
                "--coincidence-windows", "20",
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0, f"Scan failed: {result.stderr}"
        
        output_file = Path(tmpdir) / "test_output.json"
        with open(output_file) as f:
            data = json.load(f)
        
        result = data["results"][0]
        
        # All 100 events should fail (outside coincidence window)
        assert result["n_events"] == 100
        assert result["n_trigger_pass"] == 0, f"Expected 0 pass, got {result[n_trigger_pass]}"
        assert abs(result["efficiency"] - 0.0) < 1e-6, f"Expected efficiency 0.0, got {result[efficiency]}"
        
        print("test_off_time_hits: PASS")


def test_sub_threshold_hits():
    """Test event with hits below energy threshold."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root_file = Path(tmpdir) / "test.root"
        
        # Create 100 events: all should fail (0.1 MeV in both, below 0.5 MeV threshold)
        events = []
        for i in range(100):
            events.append({
                "T1_EDep": np.array([0.1], dtype=np.float32),
                "T1_Time": np.array([0.0], dtype=np.float32),
                "T2_EDep": np.array([0.1], dtype=np.float32),
                "T2_Time": np.array([5.0], dtype=np.float32),
            })
        
        create_synthetic_tree(str(root_file), events)
        
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                "scripts/trigger_threshold_scan.py",
                "--input", str(root_file),
                "--output", "test_output.json",
                "--repo-root", tmpdir,
                "--thresholds", "0.5",
                "--coincidence-windows", "10",
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0, f"Scan failed: {result.stderr}"
        
        output_file = Path(tmpdir) / "test_output.json"
        with open(output_file) as f:
            data = json.load(f)
        
        result = data["results"][0]
        
        # All 100 events should fail (below threshold)
        assert result["n_events"] == 100
        assert result["n_trigger_pass"] == 0, f"Expected 0 pass, got {result[n_trigger_pass]}"
        assert abs(result["efficiency"] - 0.0) < 1e-6, f"Expected efficiency 0.0, got {result[efficiency]}"
        
        print("test_sub_threshold_hits: PASS")


def test_edge_of_window():
    """Test event at coincidence boundary (exactly at window limit)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root_file = Path(tmpdir) / "test.root"
        
        # Create 100 events: should FAIL (time diff = 10 ns, coinc window = 10 ns, NOT < 10)
        events = []
        for i in range(100):
            events.append({
                "T1_EDep": np.array([1.0], dtype=np.float32),
                "T1_Time": np.array([0.0], dtype=np.float32),
                "T2_EDep": np.array([1.0], dtype=np.float32),
                "T2_Time": np.array([10.0], dtype=np.float32),
            })
        
        create_synthetic_tree(str(root_file), events)
        
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                "scripts/trigger_threshold_scan.py",
                "--input", str(root_file),
                "--output", "test_output.json",
                "--repo-root", tmpdir,
                "--thresholds", "0.5",
                "--coincidence-windows", "10",
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0, f"Scan failed: {result.stderr}"
        
        output_file = Path(tmpdir) / "test_output.json"
        with open(output_file) as f:
            data = json.load(f)
        
        result = data["results"][0]
        
        # All events should FAIL (abs(10 - 0) = 10, NOT < 10)
        assert result["n_events"] == 100
        assert result["n_trigger_pass"] == 0, f"Expected 0 pass (edge is exclusive), got {result[n_trigger_pass]}"
        assert abs(result["efficiency"] - 0.0) < 1e-6, f"Expected efficiency 0.0, got {result[efficiency]}"
        
        print("test_edge_of_window: PASS")


def test_mixed_events():
    """Test mixed scenario: some pass, some fail."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root_file = Path(tmpdir) / "test.root"
        
        # Create 100 events: 25 pass, 75 fail
        events = []
        for i in range(25):
            # Pass: 1 MeV, time diff = 5 ns
            events.append({
                "T1_EDep": np.array([1.0], dtype=np.float32),
                "T1_Time": np.array([0.0], dtype=np.float32),
                "T2_EDep": np.array([1.0], dtype=np.float32),
                "T2_Time": np.array([5.0], dtype=np.float32),
            })
        for i in range(75):
            # Fail: off-time (25 ns)
            events.append({
                "T1_EDep": np.array([1.0], dtype=np.float32),
                "T1_Time": np.array([0.0], dtype=np.float32),
                "T2_EDep": np.array([1.0], dtype=np.float32),
                "T2_Time": np.array([25.0], dtype=np.float32),
            })
        
        create_synthetic_tree(str(root_file), events)
        
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                "scripts/trigger_threshold_scan.py",
                "--input", str(root_file),
                "--output", "test_output.json",
                "--repo-root", tmpdir,
                "--thresholds", "0.5",
                "--coincidence-windows", "20",
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0, f"Scan failed: {result.stderr}"
        
        output_file = Path(tmpdir) / "test_output.json"
        with open(output_file) as f:
            data = json.load(f)
        
        result = data["results"][0]
        
        # 25/100 should pass
        assert result["n_events"] == 100
        assert result["n_trigger_pass"] == 25, f"Expected 25 pass, got {result[n_trigger_pass]}"
        assert abs(result["efficiency"] - 0.25) < 1e-6, f"Expected efficiency 0.25, got {result[efficiency]}"
        
        print("test_mixed_events: PASS")


def test_hardware_species_join():
    """Hardware mode must pick up per-species enter/pass when Sci_bar branches
    are present in the same file, using the proxy enter_B denominator."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root_file = Path(tmpdir) / "test.root"

        # 10 events: all have a charged primary entering the B arm; 5 fire the
        # hardware T1/T2 coincidence (1 MeV in both, 5 ns apart).
        events = []
        for i in range(10):
            events.append({
                "T1_EDep": np.array([1.0], dtype=np.float32),
                "T1_Time": np.array([0.0], dtype=np.float32),
                "T2_EDep": np.array([1.0], dtype=np.float32),
                "T2_Time": np.array([5.0], dtype=np.float32),
                # charged primary proton through first B-arm bar layer
                "Sci_bar_LayerID": np.array([0], dtype=np.int32),
                "Sci_bar_LayerID1": np.array([1], dtype=np.int32),  # B_ARM
                "Sci_bar_PDG": np.array([2212], dtype=np.int64),
                "Sci_bar_Time": np.array([0.0], dtype=np.float32),
            })
        for i in range(5):
            events[i]["T2_Time"] = np.array([5.0], dtype=np.float32)
        for i in range(5, 10):
            events[i]["T2_EDep"] = np.array([0.1], dtype=np.float32)  # sub-threshold

        create_synthetic_tree(str(root_file), events, hrd_branches=True)

        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                "scripts/trigger_threshold_scan.py",
                "--input", str(root_file),
                "--output", "test_output.json",
                "--repo-root", tmpdir,
                "--thresholds", "0.5",
                "--coincidence-windows", "10",
                "--mode", "hardware",
            ],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Scan failed: {result.stderr}"

        output_file = Path(tmpdir) / "test_output.json"
        with open(output_file) as f:
            data = json.load(f)

        result = data["results"][0]
        assert result["n_trigger_pass"] == 5, (
            f"Expected 5 hardware passes, got {result['n_trigger_pass']}"
        )
        assert result["species_breakdown"].get("proton") == {
            "n_enter": 10, "n_pass": 5
        }, f"Unexpected species breakdown: {result['species_breakdown']}"

        print("test_hardware_species_join: PASS")


if __name__ == "__main__":
    # Run all tests
    print("Running synthetic-branch unit tests for trigger_threshold_scan.py")
    print("=" * 60)

    test_pure_hits()
    test_off_time_hits()
    test_sub_threshold_hits()
    test_edge_of_window()
    test_mixed_events()
    test_hardware_species_join()

    print("=" * 60)
    print("All tests passed!")
