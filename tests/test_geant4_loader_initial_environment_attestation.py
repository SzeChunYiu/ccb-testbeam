from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import tools.audit.geant4_loader_initial_environment_attestation as initial_env


def _with_digest(body: dict[str, object]) -> dict[str, object]:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result = dict(body)
    result["receipt_sha256"] = hashlib.sha256(payload).hexdigest()
    return result


def _env_record(value: bytes | None) -> dict[str, object]:
    if value is None:
        return {"present": False}
    return {
        "present": True,
        "bytes": len(value),
        "sha256": hashlib.sha256(value).hexdigest(),
        "base64": base64.b64encode(value).decode("ascii"),
        "utf8": value.decode("utf-8"),
    }


def _runtime(
    *,
    pid: int = 4242,
    starttime: int = 123456,
    ld_library_path: bytes | None = b"/g4:/root",
    marker: bytes | None = None,
) -> dict[str, object]:
    env: dict[str, object] = {
        "LD_LIBRARY_PATH": _env_record(ld_library_path),
        "LD_PRELOAD": _env_record(None),
        "LD_AUDIT": _env_record(None),
        "GLIBC_TUNABLES": _env_record(None),
    }
    if marker is not None:
        env["CCB_LAUNCH_MARKER"] = _env_record(marker)
    return _with_digest(
        {
            "schema": initial_env.RUNTIME_RECEIPT_SCHEMA,
            "status": "PASS",
            "process": {"pid": pid, "starttime_ticks": starttime},
            "loader_environment": env,
        }
    )


def _secure(
    runtime: dict[str, object],
    *,
    pid: int = 4242,
    starttime: int = 123456,
    at_secure: int = 0,
) -> dict[str, object]:
    return _with_digest(
        {
            "schema": initial_env.SECURE_RECEIPT_SCHEMA,
            "status": "PASS",
            "parent_runtime_dependency_receipt_sha256": runtime["receipt_sha256"],
            "process": {"pid": pid, "starttime_ticks": starttime},
            "auxv": {"at_secure": at_secure},
        }
    )


def _fake_stat(pid: int, starttime: int) -> str:
    tail = ["S", *(["0"] * 18), str(starttime), *(["0"] * 8)]
    return f"{pid} (fixture proc) " + " ".join(tail) + "\n"


def _proc(
    tmp_path: Path,
    *,
    environ: bytes,
    pid: int = 4242,
    starttime: int = 123456,
) -> Path:
    root = tmp_path / "proc"
    proc_dir = root / str(pid)
    proc_dir.mkdir(parents=True)
    (proc_dir / "stat").write_text(_fake_stat(pid, starttime), encoding="ascii")
    (proc_dir / "environ").write_bytes(environ)
    return root


def test_stable_initial_environment_matches_runtime_receipt(tmp_path: Path) -> None:
    runtime = _runtime()
    payload = b"LD_LIBRARY_PATH=/g4:/root\0IGNORED=x\0"
    result = initial_env.attest_loader_initial_environment(
        runtime_receipt=runtime,
        secure_receipt=_secure(runtime),
        proc_root=_proc(tmp_path, environ=payload),
    )
    assert result["status"] == "PASS"
    assert result["proc_initial_environment"]["bytes"] == len(payload)
    assert result["proc_initial_environment"]["stable_across_attestation"] is True
    assert result["tracked_key_semantics"]["LD_LIBRARY_PATH"][
        "presence_inference"
    ] == "OBSERVED_AT_ATTESTATION_BOUNDARY"


def test_kernel_secure_state_restricts_environment_search_authority(tmp_path: Path) -> None:
    runtime = _runtime()
    result = initial_env.attest_loader_initial_environment(
        runtime_receipt=runtime,
        secure_receipt=_secure(runtime, at_secure=1),
        proc_root=_proc(tmp_path, environ=b"LD_LIBRARY_PATH=/g4:/root\0"),
    )
    assert result["tracked_key_semantics"]["LD_LIBRARY_PATH"][
        "loader_search_interpretation"
    ] == "KERNEL_SECURE_MODE_RESTRICTS_OR_IGNORES_ENV_INPUT"


def test_absence_is_not_promoted_to_execve_absence(tmp_path: Path) -> None:
    runtime = _runtime(ld_library_path=None)
    result = initial_env.attest_loader_initial_environment(
        runtime_receipt=runtime,
        secure_receipt=_secure(runtime),
        proc_root=_proc(tmp_path, environ=b"OTHER=x\0"),
    )
    assert result["tracked_key_semantics"]["LD_LIBRARY_PATH"][
        "presence_inference"
    ] == "ABSENT_AT_OBSERVATION_NOT_PROOF_OF_EXECVE_ABSENCE"


def test_proc_environment_must_match_runtime_receipt(tmp_path: Path) -> None:
    runtime = _runtime()
    with pytest.raises(ValueError, match="differs from runtime receipt"):
        initial_env.attest_loader_initial_environment(
            runtime_receipt=runtime,
            secure_receipt=_secure(runtime),
            proc_root=_proc(tmp_path, environ=b"LD_LIBRARY_PATH=/different\0"),
        )


