from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path

import pytest

import tools.audit.geant4_runtime_link_coobservation as coobs
from tools.audit.geant4_runtime_link_coobservation import (
    FINAL_RECEIPT_SCHEMA,
    RUNTIME_RECEIPT_SCHEMA,
    _digest_body,
    attest_runtime_link_coobservation,
)


def _receipt(body: dict[str, object]) -> dict[str, object]:
    result = dict(body)
    result["receipt_sha256"] = _digest_body(body)
    return result


def _write_elf(
    path: Path,
    *,
    needed: tuple[str, ...] = (),
    soname: str | None = None,
    interpreter: str | None = None,
) -> None:
    program_count = 2 + int(interpreter is not None)
    program_offset = 64
    program_entry_size = 56
    payload = bytearray(0x600)
    payload[:16] = b"\x7fELF" + bytes([2, 1, 1, 0]) + bytes(8)
    struct.pack_into(
        "<HHIQQQIHHHHHH",
        payload,
        16,
        3,
        62,
        1,
        0,
        program_offset,
        0,
        0,
        64,
        program_entry_size,
        program_count,
        0,
        0,
        0,
    )

    strings = bytearray(b"\0")
    offsets: dict[str, int] = {}
    for value in list(needed) + ([soname] if soname is not None else []):
        if value not in offsets:
            offsets[value] = len(strings)
            strings.extend(value.encode("utf-8"))
            strings.append(0)
    strings_file_offset = 0x300
    strings_virtual_address = 0x4300
    payload[strings_file_offset : strings_file_offset + len(strings)] = strings

    dynamic_entries = [(1, offsets[value]) for value in needed]
    dynamic_entries.extend([(5, strings_virtual_address), (10, len(strings))])
    if soname is not None:
        dynamic_entries.append((14, offsets[soname]))
    dynamic_entries.append((0, 0))
    dynamic_offset = 0x400
    for index, (tag, value) in enumerate(dynamic_entries):
        struct.pack_into("<qQ", payload, dynamic_offset + index * 16, tag, value)

    header_index = 0
    struct.pack_into(
        "<IIQQQQQQ",
        payload,
        program_offset + header_index * program_entry_size,
        1,
        5,
        0x200,
        0x4200,
        0,
        len(payload) - 0x200,
        len(payload) - 0x200,
        0x1000,
    )
    header_index += 1
    if interpreter is not None:
        raw = interpreter.encode("utf-8") + b"\0"
        payload[0x200 : 0x200 + len(raw)] = raw
        struct.pack_into(
            "<IIQQQQQQ",
            payload,
            program_offset + header_index * program_entry_size,
            3,
            4,
            0x200,
            0x4200,
            0,
            len(raw),
            len(raw),
            1,
        )
        header_index += 1
    struct.pack_into(
        "<IIQQQQQQ",
        payload,
        program_offset + header_index * program_entry_size,
        2,
        6,
        dynamic_offset,
        0x4400,
        0,
        len(dynamic_entries) * 16,
        len(dynamic_entries) * 16,
        8,
    )
    path.write_bytes(payload)


def _stat_text(pid: int, starttime: int) -> str:
    tail = ["S"] + ["0"] * 18 + [str(starttime)] + ["0"] * 5
    return f"{pid} (fixture) " + " ".join(tail) + "\n"


def _mapped_record(path: Path, *, start: int) -> dict[str, object]:
    payload = path.read_bytes()
    st = path.stat()
    return {
        "device_major": os.major(st.st_dev),
        "device_minor": os.minor(st.st_dev),
        "inode": st.st_ino,
        "paths": [str(path.resolve())],
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "segments": [
            {
                "start": start,
                "end": start + 0x1000,
                "perms": "r-xp",
                "offset": 0,
            }
        ],
    }


def _maps_line(record: dict[str, object]) -> str:
    segment = record["segments"][0]
    return (
        f"{segment['start']:x}-{segment['end']:x} {segment['perms']} "
        f"{segment['offset']:08x} {record['device_major']:02x}:"
        f"{record['device_minor']:02x} {record['inode']} {record['paths'][0]}\n"
    )


