"""YAML configuration loading with strict schema enforcement."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ccb_mc_validation.constants import (
    ADC_SAMPLES,
    B_ARM,
    A_ARM,
    COINC_NS_DEFAULT,
    NB_LAYERS,
    SAMPLE_SPACING_NS,
)
from ccb_mc_validation.exceptions import ConfigurationError, InputNotFoundError

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")

_ALLOWED_KEYS: dict[str, set[str] | dict[str, set[str]]] = {
    "schema_version": set(),
    "paths": {
        "repo_root",
        "mc_root",
        "data_pulses",
        "reports_dir",
        "resolved_config_dir",
        "artifact_root",
        "cache_root",
    },
    "profile": set(),
    "mc_tree": set(),
    "cluster": {
        "host",
        "ssh_host",
        "python",
        "project_root",
        "account",
        "partition",
    },
    "execution": {
        "overwrite",
        "resume",
        "fail_fast",
        "max_infrastructure_retries",
        "smoke_max_events",
        "smoke_max_tracks",
    },
    "seeds": {"global", "split", "bootstrap"},
    "units": {"energy", "time", "adc", "documented"},
    "waveform": {"adc_samples", "sample_spacing_ns"},
    "coincidence_ns": set(),
    "detector": {"b_arm", "a_arm", "nb_layers"},
    "logging": {"level"},
    "studies": {
        "mv0",
        "mv1",
        "mv2",
        "mv3",
        "mv4",
        "mv5",
        "mv6",
        "mv7",
        "mv8",
        "mv9",
    },
}

_STUDY_SUBKEYS = {"enabled", "output_subdir", "description", "tier"}


@dataclass(frozen=True)
class ResolvedConfig:
    """Fully resolved configuration with absolute paths and content hash."""

    schema_version: str
    repo_root: Path
    mc_root: Path
    data_pulses: Path
    reports_dir: Path
    resolved_config_dir: Path
    seeds: dict[str, int]
    units: dict[str, str]
    unit_docs: dict[str, str]
    waveform: dict[str, float | int]
    coincidence_ns: float
    detector: dict[str, int]
    logging_level: str
    studies: dict[str, dict[str, Any]]
    source_path: Path
    content_sha256: str
    raw: dict[str, Any] = field(repr=False)

    def study_output_dir(self, study_id: str) -> Path:
        study_key = study_id.lower().replace("-", "")
        study = self.studies.get(study_key, {})
        subdir = study.get("output_subdir", f"mc_validation/{study_key}")
        return self.reports_dir / subdir


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):

        def repl(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group(2)
            if name in os.environ:
                return os.environ[name]
            if default is not None:
                return default
            raise ConfigurationError(f"environment variable ${{{name}}} is not set")

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


def _reject_unknown_keys(raw: dict[str, Any]) -> None:
    allowed_top = set(_ALLOWED_KEYS.keys())
    unknown_top = set(raw) - allowed_top
    if unknown_top:
        raise ConfigurationError(f"unknown top-level config keys: {sorted(unknown_top)}")

    for section, spec in _ALLOWED_KEYS.items():
        if section not in raw or not isinstance(raw[section], dict):
            continue
        if not isinstance(spec, set):
            unknown = set(raw[section]) - spec
            if unknown:
                raise ConfigurationError(
                    f"unknown keys in config.{section}: {sorted(unknown)}"
                )

    studies = raw.get("studies", {})
    if isinstance(studies, dict):
        for study_name, study_cfg in studies.items():
            if not isinstance(study_cfg, dict):
                raise ConfigurationError(f"studies.{study_name} must be a mapping")
            unknown = set(study_cfg) - _STUDY_SUBKEYS
            if unknown:
                raise ConfigurationError(
                    f"unknown keys in studies.{study_name}: {sorted(unknown)}"
                )


def _resolve_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    return path


def load_config(path: Path | str, *, repo_root: Path | None = None) -> ResolvedConfig:
    """Load, validate, and resolve an MC validation YAML config."""
    config_path = Path(path).resolve()
    if not config_path.is_file():
        raise InputNotFoundError(f"config file not found: {config_path}")

    raw_text = config_path.read_text(encoding="utf-8")
    content_sha256 = sha256_bytes(raw_text.encode("utf-8"))
    raw_loaded = yaml.safe_load(raw_text)
    if not isinstance(raw_loaded, dict):
        raise ConfigurationError("config root must be a mapping")

    raw = _expand_env(raw_loaded)
    _reject_unknown_keys(raw)

    schema_version = str(raw.get("schema_version", "")).strip()
    if not schema_version:
        raise ConfigurationError("schema_version is required")

    paths = raw.get("paths", {})
    if not isinstance(paths, dict):
        raise ConfigurationError("paths must be a mapping")

    root = repo_root or _resolve_path(Path.cwd(), str(paths.get("repo_root", ".")))

    required_paths = ("mc_root", "data_pulses", "reports_dir", "resolved_config_dir")
    missing = [key for key in required_paths if key not in paths]
    if missing:
        raise ConfigurationError(f"paths missing required keys: {missing}")

    seeds_raw = raw.get("seeds", {})
    if not isinstance(seeds_raw, dict):
        raise ConfigurationError("seeds must be a mapping")
    seeds = {str(k): int(v) for k, v in seeds_raw.items()}

    units_raw = raw.get("units", {})
    if not isinstance(units_raw, dict):
        raise ConfigurationError("units must be a mapping")
    unit_docs = units_raw.get("documented", {})
    if unit_docs is None:
        unit_docs = {}
    if not isinstance(unit_docs, dict):
        raise ConfigurationError("units.documented must be a mapping")
    units = {
        key: str(units_raw[key])
        for key in ("energy", "time", "adc")
        if key in units_raw
    }

    waveform_raw = raw.get("waveform", {})
    if not isinstance(waveform_raw, dict):
        raise ConfigurationError("waveform must be a mapping")
    waveform = {
        "adc_samples": int(waveform_raw.get("adc_samples", ADC_SAMPLES)),
        "sample_spacing_ns": float(waveform_raw.get("sample_spacing_ns", SAMPLE_SPACING_NS)),
    }

    detector_raw = raw.get("detector", {})
    if not isinstance(detector_raw, dict):
        raise ConfigurationError("detector must be a mapping")
    detector = {
        "b_arm": int(detector_raw.get("b_arm", B_ARM)),
        "a_arm": int(detector_raw.get("a_arm", A_ARM)),
        "nb_layers": int(detector_raw.get("nb_layers", NB_LAYERS)),
    }

    logging_cfg = raw.get("logging", {})
    if logging_cfg is None:
        logging_cfg = {}
    if not isinstance(logging_cfg, dict):
        raise ConfigurationError("logging must be a mapping")
    logging_level = str(logging_cfg.get("level", "INFO"))

    studies_raw = raw.get("studies", {})
    if studies_raw is None:
        studies_raw = {}
    if not isinstance(studies_raw, dict):
        raise ConfigurationError("studies must be a mapping")
    studies = {str(k): dict(v) for k, v in studies_raw.items() if isinstance(v, dict)}

    return ResolvedConfig(
        schema_version=schema_version,
        repo_root=root,
        mc_root=_resolve_path(root, str(paths["mc_root"])),
        data_pulses=_resolve_path(root, str(paths["data_pulses"])),
        reports_dir=_resolve_path(root, str(paths["reports_dir"])),
        resolved_config_dir=_resolve_path(root, str(paths["resolved_config_dir"])),
        seeds=seeds,
        units=units,
        unit_docs={str(k): str(v) for k, v in unit_docs.items()},
        waveform=waveform,
        coincidence_ns=float(raw.get("coincidence_ns", COINC_NS_DEFAULT)),
        detector=detector,
        logging_level=logging_level,
        studies=studies,
        source_path=config_path,
        content_sha256=content_sha256,
        raw=raw,
    )


def write_resolved_config(config: ResolvedConfig, destination: Path | None = None) -> Path:
    """Write a resolved, provenance-rich config snapshot to disk."""
    out_dir = destination or config.resolved_config_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"resolved_{config.content_sha256[:12]}.yaml"

    payload = {
        "schema_version": config.schema_version,
        "source_path": str(config.source_path),
        "content_sha256": config.content_sha256,
        "repo_root": str(config.repo_root),
        "paths": {
            "mc_root": str(config.mc_root),
            "data_pulses": str(config.data_pulses),
            "reports_dir": str(config.reports_dir),
            "resolved_config_dir": str(config.resolved_config_dir),
        },
        "seeds": config.seeds,
        "units": config.units,
        "unit_docs": config.unit_docs,
        "waveform": config.waveform,
        "coincidence_ns": config.coincidence_ns,
        "detector": config.detector,
        "logging_level": config.logging_level,
        "studies": config.studies,
    }
    # PROV-002: digest the FULLY resolved config (seeds, units, waveform,
    # detector, coincidence, logging, studies, paths), not just a 4-field subset,
    # so two effective runs sharing a config file cannot collide on the digest.
    payload["resolved_digest"] = sha256_bytes(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    )

    with out_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)
    return out_path
