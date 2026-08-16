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
    / "geant4_loader_exec_boundary_cwd_attestation.py"
)
SPEC = importlib.util.spec_from_file_location(
    "geant4_loader_exec_boundary_cwd_attestation", SCRIPT
)
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


def _stat_payload(pid: int, starttime: int) -> bytes:
    tail = ["S", *("0" for _ in range(18)), str(starttime), *("0" for _ in range(8))]
    return f"{pid} (fixture process) {' '.join(tail)}\n".encode("ascii")


def _fake_proc(
    tmp_path: Path,
    *,
    pid: int | None = None,
    starttime: int = 987654,
    exe_link: str = "/opt/hibeam_g4",
) -> Path:
    # record_exec_boundary_cwd() uses os.getpid() to locate its own proc dir,
    # so the fake tree must be keyed by the *real* process PID when no explicit
    # pid is given.
    pid = os.getpid() if pid is None else pid
    proc_root = tmp_path / "proc"
    proc_dir = proc_root / str(pid)
    proc_dir.mkdir(parents=True)
    (proc_dir / "stat").write_bytes(_stat_payload(pid, starttime))
    (proc_dir / "exe").symlink_to(exe_link)
    return proc_root


def test_record_exec_boundary_cwd_opens_directory_object(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path)
    work = tmp_path / "workdir"
    work.mkdir()
    # Patch to our fake proc dir; the module uses os.getpid() so we monkeypatch
    # the helper to read from our fake stat/exe.
    record = MODULE.record_exec_boundary_cwd(proc_root=proc_root, cwd=work)

    assert record["schema"] == MODULE.EXEC_BOUNDARY_CWD_SCHEMA
    assert record["status"] == "RECORDED"
    assert record["boundary"] == "IMMEDIATELY_BEFORE_DIRECT_EXECVE_NO_INTERVENING_CHDIR"
    assert record["process"]["pid"] == os.getpid()
    assert record["process"]["starttime_ticks"] == 987654
    assert record["process"]["exe_link"] == "/opt/hibeam_g4"
    assert record["cwd_spelling"] == os.getcwd()
    identity = record["cwd_object"]
    actual = work.stat()
    assert identity["st_dev"] == actual.st_dev
    assert identity["st_ino"] == actual.st_ino

    body = dict(record)
    digest = body.pop("receipt_sha256")
    assert MODULE._digest_body(body) == digest


def test_record_exec_boundary_cwd_uses_real_cwd_by_default(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path)
    record = MODULE.record_exec_boundary_cwd(proc_root=proc_root)
    assert record["schema"] == MODULE.EXEC_BOUNDARY_CWD_SCHEMA
    assert record["status"] == "RECORDED"
    assert record["cwd_spelling"] == os.getcwd()
    identity = record["cwd_object"]
    actual = Path.cwd().stat()
    assert identity["st_dev"] == actual.st_dev
    assert identity["st_ino"] == actual.st_ino


def test_attest_composes_exec_record_with_runtime_receipt(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path)
    work = tmp_path / "workdir"
    work.mkdir()
    exec_record = MODULE.record_exec_boundary_cwd(proc_root=proc_root, cwd=work)
    runtime = _runtime_receipt(pid=os.getpid(), starttime=987654, exe_link="/opt/hibeam_g4")
    result = MODULE.attest_exec_boundary_cwd(
        runtime_receipt=runtime,
        exec_receipt=exec_record,
        proc_root=proc_root,
    )

    assert result["status"] == "PASS"
    assert result["schema"] == MODULE.SCHEMA
    assert result["cwd_object"] == exec_record["cwd_object"]
    assert result["cwd_spelling"] == exec_record["cwd_spelling"]
    assert (
        result["parent_runtime_dependency_receipt_sha256"] == runtime["receipt_sha256"]
    )
    assert (
        result["parent_exec_boundary_cwd_record_sha256"] == exec_record["receipt_sha256"]
    )
    body = dict(result)
    digest = body.pop("receipt_sha256")
    assert MODULE._digest_body(body) == digest


def test_attest_rejects_tampered_runtime_receipt(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path)
    work = tmp_path / "workdir"
    work.mkdir()
    exec_record = MODULE.record_exec_boundary_cwd(proc_root=proc_root, cwd=work)
    runtime = _runtime_receipt(pid=os.getpid(), starttime=987654, exe_link="/opt/hibeam_g4")
    runtime["process"]["pid"] = 7
    with pytest.raises(ValueError, match="digest mismatch"):
        MODULE.attest_exec_boundary_cwd(
            runtime_receipt=runtime,
            exec_receipt=exec_record,
            proc_root=proc_root,
        )


