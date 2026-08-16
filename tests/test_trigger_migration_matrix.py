#!/usr/bin/env python3
"""Unit tests for trigger_migration_matrix.py using synthetic scan outputs.

Tests fabricate minimal scan-result JSONs with known migration patterns:
- Perfect migration (proxy == hardware)
- Complete loss (proxy selects events that hardware rejects)
- Partial migration (some overlap)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def create_synthetic_scan_output(
    mode: str,
    n_events: int = 1000,
    n_pass: int = 100,
    species: dict | None = None,
) -> dict:
    """Create a synthetic scan-output JSON structure.

    Args:
        mode: "proxy" or "hardware"
        n_events: Total number of events
        n_pass: Number of events passing trigger
        species: Optional dict mapping species name to {"n_enter": int, "n_pass": int}

    Returns:
        Dictionary matching the scan-output JSON schema.
    """
    if species is None:
        species = {
            "deuteron": {"n_enter": 700, "n_pass": n_pass},
            "proton": {"n_enter": 300, "n_pass": 0},
        }

    return {
        "scan_config": {
            "input_file": f"synthetic_{mode}.root",
            "mode": mode,
            "thresholds_mev": [1.0],
            "coincidence_windows_ns": [15.0],
            "max_events": n_events,
        },
        "results": [
            {
                "threshold_mev": 1.0,
                "coinc_ns": 15.0,
                "n_events": n_events,
                "n_trigger_pass": n_pass,
                "efficiency": n_pass / n_events,
                "species_breakdown": species,
            }
        ],
    }


def run_migration_analysis(proxy_json: str, hardware_json: str) -> dict:
    """Run the migration matrix script and return the output."""
    result = subprocess.run(
        [
            sys.executable or "python3",
            "scripts/trigger_migration_matrix.py",
            "--proxy-json",
            proxy_json,
            "--hardware-json",
            hardware_json,
            "--output",
            "-",
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Script failed: {result.stderr}")
    return json.loads(result.stdout)


def test_perfect_migration():
    """Test perfect migration: proxy and hardware select identical events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Both proxy and hardware select the same 100 events
        species_data = {
            "deuteron": {"n_enter": 700, "n_pass": 100},
            "proton": {"n_enter": 300, "n_pass": 0},
        }
        proxy_json = tmpdir / "proxy.json"
        hardware_json = tmpdir / "hardware.json"

        proxy_json.write_text(
            json.dumps(create_synthetic_scan_output("proxy", 1000, 100, species_data))
        )
        hardware_json.write_text(
            json.dumps(create_synthetic_scan_output("hardware", 1000, 100, species_data))
        )

        # Note: Script writes to file, not stdout. Need to adapt test.
        # For now, just verify the script can import and run without error.
        result = subprocess.run(
            [
                sys.executable or "python3",
                "scripts/trigger_migration_matrix.py",
                "--proxy-json",
                str(proxy_json),
                "--hardware-json",
                str(hardware_json),
                "--output",
                str(tmpdir / "output.json"),
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Load and verify output
        output = json.loads((tmpdir / "output.json").read_text())

        # In perfect migration, proxy-only and hardware-only should be 0
        q = output["aggregate_migration"]["quadrants"]
        assert q["both"] == 100, f"Expected both=100, got {q['both']}"
        assert q["proxy_only"] == 0, f"Expected proxy_only=0, got {q['proxy_only']}"
        assert q["hardware_only"] == 0, f"Expected hardware_only=0, got {q['hardware_only']}"
        assert q["neither"] == 900, f"Expected neither=900, got {q['neither']}"

        # Migration loss should be 0%
        assert output["headline_metrics"]["migration_loss_percent"] == 0.0


def test_complete_loss():
    """Test complete migration loss: proxy selects events that hardware rejects."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Proxy selects 100 events, hardware selects 0 (different 100)
        proxy_species = {
            "deuteron": {"n_enter": 700, "n_pass": 100},
            "proton": {"n_enter": 300, "n_pass": 0},
        }
        hardware_species = {
            "deuteron": {"n_enter": 700, "n_pass": 0},
            "proton": {"n_enter": 300, "n_pass": 0},
        }

        proxy_json = tmpdir / "proxy.json"
        hardware_json = tmpdir / "hardware.json"

        proxy_json.write_text(
            json.dumps(create_synthetic_scan_output("proxy", 1000, 100, proxy_species))
        )
        hardware_json.write_text(
            json.dumps(
                create_synthetic_scan_output("hardware", 1000, 0, hardware_species)
            )
        )

        result = subprocess.run(
            [
                sys.executable or "python3",
                "scripts/trigger_migration_matrix.py",
                "--proxy-json",
                str(proxy_json),
                "--hardware-json",
                str(hardware_json),
                "--output",
                str(tmpdir / "output.json"),
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"

        output = json.loads((tmpdir / "output.json").read_text())

        # All proxy passes should be proxy-only (complete loss)
        q = output["aggregate_migration"]["quadrants"]
        assert q["both"] == 0, f"Expected both=0, got {q['both']}"
        assert q["proxy_only"] == 100, f"Expected proxy_only=100, got {q['proxy_only']}"
        assert q["hardware_only"] == 0, f"Expected hardware_only=0, got {q['hardware_only']}"
        assert q["neither"] == 900, f"Expected neither=900, got {q['neither']}"

        # Migration loss should be 100%
        assert output["headline_metrics"]["migration_loss_percent"] == 100.0


def test_partial_migration():
    """Test partial migration: some overlap between proxy and hardware."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Proxy selects 100, hardware selects 60, overlap of 40
        # This is modeled by having:
        # - 40 events that pass both
        # - 60 events that pass only proxy
        # - 20 events that pass only hardware
        # - 880 events that pass neither
        proxy_species = {
            "deuteron": {"n_enter": 700, "n_pass": 100},
        }
        hardware_species = {
            "deuteron": {"n_enter": 700, "n_pass": 60},
        }

        proxy_json = tmpdir / "proxy.json"
        hardware_json = tmpdir / "hardware.json"

        proxy_json.write_text(
            json.dumps(create_synthetic_scan_output("proxy", 1000, 100, proxy_species))
        )
        hardware_json.write_text(
            json.dumps(
                create_synthetic_scan_output("hardware", 1000, 60, hardware_species)
            )
        )

        result = subprocess.run(
            [
                sys.executable or "python3",
                "scripts/trigger_migration_matrix.py",
                "--proxy-json",
                str(proxy_json),
                "--hardware-json",
                str(hardware_json),
                "--output",
                str(tmpdir / "output.json"),
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"

        output = json.loads((tmpdir / "output.json").read_text())

        # Quadrants: both=40, proxy_only=60, hardware_only=20, neither=880
        q = output["aggregate_migration"]["quadrants"]
        assert q["both"] == 40, f"Expected both=40, got {q['both']}"
        assert q["proxy_only"] == 60, f"Expected proxy_only=60, got {q['proxy_only']}"
        assert q["hardware_only"] == 20, f"Expected hardware_only=20, got {q['hardware_only']}"
        assert q["neither"] == 880, f"Expected neither=880, got {q['neither']}"

        # Migration loss: 60/(60+40) = 60%
        loss = output["headline_metrics"]["migration_loss_percent"]
        assert abs(loss - 60.0) < 0.01, f"Expected loss=60%, got {loss}%"


def test_species_breakdown():
    """Test that per-species migration is computed correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Two species with different migration patterns
        proxy_species = {
            "deuteron": {"n_enter": 500, "n_pass": 80},
            "proton": {"n_enter": 500, "n_pass": 20},
        }
        hardware_species = {
            "deuteron": {"n_enter": 500, "n_pass": 50},
            "proton": {"n_enter": 500, "n_pass": 10},
        }

        proxy_json = tmpdir / "proxy.json"
        hardware_json = tmpdir / "hardware.json"

        proxy_json.write_text(
            json.dumps(create_synthetic_scan_output("proxy", 1000, 100, proxy_species))
        )
        hardware_json.write_text(
            json.dumps(create_synthetic_scan_output("hardware", 1000, 60, hardware_species))
        )

        result = subprocess.run(
            [
                sys.executable or "python3",
                "scripts/trigger_migration_matrix.py",
                "--proxy-json",
                str(proxy_json),
                "--hardware-json",
                str(hardware_json),
                "--output",
                str(tmpdir / "output.json"),
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"

        output = json.loads((tmpdir / "output.json").read_text())

        # Check per-species migration
        deuteron = output["species_migration"]["deuteron"]
        proton = output["species_migration"]["proton"]

        # Deuteron: 80 proxy pass, 50 hardware pass => both=50, proxy_only=30, hw_only=0
        # Loss: 30/(30+50) = 37.5%
        assert deuteron["quadrants"]["both"] == 50
        assert deuteron["quadrants"]["proxy_only"] == 30
        assert abs(deuteron["migration_loss_fraction"] - 0.375) < 0.01

        # Proton: 20 proxy pass, 10 hardware pass => both=10, proxy_only=10, hw_only=0
        # Loss: 10/(10+10) = 50%
        assert proton["quadrants"]["both"] == 10
        assert proton["quadrants"]["proxy_only"] == 10
        assert abs(proton["migration_loss_fraction"] - 0.5) < 0.01


if __name__ == "__main__":
    test_perfect_migration()
    print("test_perfect_migration: PASS")

    test_complete_loss()
    print("test_complete_loss: PASS")

    test_partial_migration()
    print("test_partial_migration: PASS")

    test_species_breakdown()
    print("test_species_breakdown: PASS")

    print()
    print("All tests passed!")
