from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pandas as pd
import pytest


SCRIPT = (
    Path(__file__).parents[1]
    / "scripts"
    / "single_stave"
    / "deltaE_E_data_bridge_strict.py"
)
SPEC = importlib.util.spec_from_file_location("deltae_strict", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

FAKE_COMMIT = "1" * 40
CSV_READER_CONTRACT = (
    Path(__file__).parents[1]
    / "docs"
    / "contracts"
    / "deltae_event_csv_reader.json"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_event_csv(path: Path) -> pd.DataFrame:
    contract = json.loads(CSV_READER_CONTRACT.read_text(encoding="utf-8"))
    return pd.read_csv(path, dtype=contract["pandas_read_csv_dtype"])


def _write_input(path: Path) -> None:
    pd.DataFrame(
        {
            "run": [1, 1, 1, 2],
            "evt": [10, 10, 11, 10],
            "eventno": [100, 101, 102, 100],
            "stave": ["B2", "B4", "B8", "B2"],
            "median_amp_adc": [250.0, 300.0, 500.0, 400.0],
        }
    ).to_csv(path, index=False)


def _write_bridge(path: Path, *, duplicate: bool = False, nonfinite: bool = False) -> None:
    duplicate_literal = "True" if duplicate else "False"
    nonfinite_literal = "True" if nonfinite else "False"
    path.write_text(
        f"""from __future__ import annotations
import pandas as pd


def build_event_table(
    pulses,
    *,
    source_file_id,
    threshold_adc,
    amplitude_column,
    amplitude_convention,
    amplitude_polarity,
):
    wide = pd.DataFrame({{
        'source_file_id': [source_file_id, source_file_id],
        'run': [1, 2],
        'evt': [10, 10],
        'amp_B2': [250.0, 400.0],
        'amp_B4': [300.0, 0.0],
        'amp_B6': [0.0, 0.0],
        'amp_B8': [0.0, 0.0],
        'deltaE_data_adc': [250.0, 400.0],
        'E_data_adc': [300.0, 0.0],
        'stopping_layer': ['B4', 'B2'],
        'category': ['ok', 'ok'],
    }})
    if {duplicate_literal}:
        wide.loc[1, ['run', 'evt']] = [1, 10]
    if {nonfinite_literal}:
        wide.loc[1, 'amp_B2'] = float('nan')
    result = {{
        'n_events_composite_key': 2,
        'stopping_distribution_total': 2,
        'stopping_distribution': {{'B4': 1, 'B2': 1}},
        'amplitude_column': amplitude_column,
        'amplitude_convention': amplitude_convention,
        'amplitude_polarity': amplitude_polarity,
    }}
    return wide, result
""",
        encoding="utf-8",
    )


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "git_provenance",
        lambda root: {
            "repository_root": str(Path(root).resolve()),
            "commit": FAKE_COMMIT,
            "tracked_worktree_clean": True,
            "status_policy": "TEST_FIXTURE",
        },
    )


def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    bridge_duplicate: bool = False,
    bridge_nonfinite: bool = False,
    overwrite: bool = False,
):
    _configure(monkeypatch)
    input_path = tmp_path / "pulse_table.csv"
    bridge_path = tmp_path / "deltaE_E_data_bridge.py"
    output_dir = tmp_path / "out"
    _write_input(input_path)
    _write_bridge(
        bridge_path,
        duplicate=bridge_duplicate,
        nonfinite=bridge_nonfinite,
    )
    payload = MODULE.run_strict_bridge(
        input_path=input_path,
        output_dir=output_dir,
        expected_input_sha256=_sha(input_path),
        expected_repo_commit=FAKE_COMMIT,
        amplitude_column="median_amp_adc",
        amplitude_convention="net",
        amplitude_polarity=None,
        threshold_adc=200.0,
        source_file_id="fixture",
        overwrite=overwrite,
        command="python strict.py --fixture",
        bridge_path=bridge_path,
        repository_root=tmp_path,
    )
    return input_path, bridge_path, output_dir, payload


