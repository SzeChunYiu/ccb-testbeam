from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
import time
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "audit"
    / "geant4_exec_cwd_attestation.py"
)
SPEC = importlib.util.spec_from_file_location("geant4_exec_cwd_attestation", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or not Path("/proc").is_dir(),
    reason="Linux procfs required",
)


def _kill_and_reap(process) -> None:
    if process.poll() is None:
        process.kill()
    process.wait(timeout=2)


def _wait_for_path(path: Path, *, process, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if path.exists():
            return
        try:
            status = process.poll()
        except ChildProcessError as exc:
            raise AssertionError("child disappeared before readiness marker") from exc
        if status is not None:
            raise AssertionError(f"child exited before readiness marker: status={status}")
        time.sleep(0.01)
    raise AssertionError("timed out waiting for child readiness marker")


def _runtime_receipt(exec_receipt: dict) -> dict:
    process = exec_receipt["process"]
    executable = process["executable_object"]
    return MODULE._with_digest(
        {
            "schema": MODULE.RUNTIME_RECEIPT_SCHEMA,
            "status": "PASS",
            "parent_final_build_receipt_sha256": "f" * 64,
            "process": {
                "pid": process["pid"],
                "starttime_ticks": process["starttime_ticks"],
                "exe_link": process["exe_link"],
                "executable": {
                    **executable,
                    "sha256": "0" * 64,
                },
            },
            "loader_environment": {},
            "mapped_executable_objects": [],
            "required_object_matches": {},
            "maps_sha256": "1" * 64,
            "executable_mapping_projection_stable": True,
            "scientific_scope": "fixture",
            "limitations": [],
        }
    )


def test_direct_elf_launch_binds_exec_cwd_object_and_exact_argv(tmp_path: Path) -> None:
    cwd = tmp_path / "run"
    cwd.mkdir()
    executable = Path("/bin/sleep").resolve()
    argv = [b"hibeam-fixture", b"5"]

    process, receipt = MODULE.launch_exec_cwd_attested(
        cwd=cwd,
        executable=executable,
        argv=argv,
    )
    try:
        assert receipt["status"] == "PASS"
        assert receipt["process"]["pid"] == process.pid
        cwd_identity = receipt["exec_boundary_cwd"]["opened_directory_identity"]
        actual = cwd.stat()
        assert cwd_identity["st_dev"] == actual.st_dev
        assert cwd_identity["st_ino"] == actual.st_ino
        assert receipt["exec_boundary_cwd"]["requested_path"] == os.fspath(cwd)
        assert [
            os.fsdecode(MODULE.base64.b64decode(item["base64"]))
            for item in receipt["argv_passed_to_execve"]
        ] == ["hibeam-fixture", "5"]
        body = dict(receipt)
        observed = body.pop("receipt_sha256")
        assert MODULE._digest_body(body) == observed
    finally:
        _kill_and_reap(process)


def test_parent_cwd_is_not_substituted_for_explicit_exec_cwd(tmp_path: Path) -> None:
    child_cwd = tmp_path / "child"
    child_cwd.mkdir()
    parent_cwd = Path.cwd().stat()
    process, receipt = MODULE.launch_exec_cwd_attested(
        cwd=child_cwd,
        executable=Path("/bin/sleep").resolve(),
        argv=[b"sleep", b"5"],
    )
    try:
        observed = receipt["exec_boundary_cwd"]["opened_directory_identity"]
        assert (observed["st_dev"], observed["st_ino"]) == (
            child_cwd.stat().st_dev,
            child_cwd.stat().st_ino,
        )
        assert (observed["st_dev"], observed["st_ino"]) != (
            parent_cwd.st_dev,
            parent_cwd.st_ino,
        )
    finally:
        _kill_and_reap(process)


def test_post_exec_chdir_does_not_rewrite_exec_boundary_receipt(tmp_path: Path) -> None:
    initial = tmp_path / "initial"
    later = tmp_path / "later"
    marker = tmp_path / "post-chdir.ready"
    initial.mkdir()
    later.mkdir()
    code = (
        b"import os,time; "
        b"os.chdir(os.environ['TARGET_CWD']); "
        b"open(os.environ['READY_FILE'],'wb').close(); "
        b"time.sleep(20)"
    )
    env = dict(os.environb)
    env[b"TARGET_CWD"] = os.fsencode(later)
    env[b"READY_FILE"] = os.fsencode(marker)
    executable = Path(sys.executable).resolve()
    process, receipt = MODULE.launch_exec_cwd_attested(
        cwd=initial,
        executable=executable,
        argv=[os.fsencode(sys.executable), b"-c", code],
        env=env,
    )
    try:
        _wait_for_path(marker, process=process)
        current_link = Path(os.readlink(Path("/proc") / str(process.pid) / "cwd")).resolve()
        assert current_link == later.resolve()
        recorded = receipt["exec_boundary_cwd"]["opened_directory_identity"]
        initial_info = initial.stat()
        later_info = later.stat()
        assert (recorded["st_dev"], recorded["st_ino"]) == (
            initial_info.st_dev,
            initial_info.st_ino,
        )
        assert (recorded["st_dev"], recorded["st_ino"]) != (
            later_info.st_dev,
            later_info.st_ino,
        )
    finally:
        _kill_and_reap(process)


def test_post_exec_fchdir_does_not_rewrite_exec_boundary_receipt(tmp_path: Path) -> None:
    initial = tmp_path / "initial"
    later = tmp_path / "later"
    marker = tmp_path / "post-fchdir.ready"
    initial.mkdir()
    later.mkdir()
    code = (
        b"import os,time; "
        b"fd=os.open(os.environ['TARGET_CWD'],os.O_RDONLY|os.O_DIRECTORY); "
        b"os.fchdir(fd); os.close(fd); "
        b"open(os.environ['READY_FILE'],'wb').close(); "
        b"time.sleep(20)"
    )
    env = dict(os.environb)
    env[b"TARGET_CWD"] = os.fsencode(later)
    env[b"READY_FILE"] = os.fsencode(marker)
    executable = Path(sys.executable).resolve()
    process, receipt = MODULE.launch_exec_cwd_attested(
        cwd=initial,
        executable=executable,
        argv=[os.fsencode(sys.executable), b"-c", code],
        env=env,
    )
    try:
        _wait_for_path(marker, process=process)
        current_link = Path(os.readlink(Path("/proc") / str(process.pid) / "cwd")).resolve()
        assert current_link == later.resolve()
        recorded = receipt["exec_boundary_cwd"]["opened_directory_identity"]
        assert (recorded["st_dev"], recorded["st_ino"]) == (
            initial.stat().st_dev,
            initial.stat().st_ino,
        )
    finally:
        _kill_and_reap(process)


def test_rejects_script_wrapper_target(tmp_path: Path) -> None:
    script = tmp_path / "wrapper.sh"
    script.write_text("#!/bin/sh\nsleep 1\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    with pytest.raises(ValueError, match="direct ELF executable"):
        MODULE.launch_exec_cwd_attested(
            cwd=tmp_path,
            executable=script,
            argv=[os.fsencode(script)],
        )


def test_rejects_non_absolute_launch_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute paths"):
        MODULE.launch_exec_cwd_attested(
            cwd=Path("."),
            executable=Path("/bin/sleep").resolve(),
            argv=[b"sleep", b"1"],
        )


def test_runtime_binding_requires_same_process_and_executable(tmp_path: Path) -> None:
    cwd = tmp_path / "run"
    cwd.mkdir()
    process, receipt = MODULE.launch_exec_cwd_attested(
        cwd=cwd,
        executable=Path("/bin/sleep").resolve(),
        argv=[b"sleep", b"5"],
    )
    try:
        runtime = _runtime_receipt(receipt)
        binding = MODULE.bind_exec_cwd_to_runtime(
            exec_cwd_receipt=receipt,
            runtime_receipt=runtime,
        )
        assert binding["status"] == "PASS"
        assert binding["process"]["pid"] == process.pid

        wrong_start = dict(runtime)
        wrong_start["process"] = dict(runtime["process"])
        wrong_start["process"]["starttime_ticks"] += 1
        wrong_start = MODULE._with_digest(
            {key: value for key, value in wrong_start.items() if key != "receipt_sha256"}
        )
        with pytest.raises(ValueError, match="starttime_ticks differs"):
            MODULE.bind_exec_cwd_to_runtime(
                exec_cwd_receipt=receipt,
                runtime_receipt=wrong_start,
            )

        wrong_inode = dict(runtime)
        wrong_inode["process"] = dict(runtime["process"])
        wrong_inode["process"]["executable"] = dict(runtime["process"]["executable"])
        wrong_inode["process"]["executable"]["inode"] += 1
        wrong_inode = MODULE._with_digest(
            {key: value for key, value in wrong_inode.items() if key != "receipt_sha256"}
        )
        with pytest.raises(ValueError, match="executable object differs"):
            MODULE.bind_exec_cwd_to_runtime(
                exec_cwd_receipt=receipt,
                runtime_receipt=wrong_inode,
            )
    finally:
        _kill_and_reap(process)


def test_runtime_binding_rejects_tampered_exec_receipt(tmp_path: Path) -> None:
    cwd = tmp_path / "run"
    cwd.mkdir()
    process, receipt = MODULE.launch_exec_cwd_attested(
        cwd=cwd,
        executable=Path("/bin/sleep").resolve(),
        argv=[b"sleep", b"5"],
    )
    try:
        runtime = _runtime_receipt(receipt)
        receipt["exec_boundary_cwd"]["requested_path"] = "/tampered"
        with pytest.raises(ValueError, match="digest mismatch"):
            MODULE.bind_exec_cwd_to_runtime(
                exec_cwd_receipt=receipt,
                runtime_receipt=runtime,
            )
    finally:
        _kill_and_reap(process)


def test_build_receipt_rejects_parent_selected_target_mismatch(tmp_path: Path) -> None:
    cwd = tmp_path / "run"
    cwd.mkdir()
    target = MODULE._file_object_identity(Path("/bin/sleep").resolve().stat())
    wrong_target = dict(target)
    wrong_target["inode"] += 1
    cwd_object = MODULE._directory_object_identity(cwd.stat())
    pre_exec = MODULE._with_digest(
        {
            "stage": "PRE_EXEC_READY",
            "pid": 123,
            "starttime_ticks": 456,
            "cwd": {
                "procfs_link_text": str(cwd),
                "opened_directory_identity": cwd_object,
            },
            "target": {
                "requested_path": "/bin/sleep",
                "opened_file_identity": target,
                "direct_exec_mechanism": "FD_EXECVE_ELF_NO_PATH_REOPEN",
            },
            "argv": [],
        }
    )
    post_exec = {
        "pid": 123,
        "starttime_ticks": 456,
        "exe_link": "/bin/sleep",
        "executable_object": target,
    }
    with pytest.raises(ValueError, match="parent-selected target object"):
        MODULE._build_exec_cwd_receipt(
            requested_cwd=cwd,
            expected_cwd_object=cwd_object,
            expected_target_object=wrong_target,
            expected_environment_sha256="e" * 64,
            pre_exec=pre_exec,
            post_exec=post_exec,
        )


def test_receipt_json_serialization_is_stable(tmp_path: Path) -> None:
    cwd = tmp_path / "run"
    cwd.mkdir()
    process, receipt = MODULE.launch_exec_cwd_attested(
        cwd=cwd,
        executable=Path("/bin/sleep").resolve(),
        argv=[b"sleep", b"5"],
    )
    try:
        round_trip = json.loads(json.dumps(receipt, sort_keys=True))
        MODULE._verify_receipt(round_trip, schema=MODULE.SCHEMA, label="round-trip")
    finally:
        _kill_and_reap(process)