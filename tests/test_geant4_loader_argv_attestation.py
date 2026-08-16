from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "audit"
    / "geant4_loader_argv_attestation.py"
)
SPEC = importlib.util.spec_from_file_location("geant4_loader_argv_attestation", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _with_digest(body: dict) -> dict:
    return MODULE._with_digest(body)


def _runtime_receipt(*, pid: int, starttime: int, exe_link: str) -> dict:
    return _with_digest(
        {
            "schema": MODULE.RUNTIME_RECEIPT_SCHEMA,
            "status": "PASS",
            "parent_final_build_receipt_sha256": "f" * 64,
            "process": {
                "pid": pid,
                "starttime_ticks": starttime,
                "exe_link": exe_link,
                "executable": {"bytes": 1, "sha256": "0" * 64},
            },
            "loader_environment": {"LD_LIBRARY_PATH": {"present": False}},
            "mapped_executable_objects": [],
            "required_object_matches": {},
            "maps_sha256": "1" * 64,
            "executable_mapping_projection_stable": True,
            "scientific_scope": "fixture",
            "limitations": [],
        }
    )


def _stat_payload(pid: int, starttime: int) -> bytes:
    tail = ["S", *("0" for _ in range(18)), str(starttime), *("0" for _ in range(8))]
    return f"{pid} (fixture process) {' '.join(tail)}\n".encode("ascii")


def _fake_proc(
    tmp_path: Path,
    *,
    pid: int = 4321,
    starttime: int = 987654,
    exe_link: str = "/opt/hibeam_g4",
    cmdline: bytes = b"./hibeam_g4\0-c\0krakow.config\0-m\0run_krakow.mac\0output.root\0",
) -> Path:
    proc_root = tmp_path / "proc"
    proc_dir = proc_root / str(pid)
    proc_dir.mkdir(parents=True)
    (proc_dir / "stat").write_bytes(_stat_payload(pid, starttime))
    (proc_dir / "cmdline").write_bytes(cmdline)
    (proc_dir / "exe").symlink_to(exe_link)
    return proc_root


def _wait_for_exec_observation(
    process: subprocess.Popen,
    *,
    expected_exe: Path,
    timeout_s: float = 2.0,
) -> tuple[Path, int, str]:
    proc_dir = Path("/proc") / str(process.pid)
    deadline = time.monotonic() + timeout_s
    last_state = "not observed"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                f"child exited before procfs exec observation: returncode={process.returncode}"
            )
        try:
            cmdline = (proc_dir / "cmdline").read_bytes()
            exe_link = os.readlink(proc_dir / "exe")
            starttime = MODULE._read_process_starttime(proc_dir)
        except (OSError, ValueError) as exc:
            last_state = str(exc)
            time.sleep(0.01)
            continue
        if not cmdline:
            last_state = "empty cmdline"
            time.sleep(0.01)
            continue
        try:
            observed_exe = Path(exe_link).resolve(strict=True)
        except OSError as exc:
            last_state = str(exc)
            time.sleep(0.01)
            continue
        if observed_exe != expected_exe.resolve(strict=True):
            last_state = f"unexpected exe {observed_exe}"
            time.sleep(0.01)
            continue
        return proc_dir, starttime, exe_link
    raise AssertionError(f"timed out waiting for stable child exec observation: {last_state}")


def test_nominal_stable_cmdline_records_exact_arguments(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path)
    receipt = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    result = MODULE.attest_loader_argv(runtime_receipt=receipt, proc_root=proc_root)

    assert result["status"] == "PASS"
    assert result["process"]["pid"] == 4321
    assert result["cmdline_region"]["trailing_nul_observed"] is True
    assert result["cmdline_region"]["nul_delimited_slot_count_observed"] == 6
    assert [item["utf8"] for item in result["cmdline_region"]["nul_delimited_slots"]] == [
        "./hibeam_g4",
        "-c",
        "krakow.config",
        "-m",
        "run_krakow.mac",
        "output.root",
    ]
    body = dict(result)
    digest = body.pop("receipt_sha256")
    assert MODULE._digest_body(body) == digest


def test_preserves_empty_and_non_utf8_argument_slots(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path, cmdline=b"prog\0\0\xffarg\0")
    receipt = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    result = MODULE.attest_loader_argv(runtime_receipt=receipt, proc_root=proc_root)

    args = result["cmdline_region"]["nul_delimited_slots"]
    assert len(args) == 3
    assert args[1]["bytes"] == 0
    assert args[1]["utf8"] == ""
    assert args[2]["utf8"] is None


def test_rejects_tampered_runtime_receipt(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path)
    receipt = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    receipt["process"]["pid"] = 5
    with pytest.raises(ValueError, match="digest mismatch"):
        MODULE.attest_loader_argv(runtime_receipt=receipt, proc_root=proc_root)


