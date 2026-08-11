from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from tools.audit.geant4_runtime_codepage_attestation import (
    RUNTIME_RECEIPT_SCHEMA,
    _digest_body,
    attest_runtime_codepages,
)


def _receipt(body: dict[str, object]) -> dict[str, object]:
    result = dict(body)
    result["receipt_sha256"] = _digest_body(body)
    return result


def _stat_text(pid: int, starttime: int) -> str:
    tail = ["S"] + ["0"] * 18 + [str(starttime)] + ["0"] * 5
    return f"{pid} (fixture) " + " ".join(tail) + "\n"


def _mapped_record(
    path: Path,
    *,
    start: int,
    end: int,
    offset: int,
) -> dict[str, object]:
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
                "end": end,
                "perms": "r-xp",
                "offset": offset,
            }
        ],
    }


def _maps_line(record: dict[str, object]) -> str:
    segment = record["segments"][0]
    return (
        f"{segment['start']:x}-{segment['end']:x} "
        f"{segment['perms']} {segment['offset']:08x} "
        f"{record['device_major']:02x}:{record['device_minor']:02x} "
        f"{record['inode']} {record['paths'][0]}\n"
    )


def _fixture(
    tmp_path: Path,
    *,
    file_size: int = 0x1000,
    start: int = 0x1000,
    end: int = 0x2000,
    offset: int = 0,
) -> tuple[dict[str, object], Path, Path, dict[str, object]]:
    pid = 4242
    starttime = 123456
    backing = tmp_path / "libfixture.so"
    payload = bytes((index * 17 + 3) % 251 for index in range(file_size))
    backing.write_bytes(payload)

    record = _mapped_record(
        backing,
        start=start,
        end=end,
        offset=offset,
    )
    proc_dir = tmp_path / "proc" / str(pid)
    proc_dir.mkdir(parents=True)
    (proc_dir / "stat").write_text(_stat_text(pid, starttime), encoding="ascii")
    (proc_dir / "maps").write_text(_maps_line(record), encoding="utf-8")

    file_bytes = min(end - start, file_size - offset)
    expected = payload[offset : offset + file_bytes] + b"\0" * (
        (end - start) - file_bytes
    )
    mem = proc_dir / "mem"
    with mem.open("wb") as stream:
        stream.truncate(end + 0x1000)
    fd = os.open(mem, os.O_RDWR)
    try:
        assert os.pwrite(fd, expected, start) == len(expected)
    finally:
        os.close(fd)

    receipt = _receipt(
        {
            "schema": RUNTIME_RECEIPT_SCHEMA,
            "status": "PASS",
            "process": {
                "pid": pid,
                "starttime_ticks": starttime,
            },
            "mapped_executable_objects": [record],
        }
    )
    return receipt, tmp_path / "proc", mem, record


def test_nominal_exact_codepage_match(tmp_path: Path) -> None:
    receipt, proc_root, _mem, _record = _fixture(tmp_path)

    result = attest_runtime_codepages(
        runtime_receipt=receipt,
        proc_root=proc_root,
    )

    assert result["status"] == "PASS"
    segment = result["objects"][0]["executable_segments"][0]
    assert segment["bytes"] == 0x1000
    assert segment["zero_fill_bytes"] == 0
    assert segment["memory_sha256"] == segment["expected_backing_sha256"]


def test_partial_final_page_zero_fill_is_compared(tmp_path: Path) -> None:
    receipt, proc_root, _mem, _record = _fixture(
        tmp_path,
        file_size=0x1800,
        start=0x3000,
        end=0x4000,
        offset=0x1000,
    )

    result = attest_runtime_codepages(
        runtime_receipt=receipt,
        proc_root=proc_root,
    )

    segment = result["objects"][0]["executable_segments"][0]
    assert segment["file_bytes"] == 0x800
    assert segment["zero_fill_bytes"] == 0x800


