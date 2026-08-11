#!/usr/bin/env python3
"""Bind ELF link declarations to content-attested runtime mappings.

This bounded provenance primitive composes the validated Geant4 build-binding
receipt with the validated live runtime-mapping receipt. It parses ELF64
little-endian x86-64 bytes directly rather than invoking ``ldd`` or an
unattested ``readelf`` process, then checks that each direct ``DT_NEEDED`` and
``PT_INTERP`` declaration has exactly one content-bound runtime counterpart.

The receipt does not prove linker command lines, static archive inputs, loader
search-state completeness, later ``dlopen`` activity, or any Geant4 physics
observable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import struct
from pathlib import Path
from typing import Any

SCHEMA = "ccb_geant4_elf_link_attestation_v1"
FINAL_RECEIPT_SCHEMA = "ccb_geant4_build_binding_final_v1"
RUNTIME_RECEIPT_SCHEMA = "ccb_geant4_runtime_dependency_attestation_v1"

PT_LOAD = 1
PT_DYNAMIC = 2
PT_INTERP = 3

DT_NULL = 0
DT_NEEDED = 1
DT_STRTAB = 5
DT_STRSZ = 10
DT_SONAME = 14
DT_RPATH = 15
DT_RUNPATH = 29

EM_X86_64 = 62


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest_body(body: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(body)).hexdigest()


def _with_receipt_digest(body: dict[str, Any]) -> dict[str, Any]:
    result = dict(body)
    result["receipt_sha256"] = _digest_body(body)
    return result


def _verify_receipt(
    receipt: dict[str, Any],
    *,
    schema: str,
    label: str,
) -> None:
    if receipt.get("schema") != schema:
        raise ValueError(f"{label} has unsupported schema")
    if receipt.get("status") != "PASS":
        raise ValueError(f"{label} is not PASS")
    observed = receipt.get("receipt_sha256")
    if not isinstance(observed, str):
        raise ValueError(f"{label} is missing receipt_sha256")
    body = dict(receipt)
    del body["receipt_sha256"]
    if _digest_body(body) != observed:
        raise ValueError(f"{label} digest mismatch")


def _stat_identity(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _read_path(
    path: Path,
    *,
    label: str,
    expected: dict[str, Any] | None = None,
) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
    except OSError as exc:
        raise ValueError(f"cannot open {label} {path}: {exc}") from exc

    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"{label} must be a regular file")
        os.lseek(fd, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(fd, 1024 * 1024)
            if not block:
                break
            chunks.append(block)
            digest.update(block)
            total += len(block)
        after = os.fstat(fd)
    finally:
        os.close(fd)

    if _stat_identity(before) != _stat_identity(after):
        raise ValueError(f"{label} changed while being read")
    if total != before.st_size:
        raise ValueError(f"short/long read while reading {label}")

    record = {
        "bytes": total,
        "sha256": digest.hexdigest(),
        "device_major": os.major(before.st_dev),
        "device_minor": os.minor(before.st_dev),
        "inode": before.st_ino,
    }
    if expected is not None:
        for key in ("bytes", "sha256"):
            if expected.get(key) != record[key]:
                raise ValueError(f"{label} content identity differs from receipt")
        for key in ("device_major", "device_minor", "inode"):
            if key in expected and expected.get(key) != record[key]:
                raise ValueError(
                    f"{label} inode identity differs from runtime receipt"
                )
    return b"".join(chunks)


def _cstring(
    data: bytes,
    offset: int,
    end: int,
    *,
    label: str,
) -> str:
    if offset < 0 or offset >= end or end > len(data):
        raise ValueError(f"{label} offset outside dynamic string table")
    terminator = data.find(b"\0", offset, end)
    if terminator < 0:
        raise ValueError(
            f"{label} is not NUL terminated within dynamic string table"
        )
    try:
        return data[offset:terminator].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not UTF-8") from exc


def parse_elf_link_metadata(data: bytes) -> dict[str, Any]:
    """Parse the bounded ELF metadata needed by the link-provenance contract."""
    if len(data) < 64 or data[:4] != b"\x7fELF":
        raise ValueError("not an ELF file")
    if data[4] != 2:
        raise ValueError("only ELF64 is supported")
    if data[5] != 1:
        raise ValueError("only little-endian ELF is supported")
    if data[6] != 1:
        raise ValueError("unsupported ELF identification version")

    elf_type, machine, version = struct.unpack_from("<HHI", data, 16)
    if machine != EM_X86_64:
        raise ValueError(f"unsupported ELF machine: {machine}")
    if version != 1:
        raise ValueError("unsupported ELF header version")

    program_offset = struct.unpack_from("<Q", data, 32)[0]
    program_entry_size, program_count = struct.unpack_from("<HH", data, 54)
    if program_entry_size != 56:
        raise ValueError("unexpected ELF64 program-header size")
    if program_count == 0:
        raise ValueError("ELF has no program headers")
    program_end = program_offset + program_entry_size * program_count
    if program_end > len(data):
        raise ValueError("program-header table exceeds file bounds")

    load_segments: list[tuple[int, int, int]] = []
    dynamic_segments: list[tuple[int, int]] = []
    interpreters: list[str] = []

    for index in range(program_count):
        offset = program_offset + index * program_entry_size
        (
            segment_type,
            _flags,
            file_offset,
            virtual_address,
            _physical_address,
            file_size,
            _memory_size,
            _alignment,
        ) = struct.unpack_from("<IIQQQQQQ", data, offset)
        if file_offset + file_size > len(data):
            raise ValueError("program segment exceeds file bounds")

        if segment_type == PT_LOAD:
            load_segments.append((virtual_address, file_offset, file_size))
        elif segment_type == PT_DYNAMIC:
            dynamic_segments.append((file_offset, file_size))
        elif segment_type == PT_INTERP:
            raw = data[file_offset : file_offset + file_size]
            if not raw or raw[-1:] != b"\0" or b"\0" in raw[:-1]:
                raise ValueError(
                    "PT_INTERP must contain one NUL-terminated pathname"
                )
            try:
                interpreters.append(raw[:-1].decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise ValueError("PT_INTERP is not UTF-8") from exc

    if len(interpreters) > 1:
        raise ValueError("ELF has multiple PT_INTERP segments")
    if len(dynamic_segments) > 1:
        raise ValueError("ELF has multiple PT_DYNAMIC segments")

    dynamic_tags: list[tuple[int, int]] = []
    if dynamic_segments:
        dynamic_offset, dynamic_size = dynamic_segments[0]
        if dynamic_size % 16:
            raise ValueError("PT_DYNAMIC size is not an Elf64_Dyn multiple")
        for offset in range(
            dynamic_offset,
            dynamic_offset + dynamic_size,
            16,
        ):
            tag, value = struct.unpack_from("<qQ", data, offset)
            dynamic_tags.append((tag, value))
            if tag == DT_NULL:
                break
        else:
            raise ValueError("PT_DYNAMIC has no DT_NULL terminator")

    strtabs = [value for tag, value in dynamic_tags if tag == DT_STRTAB]
    strsizes = [value for tag, value in dynamic_tags if tag == DT_STRSZ]
    string_tags = [
        (tag, value)
        for tag, value in dynamic_tags
        if tag in (DT_NEEDED, DT_SONAME, DT_RPATH, DT_RUNPATH)
    ]

    string_offset = 0
    string_end = 0
    if string_tags:
        if len(strtabs) != 1 or len(strsizes) != 1:
            raise ValueError(
                "dynamic string metadata requires one DT_STRTAB "
                "and one DT_STRSZ"
            )
        string_address = strtabs[0]
        string_size = strsizes[0]
        if string_size <= 0:
            raise ValueError("DT_STRSZ must be positive")

        candidates = []
        for virtual_address, file_offset, file_size in load_segments:
            if (
                string_address >= virtual_address
                and string_address + string_size
                <= virtual_address + file_size
            ):
                candidates.append(
                    file_offset + (string_address - virtual_address)
                )
        if len(candidates) != 1:
            raise ValueError(
                "DT_STRTAB does not map uniquely into a file-backed PT_LOAD"
            )
        string_offset = candidates[0]
        string_end = string_offset + string_size
        if string_end > len(data):
            raise ValueError("dynamic string table exceeds file bounds")

    def string_value(relative_offset: int, *, label: str) -> str:
        return _cstring(
            data,
            string_offset + relative_offset,
            string_end,
            label=label,
        )

    needed = [
        string_value(value, label="DT_NEEDED")
        for tag, value in string_tags
        if tag == DT_NEEDED
    ]

    def singleton(tag_value: int, name: str) -> str | None:
        values = [
            string_value(value, label=name)
            for tag, value in string_tags
            if tag == tag_value
        ]
        if len(values) > 1:
            raise ValueError(f"multiple {name} entries")
        return values[0] if values else None

    return {
        "elf_class": "ELF64",
        "endianness": "little",
        "machine": machine,
        "type": elf_type,
        "interpreter": interpreters[0] if interpreters else None,
        "dt_needed": needed,
        "dt_soname": singleton(DT_SONAME, "DT_SONAME"),
        "dt_rpath": singleton(DT_RPATH, "DT_RPATH"),
        "dt_runpath": singleton(DT_RUNPATH, "DT_RUNPATH"),
    }


def _runtime_objects(runtime_receipt: dict[str, Any]) -> list[dict[str, Any]]:
    raw_objects = runtime_receipt.get("mapped_executable_objects")
    if not isinstance(raw_objects, list) or not raw_objects:
        raise ValueError(
            "runtime receipt has no mapped executable objects"
        )

    result: list[dict[str, Any]] = []
    for index, raw_object in enumerate(raw_objects):
        if not isinstance(raw_object, dict):
            raise ValueError(
                "runtime mapped object record is not an object"
            )
        paths = raw_object.get("paths")
        if (
            not isinstance(paths, list)
            or not paths
            or not all(
                isinstance(path, str) and path.startswith("/")
                for path in paths
            )
        ):
            raise ValueError("runtime mapped object paths are invalid")
        if (
            not isinstance(raw_object.get("sha256"), str)
            or not isinstance(raw_object.get("bytes"), int)
        ):
            raise ValueError(
                "runtime mapped object content identity is incomplete"
            )

        metadata_records: list[dict[str, Any] | None] = []
        for path_text in paths:
            data = _read_path(
                Path(path_text),
                label=f"runtime mapped object {index}",
                expected=raw_object,
            )
            try:
                metadata = parse_elf_link_metadata(data)
            except ValueError:
                metadata = None
            metadata_records.append(metadata)

        parsed = [record for record in metadata_records if record is not None]
        if parsed and any(record != parsed[0] for record in parsed[1:]):
            raise ValueError(
                "hardlink-equivalent mapped paths yielded "
                "inconsistent ELF metadata"
            )

        result.append(
            {
                "index": index,
                "receipt": raw_object,
                "elf": parsed[0] if parsed else None,
            }
        )
    return result


def attest_elf_link_metadata(
    *,
    final_receipt: dict[str, Any],
    runtime_receipt: dict[str, Any],
) -> dict[str, Any]:
    """Create a link-declaration-to-runtime-mapping provenance receipt."""
    _verify_receipt(
        final_receipt,
        schema=FINAL_RECEIPT_SCHEMA,
        label="final build-binding receipt",
    )
    _verify_receipt(
        runtime_receipt,
        schema=RUNTIME_RECEIPT_SCHEMA,
        label="runtime dependency receipt",
    )
    if (
        runtime_receipt.get("parent_final_build_receipt_sha256")
        != final_receipt["receipt_sha256"]
    ):
        raise ValueError(
            "runtime dependency receipt belongs to another "
            "final build receipt"
        )

    executable = final_receipt.get("executable")
    if (
        not isinstance(executable, dict)
        or not isinstance(executable.get("path"), str)
        or not executable["path"].startswith("/")
    ):
        raise ValueError("final executable record is incomplete")

    executable_data = _read_path(
        Path(executable["path"]),
        label="final executable",
        expected=executable,
    )
    executable_elf = parse_elf_link_metadata(executable_data)

    process = runtime_receipt.get("process")
    live_executable = (
        process.get("executable")
        if isinstance(process, dict)
        else None
    )
    if (
        not isinstance(live_executable, dict)
        or (
            live_executable.get("bytes"),
            live_executable.get("sha256"),
        )
        != (
            executable.get("bytes"),
            executable.get("sha256"),
        )
    ):
        raise ValueError(
            "runtime executable identity differs from final build receipt"
        )

    runtime_objects = _runtime_objects(runtime_receipt)
    unique_needed = list(dict.fromkeys(executable_elf["dt_needed"]))
    direct_dependency_matches: dict[str, int] = {}

    for dependency in unique_needed:
        if "/" in dependency:
            if not dependency.startswith("/"):
                raise ValueError(
                    "relative DT_NEEDED path requires cwd provenance: "
                    f"{dependency}"
                )
            dependency_data = _read_path(
                Path(dependency),
                label=f"absolute DT_NEEDED {dependency}",
            )
            identity = (
                len(dependency_data),
                hashlib.sha256(dependency_data).hexdigest(),
            )
            matches = [
                item["index"]
                for item in runtime_objects
                if (
                    item["receipt"]["bytes"],
                    item["receipt"]["sha256"],
                )
                == identity
            ]
        else:
            matches = [
                item["index"]
                for item in runtime_objects
                if (
                    item["elf"] is not None
                    and item["elf"]["dt_soname"] == dependency
                )
            ]

        if len(matches) != 1:
            raise ValueError(
                f"DT_NEEDED {dependency!r} matched {len(matches)} "
                "runtime objects; expected exactly one"
            )
        direct_dependency_matches[dependency] = matches[0]

    interpreter_match: int | None = None
    interpreter = executable_elf["interpreter"]
    if interpreter is not None:
        if not interpreter.startswith("/"):
            raise ValueError("PT_INTERP is not an absolute path")
        interpreter_data = _read_path(
            Path(interpreter),
            label="PT_INTERP",
        )
        identity = (
            len(interpreter_data),
            hashlib.sha256(interpreter_data).hexdigest(),
        )
        matches = [
            item["index"]
            for item in runtime_objects
            if (
                item["receipt"]["bytes"],
                item["receipt"]["sha256"],
            )
            == identity
        ]
        if len(matches) != 1:
            raise ValueError(
                f"PT_INTERP matched {len(matches)} runtime objects; "
                "expected exactly one"
            )
        interpreter_match = matches[0]

    body = {
        "schema": SCHEMA,
        "status": "PASS",
        "parent_final_build_receipt_sha256": (
            final_receipt["receipt_sha256"]
        ),
        "parent_runtime_dependency_receipt_sha256": (
            runtime_receipt["receipt_sha256"]
        ),
        "executable": {
            "path": executable["path"],
            "bytes": executable["bytes"],
            "sha256": executable["sha256"],
            "elf": executable_elf,
        },
        "direct_dependency_matches": direct_dependency_matches,
        "interpreter_object_index": interpreter_match,
        "mapped_object_elf": [
            {
                "object_index": item["index"],
                "elf": item["elf"],
            }
            for item in runtime_objects
        ],
        "scientific_scope": (
            "ELF_LINK_DECLARATION_TO_RUNTIME_FILE_IDENTITY_ONLY"
        ),
        "limitations": [
            "LINK_COMMAND_STATIC_ARCHIVES_AND_RESPONSE_FILES_NOT_BOUND",
            "LOADER_SEARCH_STATE_NOT_FULLY_BOUND",
            "LATE_DLOPEN_AFTER_RUNTIME_SNAPSHOT_NOT_BOUND",
            (
                "NO_GEANT4_EVENT_SOURCE_TRANSPORT_OR_DETECTOR_"
                "OBSERVABLE_VALIDATED"
            ),
        ],
    }
    return _with_receipt_digest(body)


def _load_json_object(
    path: Path,
    *,
    label: str,
) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load {label} JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} JSON must contain an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--final-receipt-json",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--runtime-receipt-json",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    try:
        result = attest_elf_link_metadata(
            final_receipt=_load_json_object(
                args.final_receipt_json,
                label="final build-binding receipt",
            ),
            runtime_receipt=_load_json_object(
                args.runtime_receipt_json,
                label="runtime dependency receipt",
            ),
        )
    except (KeyError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {"status": "BLOCKED", "error": str(exc)},
                sort_keys=True,
            )
        )
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
