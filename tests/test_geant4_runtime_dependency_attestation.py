from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.audit import geant4_runtime_dependency_attestation as runtime_attest
from tools.audit.geant4_runtime_dependency_attestation import attest_runtime_dependencies


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _with_digest(body: dict[str, object]) -> dict[str, object]:
    result = dict(body)
    result["receipt_sha256"] = hashlib.sha256(_canonical_bytes(body)).hexdigest()
    return result


def _parent(executable: Path) -> dict[str, object]:
    payload = executable.read_bytes()
    return _with_digest(
        {
            "schema": "ccb_geant4_build_binding_final_v1",
            "status": "PASS",
            "executable": {
                "path": str(executable.resolve()),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            },
            "fixture": True,
        }
    )


def _dev(st: os.stat_result) -> str:
    return f"{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}"


def _map_line(path: Path, start: int, *, perms: str = "r-xp") -> str:
    st = path.stat()
    return (
        f"{start:08x}-{start + 0x1000:08x} {perms} 00000000 "
        f"{_dev(st)} {st.st_ino} {path.resolve()}\n"
    )


def _fake_stat(pid: int, starttime: int) -> str:
    tail = ["S", *(["0"] * 18), str(starttime), *(["0"] * 8)]
    return f"{pid} (fixture proc) " + " ".join(tail) + "\n"


def _fake_proc(
    tmp_path: Path,
    *,
    executable: Path,
    mapped_objects: list[Path],
    environ: bytes = b"",
    extra_maps: str = "",
) -> tuple[Path, int]:
    proc_root = tmp_path / "proc"
    pid = 4242
    proc_dir = proc_root / str(pid)
    proc_dir.mkdir(parents=True)
    (proc_dir / "exe").symlink_to(executable.resolve())
    (proc_dir / "stat").write_text(_fake_stat(pid, 123456), encoding="ascii")
    lines = [_map_line(executable, 0x400000)]
    for index, path in enumerate(mapped_objects, start=1):
        lines.append(_map_line(path, 0x400000 + index * 0x20000))
    (proc_dir / "maps").write_text("".join(lines) + extra_maps, encoding="utf-8")
    (proc_dir / "environ").write_bytes(environ)
    return proc_root, pid


def _make_file(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)
    path.chmod(0o755)


def test_attests_file_backed_executable_objects_and_loader_env(tmp_path: Path) -> None:
    executable = tmp_path / "hibeam_g4"
    g4 = tmp_path / "libG4run.so.11"
    root = tmp_path / "libCore.so.6"
    _make_file(executable, b"fixture executable")
    _make_file(g4, b"geant4 bytes")
    _make_file(root, b"root bytes")
    proc_root, pid = _fake_proc(
        tmp_path,
        executable=executable,
        mapped_objects=[g4, root],
        environ=b"LD_LIBRARY_PATH=/g4:/root\0LD_PRELOAD=/x/pre.so\0SECRET=omit-me\0",
    )

    result = attest_runtime_dependencies(
        final_receipt=_parent(executable),
        pid=pid,
        requirements=[("geant4", "libG4*.so*"), ("root", "libCore.so*")],
        proc_root=proc_root,
    )

    assert result["status"] == "PASS"
    assert result["schema"] == "ccb_geant4_runtime_dependency_attestation_v1"
    assert len(result["mapped_executable_objects"]) == 3
    assert result["loader_environment"]["LD_LIBRARY_PATH"]["utf8"] == "/g4:/root"
    assert "SECRET" not in result["loader_environment"]
    assert result["required_object_matches"]["geant4"]["object_indexes"]


def test_live_executable_bytes_must_match_final_receipt(tmp_path: Path) -> None:
    expected = tmp_path / "expected"
    live = tmp_path / "live"
    lib = tmp_path / "libG4x.so"
    _make_file(expected, b"expected bytes")
    _make_file(live, b"different live bytes")
    _make_file(lib, b"library")
    proc_root, pid = _fake_proc(tmp_path, executable=live, mapped_objects=[lib])

    with pytest.raises(ValueError, match="bytes differ from final build receipt"):
        attest_runtime_dependencies(
            final_receipt=_parent(expected),
            pid=pid,
            requirements=[("geant4", "libG4*.so*")],
            proc_root=proc_root,
        )


def test_required_runtime_object_must_be_present(tmp_path: Path) -> None:
    executable = tmp_path / "hibeam_g4"
    other = tmp_path / "libOther.so"
    _make_file(executable, b"fixture executable")
    _make_file(other, b"other")
    proc_root, pid = _fake_proc(tmp_path, executable=executable, mapped_objects=[other])

    with pytest.raises(ValueError, match="pattern matched nothing"):
        attest_runtime_dependencies(
            final_receipt=_parent(executable),
            pid=pid,
            requirements=[("geant4", "libG4*.so*")],
            proc_root=proc_root,
        )


