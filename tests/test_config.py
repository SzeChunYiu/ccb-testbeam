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


def _seed_config(tmp_path: Path, global_seed: int) -> Path:
    p = tmp_path / f"cfg_{global_seed}.yaml"
    p.write_text(
        f'''
schema_version: "1.0.0"
paths:
  repo_root: "."
  mc_root: "geant4/data/output_krakow_1M.root"
  data_pulses: "data/tables/s00_selected_b_pulses.csv.gz"
  reports_dir: "reports"
  resolved_config_dir: "reports/mc_validation/resolved_configs"
seeds:
  global: {global_seed}
units:
  energy: MeV
  time: ns
  adc: ADC
''',
        encoding="utf-8",
    )
    return p


def test_resolved_digest_covers_seeds(tmp_path: Path) -> None:
    """PROV-002: the resolved digest must change with scientific settings (seeds),
    not just the raw config file identity."""
    import yaml
    from ccb_mc_validation.config import write_resolved_config

    out_a = tmp_path / "a"; out_a.mkdir()
    out_b = tmp_path / "b"; out_b.mkdir()
    cfg_a = load_config(_seed_config(tmp_path, 111), repo_root=REPO_ROOT)
    cfg_b = load_config(_seed_config(tmp_path, 222), repo_root=REPO_ROOT)
    pa = write_resolved_config(cfg_a, destination=out_a / "resolved.yaml")
    pb = write_resolved_config(cfg_b, destination=out_b / "resolved.yaml")
    da = yaml.safe_load(pa.read_text(encoding="utf-8"))["resolved_digest"]
    db = yaml.safe_load(pb.read_text(encoding="utf-8"))["resolved_digest"]
    assert da != db, "resolved_digest must be sensitive to seeds (PROV-002)"
