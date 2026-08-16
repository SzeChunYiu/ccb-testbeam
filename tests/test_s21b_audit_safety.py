"""SEC-001 regression: the S21b audit script must invoke ROOT injection-safely.

Paths flow through the subprocess *environment*; neither the bash command
string nor the generated ROOT/C++ macro may contain user-controlled path data.
"""
from __future__ import annotations
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = REPO_ROOT / (
    "scripts/s21b_1783656688_10969_21015d93_weighted_source_geometry_audit.py"
)


@pytest.fixture(scope="module")
def s21b():
    spec = importlib.util.spec_from_file_location("s21b_audit", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["s21b_audit"] = mod
    spec.loader.exec_module(mod)  # noqa: top-level imports need numpy/pandas/scipy
    return mod


# Adversarial path carrying shell AND C++ injection payloads + spaces.
EVIL = "a b$(whoami)`id`;rm -rf \"$HOME\".root"
INJECTION_TOKENS = ["$(whoami)", "`id`", "rm -rf"]


def test_root_command_is_static_literal(s21b):
    """root_command() argv contains no path data — only static env-var refs."""
    argv = s21b.root_command()
    assert argv[0] == "bash" and argv[1] == "-c"
    script = argv[2]
    # The script reads everything via quoted $CCB_* env vars; no literal paths.
    assert '"$CCB_ROOT_SETUP"' in script
    assert '"$CCB_MACRO"' in script
    for tok in INJECTION_TOKENS:
        assert tok not in script


def test_controlled_env_carries_path_verbatim(s21b):
    """Adversarial path is carried verbatim in the env, not parsed by a shell."""
    env = s21b._controlled_env(CCB_ROOT_FILE=EVIL, CCB_MACRO="/tmp/m.C")
    assert env["CCB_ROOT_FILE"] == EVIL
    # And it never leaks into the command argv.
    assert EVIL not in " ".join(s21b.root_command())


def test_extract_paths_neither_shell_nor_cpp_interpolated(s21b, tmp_path, monkeypatch):
    """extract_root_event_csv must not interpolate the path into shell or C++."""
    captured = {}

    def fake_run(argv, cwd=None, env=None):
        captured["argv"] = list(argv)
        captured["env"] = dict(env or {})
        # The macro file is the canary: it must not contain the evil path.
        macro_text = Path(env["CCB_MACRO"]).read_text()
        captured["macro_text"] = macro_text
        return subprocess.CompletedProcess(
            args=argv, returncode=0,
            stdout="entries=10 exported_events=5\n", stderr="")

    monkeypatch.setattr(s21b, "run", fake_run)

    evil_root = tmp_path / (EVIL + ".root")
    evil_root.write_bytes(b"x")
    out_csv = tmp_path / "out.csv"
    s21b.extract_root_event_csv(evil_root, out_csv, max_events=7)

    # 1) the bash command string carries no path data
    assert " ".join(captured["argv"]) == " ".join(s21b.root_command())
    for tok in INJECTION_TOKENS:
        assert tok not in " ".join(captured["argv"])
        assert tok not in captured["macro_text"]
    # 2) the evil path is passed verbatim via env, not via the command/macro
    assert captured["env"]["CCB_ROOT_FILE"] == str(evil_root)
    assert captured["env"]["CCB_OUT_CSV"] == str(out_csv)
    assert captured["env"]["CCB_MAX_EVENTS"] == "7"
    assert str(evil_root) not in " ".join(captured["argv"])
    assert str(evil_root) not in captured["macro_text"]
    # 3) the macro reads paths from gSystem->Getenv, not from a string literal
    assert 'Getenv("CCB_ROOT_FILE")' in captured["macro_text"]
    assert 'Getenv("CCB_OUT_CSV")' in captured["macro_text"]


def test_geometry_macro_reads_paths_from_env(s21b):
    """The geometry macro source is path-free; it reads gSystem->Getenv."""
    # Build the geometry macro by invoking the function's macro literal through a
    # capture of the generated source (same construction extract uses).
    captured = {}

    def fake_run(argv, cwd=None, env=None):
        captured["macro_text"] = Path(env["CCB_MACRO"]).read_text()
        return subprocess.CompletedProcess(args=argv, returncode=0, stdout="", stderr="")

    original_run = s21b.run
    s21b.run = fake_run
    try:
        json_path = tmp = None
        import tempfile
        td = tempfile.mkdtemp()
        out_dir = Path(td)
        # geometry_audit reads out_dir/"geometry_root_audit.json" after run();
        # pre-seed it so the function completes without ROOT actually executing.
        (out_dir / "geometry_root_audit.json").write_text(
            '{"top_volume":"world","n_volumes":0,"n_top_nodes":0,'
            '"n_overlaps":0,"volumes":[]}')
        s21b.geometry_audit(Path("/nonexistent/geom.root"), out_dir)
    finally:
        s21b.run = original_run

    for tok in INJECTION_TOKENS:
        assert tok not in captured["macro_text"]
    assert 'Getenv("CCB_GEOM_FILE")' in captured["macro_text"]
    assert 'Getenv("CCB_GEOM_JSON")' in captured["macro_text"]
