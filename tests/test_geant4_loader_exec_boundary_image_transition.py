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
SPEC = importlib.util.spec_from_file_location("exec_boundary_cwd", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _runtime_receipt_from_record(record: dict, *, exe_link: str) -> dict:
    target = record["exec_intent"]["target"]
    return MODULE._with_digest(
        {
            "schema": MODULE.RUNTIME_RECEIPT_SCHEMA,
            "status": "PASS",
            "parent_final_build_receipt_sha256": "f" * 64,
            "process": {
                "pid": record["process"]["pid"],
                "starttime_ticks": record["process"]["starttime_ticks"],
                "exe_link": exe_link,
                "executable": {
                    "bytes": target["bytes"],
                    "sha256": target["sha256"],
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


def _wait_for_exec(
    process: subprocess.Popen[bytes], receipt: Path, target: Path
) -> str:
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"child exited early: {process.returncode}")
        if receipt.exists():
            try:
                exe_link = os.readlink(Path("/proc") / str(process.pid) / "exe")
            except OSError:
                time.sleep(0.01)
                continue
            if os.path.realpath(exe_link) == os.path.realpath(target):
                return exe_link
        time.sleep(0.01)
    raise AssertionError("timed out waiting for direct exec transition")


@pytest.mark.skipif(not Path("/proc").is_dir(), reason="Linux procfs required")
def test_real_direct_exec_replaces_image_but_preserves_process_identity(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "exec-record.json"
    target = Path("/bin/sleep")
    process = subprocess.Popen(
        [
            sys.executable,
            os.fspath(SCRIPT),
            "record",
            "--receipt-out",
            os.fspath(receipt),
            "--command",
            os.fspath(target),
            "5",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        runtime_exe = _wait_for_exec(process, receipt, target)
        record = json.loads(receipt.read_text(encoding="utf-8"))
        assert record["process"]["pid"] == process.pid
        assert record["process"]["exe_link"] != runtime_exe
        assert record["exec_intent"]["mode"] == "DIRECT_OS_EXECV"
        proc_dir = Path("/proc") / str(process.pid)
        assert (
            MODULE._read_process_starttime(proc_dir)
            == record["process"]["starttime_ticks"]
        )

        result = MODULE.attest_exec_boundary_cwd(
            runtime_receipt=_runtime_receipt_from_record(
                record, exe_link=runtime_exe
            ),
            exec_receipt=record,
        )
        assert result["status"] == "PASS"
        assert result["exec_transition"]["same_pid_starttime"] is True
        assert result["exec_transition"]["exec_intent_bound"] is True
        assert result["exec_transition"]["kernel_execve_event_observed"] is False
    finally:
        process.terminate()
        process.wait(timeout=2)


def test_exec_intent_rejects_runtime_target_content_mismatch(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    proc_dir = proc_root / str(os.getpid())
    proc_dir.mkdir(parents=True)
    fields = ["S", *("0" for _ in range(18)), "12345", *("0" for _ in range(8))]
    (proc_dir / "stat").write_text(
        f"{os.getpid()} (fixture) {' '.join(fields)}\n", encoding="ascii"
    )
    (proc_dir / "exe").symlink_to(sys.executable)
    record = MODULE.record_exec_boundary_cwd(
        proc_root=proc_root,
        exec_argv=["/bin/sleep", "1"],
    )
    runtime = _runtime_receipt_from_record(
        record, exe_link=os.path.realpath("/bin/sleep")
    )
    runtime["process"]["executable"]["sha256"] = "0" * 64
    body = dict(runtime)
    body.pop("receipt_sha256")
    runtime = MODULE._with_digest(body)
    with pytest.raises(ValueError, match="bytes differ"):
        MODULE.attest_exec_boundary_cwd(
            runtime_receipt=runtime,
            exec_receipt=record,
        )
