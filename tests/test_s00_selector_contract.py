"""Deterministic tests for the no-I/O S00 selector config contract (#1141)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from ccb_mc_validation.s00_selector_contract import (
    S00SelectorConfigError,
    s00_selector_model_identity,
    validate_s00_selector_contract,
)
from ccb_mc_validation.selector import (
    S00_SELECTOR_V1_BASELINE_INDICES,
    S00_SELECTOR_V1_ID,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
S00_SCRIPT = REPO_ROOT / "scripts" / "01_build_pulse_table_from_root.py"


def _load_s00_module():
    spec = importlib.util.spec_from_file_location("s00_selector_preflight", S00_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_canonical_selector_contract_is_accepted() -> None:
    assert validate_s00_selector_contract({"baseline_samples": [0, 1, 2, 3]}) == (
        0,
        1,
        2,
        3,
    )


def test_numpy_integral_aliases_are_accepted_as_discrete_indices() -> None:
    config = {
        "baseline_samples": [np.int64(0), np.int32(1), np.int16(2), np.int8(3)]
    }
    assert validate_s00_selector_contract(config) == S00_SELECTOR_V1_BASELINE_INDICES


@pytest.mark.parametrize(
    "bad",
    [
        [2, 3, 4, 5],
        [3, 2, 1, 0],
        [0, 1, 2],
        [0, 1, 2, 3, 4],
        [0, 1, 1, 3],
        [-1, 1, 2, 3],
        ["0", 1, 2, 3],
        [0.0, 1.0, 2.0, 3.0],
        [False, True, 2, 3],
        (0, 1, 2, 3),
        {0, 1, 2, 3},
        {0: "a", 1: "b", 2: "c", 3: "d"},
        123,
        None,
    ],
)
def test_hostile_baseline_mutations_fail_closed(bad: object) -> None:
    with pytest.raises(S00SelectorConfigError):
        validate_s00_selector_contract({"baseline_samples": bad})


def test_missing_baseline_samples_fails_closed() -> None:
    with pytest.raises(S00SelectorConfigError):
        validate_s00_selector_contract({})


def test_non_mapping_config_fails_closed() -> None:
    with pytest.raises(S00SelectorConfigError):
        validate_s00_selector_contract([0, 1, 2, 3])  # type: ignore[arg-type]


def test_manifest_identity_fragment_is_exact_and_self_describing() -> None:
    identity = s00_selector_model_identity()
    assert identity == {
        "selector_id": S00_SELECTOR_V1_ID,
        "baseline_indices": [0, 1, 2, 3],
    }


def test_identity_fragment_returns_fresh_mutable_container() -> None:
    first = s00_selector_model_identity()
    first["baseline_indices"].append(99)  # type: ignore[union-attr]
    second = s00_selector_model_identity()
    assert second["baseline_indices"] == [0, 1, 2, 3]


def test_main_rejects_bad_selector_before_any_producer_side_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The hostile config must fail before namespace, staging, ROOT, or artifacts."""
    s00 = _load_s00_module()
    bad_config = {"baseline_samples": [2, 3, 4, 5]}
    calls: dict[str, int] = {
        "resolve_amplitude_cut": 0,
        "resolve_output_namespace": 0,
        "scan_raw": 0,
        "iter_raw_events": 0,
        "uproot_open": 0,
        "mkdir": 0,
        "write_manifest": 0,
        "make_figures": 0,
    }

    def forbidden(name: str):
        def _forbidden(*args, **kwargs):
            calls[name] += 1
            raise AssertionError(
                f"producer side effect reached before selector preflight: {name}"
            )

        return _forbidden

    original_mkdir = Path.mkdir

    def counted_mkdir(self, *args, **kwargs):
        calls["mkdir"] += 1
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(s00, "load_config", lambda _path: bad_config)
    monkeypatch.setattr(
        s00,
        "resolve_amplitude_cut",
        forbidden("resolve_amplitude_cut"),
    )
    monkeypatch.setattr(
        s00,
        "resolve_output_namespace",
        forbidden("resolve_output_namespace"),
    )
    monkeypatch.setattr(s00, "scan_raw", forbidden("scan_raw"))
    monkeypatch.setattr(s00, "iter_raw_events", forbidden("iter_raw_events"))
    monkeypatch.setattr(s00.uproot, "open", forbidden("uproot_open"))
    monkeypatch.setattr(s00, "write_manifest", forbidden("write_manifest"))
    monkeypatch.setattr(s00, "make_figures", forbidden("make_figures"))
    monkeypatch.setattr(Path, "mkdir", counted_mkdir)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(S00_SCRIPT), "--config", "ignored.yaml"],
    )

    assert s00.main() == 2
    assert calls == {name: 0 for name in calls}


def test_main_canonical_selector_reaches_next_execution_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The checked-in selector semantics pass preflight without needing ROOT."""
    s00 = _load_s00_module()
    canonical_config = {
        "baseline_samples": [0, 1, 2, 3],
        "amplitude_cut_adc": 1000.0,
    }

    class ReachedAmplitudeResolution(RuntimeError):
        pass

    def reached_boundary(*args, **kwargs):
        raise ReachedAmplitudeResolution

    monkeypatch.setattr(s00, "load_config", lambda _path: canonical_config)
    monkeypatch.setattr(s00, "resolve_amplitude_cut", reached_boundary)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(S00_SCRIPT), "--config", "ignored.yaml"],
    )

    with pytest.raises(ReachedAmplitudeResolution):
        s00.main()


def test_main_source_binds_selector_identity_into_manifest() -> None:
    """The producer must merge the exact selector fragment into model_identity."""
    source = S00_SCRIPT.read_text(encoding="utf-8")
    assert "selector_identity = s00_selector_model_identity()" in source
    selector_line = (
        "\"selector\": f\"ccb_mc_validation.selector "
        "{selector_identity['selector_id']}\""
    )
    assert selector_line in source
    assert "**selector_identity" in source
