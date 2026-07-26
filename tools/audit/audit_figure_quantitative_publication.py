#!/usr/bin/env python3
"""Audit quantitative paper-figure publication for atomic failure safety."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "QUANTITATIVE_FIGURE_PUBLICATION_MUST_BE_ATOMIC_AND_FAILURE_SAFE"


class AuditInputError(RuntimeError):
    """Controlled source-input or evidence-publication failure."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_snapshot(path: Path) -> tuple[bytes, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AuditInputError(f"cannot read source: {exc}") from exc
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditInputError(f"source is not strict UTF-8: {exc}") from exc
    return raw, text


def _same_file(left: Path, right: Path) -> bool:
    try:
        if left.resolve() == right.resolve():
            return True
    except OSError:
        pass
    try:
        return left.exists() and right.exists() and os.path.samefile(left, right)
    except OSError:
        return False


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return {
        "bytes": len(encoded),
        "sha256": _sha256(encoded),
        "publication": "SAME_DIRECTORY_TEMP_FLUSH_FSYNC_OS_REPLACE",
    }


def _functions(tree: ast.AST) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _segment(text: str, node: ast.AST) -> str:
    return ast.get_source_segment(text, node) or ""


def _is_inside_finally(target: ast.AST, function: ast.FunctionDef) -> bool:
    for node in ast.walk(function):
        if not isinstance(node, ast.Try):
            continue
        for final_node in node.finalbody:
            if target is final_node or target in ast.walk(final_node):
                return True
    return False


def source_patterns(tree: ast.AST, text: str) -> dict[str, Any]:
    function = _functions(tree).get("_emit_quantitative")
    if function is None:
        raise AuditInputError("source has no _emit_quantitative function")

    direct_final_save = False
    atomic_figure_publish = False
    temporary_render = False
    close_in_finally = False
    savefig_calls: list[str] = []

    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        call_text = _segment(text, node)
        if name == "savefig":
            savefig_calls.append(call_text)
            if node.args and "figure_path" in _segment(text, node.args[0]):
                direct_final_save = True
            if node.args and any(
                token in _segment(text, node.args[0])
                for token in ("temporary", "temp_path", "render_path")
            ):
                temporary_render = True
        elif name == "_atomic_publish_snapshot" and "figure_path" in call_text:
            atomic_figure_publish = True
        elif name in {"mkstemp", "NamedTemporaryFile"}:
            temporary_render = True
        elif name == "close" and "fig" in call_text:
            close_in_finally = close_in_finally or _is_inside_finally(node, function)

    return {
        "direct_final_save": direct_final_save,
        "atomic_figure_publish": atomic_figure_publish,
        "temporary_render": temporary_render,
        "close_in_finally": close_in_finally,
        "savefig_calls": savefig_calls,
    }