def _fixture(
    tmp_path: Path,
    *,
    needed: tuple[str, ...] = ("libfixture.so.1",),
    interpreter_symlink: bool = True,
) -> tuple[dict[str, object], dict[str, object], Path, Path, Path]:
    loader = tmp_path / "ld-fixture-real.so"
    library = tmp_path / "libfixture.so.1.2.3"
    executable = tmp_path / "generator"
    _write_elf(loader, soname="ld-fixture.so")
    _write_elf(library, soname="libfixture.so.1")
    interp = loader
    if interpreter_symlink:
        interp = tmp_path / "ld-fixture.so"
        interp.symlink_to(loader.name)
    _write_elf(executable, needed=needed, interpreter=str(interp))

    records = [
        _mapped_record(executable, start=0x1000),
        _mapped_record(loader, start=0x3000),
        _mapped_record(library, start=0x5000),
    ]
    pid = 4242
    starttime = 123456
    proc_dir = tmp_path / "proc" / str(pid)
    proc_dir.mkdir(parents=True)
    (proc_dir / "stat").write_text(_stat_text(pid, starttime), encoding="ascii")
    (proc_dir / "maps").write_text(
        "".join(_maps_line(record) for record in records), encoding="utf-8"
    )

    final = _receipt(
        {
            "schema": FINAL_RECEIPT_SCHEMA,
            "status": "PASS",
            "executable": {
                "path": str(executable.resolve()),
                "bytes": records[0]["bytes"],
                "sha256": records[0]["sha256"],
            },
        }
    )
    runtime = _receipt(
        {
            "schema": RUNTIME_RECEIPT_SCHEMA,
            "status": "PASS",
            "parent_final_build_receipt_sha256": final["receipt_sha256"],
            "process": {
                "pid": pid,
                "starttime_ticks": starttime,
                "executable": {
                    "bytes": records[0]["bytes"],
                    "sha256": records[0]["sha256"],
                    "device_major": records[0]["device_major"],
                    "device_minor": records[0]["device_minor"],
                    "inode": records[0]["inode"],
                },
            },
            "mapped_executable_objects": records,
        }
    )
    return final, runtime, tmp_path / "proc", library, loader


def test_nominal_same_descriptor_link_closure_with_symlink_interpreter(
    tmp_path: Path,
) -> None:
    final, runtime, proc_root, _library, _loader = _fixture(tmp_path)
    result = attest_runtime_link_coobservation(
        final_receipt=final,
        runtime_receipt=runtime,
        proc_root=proc_root,
    )
    assert result["status"] == "PASS"
    assert result["process"]["executable_object_index"] == 0
    assert result["direct_dependency_matches"] == {"libfixture.so.1": 2}
    assert result["interpreter_object_index"] == 1
    assert result["objects"][2]["elf"]["dt_soname"] == "libfixture.so.1"


def test_absolute_needed_matches_by_stable_path_resolution(tmp_path: Path) -> None:
    library = tmp_path / "libprivate-real.so"
    _write_elf(library)
    alias = tmp_path / "libprivate.so"
    alias.symlink_to(library.name)
    final, runtime, proc_root, default_library, _loader = _fixture(
        tmp_path,
        needed=(str(alias),),
    )
    runtime["mapped_executable_objects"][2] = _mapped_record(library, start=0x5000)
    pid = runtime["process"]["pid"]
    records = runtime["mapped_executable_objects"]
    (proc_root / str(pid) / "maps").write_text(
        "".join(_maps_line(record) for record in records), encoding="utf-8"
    )
    body = dict(runtime)
    body.pop("receipt_sha256")
    runtime = _receipt(body)
    result = attest_runtime_link_coobservation(
        final_receipt=final, runtime_receipt=runtime, proc_root=proc_root
    )
    assert result["direct_dependency_matches"] == {str(alias): 2}
    assert default_library.exists()


