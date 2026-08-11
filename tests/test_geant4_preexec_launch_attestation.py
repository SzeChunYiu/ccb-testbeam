from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import tools.audit.geant4_preexec_launch_attestation as launch


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path: Path) -> tuple[int, str]:
    payload = path.read_bytes()
    return len(payload), hashlib.sha256(payload).hexdigest()


def _final_receipt(executable: Path) -> dict[str, object]:
    executable = executable.resolve()
    size, sha256 = _sha256_file(executable)
    body: dict[str, object] = {
        "schema": launch.FINAL_RECEIPT_SCHEMA,
        "status": "PASS",
        "executable": {
            "path": str(executable),
            "bytes": size,
            "sha256": sha256,
        },
        "source": {"fixture": True},
        "staged_inputs": [{"fixture": True}],
        "build_contract": {"fixture": True},
        "limitations": ["fixture"],
        "scientific_scope": "fixture",
        "begin_receipt_sha256": "f" * 64,
    }
    body["receipt_sha256"] = hashlib.sha256(_canonical_bytes(body)).hexdigest()
    return body


def _re_digest(receipt: dict[str, object]) -> None:
    receipt.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = hashlib.sha256(_canonical_bytes(receipt)).hexdigest()


def test_environment_record_binds_all_loader_controls_and_complete_block() -> None:
    env = {
        b"ZZ": b"last",
        b"LD_LIBRARY_PATH": b"/g4:/vgm",
        b"GLIBC_TUNABLES": b"glibc.rtld.dynamic_sort=1",
        b"AA": b"first",
        b"LD_AUDIT": b"audit.so",
    }
    result = launch._environment_record(env)
    canonical = (
        b"AA=first\0"
        b"GLIBC_TUNABLES=glibc.rtld.dynamic_sort=1\0"
        b"LD_AUDIT=audit.so\0"
        b"LD_LIBRARY_PATH=/g4:/vgm\0"
        b"ZZ=last\0"
    )
    assert result["entry_count"] == 5
    assert result["canonical_nul_block_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert [row["name_ascii"] for row in result["loader_controls"]] == [
        "GLIBC_TUNABLES",
        "LD_AUDIT",
        "LD_LIBRARY_PATH",
    ]


