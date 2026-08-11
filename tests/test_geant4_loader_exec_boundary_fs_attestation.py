from __future__ import annotations

import base64
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
    / "geant4_loader_exec_boundary_fs_attestation.py"
)
SPEC = importlib.util.spec_from_file_location(
    "geant4_loader_exec_boundary_fs_attestation", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _runtime_receipt(
    *,
    pid: int,
    starttime: int,
    exe_link: str,
    executable: dict | None = None,
) -> dict:
    return MODULE._with_digest(
        {
            "schema": MODULE.RUNTIME_RECEIPT_SCHEMA,
            "status": "PASS",
            "parent_final_build_receipt_sha256": "f" * 64,
            "process": {
                "pid": pid,
                "starttime_ticks": starttime,
                "exe_link": exe_link,
                "executable": executable or {"bytes": 0, "sha256": "0" * 64},
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


def _wait_until(predicate, *, timeout_s: float = 5.0, label: str = "condition") -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError(f"timed out waiting for {label}")


@pytest.mark.skipif(not Path("/proc/self/mountinfo").exists(), reason="Linux procfs required")
def test_real_proc_record_binds_namespace_root_mountinfo_and_digest(tmp_path: Path) -> None:
    record = MODULE.record_exec_boundary_fs()
    assert record["status"] == "RECORDED"
    assert record["schema"] == MODULE.EXEC_BOUNDARY_FS_SCHEMA
    assert record["process"]["pid"] == os.getpid()
    assert record["mount_namespace"]["link_text"].startswith("mnt:[")
    assert record["mount_namespace"]["st_ino"] > 0
    assert record["root"]["object"]["st_ino"] > 0
    assert record["cwd"]["object"]["st_ino"] > 0
    assert record["thread_state"]["caller_is_thread_group_leader"] is True

    mountinfo = base64.b64decode(record["mountinfo"]["content_base64"], validate=True)
    assert len(mountinfo) == record["mountinfo"]["bytes"]
    assert MODULE.hashlib.sha256(mountinfo).hexdigest() == record["mountinfo"]["sha256"]
    assert len(mountinfo.splitlines()) == record["mountinfo"]["line_count"]

    body = dict(record)
    digest = body.pop("receipt_sha256")
    assert MODULE._digest_body(body) == digest


@pytest.mark.skipif(not Path("/proc/self/mountinfo").exists(), reason="Linux procfs required")
def test_attest_same_process_without_exec_intent_passes() -> None:
    record = MODULE.record_exec_boundary_fs()
    runtime = _runtime_receipt(
        pid=os.getpid(),
        starttime=record["process"]["starttime_ticks"],
        exe_link=record["process"]["exe_link"],
    )
    result = MODULE.attest_exec_boundary_fs(
        runtime_receipt=runtime,
        exec_fs_record=record,
    )
    assert result["status"] == "PASS"
    assert result["mount_namespace"] == record["mount_namespace"]
    assert result["mountinfo"] == record["mountinfo"]
    assert result["exec_transition"]["kernel_execve_event_observed"] is False
    assert (
        result["interpretation"]["actual_relative_input_consumption"]
        == "NOT_ATTESTED_REQUIRES_OPEN_EVENT_AND_OPENED_BYTES_CHILD"
    )


@pytest.mark.skipif(not Path("/proc/self/mountinfo").exists(), reason="Linux procfs required")
def test_attest_rejects_tampered_filesystem_record() -> None:
    record = MODULE.record_exec_boundary_fs()
    runtime = _runtime_receipt(
        pid=os.getpid(),
        starttime=record["process"]["starttime_ticks"],
        exe_link=record["process"]["exe_link"],
    )
    record["mountinfo"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="digest mismatch"):
        MODULE.attest_exec_boundary_fs(runtime_receipt=runtime, exec_fs_record=record)


@pytest.mark.skipif(not Path("/proc/self/mountinfo").exists(), reason="Linux procfs required")
def test_attest_rejects_process_identity_mismatch() -> None:
    record = MODULE.record_exec_boundary_fs()
    runtime = _runtime_receipt(
        pid=os.getpid() + 1,
        starttime=record["process"]["starttime_ticks"],
        exe_link=record["process"]["exe_link"],
    )
    with pytest.raises(ValueError, match="different processes"):
        MODULE.attest_exec_boundary_fs(runtime_receipt=runtime, exec_fs_record=record)


def test_record_rejects_mountinfo_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    original = MODULE._read_proc_bytes
    calls = {"mountinfo": 0}

    def fake(proc_dir: Path, name: str, *, label: str) -> bytes:
        if name == "mountinfo":
            calls["mountinfo"] += 1
            return b"1 1 0:1 / / rw - tmpfs tmpfs rw\n" + (
                b"" if calls["mountinfo"] == 1 else b"2 1 0:2 /x /x rw - tmpfs tmpfs rw\n"
            )
        return original(proc_dir, name, label=label)

    monkeypatch.setattr(MODULE, "_read_proc_bytes", fake)
    with pytest.raises(ValueError, match="mountinfo changed"):
        MODULE.record_exec_boundary_fs()


def test_record_rejects_mount_namespace_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    original = MODULE._mount_namespace_identity
    calls = {"n": 0}

    def fake(proc_dir: Path) -> dict:
        calls["n"] += 1
        result = dict(original(proc_dir))
        if calls["n"] == 2:
            result["st_ino"] += 1
        return result

    monkeypatch.setattr(MODULE, "_mount_namespace_identity", fake)
    with pytest.raises(ValueError, match="mount namespace identity changed"):
        MODULE.record_exec_boundary_fs()


@pytest.mark.skipif(
    not Path("/proc/self/mountinfo").exists(), reason="Linux procfs required"
)
def test_direct_exec_transition_composes_same_pid_starttime_and_target_bytes(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "fs_record.json"
    target = Path("/bin/sleep")
    process = subprocess.Popen(
        [
            sys.executable,
            os.fspath(SCRIPT),
            "record",
            "--receipt-out",
            os.fspath(receipt_path),
            "--command",
            os.fspath(target),
            "2",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_until(receipt_path.exists, label="pre-exec filesystem receipt")
        record = json.loads(receipt_path.read_text(encoding="utf-8"))
        expected_runtime = record["exec_intent"]["target"]["resolved_path"]

        def transitioned() -> bool:
            try:
                return os.path.realpath(os.readlink(f"/proc/{process.pid}/exe")) == expected_runtime
            except OSError:
                return False

        _wait_until(transitioned, label="direct exec image transition")
        proc_dir = Path("/proc") / str(process.pid)
        runtime_exe = os.readlink(proc_dir / "exe")
        runtime = _runtime_receipt(
            pid=process.pid,
            starttime=MODULE._read_process_starttime(proc_dir),
            exe_link=runtime_exe,
            executable={
                "bytes": record["exec_intent"]["target"]["bytes"],
                "sha256": record["exec_intent"]["target"]["sha256"],
            },
        )
        result = MODULE.attest_exec_boundary_fs(
            runtime_receipt=runtime,
            exec_fs_record=record,
        )
        assert result["status"] == "PASS"
        assert result["exec_transition"]["same_pid_starttime"] is True
        assert result["exec_transition"]["exec_intent_bound"] is True
        assert result["exec_transition"]["launcher_exe_link"] != runtime_exe
    finally:
        process.terminate()
        process.wait(timeout=3)


@pytest.mark.skipif(
    os.geteuid() != 0, reason="post-exec chroot control requires root/CAP_SYS_CHROOT"
)
def test_post_exec_chroot_demonstrates_exec_snapshot_is_not_input_consumption_state(
    tmp_path: Path,
) -> None:
    new_root = tmp_path / "new_root"
    new_root.mkdir()
    receipt_path = tmp_path / "fs_record.json"
    code = (
        "import os,time; "
        f"os.chroot({str(new_root)!r}); "
        "os.chdir('/'); "
        "time.sleep(2)"
    )
    process = subprocess.Popen(
        [
            sys.executable,
            os.fspath(SCRIPT),
            "record",
            "--receipt-out",
            os.fspath(receipt_path),
            "--command",
            sys.executable,
            "-c",
            code,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_until(receipt_path.exists, label="pre-exec filesystem receipt")
        record = json.loads(receipt_path.read_text(encoding="utf-8"))
        proc_dir = Path("/proc") / str(process.pid)

        def chrooted() -> bool:
            try:
                root_link = os.readlink(proc_dir / "root")
            except OSError:
                return False
            return Path(root_link).resolve() == new_root.resolve()

        _wait_until(chrooted, label="post-exec chroot")
        flags = getattr(os, "O_PATH", os.O_RDONLY) | getattr(os, "O_DIRECTORY", 0)
        fd = os.open(proc_dir / "root", flags)
        try:
            later = os.fstat(fd)
        finally:
            os.close(fd)

        pre = record["root"]["object"]
        assert (pre["st_dev"], pre["st_ino"]) != (later.st_dev, later.st_ino)
        assert any("POST_EXEC_CHDIR" in item for item in record["limitations"])
        assert any("INPUT_OPEN_EVENTS_NOT_OBSERVED" in item for item in record["limitations"])
    finally:
        process.terminate()
        process.wait(timeout=3)
