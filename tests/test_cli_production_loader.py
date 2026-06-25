"""CLI production loader wiring tests."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import yaml

from ccb_mc_validation import cli


def _config(tmp_path: Path) -> Path:
    root = tmp_path
    mc = root / "mc.root"
    mc.write_bytes(b"placeholder")
    cfg = root / "config.yaml"
    cfg.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "paths": {
                    "repo_root": ".",
                    "mc_root": str(mc),
                    "data_pulses": "pulses.csv.gz",
                    "reports_dir": "reports",
                    "resolved_config_dir": "reports/resolved",
                },
                "seeds": {"global": 1},
                "units": {"energy": "MeV", "time": "ns", "adc": "ADC", "documented": {}},
                "studies": {"mv1": {"enabled": True, "output_subdir": "mv1"}},
            }
        ),
        encoding="utf-8",
    )
    return cfg


def test_mv1_production_uses_loader_inside_slurm(monkeypatch, tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    loaded = {}

    def fake_loader(path, **kwargs):
        loaded["path"] = path
        loaded["kwargs"] = kwargs
        return {
            "pdg": np.array([2212, 1000010020, 2212, 1000010020]),
            "edep_l0": np.array([1.0, 3.0, 1.2, 3.2]),
            "edep_l1": np.array([0.5, 1.0, 0.6, 1.1]),
            "edep_tot": np.array([1.5, 4.0, 1.8, 4.3]),
            "stop_layer": np.array([1, 3, 1, 3]),
        }

    monkeypatch.setattr(cli, "load_truth_records", fake_loader)
    monkeypatch.setenv("SLURM_JOB_ID", "123")
    monkeypatch.setenv("CCB_MAX_ROOT_EVENTS", "12")
    args = argparse.Namespace(config=str(cfg), repo_root=str(tmp_path), fixture=False)

    assert cli.cmd_mv1(args) == 0
    assert loaded["kwargs"]["max_events"] == 12
    assert (tmp_path / "reports" / "mv1" / "study_result.json").is_file()
