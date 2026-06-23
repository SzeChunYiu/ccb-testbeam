from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ccb_mc_validation.config import load_config, sha256_bytes, write_resolved_config
from ccb_mc_validation.exceptions import (
    EXIT_CODES,
    ConfigurationError,
    StudyBlockedError,
    UnitValidationError,
    exit_code_for,
)
from ccb_mc_validation.units import convert_energy, validate_unit


def test_validate_unit_energy() -> None:
    assert validate_unit("MeV") == "MeV"
    with pytest.raises(UnitValidationError):
        validate_unit("furlongs", kind="energy")


def test_convert_energy_mev_kev() -> None:
    assert convert_energy(1.0, "MeV", "keV") == pytest.approx(1000.0)


def test_convert_energy_adc_requires_scale() -> None:
    with pytest.raises(UnitValidationError):
        convert_energy(100.0, "ADC", "MeV")
    assert convert_energy(100.0, "ADC", "MeV", adc_per_mev=10.0) == pytest.approx(10.0)


def test_exit_codes_cover_hierarchy() -> None:
    assert EXIT_CODES["success"] == 0
    assert exit_code_for(StudyBlockedError("blocked")) == 10
    assert exit_code_for(ConfigurationError("bad")) == 2


def test_load_config_rejects_unknown_keys(tmp_path: Path) -> None:
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("schema_version: '1.0.0'\nunexpected: true\n", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(cfg)


def test_load_config_and_write_resolved(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg_path = repo / "base.yaml"
    cfg_path.write_text(
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
            }
        ),
        encoding="utf-8",
    )
    resolved = load_config(cfg_path, repo_root=repo)
    assert resolved.schema_version == "1.0.0"
    assert resolved.mc_root == (repo / "mc.root").resolve()
    out = write_resolved_config(resolved)
    assert out.is_file()
    assert sha256_bytes(out.read_bytes())  # non-empty write
