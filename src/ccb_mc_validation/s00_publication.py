"""Crash-safe, content-bound immutable-generation publication for S00 artifacts.

This module isolates the publication primitive required by ARU issues #1110 and
#1147. It does not decide whether a scientific run is authorising; callers must
make that decision before publication. A successful publication changes authority
through one small atomic pointer replacement, while prior generations are never
deleted in the commit path.

The intended transaction is::

    build staging generation
    -> validate required artifacts/model identity
    -> bind SHA-256 identities for authoritative artifacts
    -> fsync authoritative artifacts
    -> move staging to immutable generations/<generation_id>
    -> revalidate physical containment + bound hashes
    -> fsync generation root
    -> atomically replace CURRENT.json
    -> fsync pointer directory

A crash before pointer replacement can leave an orphan generation, but it cannot
change the previously authoritative pointer. The pointer is content-bound: a
consumer resolves a logical artifact only after its current bytes reproduce the
SHA-256 digest committed in the pointer.

The current S00 producer is not wired to this primitive yet. Integration remains
part of #1110 and must also migrate downstream consumers away from assuming that
a mutable legacy path is authoritative.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
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


POINTER_SCHEMA = "ccb.s00.publication-pointer.v2"
_GENERATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class S00PublicationError(RuntimeError):
    """Controlled failure for invalid or unsafe S00 publication state."""


@dataclass(frozen=True)
class S00PublicationPointer:
    """Authoritative logical mapping to one content-bound S00 generation."""

    generation_id: str
    artifacts: dict[str, str]
    artifact_sha256: dict[str, str]
    model_identity: dict[str, object]

    def to_json_bytes(self) -> bytes:
        payload = {
            "schema": POINTER_SCHEMA,
            "generation_id": self.generation_id,
            "artifacts": self.artifacts,
            "artifact_sha256": self.artifact_sha256,
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


def _normalise_artifact_sha256(
    artifact_sha256: Mapping[str, str],
    *,
    artifacts: Mapping[str, str],
) -> dict[str, str]:
    if not isinstance(artifact_sha256, Mapping):
        raise S00PublicationError("pointer artifact_sha256 must be a mapping")
    normalised: dict[str, str] = {}
    for logical_name, digest in artifact_sha256.items():
        if not isinstance(logical_name, str) or not logical_name:
            raise S00PublicationError(
                "artifact_sha256 logical names must be non-empty strings"
            )
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise S00PublicationError(
                f"invalid SHA-256 digest for {logical_name!r}: {digest!r}"
            )
        normalised[logical_name] = digest
    if set(normalised) != set(artifacts):
        raise S00PublicationError(
            "artifact_sha256 keys must exactly match pointer artifact keys"
        )
    return dict(sorted(normalised.items()))


def _sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def _has_symlink_component(root: Path, relative_path: str) -> bool:
    current = root
    for part in Path(relative_path).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _validated_artifact_path(
    root: Path,
    relative_path: str,
    *,
    logical_name: str,
) -> Path:
    """Return a regular artifact proven physically inside ``root``.

    Lexical ``..`` checks are not sufficient because ``Path.is_file()`` follows
    symbolic links. This helper rejects any symlink component and separately
    proves that the resolved target is below the resolved generation/staging root.
    """
    root = Path(root)
    candidate = root / relative_path
    if _has_symlink_component(root, relative_path):
        raise S00PublicationError(
            f"artifact {logical_name!r} must not contain symlink components: {candidate}"
        )
    if not candidate.exists():
        raise S00PublicationError(
            "required artifact missing; authoritative artifact missing from generation: "
            f"{logical_name!r}: {candidate}"
        )
    try:
        root_resolved = root.resolve(strict=True)
        candidate_resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise S00PublicationError(
            f"required artifact {logical_name!r} cannot be resolved: {candidate}: {exc}"
        ) from exc
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise S00PublicationError(
            f"artifact {logical_name!r} escapes its immutable generation: {candidate}"
        ) from exc
    if not candidate_resolved.is_file():
        raise S00PublicationError(
            f"required artifact {logical_name!r} missing from generation: {candidate}"
        )
    return candidate


def _fsync_file(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


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
    artifact_sha256_payload = payload.get("artifact_sha256")
    model_identity = payload.get("model_identity")
    if not isinstance(artifacts_payload, dict):
        raise S00PublicationError("pointer artifacts must be a mapping")
    if not isinstance(model_identity, dict):
        raise S00PublicationError("pointer model_identity must be a mapping")
    artifacts = _normalise_artifacts(artifacts_payload)
    artifact_sha256 = _normalise_artifact_sha256(
        artifact_sha256_payload,
        artifacts=artifacts,
    )
    return S00PublicationPointer(
        generation_id=generation_id,
        artifacts=artifacts,
        artifact_sha256=artifact_sha256,
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
    """Resolve and content-verify an artifact pathname at verification time.

    WARNING (#1149): returning this ``Path`` is NOT a same-bytes read guarantee.
    A writer can mutate the file (including via hard-link alias) after verification
    and before a later reopen. Authorising consumers MUST use
    ``ccb_mc_validation.s00_verified_read.verified_artifact_snapshot`` and read
    only the yielded private snapshot. See
    ``docs/contracts/S00_VERIFIED_READ_CONTRACT.md``.
    """
    pointer = read_publication_pointer(pointer_path)
    if logical_name not in pointer.artifacts:
        raise S00PublicationError(f"unknown logical artifact {logical_name!r}")
    generation = Path(generation_root) / pointer.generation_id
    artifact = _validated_artifact_path(
        generation,
        pointer.artifacts[logical_name],
        logical_name=logical_name,
    )
    observed = _sha256_file(artifact)
    expected = pointer.artifact_sha256[logical_name]
    if observed != expected:
        raise S00PublicationError(
            "authoritative artifact content hash mismatch for "
            f"{logical_name!r}: expected {expected}, observed {observed}"
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
    """Publish one content-bound immutable generation and atomically commit its pointer.

    All authoritative artifacts, their physical containment, their SHA-256 identities,
    and pointer serialization are validated before the staging directory is moved.
    The staging directory must be a direct child of ``generation_root`` so its rename
    to the immutable final directory stays on one filesystem.

    After the move, the same paths and digests are revalidated before pointer commit.
    If pointer publication fails, the previous pointer is unchanged. The new generation
    can remain as a non-authoritative orphan; rollback never deletes prior authority.
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
    if staging_dir.is_symlink():
        raise S00PublicationError("staging_dir itself must not be a symbolic link")
    if staging_dir.parent.resolve() != generation_root.resolve():
        raise S00PublicationError(
            "staging_dir must be a direct child of generation_root for "
            "same-filesystem rename"
        )
    if not staging_dir.is_dir():
        raise S00PublicationError(
            f"staging directory does not exist: {staging_dir}"
        )

    artifact_sha256: dict[str, str] = {}
    for logical_name, relative_path in normalised_artifacts.items():
        candidate = _validated_artifact_path(
            staging_dir,
            relative_path,
            logical_name=logical_name,
        )
        artifact_sha256[logical_name] = _sha256_file(candidate)
        _fsync_file(candidate)

    final_generation = generation_root / generation_id
    pointer = S00PublicationPointer(
        generation_id=generation_id,
        artifacts=normalised_artifacts,
        artifact_sha256=dict(sorted(artifact_sha256.items())),
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

        # Revalidate both physical containment and bytes after the move. A concurrent
        # mutation can at worst cause this publication to fail before authority changes.
        for logical_name, relative_path in normalised_artifacts.items():
            candidate = _validated_artifact_path(
                final_generation,
                relative_path,
                logical_name=logical_name,
            )
            observed = _sha256_file(candidate)
            if observed != artifact_sha256[logical_name]:
                raise S00PublicationError(
                    "artifact changed between staging validation and generation commit: "
                    f"{logical_name!r}"
                )

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