def test_whole_page_beyond_eof_is_not_synthesized_as_zero(tmp_path: Path) -> None:
    receipt, proc_root, _mem, _record = _fixture(
        tmp_path,
        file_size=0x1800,
        start=0x5000,
        end=0x7000,
        offset=0x1000,
    )

    with pytest.raises(ValueError, match="whole page beyond backing EOF"):
        attest_runtime_codepages(
            runtime_receipt=receipt,
            proc_root=proc_root,
        )


def test_live_memory_mutation_blocks(tmp_path: Path) -> None:
    receipt, proc_root, mem, _record = _fixture(tmp_path)
    fd = os.open(mem, os.O_RDWR)
    try:
        os.pwrite(fd, b"\xff", 0x1000 + 77)
    finally:
        os.close(fd)

    with pytest.raises(ValueError, match="live executable bytes differ"):
        attest_runtime_codepages(
            runtime_receipt=receipt,
            proc_root=proc_root,
        )


def test_nonzero_partial_page_tail_blocks(tmp_path: Path) -> None:
    receipt, proc_root, mem, _record = _fixture(
        tmp_path,
        file_size=0x1800,
        start=0x3000,
        end=0x4000,
        offset=0x1000,
    )
    fd = os.open(mem, os.O_RDWR)
    try:
        os.pwrite(fd, b"\x01", 0x3800)
    finally:
        os.close(fd)

    with pytest.raises(ValueError, match="live executable bytes differ"):
        attest_runtime_codepages(
            runtime_receipt=receipt,
            proc_root=proc_root,
        )


def test_backing_mutation_after_runtime_receipt_blocks(tmp_path: Path) -> None:
    receipt, proc_root, _mem, record = _fixture(tmp_path)
    backing = Path(record["paths"][0])
    payload = bytearray(backing.read_bytes())
    payload[10] ^= 0xFF
    backing.write_bytes(payload)

    with pytest.raises(ValueError, match="content differs"):
        attest_runtime_codepages(
            runtime_receipt=receipt,
            proc_root=proc_root,
        )


def test_process_identity_mismatch_blocks(tmp_path: Path) -> None:
    receipt, proc_root, _mem, _record = _fixture(tmp_path)
    pid = receipt["process"]["pid"]
    (proc_root / str(pid) / "stat").write_text(
        _stat_text(pid, 999999), encoding="ascii"
    )

    with pytest.raises(ValueError, match="process identity differs"):
        attest_runtime_codepages(
            runtime_receipt=receipt,
            proc_root=proc_root,
        )


def test_mapping_projection_mismatch_blocks(tmp_path: Path) -> None:
    receipt, proc_root, _mem, record = _fixture(tmp_path)
    pid = receipt["process"]["pid"]
    line = _maps_line(record).replace("1000-2000", "1100-2100", 1)
    (proc_root / str(pid) / "maps").write_text(line, encoding="utf-8")

    with pytest.raises(ValueError, match="mapping projection differs"):
        attest_runtime_codepages(
            runtime_receipt=receipt,
            proc_root=proc_root,
        )


def test_runtime_receipt_digest_tamper_blocks(tmp_path: Path) -> None:
    receipt, proc_root, _mem, _record = _fixture(tmp_path)
    receipt["process"]["starttime_ticks"] += 1

    with pytest.raises(ValueError, match="digest mismatch"):
        attest_runtime_codepages(
            runtime_receipt=receipt,
            proc_root=proc_root,
        )


def test_duplicate_runtime_inode_object_blocks(tmp_path: Path) -> None:
    receipt, proc_root, _mem, _record = _fixture(tmp_path)
    body = dict(receipt)
    body.pop("receipt_sha256")
    body["mapped_executable_objects"] = [
        dict(body["mapped_executable_objects"][0]),
        dict(body["mapped_executable_objects"][0]),
    ]
    duplicate = _receipt(body)

    with pytest.raises(ValueError, match="duplicates a mapped inode"):
        attest_runtime_codepages(
            runtime_receipt=duplicate,
            proc_root=proc_root,
        )
