#!/usr/bin/env python3
"""Fail-closed audit of repository-local links in Markdown files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

VERSION = "2.0.0"
POLICY = "MARKDOWN_LINK_TARGETS_MUST_BE_UTF8_AND_REPOSITORY_LOCAL"
LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
SKIPPED_SCHEMES = {"data", "http", "https", "mailto", "tel"}


@dataclass(frozen=True)
class Finding:
    code: str
    source: str
    line: int | None
    target: str | None
    resolved: str | None
    detail: str


IGNORE_DIR_PARTS = {
    ".git", "artifacts", "node_modules", "__pycache__", ".venv", "venv", ".claude",
}
# Generated pipeline output dirs, named "<epoch>.<run>.<hex>__<study>"
# (e.g. 1781068159.1612.2426717d__p05f_two_pulse_risk_coverage_sidebands).
GENERATED_DIR_RE = re.compile(r"^\d{8,}\.\d+\.")


def find_markdown_files(root: Path) -> list[Path]:
    """Return curated Markdown files in deterministic repository-relative order.

    Generated content is excluded so the audit covers hand-maintained docs only:
      * artifacts/        - timestamped pipeline snapshot bundles
      * reports/<epoch>.  - generated per-run pipeline reports
      * ._*.md            - macOS AppleDouble resource-fork junk
    """
    out = []
    for path in root.rglob("*.md"):
        parts = path.relative_to(root).parts
        if ".git" in parts:
            continue
        if any(part in IGNORE_DIR_PARTS for part in parts):
            continue
        if any(GENERATED_DIR_RE.match(part) for part in parts):
            continue
        if any(part.startswith("._") for part in parts):
            continue
        if path.is_file():
            out.append(path)
    return sorted(out)


def decode_markdown(path: Path, root: Path) -> tuple[str | None, Finding | None]:
    """Decode one Markdown file strictly as UTF-8 without hiding byte errors."""
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError as exc:
        relative = path.relative_to(root).as_posix()
        finding = Finding(
            code="INVALID_UTF8",
            source=relative,
            line=None,
            target=None,
            resolved=None,
            detail=(
                f"UTF-8 decode failed at byte {exc.start}: "
                f"{exc.reason}; file bytes were not modified"
            ),
        )
        return None, finding


def extract_links(text: str) -> list[tuple[int, str, str]]:
    """Extract inline Markdown links and images with source line numbers."""
    links: list[tuple[int, str, str]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for match in LINK_RE.finditer(line):
            links.append((line_number, match.group(1), match.group(2).strip()))
    return links


def link_path(target: str) -> str | None:
    """Return the local path component, or None for links not checked here."""
    if target.startswith("#"):
        return None
    parsed = urlsplit(target)
    if parsed.scheme.lower() in SKIPPED_SCHEMES or parsed.netloc:
        return None
    candidate = parsed.path.strip()
    if candidate.startswith("<") and candidate.endswith(">"):
        candidate = candidate[1:-1]
    return unquote(candidate) or None


def resolve_local_target(root: Path, source: Path, target: str) -> tuple[Path, bool]:
    """Resolve a local target and report whether it remains beneath root."""
    candidate = source.parent / target
    resolved = candidate.resolve(strict=False)
    return resolved, resolved.is_relative_to(root)


def audit_markdown_links(root: Path) -> dict[str, object]:
    """Audit all Markdown files beneath root and return a stable result record."""
    root = root.resolve()
    findings: list[Finding] = []
    files = find_markdown_files(root)
    links_seen = 0
    local_links_checked = 0

    for source in files:
        text, decode_finding = decode_markdown(source, root)
        if decode_finding is not None:
            findings.append(decode_finding)
            continue
        assert text is not None
        for line_number, label, target in extract_links(text):
            links_seen += 1
            target_path = link_path(target)
            if target_path is None:
                continue
            local_links_checked += 1
            resolved, inside_root = resolve_local_target(root, source, target_path)
            relative_source = source.relative_to(root).as_posix()
            try:
                relative_resolved = resolved.relative_to(root).as_posix()
            except ValueError:
                relative_resolved = str(resolved)

            if not inside_root:
                findings.append(
                    Finding(
                        code="TARGET_ESCAPES_ROOT",
                        source=relative_source,
                        line=line_number,
                        target=target,
                        resolved=relative_resolved,
                        detail=f"link label {label!r} resolves outside the repository root",
                    )
                )
            elif not resolved.exists():
                findings.append(
                    Finding(
                        code="MISSING_TARGET",
                        source=relative_source,
                        line=line_number,
                        target=target,
                        resolved=relative_resolved,
                        detail=f"link label {label!r} points to a missing repository path",
                    )
                )

    ordered = sorted(
        findings,
        key=lambda item: (
            item.source,
            item.line if item.line is not None else -1,
            item.code,
            item.target or "",
        ),
    )
    return {
        "validator": "scripts/broken_link_checker.py",
        "version": VERSION,
        "policy": POLICY,
        "root": str(root),
        "markdown_files": len(files),
        "links_seen": links_seen,
        "local_links_checked": local_links_checked,
        "status": "VALIDATED" if not ordered else "FLAWED",
        "finding_count": len(ordered),
        "findings": [asdict(item) for item in ordered],
        "limitations": [
            "Inline Markdown links and images are checked; reference-style links are not parsed.",
            "Fragment-only links and heading-anchor existence are not evaluated.",
            "External URLs are intentionally not requested by this offline repository audit.",
        ],
    }


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    """Publish a JSON result atomically in the destination directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument("--json-out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = audit_markdown_links(args.root)
        if args.json_out is not None:
            write_json_atomic(args.json_out, result)
    except OSError as exc:
        print(f"ERROR: unable to audit Markdown links: {exc}", file=sys.stderr)
        return 2

    for finding in result["findings"]:
        line = finding["line"] if finding["line"] is not None else "?"
        print(
            f"{finding['code']}: {finding['source']}:{line}: "
            f"{finding['target'] or '-'} -> {finding['resolved'] or '-'}"
        )
    count = result["finding_count"]
    if count:
        print(f"\n{count} Markdown link finding(s) found.")
        return 1
    print("All checked repository-local Markdown links are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