def test_relative_needed_requires_cwd_provenance(tmp_path: Path) -> None:
    final, runtime, proc_root, _library, _loader = _fixture(
        tmp_path, needed=("relative/libfixture.so",)
    )
    with pytest.raises(ValueError, match="requires cwd provenance"):
        attest_runtime_link_coobservation(
            final_receipt=final, runtime_receipt=runtime, proc_root=proc_root
        )


def test_duplicate_soname_is_ambiguous(tmp_path: Path) -> None:
    final, runtime, proc_root, _library, _loader = _fixture(tmp_path)
    duplicate = tmp_path / "other-libfixture.so"
    _write_elf(duplicate, soname="libfixture.so.1")
    record = _mapped_record(duplicate, start=0x7000)
    runtime["mapped_executable_objects"].append(record)
    pid = runtime["process"]["pid"]
    (proc_root / str(pid) / "maps").write_text(
        "".join(_maps_line(r) for r in runtime["mapped_executable_objects"]),
        encoding="utf-8",
    )
    body = dict(runtime)
    body.pop("receipt_sha256")
    runtime = _receipt(body)
    with pytest.raises(ValueError, match="matched 2 mapped objects"):
        attest_runtime_link_coobservation(
            final_receipt=final, runtime_receipt=runtime, proc_root=proc_root
        )


def test_malformed_elf_magic_fails_closed_instead_of_becoming_nonelf(
    tmp_path: Path,
) -> None:
    final, runtime, proc_root, library, _loader = _fixture(tmp_path)
    library.write_bytes(b"\x7fELFbroken")
    record = _mapped_record(library, start=0x5000)
    runtime["mapped_executable_objects"][2] = record
    pid = runtime["process"]["pid"]
    (proc_root / str(pid) / "maps").write_text(
        "".join(_maps_line(r) for r in runtime["mapped_executable_objects"]),
        encoding="utf-8",
    )
    body = dict(runtime)
    body.pop("receipt_sha256")
    runtime = _receipt(body)
    with pytest.raises(ValueError, match="not an ELF|only ELF64|program"):
        attest_runtime_link_coobservation(
            final_receipt=final, runtime_receipt=runtime, proc_root=proc_root
        )


def test_path_replacement_during_open_descriptor_read_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    final, runtime, proc_root, library, _loader = _fixture(tmp_path)
    replacement = tmp_path / "replacement.so"
    _write_elf(replacement, soname="libfixture.so.1")
    original = coobs._fd_snapshot
    swapped = False

    def swap_then_read(fd: int, *, label: str):
        nonlocal swapped
        if "runtime object 2" in label and not swapped:
            os.replace(replacement, library)
            swapped = True
        return original(fd, label=label)

    monkeypatch.setattr(coobs, "_fd_snapshot", swap_then_read)
    with pytest.raises(ValueError, match="pathname resolution changed"):
        attest_runtime_link_coobservation(
            final_receipt=final, runtime_receipt=runtime, proc_root=proc_root
        )


def test_mapping_projection_mismatch_blocks(tmp_path: Path) -> None:
    final, runtime, proc_root, _library, _loader = _fixture(tmp_path)
    pid = runtime["process"]["pid"]
    maps = proc_root / str(pid) / "maps"
    maps.write_text(maps.read_text().replace("1000-2000", "1100-2100", 1))
    with pytest.raises(ValueError, match="mapping projection differs"):
        attest_runtime_link_coobservation(
            final_receipt=final, runtime_receipt=runtime, proc_root=proc_root
        )


def test_runtime_receipt_from_other_build_blocks(tmp_path: Path) -> None:
    final, runtime, proc_root, _library, _loader = _fixture(tmp_path)
    body = dict(runtime)
    body.pop("receipt_sha256")
    body["parent_final_build_receipt_sha256"] = "0" * 64
    runtime = _receipt(body)
    with pytest.raises(ValueError, match="another final build"):
        attest_runtime_link_coobservation(
            final_receipt=final, runtime_receipt=runtime, proc_root=proc_root
        )
