from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest

import tools.audit.geant4_loader_secure_state_attestation as loader


def _with_digest(body: dict[str, object]) -> dict[str, object]:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    result = dict(body)
    result["receipt_sha256"] = hashlib.sha256(payload).hexdigest()
    return result


def _env_record(value: str | None) -> dict[str, object]:
    if value is None:
        return {"present": False}
    raw = value.encode("utf-8")
    return {
        "present": True,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "base64": "fixture",
        "utf8": value,
    }


def _runtime(*, pid: int = 4242, starttime: int = 123456, tunables: str | None = None):
    body: dict[str, object] = {
        "schema": loader.RUNTIME_RECEIPT_SCHEMA,
        "status": "PASS",
        "process": {"pid": pid, "starttime_ticks": starttime},
        "loader_environment": {
            "LD_LIBRARY_PATH": _env_record("/g4:/root"),
            "LD_PRELOAD": _env_record(None),
            "LD_AUDIT": _env_record(None),
            "GLIBC_TUNABLES": _env_record(tunables),
        },
    }
    return _with_digest(body)


def _coobs(runtime: dict[str, object], *, pid: int = 4242, starttime: int = 123456):
    return _with_digest(
        {
            "schema": loader.COOBS_RECEIPT_SCHEMA,
            "status": "PASS",
            "parent_runtime_dependency_receipt_sha256": runtime["receipt_sha256"],
            "process": {"pid": pid, "starttime_ticks": starttime},
        }
    )


def _fake_stat(pid: int, starttime: int) -> str:
    tail = ["S", *(["0"] * 18), str(starttime), *(["0"] * 8)]
    return f"{pid} (fixture proc) " + " ".join(tail) + "\n"


def _auxv(*pairs: tuple[int, int]) -> bytes:
    return b"".join(struct.pack("<QQ", key, value) for key, value in pairs)


def _proc(tmp_path: Path, *, auxv: bytes, pid: int = 4242, starttime: int = 123456):
    root = tmp_path / "proc"
    proc_dir = root / str(pid)
    proc_dir.mkdir(parents=True)
    (proc_dir / "stat").write_text(_fake_stat(pid, starttime), encoding="ascii")
    (proc_dir / "auxv").write_bytes(auxv)
    return root


def _nominal_auxv(at_secure: int) -> bytes:
    return _auxv(
        (loader.AT_UID, 1000),
        (loader.AT_EUID, 1000),
        (loader.AT_GID, 1000),
        (loader.AT_EGID, 1000),
        (loader.AT_SECURE, at_secure),
        (loader.AT_NULL, 0),
    )


def test_nonsecure_state_marks_loader_env_eligible_not_proven(tmp_path: Path) -> None:
    runtime = _runtime()
    result = loader.attest_loader_secure_state(
        runtime_receipt=runtime,
        coobservation_receipt=_coobs(runtime),
        proc_root=_proc(tmp_path, auxv=_nominal_auxv(0)),
    )
    assert result["status"] == "PASS"
    assert result["auxv"]["at_secure"] == 0
    assert result["effective_loader_secure_state"] == "UNRESOLVED_KERNEL_AT_SECURE_ZERO"
    assert (
        result["loader_environment_semantics"]["LD_LIBRARY_PATH"]["interpretation"]
        == "UNRESOLVED_DO_NOT_USE_AS_LOADER_SEARCH_AUTHORITY_UNTIL_PRE_EXEC_STATE_IS_BOUND"
    )


def test_secure_state_blocks_loader_env_as_search_authority(tmp_path: Path) -> None:
    runtime = _runtime()
    result = loader.attest_loader_secure_state(
        runtime_receipt=runtime,
        coobservation_receipt=_coobs(runtime),
        proc_root=_proc(tmp_path, auxv=_nominal_auxv(1)),
    )
    assert result["auxv"]["at_secure"] == 1
    assert result["effective_loader_secure_state"] == "SECURE_CONFIRMED_BY_KERNEL_AT_SECURE"
    assert "DO_NOT_USE_AS_LOADER_SEARCH_AUTHORITY" in result[
        "loader_environment_semantics"
    ]["LD_LIBRARY_PATH"]["interpretation"]