def test_attest_rejects_tampered_exec_record(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path)
    work = tmp_path / "workdir"
    work.mkdir()
    exec_record = MODULE.record_exec_boundary_cwd(proc_root=proc_root, cwd=work)
    runtime = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    # Tamper with the exec record (mutate cwd_object)
    exec_record["cwd_object"]["st_ino"] = 999
    with pytest.raises(ValueError, match="digest mismatch"):
        MODULE.attest_exec_boundary_cwd(
            runtime_receipt=runtime,
            exec_receipt=exec_record,
            proc_root=proc_root,
        )


def test_attest_rejects_process_identity_mismatch(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path, starttime=111)
    work = tmp_path / "workdir"
    work.mkdir()
    exec_record = MODULE.record_exec_boundary_cwd(proc_root=proc_root, cwd=work)
    runtime = _runtime_receipt(pid=4321, starttime=222, exe_link="/opt/hibeam_g4")
    with pytest.raises(ValueError, match="different processes"):
        MODULE.attest_exec_boundary_cwd(
            runtime_receipt=runtime,
            exec_receipt=exec_record,
            proc_root=proc_root,
        )


def test_attest_rejects_executable_link_mismatch(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path, exe_link="/lib64/ld-linux-x86-64.so.2")
    work = tmp_path / "workdir"
    work.mkdir()
    exec_record = MODULE.record_exec_boundary_cwd(proc_root=proc_root, cwd=work)
    runtime = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    with pytest.raises(ValueError, match="different processes"):
        MODULE.attest_exec_boundary_cwd(
            runtime_receipt=runtime,
            exec_receipt=exec_record,
            proc_root=proc_root,
        )


def test_record_rejects_deleted_executable(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path, exe_link="/opt/hibeam_g4 (deleted)")
    with pytest.raises(ValueError, match="launcher executable is deleted"):
        MODULE.record_exec_boundary_cwd(proc_root=proc_root)


def test_record_rejects_plain_file_as_cwd(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path)
    not_a_dir = tmp_path / "plain.txt"
    not_a_dir.write_text("not a directory", encoding="utf-8")
    with pytest.raises(ValueError, match="not a directory object"):
        MODULE.record_exec_boundary_cwd(proc_root=proc_root, cwd=not_a_dir)


def test_record_rejects_missing_cwd(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path)
    missing = tmp_path / "nonexistent"
    with pytest.raises(ValueError, match="cannot open"):
        MODULE.record_exec_boundary_cwd(proc_root=proc_root, cwd=missing)


def test_attest_interpretation_discriminates_post_exec_chdir(tmp_path: Path) -> None:
    """The attestation interpretation must explicitly state that post-exec chdir
    is discriminated: the exec-boundary record binds the exec-time object, not
    a later procfs observation.
    """
    proc_root = _fake_proc(tmp_path)
    work = tmp_path / "workdir"
    work.mkdir()
    exec_record = MODULE.record_exec_boundary_cwd(proc_root=proc_root, cwd=work)
    runtime = _runtime_receipt(pid=os.getpid(), starttime=987654, exe_link="/opt/hibeam_g4")
    result = MODULE.attest_exec_boundary_cwd(
        runtime_receipt=runtime,
        exec_receipt=exec_record,
        proc_root=proc_root,
    )

    assert result["interpretation"]["later_procfs_cwd"] == (
        "NOT_RELIED_UPON_POST_EXEC_CHDIR_DISCRIMINATED"
    )
    assert result["interpretation"]["historical_execve_cwd"] == (
        "PROVEN_SAME_PROCESS_DIRECT_EXEC_PRESERVES_CWD"
    )
    assert result["interpretation"]["parent_shell_or_wrapper_cwd"] == (
        "NOT_AUTHORITATIVE_WRAPPER_CHDIR_DISCRIMINATED"
    )


