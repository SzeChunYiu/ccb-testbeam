from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "single_stave" / "compare_stopping_power.py"
REFERENCE = (
    REPO_ROOT
    / "data"
    / "reference"
    / "stopping_power"
    / "pstar_polystyrene.csv"
)


def load_module():
    spec = importlib.util.spec_from_file_location("compare_stopping_power", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_default_reference_resolves_inside_repository():
    module = load_module()

    assert module.REPO_ROOT == REPO_ROOT
    assert module.DEFAULT_REF == REFERENCE
    assert module.DEFAULT_REF.is_file()

    legacy_wrong_path = module.HERE.parents[2] / REFERENCE.relative_to(REPO_ROOT)
    assert legacy_wrong_path != module.DEFAULT_REF


def test_self_test_fails_closed_when_reference_is_missing(tmp_path, capsys):
    module = load_module()
    missing = tmp_path / "missing.csv"

    assert module.self_test(missing) == 1
    captured = capsys.readouterr()
    assert "SELF-TEST: FAIL" in captured.err
    assert str(missing) in captured.err


def test_cli_self_test_uses_committed_reference_from_any_working_directory(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"reference={REFERENCE.resolve()}" in proc.stdout
    assert f"sha256={sha256_file(REFERENCE)}" in proc.stdout
    assert "SELF-TEST SCOPE: arithmetic and committed-reference path only" in proc.stdout
    assert "SCIENTIFIC STATUS: DIAGNOSTIC_ONLY" in proc.stdout
    assert "SELF-TEST: PASS" in proc.stdout
    assert "inline test reference" not in proc.stdout