def test_valid_bundle_is_content_addressed_and_reconstructable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path, bridge_path, output_dir, payload = _run(tmp_path, monkeypatch)

    result = json.loads((output_dir / MODULE.OUTPUT_JSON).read_text(encoding="utf-8"))
    events = _read_event_csv(output_dir / MODULE.OUTPUT_CSV)
    svg = (output_dir / MODULE.OUTPUT_SVG).read_text(encoding="utf-8")

    assert result["status"] == "VALIDATED_SOFTWARE_RERUN_OUTPUT"
    assert result["scientific_acceptance"].startswith("BLOCKED_")
    assert result["provenance"]["input"]["sha256"] == _sha(input_path)
    assert result["provenance"]["bridge_script"]["sha256"] == _sha(bridge_path)
    assert result["provenance"]["git"]["commit"] == FAKE_COMMIT
    assert result["output_validation"]["event_rows"] == 2
    assert result["output_validation"]["unique_composite_keys"] == 2
    assert payload["published_bundle"][MODULE.OUTPUT_JSON]["sha256"] == _sha(
        output_dir / MODULE.OUTPUT_JSON
    )
    assert set(events["provenance_input_sha256"]) == {_sha(input_path)}
    assert set(events["provenance_repository_commit"]) == {FAKE_COMMIT}
    assert set(events["provenance_generation_command"]) == {
        "python strict.py --fixture"
    }
    assert MODULE.POLICY in svg
    assert _sha(input_path) in svg
    assert FAKE_COMMIT in svg


def test_input_hash_mismatch_fails_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    input_path = tmp_path / "pulse_table.csv"
    bridge_path = tmp_path / "deltaE_E_data_bridge.py"
    _write_input(input_path)
    _write_bridge(bridge_path)

    with pytest.raises(MODULE.StrictBridgeError, match="input SHA-256 mismatch"):
        MODULE.run_strict_bridge(
            input_path=input_path,
            output_dir=tmp_path / "out",
            expected_input_sha256="0" * 64,
            expected_repo_commit=FAKE_COMMIT,
            amplitude_column="median_amp_adc",
            amplitude_convention="net",
            amplitude_polarity=None,
            threshold_adc=200.0,
            source_file_id="fixture",
            overwrite=False,
            command="fixture",
            bridge_path=bridge_path,
            repository_root=tmp_path,
        )
    assert not (tmp_path / "out").exists()


def test_repository_commit_mismatch_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    input_path = tmp_path / "pulse_table.csv"
    bridge_path = tmp_path / "deltaE_E_data_bridge.py"
    _write_input(input_path)
    _write_bridge(bridge_path)

    with pytest.raises(MODULE.StrictBridgeError, match="repository commit mismatch"):
        MODULE.run_strict_bridge(
            input_path=input_path,
            output_dir=tmp_path / "out",
            expected_input_sha256=_sha(input_path),
            expected_repo_commit="2" * 40,
            amplitude_column="median_amp_adc",
            amplitude_convention="net",
            amplitude_polarity=None,
            threshold_adc=200.0,
            source_file_id="fixture",
            overwrite=False,
            command="fixture",
            bridge_path=bridge_path,
            repository_root=tmp_path,
        )


def test_input_output_alias_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    input_path = output_dir / MODULE.OUTPUT_CSV
    bridge_path = tmp_path / "deltaE_E_data_bridge.py"
    _write_input(input_path)
    _write_bridge(bridge_path)

    with pytest.raises(MODULE.StrictBridgeError, match="protected input/code path"):
        MODULE.run_strict_bridge(
            input_path=input_path,
            output_dir=output_dir,
            expected_input_sha256=_sha(input_path),
            expected_repo_commit=FAKE_COMMIT,
            amplitude_column="median_amp_adc",
            amplitude_convention="net",
            amplitude_polarity=None,
            threshold_adc=200.0,
            source_file_id="fixture",
            overwrite=True,
            command="fixture",
            bridge_path=bridge_path,
            repository_root=tmp_path,
        )
    assert input_path.read_text(encoding="utf-8").startswith("run,evt,eventno")