def test_same_path_replaced_after_mapping_fails_inode_identity(tmp_path: Path) -> None:
    executable = tmp_path / "hibeam_g4"
    library = tmp_path / "libG4run.so"
    _make_file(executable, b"fixture executable")
    _make_file(library, b"old library")
    proc_root, pid = _fake_proc(tmp_path, executable=executable, mapped_objects=[library])

    replacement = tmp_path / "replacement"
    _make_file(replacement, b"new bytes but same soname path")
    replacement.replace(library)

    with pytest.raises(ValueError, match="no longer names the mapped inode"):
        attest_runtime_dependencies(
            final_receipt=_parent(executable),
            pid=pid,
            requirements=[("geant4", "libG4*.so*")],
            proc_root=proc_root,
        )


def test_same_inode_same_size_mutation_after_hash_fails_metadata_recheck(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "hibeam_g4"
    library = tmp_path / "libG4run.so"
    _make_file(executable, b"fixture executable")
    _make_file(library, b"library-A")
    proc_root, pid = _fake_proc(tmp_path, executable=executable, mapped_objects=[library])

    original = runtime_attest._hash_open_fd
    mutated = False

    def mutate_after_library_hash(fd: int, *, label: str) -> dict[str, object]:
        nonlocal mutated
        record = original(fd, label=label)
        if "mapped executable object" in label and library.name in label and not mutated:
            library.write_bytes(b"library-B")
            library.chmod(0o755)
            mutated = True
        return record

    monkeypatch.setattr(runtime_attest, "_hash_open_fd", mutate_after_library_hash)

    with pytest.raises(ValueError, match="path changed after hashing"):
        attest_runtime_dependencies(
            final_receipt=_parent(executable),
            pid=pid,
            requirements=[("geant4", "libG4*.so*")],
            proc_root=proc_root,
        )


def test_deleted_executable_mapping_fails_closed(tmp_path: Path) -> None:
    executable = tmp_path / "hibeam_g4"
    library = tmp_path / "libG4run.so"
    _make_file(executable, b"fixture executable")
    _make_file(library, b"library")
    st = library.stat()
    deleted = (
        f"00800000-00801000 r-xp 00000000 {_dev(st)} {st.st_ino} "
        f"{library.resolve()} (deleted)\n"
    )
    proc_root, pid = _fake_proc(
        tmp_path,
        executable=executable,
        mapped_objects=[],
        extra_maps=deleted,
    )

    with pytest.raises(ValueError, match="mapping is deleted"):
        attest_runtime_dependencies(
            final_receipt=_parent(executable),
            pid=pid,
            requirements=[("geant4", "libG4*.so*")],
            proc_root=proc_root,
        )


def test_anonymous_executable_mapping_fails_closed(tmp_path: Path) -> None:
    executable = tmp_path / "hibeam_g4"
    library = tmp_path / "libG4run.so"
    _make_file(executable, b"fixture executable")
    _make_file(library, b"library")
    proc_root, pid = _fake_proc(
        tmp_path,
        executable=executable,
        mapped_objects=[library],
        extra_maps="00900000-00901000 rwxp 00000000 00:00 0\n",
    )

    with pytest.raises(ValueError, match="anonymous executable mapping"):
        attest_runtime_dependencies(
            final_receipt=_parent(executable),
            pid=pid,
            requirements=[("geant4", "libG4*.so*")],
            proc_root=proc_root,
        )


def test_loader_environment_changes_receipt_identity(tmp_path: Path) -> None:
    executable = tmp_path / "hibeam_g4"
    library = tmp_path / "libG4run.so"
    _make_file(executable, b"fixture executable")
    _make_file(library, b"library")
    proc_root, pid = _fake_proc(
        tmp_path,
        executable=executable,
        mapped_objects=[library],
        environ=b"LD_LIBRARY_PATH=/a\0",
    )
    first = attest_runtime_dependencies(
        final_receipt=_parent(executable),
        pid=pid,
        requirements=[("geant4", "libG4*.so*")],
        proc_root=proc_root,
    )
    (proc_root / str(pid) / "environ").write_bytes(b"LD_LIBRARY_PATH=/b\0")
    second = attest_runtime_dependencies(
        final_receipt=_parent(executable),
        pid=pid,
        requirements=[("geant4", "libG4*.so*")],
        proc_root=proc_root,
    )

    assert first["loader_environment"]["LD_LIBRARY_PATH"]["sha256"] != second[
        "loader_environment"
    ]["LD_LIBRARY_PATH"]["sha256"]
    assert first["receipt_sha256"] != second["receipt_sha256"]


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux procfs contract")
def test_real_procfs_python_process_round_trip() -> None:
    executable = Path(sys.executable).resolve()
    proc = subprocess.Popen(
        [
            str(executable),
            "-c",
            'import time; print("READY", flush=True); time.sleep(5)',
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "READY"
        result = attest_runtime_dependencies(
            final_receipt=_parent(executable),
            pid=proc.pid,
            requirements=[("python-entrypoint", executable.name)],
        )
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    assert result["status"] == "PASS"
    assert result["process"]["pid"] == proc.pid
    assert result["required_object_matches"]["python-entrypoint"]["object_indexes"]
