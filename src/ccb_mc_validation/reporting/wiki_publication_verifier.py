"""Verify that generated wiki pages are published on the GitHub Wiki.

The generator can prove a local ``wiki/`` bundle exists, but it cannot prove the
repository's separate GitHub Wiki git repository has been created and pushed.
This verifier is intentionally fail-closed: every page listed in the local
``WIKI_MANIFEST.json`` must be reachable from the public wiki URL and must carry
basic provenance snippets from the generated draft bundle.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_WIKI_BASE_URL = "https://github.com/SzeChunYiu/ccb-testbeam/wiki"


@dataclass(frozen=True)
class WikiPagePublicationCheck:
    """HTTP publication result for one generated wiki page."""

    page: str
    url: str
    status_code: int | None
    status: str
    reason: str
    required_snippets: tuple[str, ...]
    missing_snippets: tuple[str, ...]


Fetch = Callable[[str, float], tuple[int, str]]


def _read_manifest(manifest_path: Path) -> dict[str, object]:
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing wiki manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _page_url(base_url: str, page: str) -> str:
    slug = "" if page == "Home.md" else "/" + page.removesuffix(".md")
    return base_url.rstrip("/") + slug


def _title_snippet(page: str, page_text: str) -> str | None:
    for line in page_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _required_snippets(page: str, page_text: str, run_id: str) -> tuple[str, ...]:
    snippets: list[str] = []
    # Some generated pages carry the frozen run id directly while others inherit
    # provenance through linked artifacts.  Require the run id only where the
    # generated page actually contains it; otherwise the verifier would report a
    # publication failure for a faithful render of the local source page.
    if run_id and run_id in page_text:
        snippets.append(run_id)
    title = _title_snippet(page, page_text)
    if title:
        snippets.append(title)
    page_specific = {
        "Home.md": "Draft / not final release",
        "Claim-Evidence-Matrix.md": "Claim evidence matrix",
        "Claim-Dependency-Tree.md": "Claim dependency tree",
        "References-and-Reproducibility.md": "References and reproducibility",
    }.get(page)
    if page_specific and page_specific in page_text:
        snippets.append(page_specific)
    # Preserve order while removing duplicates.
    return tuple(dict.fromkeys(snippets))


def fetch_url(url: str, timeout: float = 20.0) -> tuple[int, str]:
    """Fetch a URL using only the Python standard library."""

    req = Request(url, headers={"User-Agent": "ccb-testbeam-wiki-verifier/1.0"})
    try:
        with urlopen(req, timeout=timeout) as response:  # nosec B310: explicit verification utility
            charset = response.headers.get_content_charset() or "utf-8"
            text = response.read().decode(charset, errors="replace")
            return int(response.status), text
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), text
    except URLError as exc:
        raise RuntimeError(f"failed to fetch {url}: {exc}") from exc


def _iter_manifest_pages(manifest: dict[str, object]) -> Iterable[str]:
    pages = manifest.get("pages")
    if not isinstance(pages, list) or not all(isinstance(page, str) for page in pages):
        raise ValueError("wiki manifest must contain a string list field named 'pages'")
    return pages


def verify_github_wiki_publication(
    manifest_path: Path,
    *,
    wiki_dir: Path | None = None,
    base_url: str = DEFAULT_WIKI_BASE_URL,
    fetch: Fetch = fetch_url,
    timeout: float = 20.0,
) -> dict[str, object]:
    """Verify public GitHub Wiki pages against a generated wiki manifest."""

    manifest_path = Path(manifest_path)
    wiki_dir = Path(wiki_dir) if wiki_dir is not None else manifest_path.parent
    manifest = _read_manifest(manifest_path)
    run_id = str(manifest.get("run_id") or "")

    page_checks: list[WikiPagePublicationCheck] = []
    for page in _iter_manifest_pages(manifest):
        if page == "WIKI_MANIFEST.json":
            continue
        generated_page = wiki_dir / page
        if not generated_page.is_file():
            page_checks.append(
                WikiPagePublicationCheck(
                    page=page,
                    url=_page_url(base_url, page),
                    status_code=None,
                    status="BLOCKED",
                    reason=f"generated page missing locally: {generated_page}",
                    required_snippets=(),
                    missing_snippets=(),
                )
            )
            continue

        generated_text = generated_page.read_text(encoding="utf-8")
        snippets = _required_snippets(page, generated_text, run_id)
        url = _page_url(base_url, page)
        try:
            status_code, published_text = fetch(url, timeout)
        except Exception as exc:  # noqa: BLE001 - report fail-closed diagnostic text
            page_checks.append(
                WikiPagePublicationCheck(
                    page=page,
                    url=url,
                    status_code=None,
                    status="BLOCKED",
                    reason=str(exc),
                    required_snippets=snippets,
                    missing_snippets=snippets,
                )
            )
            continue

        missing = tuple(snippet for snippet in snippets if snippet not in published_text)
        if status_code == 200 and not missing:
            status = "PASS"
            reason = "HTTP 200 and provenance snippets present"
        elif status_code != 200:
            status = "BLOCKED"
            reason = f"HTTP status {status_code}; expected 200"
        else:
            status = "BLOCKED"
            reason = "published page missing generated provenance snippets"
        page_checks.append(
            WikiPagePublicationCheck(
                page=page,
                url=url,
                status_code=status_code,
                status=status,
                reason=reason,
                required_snippets=snippets,
                missing_snippets=missing,
            )
        )

    blocked = [check for check in page_checks if check.status != "PASS"]
    status = "PASS" if not blocked and page_checks else "BLOCKED"
    return {
        "status": status,
        "scope": "github-wiki-publication-http",
        "base_url": base_url.rstrip("/"),
        "manifest_path": str(manifest_path),
        "run_id": run_id,
        "page_count": len(page_checks),
        "published_count": len(page_checks) - len(blocked),
        "blocked_count": len(blocked),
        "pages": [asdict(check) for check in page_checks],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed HTTP verifier for generated CCB GitHub Wiki pages.",
    )
    parser.add_argument("manifest", type=Path, help="Path to generated wiki/WIKI_MANIFEST.json")
    parser.add_argument("--wiki-dir", type=Path, default=None, help="Directory containing generated wiki markdown pages")
    parser.add_argument("--base-url", default=DEFAULT_WIKI_BASE_URL, help="GitHub Wiki base URL")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = verify_github_wiki_publication(
        args.manifest,
        wiki_dir=args.wiki_dir,
        base_url=args.base_url,
        timeout=args.timeout,
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
