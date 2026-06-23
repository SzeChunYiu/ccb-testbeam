"""Configuration loading tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ccb_mc_validation.config import load_config
from ccb_mc_validation.exceptions import ConfigurationError

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = REPO_ROOT / "configs/mc_validation/base.yaml"


def test_load_base_yaml() -> None:
    config = load_config(BASE_CONFIG, repo_root=REPO_ROOT)
    assert config.schema_version == "1.0.0"
    assert config.coincidence_ns == 15.0
    assert config.seeds["global"] == 424242
    assert config.mc_root.name == "output_krakow_1M.root"


def test_reject_unknown_keys(tmp_path: Path) -> None:
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        """
schema_version: "1.0.0"
paths:
  repo_root: "."
  mc_root: "geant4/data/output_krakow_1M.root"
  data_pulses: "data/tables/s00_selected_b_pulses.csv.gz"
  reports_dir: "reports"
  resolved_config_dir: "reports/mc_validation/resolved_configs"
unexpected_key: true
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="unknown top-level"):
        load_config(bad_config, repo_root=REPO_ROOT)
