from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.audit.geant4_tool_probe_binding import bind_tool_probes


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _with_digest(body: dict[str, object]) -> dict[str, object]:
    result = dict(body)
    result["receipt_sha256"] = hashlib.sha256(_canonical_bytes(body)).hexdigest()
    return result


def _make_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _tool_record(path: Path) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    payload = resolved.read_bytes()
    record: dict[str, object] = {
        "path": str(path.absolute()),
        "resolved_path": str(resolved),
        "resolved_bytes": len(payload),
        "resolved_sha256": hashlib.sha256(payload).hexdigest(),
        "path_is_symlink": path.is_symlink(),
        "probe_returncode": 0,
        "probe_stdout": "legacy parent probe\n",
        "probe_stderr": "",
        "probe_stdout_sha256": hashlib.sha256(
            b"legacy parent probe\n"
        ).hexdigest(),
        "probe_stderr_sha256": hashlib.sha256(b"").hexdigest(),
    }
    if path.is_symlink():
        record["symlink_target"] = path.readlink().as_posix()
    return record


def _parent(cmake: Path, cxx: Path) -> dict[str, object]:
    body: dict[str, object] = {
        "schema": "ccb_geant4_cmake_toolchain_attestation_v1",
        "status": "PASS",
        "tools": {
            "cmake": _tool_record(cmake),
            "cxx_compiler": _tool_record(cxx),
        },
        "fixture": True,
    }
    return _with_digest(body)


def test_bound_probe_executes_same_opened_tool_bytes(tmp_path: Path) -> None:
    cmake = tmp_path / "cmake"
    cxx = tmp_path / "cxx"
    _make_executable(cmake, "#!/bin/sh\necho 'cmake bound 1'\n")
    _make_executable(cxx, "#!/bin/sh\necho 'cxx bound 2'\n")

    result = bind_tool_probes(_parent(cmake, cxx))

    assert result["status"] == "PASS"
    assert result["schema"] == "ccb_geant4_tool_probe_binding_v1"
    assert result["tools"]["cmake"]["probe_exec_binding"] == (
        "LINUX_PROC_SELF_FD_OPEN_FILE_V1"
    )
    assert "cmake bound 1" in result["tools"]["cmake"]["probe_stdout"]
    assert result["tools"]["cxx_compiler"]["opened_bytes_stable_pre_post"] is True


def test_stable_symlink_alias_is_allowed_and_bound_to_target(tmp_path: Path) -> None:
    cmake_target = tmp_path / "cmake.real"
    cmake = tmp_path / "cmake"
    cxx = tmp_path / "cxx"
    _make_executable(cmake_target, "#!/bin/sh\necho 'cmake target'\n")
    cmake.symlink_to(cmake_target.name)
    _make_executable(cxx, "#!/bin/sh\necho 'cxx target'\n")

    result = bind_tool_probes(_parent(cmake, cxx))
    record = result["tools"]["cmake"]
    assert record["path_is_symlink"] is True
    assert record["symlink_target"] == cmake_target.name
    assert record["resolved_sha256"] == hashlib.sha256(
        cmake_target.read_bytes()
    ).hexdigest()


def test_symlink_target_transition_during_probe_fails_closed(tmp_path: Path) -> None:
    cmake_a = tmp_path / "cmake.a"
    cmake_b = tmp_path / "cmake.b"
    cmake = tmp_path / "cmake"
    cxx = tmp_path / "cxx"
    _make_executable(cmake_b, "#!/bin/sh\necho 'cmake B'\n")
    _make_executable(
        cmake_a,
        "#!/bin/sh\n"
        f"rm -f '{cmake}'\n"
        f"ln -s '{cmake_b.name}' '{cmake}'\n"
        "echo 'cmake A'\n",
    )
    cmake.symlink_to(cmake_a.name)
    _make_executable(cxx, "#!/bin/sh\necho cxx\n")
    parent = _parent(cmake, cxx)

    with pytest.raises(
        ValueError, match="path or resolved target changed during version probe"
    ):
        bind_tool_probes(parent)


def test_opened_tool_mutation_during_probe_fails_closed(tmp_path: Path) -> None:
    cmake = tmp_path / "cmake"
    cxx = tmp_path / "cxx"
    _make_executable(
        cmake,
        "#!/bin/sh\n"
        f"printf '\\n# changed\\n' >> '{cmake}'\n"
        "echo mutated\n",
    )
    _make_executable(cxx, "#!/bin/sh\necho cxx\n")
    parent = _parent(cmake, cxx)

    with pytest.raises(ValueError, match="changed during version probe"):
        bind_tool_probes(parent)


def test_parent_tool_bytes_changed_before_probe_fails_closed(tmp_path: Path) -> None:
    cmake = tmp_path / "cmake"
    cxx = tmp_path / "cxx"
    _make_executable(cmake, "#!/bin/sh\necho old\n")
    _make_executable(cxx, "#!/bin/sh\necho cxx\n")
    parent = _parent(cmake, cxx)
    _make_executable(cmake, "#!/bin/sh\necho new\n")

    with pytest.raises(ValueError, match="differs from parent attestation"):
        bind_tool_probes(parent)


def test_nonzero_probe_fails_closed(tmp_path: Path) -> None:
    cmake = tmp_path / "cmake"
    cxx = tmp_path / "cxx"
    _make_executable(cmake, "#!/bin/sh\necho nope >&2\nexit 9\n")
    _make_executable(cxx, "#!/bin/sh\necho cxx\n")

    with pytest.raises(ValueError, match="version probe returned 9"):
        bind_tool_probes(_parent(cmake, cxx))
