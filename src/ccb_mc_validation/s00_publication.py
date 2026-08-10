"""Crash-safe immutable-generation publication for S00 artifacts.

This module isolates the publication primitive required by ARU issue #1110.
It does not decide whether a scientific run is authorising; callers must make
that decision before publication. The primitive guarantees that a successful
publication changes authority through one small atomic pointer replacement,
while prior immutable generations are never deleted in the commit path.

The intended transaction is::

    build staging generation
    -> validate required artifacts/model identity
    -> move staging to immutable generations/<generation_id>
    -> fsync generation root
    -> atomically replace CURRENT.json
    -> fsync pointer directory

A crash before the pointer replacement can leave an orphan immutable generation,
but it cannot change the previously authoritative generation. This is preferred
to deleting/replacing a mutable report directory because concurrent readers
resolve one complete old or new generation through the pointer.

The current S00 producer is not wired to this primitive yet. Integration remains
part of #1110 and must also migrate downstream consumers away from assuming that
a mutable legacy path is authoritative.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Iterator, Mapping

try:  # Linux production/CI path; import remains controlled on other platforms.
    import fcntl
except ImportError:  # pragma: no cover - exercised only on non-POSIX systems.
    fcntl = None  # type: ignore[assignment]


POINTER_SCHEMA = "ccb.s00.publication-pointer.v1"
_GENERATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=-]{0,127}$")


class S00PublicationError(RuntimeError):
    """Controlled failure for invalid or unsafe S00 publication state."""


@dataclass(frozen=True)
class S00PublicationPointer:
    """Authoritative logical mapping to one immutable S00 generation."""

    generation_id: str
    artifacts: dict[str, str]
    model_identity: dict[str, object]

    def to_json_bytes(self) -> bytes:
        payload = {
            "schema": POINTER_SCHEMA,
            "generation_id": self.generation_id,
            "artifacts": self.artifacts,
            "model_identity": self.model_identity,
        }
        return (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _validate_generation_id(generation_id: str) -> str:
    if (
        not isinstance(generation_id, str)
        or not _GENERATION_ID_RE.fullmatch(generation_id)
    ):
        raise S00PublicationError(
            "generation_id must match [A-Za-z0-9][A-Za-z0-9._=-]{0,127}"
        )
    return generation_id


def _validate_relative_artifact_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise S00PublicationError("artifact paths must be non-empty strings")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path == Path("."):
        raise S00PublicationError(
            f"artifact path must stay inside its immutable generation: {value!r}"
        )
    return path.as_posix()


def _normalise_artifacts(artifacts: Mapping[str, str]) -> dict[str, str]:
    if not artifacts:
        raise S00PublicationError("at least one logical artifact is required")
    normalised: dict[str, str] = {}
    for logical_name, relative_path in artifacts.items():
        if not isinstance(logical_name, str) or not logical_name:
            raise S00PublicationError(
                "logical artifact names must be non-empty strings"
            )
        normalised[logical_name] = _validate_relative_artifact_path(relative_path)
    return dict(sorted(normalised.items()))


def _fsync_directory(path: Path) -> None:
    """Persist directory-entry changes on POSIX filesystems."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def _publication_lock(pointer_path: Path) -> Iterator[None]:
    """Serialize publishers; process death releases the advisory lock."""
    if fcntl is None:
        raise S00PublicationError("S00 publication requires POSIX flock support")
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = pointer_path.with_name(f".{pointer_path.name}.lock")
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def create_staging_directory(generation_root: Path, *, token: str) -> Path:
    """Create fresh staging on the same filesystem as immutable generations."""
    generation_root = Path(generation_root)
    _validate_generation_id(token)
    generation_root.mkdir(parents=True, exist_ok=True)
    staging = generation_root / f".staging-{token}-{os.getpid()}"
    if staging.exists():
        raise S00PublicationError(f"staging directory already exists: {staging}")
    staging.mkdir()
    return staging