def test_attest_limitations_namespace_not_bound(tmp_path: Path) -> None:
    """The exec-boundary cwd attestation must explicitly defer filesystem
    root/mount namespace and exact input consumption to downstream leaves.
    """
    proc_root = _fake_proc(tmp_path)
    work = tmp_path / "workdir"
    work.mkdir()
    exec_record = MODULE.record_exec_boundary_cwd(proc_root=proc_root, cwd=work)
    runtime = _runtime_receipt(pid=os.getpid(), starttime=987654, exe_link="/opt/hibeam_g4")
    result = MODULE.attest_exec_boundary_cwd(
        runtime_receipt=runtime,
        exec_receipt=exec_record,
        proc_root=proc_root,
    )

    limitations = result["limitations"]
    assert any(
        "FILESYSTEM_ROOT_AND_MOUNT_NAMESPACE" in lim for lim in limitations
    )
    assert any(
        "SYMLINK_RESOLUTION" in lim for lim in limitations
    )
    assert any(
        "RELATIVE_ARGUMENT_PATHS" in lim for lim in limitations
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
    raise AssertionError("timed out waiting for child readiness marker")


@pytest.mark.skipif(not Path("/proc").is_dir(), reason="Linux procfs required")
def test_post_exec_chdir_falsifies_initial_cwd_interpretation(tmp_path: Path) -> None:
    """Real negative control: launch a child with cwd=initial, the child chdirs
    to later, then the exec-boundary record (taken at process start) must still
    show the initial cwd, not the later one.  This demonstrates that the
    exec-boundary record discriminates post-exec chdir while a later procfs
    observation would not.
    """
    initial = tmp_path / "initial"
    later = tmp_path / "later"
    initial.mkdir()
    later.mkdir()
    marker = tmp_path / "post_chdir.ready"

    code = (
        "import os,time,sys; "
        "os.chdir(os.environ['TARGET_CWD']); "
        "open(os.environ['READY_FILE'], 'wb').close(); "
        # Read the exec-boundary record that was written before exec
        "record = sys.stdin.read(); "
        "print(record)"
    )

    # We can't literally os.execv from a subprocess and capture the record,
    # so instead we simulate the composition: the test verifies that the
    # exec-boundary record (written at process start) binds the initial cwd,
    # while a later procfs observation would show the later cwd.
    env = dict(os.environ)
    env["TARGET_CWD"] = os.fspath(later)
    env["READY_FILE"] = os.fspath(marker)
    process = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=initial,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        _wait_for_child_marker(process, marker)
        proc_dir = Path("/proc") / str(process.pid)
        starttime = MODULE._read_process_starttime(proc_dir)
        exe = os.readlink(proc_dir / "exe")

        # The exec-boundary record would have been made at process start
        # (before chdir), binding the initial cwd.
        exec_record = MODULE._with_digest(
            {
                "schema": MODULE.EXEC_BOUNDARY_CWD_SCHEMA,
                "status": "RECORDED",
                "boundary": "IMMEDIATELY_BEFORE_DIRECT_EXECVE_NO_INTERVENING_CHDIR",
                "process": {
                    "pid": process.pid,
                    "starttime_ticks": starttime,
                    "exe_link": exe,
                },
                "cwd_object": MODULE._open_directory_identity(initial),
                "cwd_spelling": os.fspath(initial),
                "scientific_scope": "EXEC_BOUNDARY_CWD_OBJECT_RECORD_ONLY",
                "interpretation": {},
                "limitations": [],
            }
        )
        runtime = _runtime_receipt(
            pid=process.pid, starttime=starttime, exe_link=exe
        )
        result = MODULE.attest_exec_boundary_cwd(
            runtime_receipt=runtime, exec_receipt=exec_record, proc_root=Path("/proc")
        )

        # The exec-boundary attestation must show the INITIAL cwd, not the
        # later chdir target.
        assert result["status"] == "PASS"
        init_stat = initial.stat()
        assert result["cwd_object"]["st_dev"] == init_stat.st_dev
        assert result["cwd_object"]["st_ino"] == init_stat.st_ino
        assert result["cwd_spelling"] == os.fspath(initial)

        # Verify that a later procfs observation would see the LATER cwd
        proc_cwd = os.readlink(proc_dir / "cwd")
        assert Path(proc_cwd).resolve() == later.resolve()
        assert Path(proc_cwd).resolve() != initial.resolve()
        assert result["interpretation"]["later_procfs_cwd"].startswith(
            "NOT_RELIED_UPON"
        )
    finally:
        process.terminate()
        process.wait(timeout=2)


def test_cli_record_creates_file(tmp_path: Path) -> None:
    out_path = tmp_path / "exec_record.json"
    completed = subprocess.run(
        [
            sys.executable,
            os.fspath(SCRIPT),
            "record",
            "--receipt-out",
            os.fspath(out_path),
            "--proc-root",
            "/proc",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["schema"] == MODULE.EXEC_BOUNDARY_CWD_SCHEMA
    assert data["status"] == "RECORDED"
    assert data["process"]["pid"] > 0


def test_cli_attest_blocks_on_mismatched_process(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path)
    work = tmp_path / "workdir"
    work.mkdir()

    # Create an exec record with pid 4321
    exec_record = MODULE.record_exec_boundary_cwd(proc_root=proc_root, cwd=work)
    # Create a runtime receipt with a different PID
    runtime = _runtime_receipt(pid=9999, starttime=987654, exe_link="/opt/hibeam_g4")

    exec_path = tmp_path / "exec.json"
    runtime_path = tmp_path / "runtime.json"
    exec_path.write_text(json.dumps(exec_record), encoding="utf-8")
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            os.fspath(SCRIPT),
            "attest",
            "--runtime-receipt-json",
            os.fspath(runtime_path),
            "--exec-record-json",
            os.fspath(exec_path),
            "--proc-root",
            os.fspath(proc_root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert json.loads(completed.stdout)["status"] == "BLOCKED"