def behavioral_controls() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        target = root / "figure.png"
        previous = b"previous-validated-figure"
        partial = b"partial-render"
        replacement = b"complete-new-render"

        target.write_bytes(previous)
        former_error = ""
        try:
            with target.open("wb") as handle:
                handle.write(partial)
                handle.flush()
                os.fsync(handle.fileno())
                raise OSError("injected render failure")
        except OSError as exc:
            former_error = str(exc)
        former_bytes = target.read_bytes()

        target.write_bytes(previous)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=root
        )
        temporary = Path(temporary_name)
        corrected_error = ""
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(partial)
                handle.flush()
                os.fsync(handle.fileno())
                raise OSError("injected render failure")
        except OSError as exc:
            corrected_error = str(exc)
            temporary.unlink(missing_ok=True)
        corrected_after_failure = target.read_bytes()
        temporary_count_after_failure = len(list(root.glob(f".{target.name}.*.tmp")))

        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=root
        )
        temporary = Path(temporary_name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(replacement)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        corrected_after_success = target.read_bytes()

        return {
            "former_direct_target_failure": {
                "injected_error": former_error,
                "previous_sha256": _sha256(previous),
                "post_failure_sha256": _sha256(former_bytes),
                "previous_target_preserved": former_bytes == previous,
                "post_failure_bytes": len(former_bytes),
                "interpretation": (
                    "Writing the rendered PNG directly to the final path can destroy a "
                    "previous validated artifact when rendering fails after truncation."
                ),
            },
            "corrected_temporary_failure": {
                "injected_error": corrected_error,
                "previous_sha256": _sha256(previous),
                "post_failure_sha256": _sha256(corrected_after_failure),
                "previous_target_preserved": corrected_after_failure == previous,
                "temporary_files_remaining": temporary_count_after_failure,
                "interpretation": (
                    "Rendering to a same-directory temporary file and deleting it on failure "
                    "preserves the prior target and leaves no partial publication."
                ),
            },
            "corrected_atomic_success": {
                "replacement_sha256": _sha256(replacement),
                "published_sha256": _sha256(corrected_after_success),
                "published_matches_replacement": corrected_after_success == replacement,
                "interpretation": (
                    "Only a complete rendered snapshot is moved onto the final path."
                ),
            },
        }


def audit_source(
    source: Path,
    *,
    source_ref: str | None = None,
    source_blob: str | None = None,
    source_scope: str = "LOCAL_SOURCE_FILE",
) -> dict[str, Any]:
    raw, text = _read_snapshot(source)
    try:
        tree = ast.parse(text, filename=str(source))
    except SyntaxError as exc:
        raise AuditInputError(f"source is not valid Python: {exc}") from exc

    patterns = source_patterns(tree, text)
    controls = behavioral_controls()
    findings: list[dict[str, str]] = []

    if patterns["direct_final_save"]:
        findings.append(
            {
                "code": "QUANTITATIVE_RENDER_WRITES_FINAL_PATH_DIRECTLY",
                "detail": (
                    "_emit_quantitative passes the final figure path directly to savefig; "
                    "a failed render can truncate or partially replace prior evidence."
                ),
            }
        )
    if not patterns["temporary_render"] or not patterns["atomic_figure_publish"]:
        findings.append(
            {
                "code": "QUANTITATIVE_FIGURE_HAS_NO_ATOMIC_PUBLICATION_BOUNDARY",
                "detail": (
                    "The quantitative PNG is not rendered to retained temporary bytes and "
                    "atomically published to the final target."
                ),
            }
        )
    if not patterns["close_in_finally"]:
        findings.append(
            {
                "code": "QUANTITATIVE_FIGURE_NOT_CLOSED_ON_RENDER_FAILURE",
                "detail": (
                    "The matplotlib figure is closed only after savefig returns; a render "
                    "exception can bypass cleanup in long registry builds."
                ),
            }
        )

    return {
        "schema": "ccb-figure-quantitative-publication-audit/1",
        "version": VERSION,
        "policy": POLICY,
        "status": "FLAWED" if findings else "VALIDATED",
        "finding_count": len(findings),
        "findings": findings,
        "source": {
            "path": str(source),
            "scope": source_scope,
            "bytes": len(raw),
            "sha256": _sha256(raw),
            "repository_ref": source_ref,
            "git_blob": source_blob,
            "snapshot_method": "SINGLE_READ_STRICT_UTF8_EXACT_BYTES",
        },
        "source_contract_observation": patterns,
        "behavioral_controls": controls,
        "required_remediation": {
            "render": (
                "Render each quantitative PNG to a same-directory temporary file with an "
                "explicit PNG format, then read and retain the complete bytes."
            ),
            "publication": (
                "Atomically publish the retained render snapshot to the final path with flush, "
                "fsync, os.replace, cleanup, and final-target digest verification."
            ),
            "cleanup": (
                "Close the matplotlib figure in a finally block so render errors cannot leak "
                "figure resources across a registry build."
            ),
            "regression": (
                "Inject save and replacement failures and prove that a pre-existing validated "
                "target remains byte-identical and no temporary file remains."
            ),
        },
        "scientific_boundary": (
            "This audit validates quantitative figure-publication integrity only. It does not "
            "validate any plotted scientific value, uncertainty, calibration, PID, timing, "
            "stopping profile, pile-up rate, or detector-performance claim."
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-ref")
    parser.add_argument("--source-blob")
    parser.add_argument("--source-scope", default="LOCAL_SOURCE_FILE")
    parser.add_argument("--repository")
    parser.add_argument("--initial-main")
    parser.add_argument("--source-path-in-repo")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.output and _same_file(args.source, args.output):
        print("INPUT_ERROR: output aliases source", file=os.sys.stderr)
        return 2
    try:
        result = audit_source(
            args.source,
            source_ref=args.source_ref,
            source_blob=args.source_blob,
            source_scope=args.source_scope,
        )
        result["repository_context"] = {
            "repository": args.repository,
            "initial_main": args.initial_main,
            "source_path": args.source_path_in_repo,
        }
        if args.output:
            result["output_publication"] = _atomic_write_json(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "VALIDATED" else 1
    except AuditInputError as exc:
        print(f"INPUT_ERROR: {exc}", file=os.sys.stderr)
        return 2
    except OSError as exc:
        print(f"OUTPUT_ERROR: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