def _load_pointer_bytes(pointer_path: Path) -> S00PublicationPointer:
    try:
        raw = pointer_path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise S00PublicationError(
            f"invalid publication pointer {pointer_path}: {exc}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema") != POINTER_SCHEMA:
        raise S00PublicationError(
            f"unsupported publication pointer schema: {payload!r}"
        )
    generation_id = _validate_generation_id(payload.get("generation_id"))
    artifacts_payload = payload.get("artifacts")
    model_identity = payload.get("model_identity")
    if not isinstance(artifacts_payload, dict):
        raise S00PublicationError("pointer artifacts must be a mapping")
    if not isinstance(model_identity, dict):
        raise S00PublicationError("pointer model_identity must be a mapping")
    artifacts = _normalise_artifacts(artifacts_payload)
    return S00PublicationPointer(
        generation_id=generation_id,
        artifacts=artifacts,
        model_identity=dict(model_identity),
    )


def read_publication_pointer(pointer_path: Path) -> S00PublicationPointer:
    """Read one complete old-or-new authority pointer snapshot."""
    pointer_path = Path(pointer_path)
    if not pointer_path.is_file():
        raise S00PublicationError(
            f"publication pointer does not exist: {pointer_path}"
        )
    return _load_pointer_bytes(pointer_path)


def resolve_artifact(
    pointer_path: Path,
    generation_root: Path,
    logical_name: str,
) -> Path:
    """Resolve a logical artifact through the authoritative immutable generation."""
    pointer = read_publication_pointer(pointer_path)
    if logical_name not in pointer.artifacts:
        raise S00PublicationError(f"unknown logical artifact {logical_name!r}")
    generation = Path(generation_root) / pointer.generation_id
    artifact = generation / pointer.artifacts[logical_name]
    if not artifact.is_file():
        raise S00PublicationError(
            "authoritative artifact missing from generation "
            f"{pointer.generation_id}: {artifact}"
        )
    return artifact


def publish_generation(
    staging_dir: Path,
    generation_root: Path,
    pointer_path: Path,
    *,
    generation_id: str,
    artifacts: Mapping[str, str],
    model_identity: Mapping[str, object],
) -> S00PublicationPointer:
    """Publish one immutable generation and atomically commit its pointer.

    All required artifacts and pointer serialization are validated before the
    staging directory is moved. The staging directory must be a direct child of
    ``generation_root`` so its rename to the immutable final directory stays on
    one filesystem.

    If pointer publication fails after the generation move, the previous pointer
    is unchanged. The new generation can remain as a non-authoritative orphan and
    may be garbage-collected later; rollback never deletes the previous authority.
    """
    staging_dir = Path(staging_dir)
    generation_root = Path(generation_root)
    pointer_path = Path(pointer_path)
    generation_id = _validate_generation_id(generation_id)
    normalised_artifacts = _normalise_artifacts(artifacts)
    if not isinstance(model_identity, Mapping):
        raise S00PublicationError("model_identity must be a mapping")

    generation_root.mkdir(parents=True, exist_ok=True)
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    if staging_dir.parent.resolve() != generation_root.resolve():
        raise S00PublicationError(
            "staging_dir must be a direct child of generation_root for "
            "same-filesystem rename"
        )
    if not staging_dir.is_dir():
        raise S00PublicationError(
            f"staging directory does not exist: {staging_dir}"
        )

    for logical_name, relative_path in normalised_artifacts.items():
        candidate = staging_dir / relative_path
        if not candidate.is_file():
            raise S00PublicationError(
                f"required artifact {logical_name!r} missing from staging: {candidate}"
            )

    final_generation = generation_root / generation_id
    pointer = S00PublicationPointer(
        generation_id=generation_id,
        artifacts=normalised_artifacts,
        model_identity=dict(model_identity),
    )
    try:
        pointer_bytes = pointer.to_json_bytes()
    except (TypeError, ValueError) as exc:
        raise S00PublicationError(
            f"model identity is not JSON-serializable: {exc}"
        ) from exc

    with _publication_lock(pointer_path):
        if final_generation.exists():
            raise S00PublicationError(
                f"immutable generation already exists: {final_generation}"
            )

        # Commit data first. Until CURRENT.json changes this generation is not authoritative.
        os.replace(staging_dir, final_generation)
        _fsync_directory(generation_root)

        # Publish one small pointer atomically; concurrent readers see old or new bytes.
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{pointer_path.name}.tmp-",
            dir=pointer_path.parent,
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(pointer_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, pointer_path)
            _fsync_directory(pointer_path.parent)
        except Exception:
            try:
                tmp_path.unlink(missing_ok=True)
            finally:
                raise

    return pointer
