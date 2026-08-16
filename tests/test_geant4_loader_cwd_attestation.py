from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "audit"
    / "geant4_loader_cwd_attestation.py"
)
SPEC = importlib.util.spec_from_file_location("geant4_loader_cwd_attestation", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _runtime_receipt(*, pid: int, starttime: int, exe_link: str) -> dict:
    return MODULE._with_digest(
        {
            "schema": MODULE.RUNTIME_RECEIPT_SCHEMA,
            "status": "PASS",
            "parent_final_build_receipt_sha256": "f" * 64,
            "process": {
                "pid": pid,
                "starttime_ticks": starttime,
                "exe_link": exe_link,
                "executable": {"bytes": 1, "sha256": "0" * 64},
            },
            "loader_environment": {"LD_LIBRARY_PATH": {"present": False}},
            "mapped_executable_objects": [],
            "required_object_matches": {},
            "maps_sha256": "1" * 64,
            "executable_mapping_projection_stable": True,
            "scientific_scope": "fixture",
            "limitations": [],
        }
    )


def _argv_receipt(runtime: dict) -> dict:
    process = runtime["process"]
    return MODULE._with_digest(
        {
            "schema": MODULE.ARGV_RECEIPT_SCHEMA,
            "status": "PASS",
            "parent_runtime_dependency_receipt_sha256": runtime["receipt_sha256"],
            "process": {
                "pid": process["pid"],
                "starttime_ticks": process["starttime_ticks"],
                "exe_link": process["exe_link"],
            },
            "cmdline_region": {"bytes": 1, "sha256": "2" * 64},
            "scientific_scope": "fixture",
            "limitations": [],
        }
    )


def _stat_payload(pid: int, starttime: int) -> bytes:
    tail = ["S", *("0" for _ in range(18)), str(starttime), *("0" for _ in range(8))]
    return f"{pid} (fixture process) {' '.join(tail)}\n".encode("ascii")


def _fake_proc(
    tmp_path: Path,
    *,
    pid: int = 4321,
    starttime: int = 987654,
    exe_link: str = "/opt/hibeam_g4",
) -> tuple[Path, Path]:
    proc_root = tmp_path / "proc"
    proc_dir = proc_root / str(pid)
    proc_dir.mkdir(parents=True)
    cwd = tmp_path / "work"
    cwd.mkdir()
    (proc_dir / "stat").write_bytes(_stat_payload(pid, starttime))
    (proc_dir / "exe").symlink_to(exe_link)
    (proc_dir / "cwd").symlink_to(cwd, target_is_directory=True)
    return proc_root, cwd


def test_nominal_current_cwd_records_link_and_directory_identity(tmp_path: Path) -> None:
    proc_root, cwd = _fake_proc(tmp_path)
    runtime = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    argv = _argv_receipt(runtime)
    result = MODULE.attest_loader_cwd(
        runtime_receipt=runtime,
        argv_receipt=argv,
        proc_root=proc_root,
    )

    assert result["status"] == "PASS"
    assert result["cwd_observation"]["link_text"] == os.fspath(cwd)
    identity = result["cwd_observation"]["opened_directory_identity"]
    actual = cwd.stat()
    assert identity["st_dev"] == actual.st_dev
    assert identity["st_ino"] == actual.st_ino
    body = dict(result)
    digest = body.pop("receipt_sha256")
    assert MODULE._digest_body(body) == digest


def test_rejects_tampered_runtime_receipt(tmp_path: Path) -> None:
    proc_root, _ = _fake_proc(tmp_path)
    runtime = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    argv = _argv_receipt(runtime)
    runtime["process"]["pid"] = 7
    with pytest.raises(ValueError, match="digest mismatch"):
        MODULE.attest_loader_cwd(
            runtime_receipt=runtime,
            argv_receipt=argv,
            proc_root=proc_root,
        )


def test_rejects_argv_receipt_from_other_runtime(tmp_path: Path) -> None:
    proc_root, _ = _fake_proc(tmp_path)
    runtime = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    other = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    other["maps_sha256"] = "3" * 64
    other = MODULE._with_digest({k: v for k, v in other.items() if k != "receipt_sha256"})
    argv = _argv_receipt(other)
    with pytest.raises(ValueError, match="another runtime"):
        MODULE.attest_loader_cwd(
            runtime_receipt=runtime,
            argv_receipt=argv,
            proc_root=proc_root,
        )


def test_rejects_process_identity_mismatch(tmp_path: Path) -> None:
    proc_root, _ = _fake_proc(tmp_path, starttime=111)
    runtime = _runtime_receipt(pid=4321, starttime=222, exe_link="/opt/hibeam_g4")
    argv = _argv_receipt(runtime)
    with pytest.raises(ValueError, match="identity differs"):
        MODULE.attest_loader_cwd(
            runtime_receipt=runtime,
            argv_receipt=argv,
            proc_root=proc_root,
        )


def test_rejects_executable_link_mismatch(tmp_path: Path) -> None:
    proc_root, _ = _fake_proc(tmp_path, exe_link="/lib64/ld-linux-x86-64.so.2")
    runtime = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    argv = _argv_receipt(runtime)
    with pytest.raises(ValueError, match="executable link differs"):
        MODULE.attest_loader_cwd(
            runtime_receipt=runtime,
            argv_receipt=argv,
            proc_root=proc_root,
        )


def test_rejects_cwd_link_mutation_between_reads(tmp_path: Path, monkeypatch) -> None:
    proc_root, _ = _fake_proc(tmp_path)
    runtime = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    argv = _argv_receipt(runtime)
    original = MODULE._read_link
    calls = 0

    def changing(proc_dir: Path, name: str, *, label: str) -> str:
        nonlocal calls
        if name == "cwd":
            calls += 1
            if calls == 2:
                return "/tmp/changed"
        return original(proc_dir, name, label=label)

    monkeypatch.setattr(MODULE, "_read_link", changing)
    with pytest.raises(ValueError, match="cwd link changed"):
        MODULE.attest_loader_cwd(
            runtime_receipt=runtime,
            argv_receipt=argv,
            proc_root=proc_root,
        )


def test_rejects_cwd_object_mutation_between_opens(tmp_path: Path, monkeypatch) -> None:
    proc_root, _ = _fake_proc(tmp_path)
    runtime = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    argv = _argv_receipt(runtime)
    original = MODULE._opened_cwd_identity
    calls = 0

    def changing(proc_dir: Path) -> dict[str, int]:
        nonlocal calls
        calls += 1
        value = original(proc_dir)
        if calls == 2:
            value = dict(value)
            value["st_ino"] += 1
        return value

    monkeypatch.setattr(MODULE, "_opened_cwd_identity", changing)
    with pytest.raises(ValueError, match="directory object changed"):
        MODULE.attest_loader_cwd(
            runtime_receipt=runtime,
            argv_receipt=argv,
            proc_root=proc_root,
        )


def _wait_for_child_marker(
    process: subprocess.Popen, marker: Path, timeout_s: float = 10.0
) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"child exited early: {process.returncode}")
        if marker.exists():
            return
        time.sleep(0.01)
    raise AssertionError("timed out waiting for child post-chdir readiness marker")