def test_rejects_process_identity_mismatch(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path, starttime=111)
    receipt = _runtime_receipt(pid=4321, starttime=222, exe_link="/opt/hibeam_g4")
    with pytest.raises(ValueError, match="process identity differs"):
        MODULE.attest_loader_argv(runtime_receipt=receipt, proc_root=proc_root)


def test_rejects_executable_link_mismatch(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path, exe_link="/lib64/ld-linux-x86-64.so.2")
    receipt = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    with pytest.raises(ValueError, match="executable link differs"):
        MODULE.attest_loader_argv(runtime_receipt=receipt, proc_root=proc_root)


def test_rejects_cmdline_mutation_between_reads(tmp_path: Path, monkeypatch) -> None:
    proc_root = _fake_proc(tmp_path)
    receipt = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    original = MODULE._read_proc_bytes
    calls = 0

    def changing(proc_dir: Path, name: str, *, label: str) -> bytes:
        nonlocal calls
        if name == "cmdline":
            calls += 1
            if calls == 2:
                return b"changed\0"
        return original(proc_dir, name, label=label)

    monkeypatch.setattr(MODULE, "_read_proc_bytes", changing)
    with pytest.raises(ValueError, match="changed during attestation"):
        MODULE.attest_loader_argv(runtime_receipt=receipt, proc_root=proc_root)


def test_rejects_process_identity_change_after_read(tmp_path: Path, monkeypatch) -> None:
    proc_root = _fake_proc(tmp_path)
    receipt = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    original = MODULE._read_process_starttime
    calls = 0

    def changing(proc_dir: Path) -> int:
        nonlocal calls
        calls += 1
        value = original(proc_dir)
        return value if calls == 1 else value + 1

    monkeypatch.setattr(MODULE, "_read_process_starttime", changing)
    with pytest.raises(ValueError, match="identity changed"):
        MODULE.attest_loader_argv(runtime_receipt=receipt, proc_root=proc_root)


def test_rejects_empty_cmdline_region(tmp_path: Path) -> None:
    proc_root = _fake_proc(tmp_path, cmdline=b"")
    receipt = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    with pytest.raises(ValueError, match="command-line region is empty"):
        MODULE.attest_loader_argv(runtime_receipt=receipt, proc_root=proc_root)


@pytest.mark.skipif(not Path("/proc").is_dir(), reason="Linux procfs required")
def test_real_linux_child_observation_is_stable() -> None:
    process = subprocess.Popen(["/bin/sleep", "5"])
    try:
        _, starttime, exe_link = _wait_for_exec_observation(
            process,
            expected_exe=Path("/bin/sleep"),
        )
        receipt = _runtime_receipt(
            pid=process.pid,
            starttime=starttime,
            exe_link=exe_link,
        )
        result = MODULE.attest_loader_argv(runtime_receipt=receipt)
        assert result["cmdline_region"]["nul_delimited_slots"][0]["utf8"] == "/bin/sleep"
        assert result["cmdline_region"]["nul_delimited_slots"][1]["utf8"] == "5"
    finally:
        process.terminate()
        process.wait(timeout=2)


def _dynamic_loader() -> Path | None:
    candidates = [
        Path("/lib64/ld-linux-x86-64.so.2"),
        Path("/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"),
        Path("/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"),
    ]
    return next((path.resolve() for path in candidates if path.exists()), None)


@pytest.mark.skipif(not Path("/proc").is_dir(), reason="Linux procfs required")
def test_explicit_dynamic_loader_is_distinguishable_from_final_executable() -> None:
    loader = _dynamic_loader()
    if loader is None:
        pytest.skip("glibc x86-64 dynamic loader not found")
    process = subprocess.Popen([str(loader), "/bin/sleep", "5"])
    try:
        _, starttime, live_exe = _wait_for_exec_observation(
            process,
            expected_exe=loader,
        )
        assert Path(live_exe).resolve() == loader
        receipt = _runtime_receipt(
            pid=process.pid,
            starttime=starttime,
            exe_link=str(Path("/bin/sleep").resolve()),
        )
        with pytest.raises(ValueError, match="executable link differs"):
            MODULE.attest_loader_argv(runtime_receipt=receipt)
    finally:
        process.terminate()
        process.wait(timeout=2)


def test_cli_blocks_on_wrong_receipt_digest(tmp_path: Path) -> None:
    receipt = _runtime_receipt(pid=4321, starttime=987654, exe_link="/opt/hibeam_g4")
    receipt["receipt_sha256"] = "0" * 64
    receipt_path = tmp_path / "runtime.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    completed = subprocess.run(
        [
            os.fspath(Path(os.sys.executable)),
            os.fspath(SCRIPT),
            "--runtime-receipt-json",
            os.fspath(receipt_path),
            "--proc-root",
            os.fspath(tmp_path / "proc"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert json.loads(completed.stdout)["status"] == "BLOCKED"