def test_duplicate_at_secure_fails(tmp_path: Path) -> None:
    runtime = _runtime()
    auxv = _auxv(
        (loader.AT_SECURE, 0),
        (loader.AT_SECURE, 1),
        (loader.AT_NULL, 0),
    )
    with pytest.raises(ValueError, match="duplicate auxiliary-vector key"):
        loader.attest_loader_secure_state(
            runtime_receipt=runtime,
            coobservation_receipt=_coobs(runtime),
            proc_root=_proc(tmp_path, auxv=auxv),
        )


def test_missing_at_secure_fails(tmp_path: Path) -> None:
    runtime = _runtime()
    auxv = _auxv((loader.AT_UID, 1000), (loader.AT_NULL, 0))
    with pytest.raises(ValueError, match="missing AT_SECURE"):
        loader.attest_loader_secure_state(
            runtime_receipt=runtime,
            coobservation_receipt=_coobs(runtime),
            proc_root=_proc(tmp_path, auxv=auxv),
        )


def test_nonboolean_at_secure_fails(tmp_path: Path) -> None:
    runtime = _runtime()
    with pytest.raises(ValueError, match="not boolean"):
        loader.attest_loader_secure_state(
            runtime_receipt=runtime,
            coobservation_receipt=_coobs(runtime),
            proc_root=_proc(tmp_path, auxv=_nominal_auxv(2)),
        )


def test_malformed_auxv_length_fails(tmp_path: Path) -> None:
    runtime = _runtime()
    with pytest.raises(ValueError, match="length"):
        loader.attest_loader_secure_state(
            runtime_receipt=runtime,
            coobservation_receipt=_coobs(runtime),
            proc_root=_proc(tmp_path, auxv=b"broken"),
        )


def test_wrong_parent_receipt_fails(tmp_path: Path) -> None:
    runtime = _runtime()
    coobs = _coobs(runtime)
    coobs["parent_runtime_dependency_receipt_sha256"] = "0" * 64
    body = dict(coobs)
    body.pop("receipt_sha256")
    coobs["receipt_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="another runtime receipt"):
        loader.attest_loader_secure_state(
            runtime_receipt=runtime,
            coobservation_receipt=coobs,
            proc_root=_proc(tmp_path, auxv=_nominal_auxv(0)),
        )


def test_process_identity_mismatch_fails(tmp_path: Path) -> None:
    runtime = _runtime()
    with pytest.raises(ValueError, match="different processes"):
        loader.attest_loader_secure_state(
            runtime_receipt=runtime,
            coobservation_receipt=_coobs(runtime, starttime=999),
            proc_root=_proc(tmp_path, auxv=_nominal_auxv(0)),
        )


def test_post_start_tunable_observation_cannot_upgrade_at_secure_zero(tmp_path: Path) -> None:
    runtime = _runtime(tunables="glibc.rtld.enable_secure=1")
    result = loader.attest_loader_secure_state(
        runtime_receipt=runtime,
        coobservation_receipt=_coobs(runtime),
        proc_root=_proc(tmp_path, auxv=_nominal_auxv(0)),
    )
    assert result["effective_loader_secure_state"] == "UNRESOLVED_KERNEL_AT_SECURE_ZERO"
    assert "UNRESOLVED" in result["loader_environment_semantics"]["LD_LIBRARY_PATH"][
        "interpretation"
    ]


def test_at_null_must_terminate_auxv(tmp_path: Path) -> None:
    runtime = _runtime()
    auxv = _auxv((loader.AT_SECURE, 0), (loader.AT_NULL, 0), (999, 1))
    with pytest.raises(ValueError, match="follows AT_NULL"):
        loader.attest_loader_secure_state(
            runtime_receipt=runtime,
            coobservation_receipt=_coobs(runtime),
            proc_root=_proc(tmp_path, auxv=auxv),
        )