@pytest.mark.skipif(not Path("/proc").is_dir(), reason="Linux procfs required")
def test_post_exec_chdir_falsifies_initial_cwd_interpretation(tmp_path: Path) -> None:
    initial = tmp_path / "initial"
    later = tmp_path / "later"
    initial.mkdir()
    later.mkdir()
    marker = tmp_path / "post_chdir.ready"
    code = (
        "import os,time; "
        "os.chdir(os.environ['TARGET_CWD']); "
        "open(os.environ['READY_FILE'], 'wb').close(); "
        "time.sleep(5)"
    )
    env = dict(os.environ)
    env["TARGET_CWD"] = os.fspath(later)
    env["READY_FILE"] = os.fspath(marker)
    process = subprocess.Popen([sys.executable, "-c", code], cwd=initial, env=env)
    try:
        _wait_for_child_marker(process, marker)
        proc_dir = Path("/proc") / str(process.pid)
        starttime = MODULE._read_process_starttime(proc_dir)
        exe = os.readlink(proc_dir / "exe")
        runtime = _runtime_receipt(pid=process.pid, starttime=starttime, exe_link=exe)
        argv = _argv_receipt(runtime)
        result = MODULE.attest_loader_cwd(runtime_receipt=runtime, argv_receipt=argv)
        assert Path(result["cwd_observation"]["link_text"]).resolve() == later.resolve()
        assert Path(result["cwd_observation"]["link_text"]).resolve() != initial.resolve()
        assert result["interpretation"]["historical_execve_cwd"].startswith("NOT_PROVEN")
    finally:
        process.terminate()
        process.wait(timeout=2)


def test_cli_blocks_on_wrong_argv_parent(tmp_path: Path) -> None:
    proc_root, _ = _fake_proc(tmp_path)
    runtime = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    argv = _argv_receipt(runtime)
    argv["parent_runtime_dependency_receipt_sha256"] = "0" * 64
    argv = MODULE._with_digest({k: v for k, v in argv.items() if k != "receipt_sha256"})
    runtime_path = tmp_path / "runtime.json"
    argv_path = tmp_path / "argv.json"
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
    argv_path.write_text(json.dumps(argv), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            os.fspath(SCRIPT),
            "--runtime-receipt-json",
            os.fspath(runtime_path),
            "--argv-receipt-json",
            os.fspath(argv_path),
            "--proc-root",
            os.fspath(proc_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert json.loads(completed.stdout)["status"] == "BLOCKED"
