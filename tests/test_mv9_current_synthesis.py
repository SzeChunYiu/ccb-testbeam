"""MV9 current artifact synthesis tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from ccb_mc_validation.cli import cmd_synthesize


def test_synthesize_prefers_current_study_results(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0.0",
                "paths": {
                    "repo_root": ".",
                    "mc_root": "mc.root",
                    "data_pulses": "pulses.csv.gz",
                    "reports_dir": "reports",
                    "resolved_config_dir": "reports/resolved",
                },
                "seeds": {"global": 1},
                "units": {"energy": "MeV", "time": "ns", "adc": "ADC", "documented": {}},
                "studies": {
                    "mv1": {"enabled": True, "output_subdir": "mc_validation/mv1_pid"},
                    "mv2": {"enabled": True, "output_subdir": "mc_validation/mv2_energy"},
                    "mv3": {"enabled": True, "output_subdir": "mc_validation/mv3_stopping_depth"},
                    "mv9": {"enabled": True, "output_subdir": "mc_validation/mv9_synthesis"},
                },
            }
        ),
        encoding="utf-8",
    )
    mv1 = tmp_path / "reports" / "mc_validation" / "mv1_pid"
    mv1.mkdir(parents=True)
    (mv1 / "study_result.json").write_text(json.dumps({"status": "PRODUCTION", "metrics": {"hgb_auc": 0.99}}), encoding="utf-8")

    args = argparse.Namespace(config=str(cfg), repo_root=str(tmp_path), fixture=False)
    assert cmd_synthesize(args) == 0

    report = tmp_path / "reports" / "mc_validation" / "mv9_synthesis" / "MV9_SYNTHESIS.md"
    text = report.read_text(encoding="utf-8")
    assert "| MV1 | PRODUCTION | hgb_auc=0.99 |" in text
    assert "MV4 | BLOCKED" in text