def test_existing_outputs_require_explicit_overwrite_and_are_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path, _, output_dir, _ = _run(tmp_path, monkeypatch)
    old_json = (output_dir / MODULE.OUTPUT_JSON).read_bytes()
    old_csv = (output_dir / MODULE.OUTPUT_CSV).read_bytes()
    old_svg = (output_dir / MODULE.OUTPUT_SVG).read_bytes()

    bridge_path = tmp_path / "deltaE_E_data_bridge.py"
    with pytest.raises(MODULE.StrictBridgeError, match="--overwrite"):
        MODULE.run_strict_bridge(
            input_path=input_path,
            output_dir=output_dir,
            expected_input_sha256=_sha(input_path),
            expected_repo_commit=FAKE_COMMIT,
            amplitude_column="median_amp_adc",
            amplitude_convention="net",
            amplitude_polarity=None,
            threshold_adc=200.0,
            source_file_id="fixture",
            overwrite=False,
            command="fixture",
            bridge_path=bridge_path,
            repository_root=tmp_path,
        )
    assert (output_dir / MODULE.OUTPUT_JSON).read_bytes() == old_json
    assert (output_dir / MODULE.OUTPUT_CSV).read_bytes() == old_csv
    assert (output_dir / MODULE.OUTPUT_SVG).read_bytes() == old_svg


def test_transactional_publish_failure_restores_previous_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path, bridge_path, output_dir, _ = _run(tmp_path, monkeypatch)
    old_files = {
        name: (output_dir / name).read_bytes()
        for name in (MODULE.OUTPUT_JSON, MODULE.OUTPUT_CSV, MODULE.OUTPUT_SVG)
    }
    real_replace = os.replace

    def fail_staging_publish(source: str | Path, destination: str | Path) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        if source_path.name.endswith(".tmp") and destination_path == output_dir:
            raise OSError("injected bundle publication failure")
        real_replace(source, destination)

    monkeypatch.setattr(MODULE.os, "replace", fail_staging_publish)
    with pytest.raises(OSError, match="injected bundle publication failure"):
        MODULE.run_strict_bridge(
            input_path=input_path,
            output_dir=output_dir,
            expected_input_sha256=_sha(input_path),
            expected_repo_commit=FAKE_COMMIT,
            amplitude_column="median_amp_adc",
            amplitude_convention="net",
            amplitude_polarity=None,
            threshold_adc=200.0,
            source_file_id="fixture",
            overwrite=True,
            command="fixture",
            bridge_path=bridge_path,
            repository_root=tmp_path,
        )
    for name, expected in old_files.items():
        assert (output_dir / name).read_bytes() == expected
    assert not list(tmp_path.glob(".out.*.tmp"))
    assert not list(tmp_path.glob(".out.backup.*"))


def test_input_replacement_during_bridge_run_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch)
    input_path = tmp_path / "pulse_table.csv"
    bridge_path = tmp_path / "deltaE_E_data_bridge.py"
    _write_input(input_path)
    _write_bridge(bridge_path)
    original_loader = MODULE._load_module

    def modifying_loader(path: Path, name: str):
        loaded = original_loader(path, name)
        original_build = loaded.build_event_table

        def build_and_modify(*args, **kwargs):
            result = original_build(*args, **kwargs)
            input_path.write_bytes(input_path.read_bytes() + b"\n")
            return result

        loaded.build_event_table = build_and_modify
        return loaded

    monkeypatch.setattr(MODULE, "_load_module", modifying_loader)
    with pytest.raises(MODULE.StrictBridgeError, match="input path changed"):
        MODULE.run_strict_bridge(
            input_path=input_path,
            output_dir=tmp_path / "out",
            expected_input_sha256=_sha(input_path),
            expected_repo_commit=FAKE_COMMIT,
            amplitude_column="median_amp_adc",
            amplitude_convention="net",
            amplitude_polarity=None,
            threshold_adc=200.0,
            source_file_id="fixture",
            overwrite=False,
            command="fixture",
            bridge_path=bridge_path,
            repository_root=tmp_path,
        )
    assert not (tmp_path / "out" / MODULE.OUTPUT_JSON).exists()


@pytest.mark.parametrize(
    ("duplicate", "nonfinite", "message"),
    [
        (True, False, "duplicate physical composite keys"),
        (False, True, "nonfinite or nonnumeric ADC values"),
    ],
)
def test_invalid_bridge_output_fails_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    duplicate: bool,
    nonfinite: bool,
    message: str,
) -> None:
    with pytest.raises(MODULE.StrictBridgeError, match=message):
        _run(
            tmp_path,
            monkeypatch,
            bridge_duplicate=duplicate,
            bridge_nonfinite=nonfinite,
        )
    assert not (tmp_path / "out" / MODULE.OUTPUT_JSON).exists()
