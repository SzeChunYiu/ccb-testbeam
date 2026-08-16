from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path

import pytest

from tools.audit.geant4_elf_link_attestation import (
    FINAL_RECEIPT_SCHEMA,
    RUNTIME_RECEIPT_SCHEMA,
    _digest_body,
    attest_elf_link_metadata,
    parse_elf_link_metadata,
)


def _write_elf(
    path: Path,
    *,
    needed: tuple[str, ...] = (),
    soname: str | None = None,
    interpreter: str | None = None,
    rpath: str | None = None,
    runpath: str | None = None,
) -> None:
    program_count = 2 + int(interpreter is not None)
    program_offset = 64
    program_entry_size = 56
    payload = bytearray(0x600)

    payload[:16] = (
        b"\x7fELF"
        + bytes([2, 1, 1, 0])
        + bytes(8)
    )
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
    all_strings = list(needed)
    for value in (soname, rpath, runpath):
        if value is not None:
            all_strings.append(value)
    for value in all_strings:
        if value not in offsets:
            offsets[value] = len(strings)
            strings.extend(value.encode("utf-8"))
            strings.append(0)

    strings_file_offset = 0x300
    strings_virtual_address = 0x4300
    payload[
        strings_file_offset : strings_file_offset + len(strings)
    ] = strings

    dynamic_entries: list[tuple[int, int]] = [
        (1, offsets[value])
        for value in needed
    ]
    dynamic_entries.extend(
        [
            (5, strings_virtual_address),
            (10, len(strings)),
        ]
    )
    if soname is not None:
        dynamic_entries.append((14, offsets[soname]))
    if rpath is not None:
        dynamic_entries.append((15, offsets[rpath]))
    if runpath is not None:
        dynamic_entries.append((29, offsets[runpath]))
    dynamic_entries.append((0, 0))

    dynamic_offset = 0x400
    for index, (tag, value) in enumerate(dynamic_entries):
        struct.pack_into(
            "<qQ",
            payload,
            dynamic_offset + index * 16,
            tag,
            value,
        )

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
        interpreter_bytes = interpreter.encode("utf-8") + b"\0"
        interpreter_offset = 0x200
        payload[
            interpreter_offset
            : interpreter_offset + len(interpreter_bytes)
        ] = interpreter_bytes
        struct.pack_into(
            "<IIQQQQQQ",
            payload,
            program_offset + header_index * program_entry_size,
            3,
            4,
            interpreter_offset,
            0x4200,
            0,
            len(interpreter_bytes),
            len(interpreter_bytes),
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


def _content_record(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _mapped_record(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    st = path.stat()
    return {
        "device_major": os.major(st.st_dev),
        "device_minor": os.minor(st.st_dev),
        "inode": st.st_ino,
        "paths": [str(path.resolve())],
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "segments": [],
    }


def _receipt(body: dict[str, object]) -> dict[str, object]:
    result = dict(body)
    result["receipt_sha256"] = _digest_body(body)
    return result


def _fixture_receipts(
    *,
    executable: Path,
    mapped_paths: list[Path],
) -> tuple[dict[str, object], dict[str, object]]:
    final = _receipt(
        {
            "schema": FINAL_RECEIPT_SCHEMA,
            "status": "PASS",
            "executable": _content_record(executable),
        }
    )
    runtime = _receipt(
        {
            "schema": RUNTIME_RECEIPT_SCHEMA,
            "status": "PASS",
            "parent_final_build_receipt_sha256": (
                final["receipt_sha256"]
            ),
            "process": {
                "executable": _content_record(executable),
            },
            "mapped_executable_objects": [
                _mapped_record(path)
                for path in mapped_paths
            ],
        }
    )
    return final, runtime


def test_nominal_versioned_soname_and_search_metadata(tmp_path: Path) -> None:
    loader = tmp_path / "ld-fixture.so"
    library = tmp_path / "libG4fixture.so.1.2.3"
    executable = tmp_path / "generator"

    _write_elf(loader, soname="ld-fixture.so")
    _write_elf(library, soname="libG4fixture.so.1")
    _write_elf(
        executable,
        needed=("libG4fixture.so.1",),
        interpreter=str(loader),
        rpath="/legacy/lib",
        runpath="/preferred/lib",
    )
    final, runtime = _fixture_receipts(
        executable=executable,
        mapped_paths=[executable, loader, library],
    )

    result = attest_elf_link_metadata(
        final_receipt=final,
        runtime_receipt=runtime,
    )

    assert result["status"] == "PASS"
    assert result["executable"]["elf"]["dt_rpath"] == "/legacy/lib"
    assert result["executable"]["elf"]["dt_runpath"] == "/preferred/lib"
    assert result["direct_dependency_matches"] == {
        "libG4fixture.so.1": 2
    }
    assert result["interpreter_object_index"] == 1


def test_duplicate_needed_is_retained_but_collapsed_for_closure(
    tmp_path: Path,
) -> None:
    library = tmp_path / "libfixture.so"
    executable = tmp_path / "generator"
    _write_elf(library, soname="libfixture.so")
    _write_elf(
        executable,
        needed=("libfixture.so", "libfixture.so"),
    )
    final, runtime = _fixture_receipts(
        executable=executable,
        mapped_paths=[executable, library],
    )

    result = attest_elf_link_metadata(
        final_receipt=final,
        runtime_receipt=runtime,
    )

    assert result["executable"]["elf"]["dt_needed"] == [
        "libfixture.so",
        "libfixture.so",
    ]
    assert result["direct_dependency_matches"] == {
        "libfixture.so": 1
    }


def test_dynamic_string_offset_outside_table_is_rejected(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "generator"
    _write_elf(executable, needed=("libfixture.so",))
    payload = bytearray(executable.read_bytes())
    dynamic_offset = 0x400
    struct.pack_into("<qQ", payload, dynamic_offset, 1, 0xFFFF)
    executable.write_bytes(payload)

    with pytest.raises(
        ValueError,
        match="offset outside dynamic string table",
    ):
        parse_elf_link_metadata(bytes(payload))


def test_mapped_object_mutation_after_runtime_receipt_is_rejected(
    tmp_path: Path,
) -> None:
    library = tmp_path / "libfixture.so"
    executable = tmp_path / "generator"
    _write_elf(library, soname="libfixture.so")
    _write_elf(executable, needed=("libfixture.so",))
    final, runtime = _fixture_receipts(
        executable=executable,
        mapped_paths=[executable, library],
    )
    library.write_bytes(library.read_bytes() + b"mutation")

    with pytest.raises(ValueError, match="differs from receipt"):
        attest_elf_link_metadata(
            final_receipt=final,
            runtime_receipt=runtime,
        )


def test_runtime_receipt_from_another_build_is_rejected(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "generator"
    _write_elf(executable)
    final, runtime = _fixture_receipts(
        executable=executable,
        mapped_paths=[executable],
    )
    body = dict(runtime)
    del body["receipt_sha256"]
    body["parent_final_build_receipt_sha256"] = "0" * 64
    other_runtime = _receipt(body)

    with pytest.raises(
        ValueError,
        match="belongs to another final build receipt",
    ):
        attest_elf_link_metadata(
            final_receipt=final,
            runtime_receipt=other_runtime,
        )


def test_missing_interpreter_mapping_is_rejected(tmp_path: Path) -> None:
    loader = tmp_path / "ld-fixture.so"
    executable = tmp_path / "generator"
    _write_elf(loader, soname="ld-fixture.so")
    _write_elf(executable, interpreter=str(loader))
    final, runtime = _fixture_receipts(
        executable=executable,
        mapped_paths=[executable],
    )

    with pytest.raises(ValueError, match="PT_INTERP matched 0"):
        attest_elf_link_metadata(
            final_receipt=final,
            runtime_receipt=runtime,
        )


def test_same_filename_family_with_wrong_soname_is_rejected(
    tmp_path: Path,
) -> None:
    library = tmp_path / "libG4fixture.so.1.2.3"
    executable = tmp_path / "generator"
    _write_elf(library, soname="libG4fixture.so.2")
    _write_elf(executable, needed=("libG4fixture.so.1",))
    final, runtime = _fixture_receipts(
        executable=executable,
        mapped_paths=[executable, library],
    )

    with pytest.raises(ValueError, match="matched 0 runtime objects"):
        attest_elf_link_metadata(
            final_receipt=final,
            runtime_receipt=runtime,
        )


def test_absolute_dependency_matches_by_content_identity(
    tmp_path: Path,
) -> None:
    library = tmp_path / "libfixture-private.so"
    executable = tmp_path / "generator"
    _write_elf(library)
    _write_elf(executable, needed=(str(library),))
    final, runtime = _fixture_receipts(
        executable=executable,
        mapped_paths=[executable, library],
    )

    result = attest_elf_link_metadata(
        final_receipt=final,
        runtime_receipt=runtime,
    )

    assert result["direct_dependency_matches"] == {
        str(library): 1
    }


def test_relative_dependency_path_requires_cwd_provenance(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "generator"
    _write_elf(
        executable,
        needed=("relative/libfixture.so",),
    )
    final, runtime = _fixture_receipts(
        executable=executable,
        mapped_paths=[executable],
    )

    with pytest.raises(
        ValueError,
        match="requires cwd provenance",
    ):
        attest_elf_link_metadata(
            final_receipt=final,
            runtime_receipt=runtime,
        )


def test_extra_non_elf_mapping_is_retained_as_non_direct(
    tmp_path: Path,
) -> None:
    library = tmp_path / "libfixture.so"
    executable = tmp_path / "generator"
    extra = tmp_path / "jit-cache.bin"
    _write_elf(library, soname="libfixture.so")
    _write_elf(executable, needed=("libfixture.so",))
    extra.write_bytes(b"not-elf-but-file-backed")
    final, runtime = _fixture_receipts(
        executable=executable,
        mapped_paths=[executable, library, extra],
    )

    result = attest_elf_link_metadata(
        final_receipt=final,
        runtime_receipt=runtime,
    )

    assert result["direct_dependency_matches"] == {
        "libfixture.so": 1
    }
    assert result["mapped_object_elf"][2] == {
        "object_index": 2,
        "elf": None,
    }


def test_duplicate_runtime_soname_is_ambiguous_and_rejected(
    tmp_path: Path,
) -> None:
    first = tmp_path / "libfixture-a.so"
    second = tmp_path / "libfixture-b.so"
    executable = tmp_path / "generator"
    _write_elf(first, soname="libfixture.so")
    _write_elf(second, soname="libfixture.so")
    _write_elf(executable, needed=("libfixture.so",))
    final, runtime = _fixture_receipts(
        executable=executable,
        mapped_paths=[executable, first, second],
    )

    with pytest.raises(ValueError, match="matched 2 runtime objects"):
        attest_elf_link_metadata(
            final_receipt=final,
            runtime_receipt=runtime,
        )
