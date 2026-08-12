#!/usr/bin/env python3
"""Create, verify, and freeze authorising ccb_stave_sim build receipts.

The receipt binds one clean superproject source revision and its ccb-sipm-core
Gitlink to the exact checked-out ccb-sipm-core worktree, ccb_stave_sim executable
bytes, CMakeCache.txt, configured CMake/C++ compiler binaries, and the Geant4
CMake package sentinel.  The running executable independently self-reports its
SHA-256 and compile-time source labels.

This is a build/execution provenance contract, not detector validation.  It does
not prove every compiler/linker invocation, exclude mutate-and-restore source
changes between observations, attest ignored submodule files, attest the runtime
dynamic-loader image set, or validate any Geant4/SiPM physics observable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

import sipm_campaign_manifest as campaign

SCHEMA = "ccb-single-stave-build-receipt/2"
RUNTIME_SCHEMA = "ccb-single-stave-runtime-build-identity/1"
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class BuildReceiptError(RuntimeError):
    """Build provenance is absent, mutable, malformed, or source-unbound."""


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_git(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not HEX40_RE.fullmatch(value) or value == "0" * 40:
        raise BuildReceiptError(f"{field}: require canonical lowercase nonzero 40-hex Git SHA")
    return value


def _canonical_sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not HEX64_RE.fullmatch(value) or value == "0" * 64:
        raise BuildReceiptError(f"{field}: require canonical lowercase nonzero 64-hex SHA-256")
    return value


def _identity(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns


def _regular_file_record(path: Path, *, label: str) -> dict[str, Any]:
    """Hash one regular non-symlink file from one stable open byte stream."""
    try:
        lst = path.lstat()
    except OSError as exc:
        raise BuildReceiptError(f"cannot inspect {label} {path}: {exc}") from exc
    if not stat.S_ISREG(lst.st_mode):
        raise BuildReceiptError(f"{label} must be a regular non-symlink file: {path}")
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            count += len(chunk)
        after = os.fstat(stream.fileno())
    final = path.lstat()
    if _identity(before) != _identity(after) or _identity(after) != _identity(final):
        raise BuildReceiptError(f"{label} changed while hashing: {path}")
    if count != before.st_size:
        raise BuildReceiptError(f"short/long read while hashing {label}: {path}")
    return {"path": str(path.resolve()), "bytes": count, "sha256": digest.hexdigest()}


def _resolved_file_record(path: Path, *, label: str) -> dict[str, Any]:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise BuildReceiptError(f"cannot resolve {label} {path}: {exc}") from exc
    record = _regular_file_record(resolved, label=label)
    record["configured_path"] = str(path)
    return record


def _git(repo_root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise BuildReceiptError(f"git {' '.join(args)} failed: {detail.strip()}") from exc
    return proc.stdout.strip()


def _core_worktree_identity(
    repo_root: Path, *, expected_core: str, require_clean: bool
) -> dict[str, Any]:
    """Bind the materialized nested core worktree, not only the superproject gitlink.

    Git commands run from an empty/non-Git directory below the superproject may
    discover the parent repository.  Requiring the reported top-level directory
    to equal the configured submodule path distinguishes a genuine independent
    nested worktree (including normal .git-file submodules) from that case.
    """
    core_path = (repo_root / campaign.CORE_PATH).resolve()
    try:
        top_level = Path(_git(core_path, "rev-parse", "--show-toplevel")).resolve()
    except BuildReceiptError as exc:
        raise BuildReceiptError(
            f"ccb-sipm-core path is not a materialized independent Git worktree: {core_path}"
        ) from exc
    if top_level != core_path:
        raise BuildReceiptError(
            "ccb-sipm-core path is not an independent Git worktree: "
            f"git top-level {top_level} != expected {core_path}"
        )

    worktree_head = _canonical_git(
        _git(core_path, "rev-parse", "HEAD"), field="ccb-sipm-core worktree HEAD"
    )
    if worktree_head != expected_core:
        raise BuildReceiptError(
            "ccb-sipm-core worktree HEAD does not equal superproject gitlink: "
            f"{worktree_head} != {expected_core}"
        )

    status = _git(core_path, "status", "--porcelain=v1", "--untracked-files=all")
    clean = status == ""
    if require_clean and not clean:
        raise BuildReceiptError(
            "authorising build receipt requires a clean ccb-sipm-core worktree; "
            f"first dirty entry: {status.splitlines()[0]}"
        )
    return {
        "ccb_sipm_core_worktree_head": worktree_head,
        "ccb_sipm_core_worktree_clean_at_receipt": clean,
    }


def source_identity(repo_root: Path, *, require_clean: bool) -> dict[str, Any]:
    head = _canonical_git(_git(repo_root, "rev-parse", "HEAD"), field="superproject HEAD")
    row = _git(repo_root, "ls-tree", head, campaign.CORE_PATH)
    fields = row.split()
    if len(fields) < 3 or fields[0] != "160000" or fields[1] != "commit":
        raise BuildReceiptError(f"{head}:{campaign.CORE_PATH}: expected gitlink, got {row!r}")
    core = _canonical_git(fields[2], field="ccb-sipm-core gitlink")
    core_worktree = _core_worktree_identity(
        repo_root, expected_core=core, require_clean=require_clean
    )
    status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    clean = status == ""
    if require_clean and not clean:
        raise BuildReceiptError(
            "authorising build receipt requires a clean repository; "
            f"first dirty entry: {status.splitlines()[0]}"
        )
    return {
        "superproject_commit": head,
        "ccb_sipm_core_commit": core,
        "source_tree_clean_at_receipt": clean,
        **core_worktree,
    }


def _parse_cache(path: Path) -> tuple[dict[str, str], dict[str, Any]]:
    record = _regular_file_record(path, label="CMakeCache.txt")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BuildReceiptError(f"cannot read CMakeCache.txt {path}: {exc}") from exc
    values: dict[str, str] = {}
    duplicates: set[str] = set()
    for raw in text.splitlines():
        if not raw or raw.startswith("#") or raw.startswith("//") or "=" not in raw:
            continue
        left, value = raw.split("=", 1)
        key = left.split(":", 1)[0]
        if not key:
            continue
        if key in values:
            duplicates.add(key)
        values[key] = value
    for key in ("CMAKE_COMMAND", "CMAKE_CXX_COMPILER", "CMAKE_GENERATOR", "Geant4_DIR"):
        if key in duplicates:
            raise BuildReceiptError(f"duplicate required CMakeCache key: {key}")
        value = values.get(key)
        if not value or value.endswith("-NOTFOUND"):
            raise BuildReceiptError(f"required CMakeCache key missing/unresolved: {key}")
    return values, record


def _probe_runtime(executable: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [str(executable), "--build-provenance-json"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise BuildReceiptError(f"runtime build-provenance probe failed: {exc}") from exc
    if proc.returncode != 0:
        raise BuildReceiptError(
            f"runtime build-provenance probe returned {proc.returncode}: {proc.stderr[:500]!r}"
        )
    try:
        value = json.loads(proc.stdout.strip())
    except json.JSONDecodeError as exc:
        raise BuildReceiptError(f"runtime build-provenance probe emitted invalid JSON: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != RUNTIME_SCHEMA:
        raise BuildReceiptError(f"runtime build-provenance schema must be {RUNTIME_SCHEMA!r}")
    return value


def _validate_runtime_identity(
    runtime: dict[str, Any], *, source: dict[str, Any], executable: dict[str, Any], cache: dict[str, str]
) -> None:
    if runtime.get("superproject_commit") != source["superproject_commit"]:
        raise BuildReceiptError(
            "compiled superproject commit does not equal source HEAD: "
            f"{runtime.get('superproject_commit')!r} != {source['superproject_commit']}"
        )
    if runtime.get("sipm_core_commit") != source["ccb_sipm_core_commit"]:
        raise BuildReceiptError(
            "compiled ccb-sipm-core commit does not equal source gitlink: "
            f"{runtime.get('sipm_core_commit')!r} != {source['ccb_sipm_core_commit']}"
        )
    if runtime.get("source_tree_clean_at_configure") is not True:
        raise BuildReceiptError("executable was not configured from a source tree recorded clean")
    if runtime.get("executable_identity_status") != "PASS_SELF_SHA256":
        raise BuildReceiptError(
            f"runtime executable identity is non-authorising: {runtime.get('executable_identity_status')!r}"
        )
    if runtime.get("executable_sha256") != executable["sha256"]:
        raise BuildReceiptError(
            "runtime self SHA-256 does not equal independent executable SHA-256"
        )
    if runtime.get("executable_bytes") != executable["bytes"]:
        raise BuildReceiptError("runtime executable byte count does not equal independent byte count")
    if runtime.get("cxx_compiler_path") != cache["CMAKE_CXX_COMPILER"]:
        raise BuildReceiptError(
            "compiled C++ compiler path does not equal CMakeCache selection: "
            f"{runtime.get('cxx_compiler_path')!r} != {cache['CMAKE_CXX_COMPILER']!r}"
        )


def create_receipt(*, repo_root: Path, build_dir: Path, executable: Path) -> dict[str, Any]:
    source = source_identity(repo_root, require_clean=True)
    executable_record = _regular_file_record(executable, label="ccb_stave_sim executable")
    cache_values, cache_record = _parse_cache(build_dir / "CMakeCache.txt")
    runtime = _probe_runtime(executable)
    _validate_runtime_identity(
        runtime, source=source, executable=executable_record, cache=cache_values
    )

    cmake_record = _resolved_file_record(Path(cache_values["CMAKE_COMMAND"]), label="CMake executable")
    compiler_record = _resolved_file_record(
        Path(cache_values["CMAKE_CXX_COMPILER"]), label="C++ compiler"
    )
    geant4_dir = Path(cache_values["Geant4_DIR"])
    if not geant4_dir.is_absolute():
        raise BuildReceiptError("Geant4_DIR must be absolute in an authorising build")
    geant4_config = _regular_file_record(
        geant4_dir / "Geant4Config.cmake", label="Geant4Config.cmake"
    )

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "source": source,
        "runtime_build_identity": runtime,
        "executable": executable_record,
        "cmake_cache": cache_record,
        "cmake_selection": {
            "CMAKE_COMMAND": cache_values["CMAKE_COMMAND"],
            "CMAKE_CXX_COMPILER": cache_values["CMAKE_CXX_COMPILER"],
            "CMAKE_GENERATOR": cache_values["CMAKE_GENERATOR"],
            "Geant4_DIR": cache_values["Geant4_DIR"],
        },
        "tools": {"cmake": cmake_record, "cxx_compiler": compiler_record},
        "geant4_package_sentinel": geant4_config,
        "scientific_scope": "BUILD_SOURCE_EXECUTABLE_CONFIGURED_TOOLCHAIN_IDENTITY_ONLY",
        "limitations": [
            "TWO_OBSERVATION_CHECK_CANNOT_EXCLUDE_TRANSIENT_MUTATE_AND_RESTORE",
            "IGNORED_CCB_SIPM_CORE_FILES_NOT_ATTESTED",
            "EXACT_COMPILER_AND_LINKER_INVOCATION_STREAM_NOT_ATTESTED",
            "RUNTIME_DYNAMIC_LIBRARY_LOAD_SET_NOT_ATTESTED",
            "SHARED_LAUNCHER_AND_VERIFIER_BYTES_NOT_ATTESTED",
            "NO_GEANT4_OR_DETECTOR_PHYSICS_OBSERVABLE_VALIDATED",
        ],
    }


def validate_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != SCHEMA or value.get("status") != "PASS":
        raise BuildReceiptError(f"receipt must be PASS schema {SCHEMA!r}")
    source = value.get("source")
    if not isinstance(source, dict) or source.get("source_tree_clean_at_receipt") is not True:
        raise BuildReceiptError("receipt source block missing or non-authorising")
    root_commit = _canonical_git(source.get("superproject_commit"), field="receipt source commit")
    core_commit = _canonical_git(source.get("ccb_sipm_core_commit"), field="receipt core commit")
    worktree_head = _canonical_git(
        source.get("ccb_sipm_core_worktree_head"), field="receipt core worktree HEAD"
    )
    if worktree_head != core_commit:
        raise BuildReceiptError(
            "receipt core worktree HEAD does not equal receipt core gitlink: "
            f"{worktree_head} != {core_commit}"
        )
    if source.get("ccb_sipm_core_worktree_clean_at_receipt") is not True:
        raise BuildReceiptError("receipt core worktree is missing or non-authorising")
    del root_commit
    exe = value.get("executable")
    if not isinstance(exe, dict):
        raise BuildReceiptError("receipt executable block missing")
    _canonical_sha256(exe.get("sha256"), field="receipt executable SHA-256")
    if not isinstance(exe.get("bytes"), int) or exe["bytes"] <= 0:
        raise BuildReceiptError("receipt executable byte count must be positive")
    runtime = value.get("runtime_build_identity")
    if not isinstance(runtime, dict) or runtime.get("schema") != RUNTIME_SCHEMA:
        raise BuildReceiptError("receipt runtime build identity missing")
    return value


def load_receipt(path: Path, *, expected_sha256: str | None = None) -> tuple[dict[str, Any], bytes, str]:
    raw = path.read_bytes()
    observed = _sha256(raw)
    if expected_sha256 is not None:
        expected = _canonical_sha256(expected_sha256, field="expected build receipt SHA-256")
        if observed != expected:
            raise BuildReceiptError(
                f"build receipt digest mismatch: actual {observed} != expected {expected}"
            )
    try:
        receipt = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BuildReceiptError(f"invalid build receipt JSON: {exc}") from exc
    validate_receipt(receipt)
    if raw != _canonical_bytes(receipt):
        raise BuildReceiptError("build receipt bytes are not canonical JSON")
    return receipt, raw, observed


def _same_record(expected: dict[str, Any], actual: dict[str, Any], *, label: str) -> None:
    for key in ("path", "bytes", "sha256"):
        if actual.get(key) != expected.get(key):
            raise BuildReceiptError(f"{label} changed since receipt: field {key}")


def verify_receipt(
    *,
    receipt: dict[str, Any],
    executable: Path,
    runtime_probe: bool,
    campaign_manifest: Path | None,
    campaign_sha256: str | None,
    repo_root: Path | None,
) -> None:
    validate_receipt(receipt)
    exe_now = _regular_file_record(executable, label="current ccb_stave_sim executable")
    _same_record(receipt["executable"], exe_now, label="executable")

    cache_now_values, cache_now = _parse_cache(Path(receipt["cmake_cache"]["path"]))
    _same_record(receipt["cmake_cache"], cache_now, label="CMakeCache.txt")
    for key, expected in receipt["cmake_selection"].items():
        if cache_now_values.get(key) != expected:
            raise BuildReceiptError(f"CMake selection changed since receipt: {key}")
    _same_record(
        receipt["tools"]["cmake"],
        _resolved_file_record(Path(receipt["cmake_selection"]["CMAKE_COMMAND"]), label="CMake executable"),
        label="CMake executable",
    )
    _same_record(
        receipt["tools"]["cxx_compiler"],
        _resolved_file_record(Path(receipt["cmake_selection"]["CMAKE_CXX_COMPILER"]), label="C++ compiler"),
        label="C++ compiler",
    )
    _same_record(
        receipt["geant4_package_sentinel"],
        _regular_file_record(
            Path(receipt["cmake_selection"]["Geant4_DIR"]) / "Geant4Config.cmake",
            label="Geant4Config.cmake",
        ),
        label="Geant4Config.cmake",
    )

    if runtime_probe:
        runtime = _probe_runtime(executable)
        _validate_runtime_identity(
            runtime,
            source=receipt["source"],
            executable=exe_now,
            cache=cache_now_values,
        )
        if runtime != receipt["runtime_build_identity"]:
            raise BuildReceiptError("runtime build identity differs from frozen receipt")

    if campaign_manifest is not None:
        if repo_root is None:
            raise BuildReceiptError("campaign verification requires --repo-root")
        manifest, _ = campaign.load_and_verify_manifest(
            campaign_manifest, expected_sha256=campaign_sha256
        )
        expected_core = campaign.verify_source_binding(manifest, repo_root)
        expected_root = manifest["superproject_commit"]
        if receipt["source"]["superproject_commit"] != expected_root:
            raise BuildReceiptError(
                "build receipt superproject commit != campaign source intent: "
                f"{receipt['source']['superproject_commit']} != {expected_root}"
            )
        if receipt["source"]["ccb_sipm_core_commit"] != expected_core:
            raise BuildReceiptError(
                "build receipt core commit != campaign source intent: "
                f"{receipt['source']['ccb_sipm_core_commit']} != {expected_core}"
            )


def _write_once(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() != data:
            raise BuildReceiptError(f"refusing to overwrite different existing file: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o444)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def _write_digest_once(path: Path, digest: str) -> None:
    _write_once(path, (digest + "\n").encode())


def _cmd_create(args: argparse.Namespace) -> int:
    receipt = create_receipt(
        repo_root=Path(args.repo_root).resolve(),
        build_dir=Path(args.build_dir).resolve(),
        executable=Path(args.executable).resolve(),
    )
    data = _canonical_bytes(receipt)
    digest = _sha256(data)
    _write_once(Path(args.receipt), data)
    _write_digest_once(Path(args.digest_file), digest)
    print(digest)
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    receipt, _, digest = load_receipt(
        Path(args.receipt), expected_sha256=args.expected_sha256
    )
    verify_receipt(
        receipt=receipt,
        executable=Path(args.executable).resolve(),
        runtime_probe=args.runtime_probe,
        campaign_manifest=Path(args.campaign_manifest).resolve() if args.campaign_manifest else None,
        campaign_sha256=args.campaign_sha256,
        repo_root=Path(args.repo_root).resolve() if args.repo_root else None,
    )
    print(digest)
    return 0


def _cmd_freeze(args: argparse.Namespace) -> int:
    source_path = Path(args.receipt).resolve()
    receipt, raw, digest = load_receipt(source_path, expected_sha256=args.expected_sha256)
    verify_receipt(
        receipt=receipt,
        executable=Path(args.executable).resolve(),
        runtime_probe=False,
        campaign_manifest=Path(args.campaign_manifest).resolve(),
        campaign_sha256=args.campaign_sha256,
        repo_root=Path(args.repo_root).resolve(),
    )
    _write_once(Path(args.output), raw)
    _write_digest_once(Path(args.digest_file), digest)
    print(digest)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--repo-root", required=True)
    create.add_argument("--build-dir", required=True)
    create.add_argument("--executable", required=True)
    create.add_argument("--receipt", required=True)
    create.add_argument("--digest-file", required=True)
    create.set_defaults(func=_cmd_create)

    verify = sub.add_parser("verify")
    verify.add_argument("--receipt", required=True)
    verify.add_argument("--expected-sha256", default=None)
    verify.add_argument("--executable", required=True)
    verify.add_argument("--runtime-probe", action="store_true")
    verify.add_argument("--campaign-manifest", default=None)
    verify.add_argument("--campaign-sha256", default=None)
    verify.add_argument("--repo-root", default=None)
    verify.set_defaults(func=_cmd_verify)

    freeze = sub.add_parser("freeze")
    freeze.add_argument("--receipt", required=True)
    freeze.add_argument("--expected-sha256", default=None)
    freeze.add_argument("--executable", required=True)
    freeze.add_argument("--campaign-manifest", required=True)
    freeze.add_argument("--campaign-sha256", required=True)
    freeze.add_argument("--repo-root", required=True)
    freeze.add_argument("--output", required=True)
    freeze.add_argument("--digest-file", required=True)
    freeze.set_defaults(func=_cmd_freeze)

    args = ap.parse_args()
    try:
        return args.func(args)
    except (BuildReceiptError, campaign.ManifestError, OSError, ValueError) as exc:
        print(f"fatal: {exc}", file=os.sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