@pytest.mark.parametrize(
    "environment,match",
    [
        ({b"": b"x"}, "invalid environment name"),
        ({b"A=B": b"x"}, "invalid environment name"),
        ({b"A": b"x\0y"}, "contains NUL"),
        ({}, "must not be empty"),
    ],
)
def test_invalid_environment_contract_fails(
    environment: dict[bytes, bytes], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        launch._environment_record(environment)


def test_argv_record_preserves_index_and_exact_bytes() -> None:
    argv = [b"/tmp/hibeam_g4", b"-c", b"krakow.config", b"\xff"]
    result = launch._argv_record(argv)
    expected = b"/tmp/hibeam_g4\0-c\0krakow.config\0\xff\0"
    assert result["canonical_nul_block_sha256"] == hashlib.sha256(expected).hexdigest()
    assert result["entries"][3]["utf8"] is None


def test_atomic_receipt_publication_refuses_overwrite(tmp_path: Path) -> None:
    path = (tmp_path / "receipt.json").resolve()
    path.write_text("original\n", encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        launch._atomic_write_json(path, {"status": "READY_TO_EXEC"})
    assert path.read_text(encoding="utf-8") == "original\n"


def test_empty_argv0_fails() -> None:
    with pytest.raises(ValueError, match=r"argv\[0\] must not be empty"):
        launch._argv_record([b""])


def test_tampered_final_receipt_fails(tmp_path: Path) -> None:
    receipt = _final_receipt(Path(sys.executable))
    receipt["scientific_scope"] = "tampered"
    with pytest.raises(ValueError, match="digest mismatch"):
        launch.prepare_launch(
            final_receipt=receipt,
            cwd=tmp_path.resolve(),
            argv=[os.fsencode(sys.executable), b"-V"],
            environment={b"PATH": b"/usr/bin"},
        )


def test_wrong_final_executable_hash_fails(tmp_path: Path) -> None:
    receipt = _final_receipt(Path(sys.executable))
    receipt["executable"]["sha256"] = "0" * 64  # type: ignore[index]
    _re_digest(receipt)
    with pytest.raises(ValueError, match="bytes differ"):
        launch.prepare_launch(
            final_receipt=receipt,
            cwd=tmp_path.resolve(),
            argv=[os.fsencode(sys.executable), b"-V"],
            environment={b"PATH": b"/usr/bin"},
        )


def test_non_elf_target_fails(tmp_path: Path) -> None:
    target = tmp_path / "script"
    target.write_text("#!/bin/sh\nexit 0\n")
    target.chmod(0o755)
    receipt = _final_receipt(target)
    with pytest.raises(ValueError, match="not an ELF"):
        launch.prepare_launch(
            final_receipt=receipt,
            cwd=tmp_path.resolve(),
            argv=[os.fsencode(target)],
            environment={b"PATH": b"/usr/bin"},
        )


def test_symlink_cwd_fails(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    receipt = _final_receipt(Path(sys.executable))
    with pytest.raises(ValueError, match="must not be a symlink"):
        launch.prepare_launch(
            final_receipt=receipt,
            cwd=alias.absolute(),
            argv=[os.fsencode(sys.executable), b"-V"],
            environment={b"PATH": b"/usr/bin"},
        )


@pytest.mark.skipif(
    os.name != "posix" or os.execve not in os.supports_fd,
    reason="descriptor execve requires supported POSIX platform",
)
def test_real_descriptor_exec_preserves_pid_starttime_env_and_cwd(tmp_path: Path) -> None:
    target = Path(sys.executable).resolve()
    final_receipt = _final_receipt(target)
    final_json = tmp_path / "final.json"
    final_json.write_text(json.dumps(final_receipt), encoding="utf-8")
    receipt_out = tmp_path / "preexec.json"
    observation = tmp_path / "observation.json"
    cwd = tmp_path / "work"
    cwd.mkdir()

    child_code = (
        "import hashlib,json,os,sys;"
        "raw=open('/proc/self/stat','rb').read().decode('ascii');"
        "tail=raw[raw.rfind(')')+1:].strip().split();"
        "env=dict(os.environb);"
        "block=b''.join(k+b'='+env[k]+b'\\0' for k in sorted(env));"
        "out={'pid':os.getpid(),'starttime_ticks':int(tail[19]),"
        "'cwd':os.getcwd(),'env_sha256':hashlib.sha256(block).hexdigest(),"
        "'ld_library_path':os.environ.get('LD_LIBRARY_PATH')};"
        "open(sys.argv[1],'w').write(json.dumps(out,sort_keys=True))"
    )

    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = "/fixture/g4:/fixture/vgm"
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(launch.__file__).resolve()),
            "--final-receipt-json",
            str(final_json.resolve()),
            "--receipt-out",
            str(receipt_out.resolve()),
            "--cwd",
            str(cwd.resolve()),
            "--",
            str(target),
            "-c",
            child_code,
            str(observation.resolve()),
        ],
        cwd=Path.cwd(),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout

    ready = json.loads(receipt_out.read_text())
    observed = json.loads(observation.read_text())
    assert ready["status"] == "READY_TO_EXEC"
    assert ready["process"]["pid"] == observed["pid"]
    assert ready["process"]["starttime_ticks"] == observed["starttime_ticks"]
    assert ready["cwd"]["path"] == observed["cwd"] == str(cwd.resolve())
    assert (
        ready["environment"]["canonical_nul_block_sha256"] == observed["env_sha256"]
    )
    controls = {
        row["name_ascii"]: row["value_utf8"]
        for row in ready["environment"]["loader_controls"]
    }
    assert controls["LD_LIBRARY_PATH"] == observed["ld_library_path"]
    assert ready["target_executable"]["sha256"] == final_receipt["executable"]["sha256"]


def test_ready_receipt_is_self_digesting_and_not_success_claim(tmp_path: Path) -> None:
    receipt = _final_receipt(Path(sys.executable))
    ready, exe_fd, cwd_fd, _ = launch.prepare_launch(
        final_receipt=receipt,
        cwd=tmp_path.resolve(),
        argv=[os.fsencode(sys.executable), b"-V"],
        environment={b"PATH": b"/usr/bin", b"LD_LIBRARY_PATH": b"/fixture"},
    )
    try:
        assert ready["status"] == "READY_TO_EXEC"
        body = dict(ready)
        observed = body.pop("receipt_sha256")
        assert observed == hashlib.sha256(launch._canonical_bytes(body)).hexdigest()
        assert "RUNTIME_CHILD_REQUIRED" in " ".join(ready["limitations"])
        assert stat.S_ISREG(os.fstat(exe_fd).st_mode)
        assert stat.S_ISDIR(os.fstat(cwd_fd).st_mode)
    finally:
        os.close(cwd_fd)
        os.close(exe_fd)