def test_duplicate_tracked_initial_environment_key_fails(tmp_path: Path) -> None:
    runtime = _runtime()
    payload = b"LD_LIBRARY_PATH=/g4:/root\0LD_LIBRARY_PATH=/g4:/root\0"
    with pytest.raises(ValueError, match="duplicate tracked"):
        initial_env.attest_loader_initial_environment(
            runtime_receipt=runtime,
            secure_receipt=_secure(runtime),
            proc_root=_proc(tmp_path, environ=payload),
        )


def test_secure_receipt_must_belong_to_runtime_receipt(tmp_path: Path) -> None:
    runtime = _runtime()
    secure = _secure(runtime)
    body = dict(secure)
    body.pop("receipt_sha256")
    body["parent_runtime_dependency_receipt_sha256"] = "0" * 64
    secure = _with_digest(body)
    with pytest.raises(ValueError, match="another runtime receipt"):
        initial_env.attest_loader_initial_environment(
            runtime_receipt=runtime,
            secure_receipt=secure,
            proc_root=_proc(tmp_path, environ=b"LD_LIBRARY_PATH=/g4:/root\0"),
        )


def test_process_identity_mismatch_fails(tmp_path: Path) -> None:
    runtime = _runtime()
    with pytest.raises(ValueError, match="different processes"):
        initial_env.attest_loader_initial_environment(
            runtime_receipt=runtime,
            secure_receipt=_secure(runtime, starttime=999),
            proc_root=_proc(tmp_path, environ=b"LD_LIBRARY_PATH=/g4:/root\0"),
        )


def test_secure_receipt_requires_auxv_record(tmp_path: Path) -> None:
    runtime = _runtime()
    secure = _secure(runtime)
    body = dict(secure)
    body.pop("receipt_sha256")
    body["auxv"] = "not-a-record"
    secure = _with_digest(body)
    with pytest.raises(ValueError, match="no auxv record"):
        initial_env.attest_loader_initial_environment(
            runtime_receipt=runtime,
            secure_receipt=secure,
            proc_root=_proc(tmp_path, environ=b"LD_LIBRARY_PATH=/g4:/root\0"),
        )


def test_environment_change_between_reads_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = _runtime()
    proc_root = _proc(tmp_path, environ=b"LD_LIBRARY_PATH=/g4:/root\0")
    original = initial_env._read_proc_bytes
    environ_reads = 0

    def mutate(proc_dir: Path, name: str, *, label: str) -> bytes:
        nonlocal environ_reads
        if name == "environ":
            environ_reads += 1
            if environ_reads == 2:
                return b"LD_LIBRARY_PATH=/changed\0"
        return original(proc_dir, name, label=label)

    monkeypatch.setattr(initial_env, "_read_proc_bytes", mutate)
    with pytest.raises(ValueError, match="changed during attestation"):
        initial_env.attest_loader_initial_environment(
            runtime_receipt=runtime,
            secure_receipt=_secure(runtime),
            proc_root=proc_root,
        )


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux procfs contract")
def test_real_procfs_keeps_launch_region_when_program_changes_environ() -> None:
    marker = "ccb_launch_before"
    code = (
        "import os,sys,time; "
        "os.environ['CCB_LAUNCH_MARKER']='ccb_runtime_after'; "
        "print('ready', flush=True); time.sleep(5)"
    )
    env = dict(os.environ)
    env["CCB_LAUNCH_MARKER"] = marker
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "ready"
        proc_dir = Path("/proc") / str(proc.pid)
        starttime = initial_env._read_process_starttime(proc_dir)
        raw = (proc_dir / "environ").read_bytes()
        assert b"CCB_LAUNCH_MARKER=ccb_launch_before" in raw.split(b"\0")
        assert b"CCB_LAUNCH_MARKER=ccb_runtime_after" not in raw.split(b"\0")

        runtime = _runtime(
            pid=proc.pid,
            starttime=starttime,
            ld_library_path=(
                os.environ.get("LD_LIBRARY_PATH", "").encode("utf-8")
                if "LD_LIBRARY_PATH" in os.environ
                else None
            ),
            marker=marker.encode("utf-8"),
        )
        # Reconstruct every tracked runtime value from the actual procfs snapshot.
        parsed = initial_env._tracked_environment(raw, set(runtime["loader_environment"]))
        runtime_body = dict(runtime)
        runtime_body.pop("receipt_sha256")
        runtime_body["loader_environment"] = {
            key: _env_record(value) for key, value in parsed.items()
        }
        runtime = _with_digest(runtime_body)
        result = initial_env.attest_loader_initial_environment(
            runtime_receipt=runtime,
            secure_receipt=_secure(
                runtime, pid=proc.pid, starttime=starttime, at_secure=0
            ),
        )
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    assert result["tracked_key_semantics"]["CCB_LAUNCH_MARKER"][
        "presence_inference"
    ] == "OBSERVED_AT_ATTESTATION_BOUNDARY"
