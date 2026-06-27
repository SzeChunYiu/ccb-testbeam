"""GitHub Wiki publication verifier tests."""
from __future__ import annotations

import json
from pathlib import Path

from ccb_mc_validation.reporting.wiki_publication_verifier import verify_github_wiki_publication


def _seed_wiki(tmp_path: Path) -> Path:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    manifest = {
        "run_id": "run-published",
        "pages": [
            "Home.md",
            "Claim-Evidence-Matrix.md",
            "References-and-Reproducibility.md",
        ],
    }
    (wiki / "WIKI_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    (wiki / "Home.md").write_text(
        "# CCB testbeam MC validation wiki draft\n\n"
        "> **Draft / not final release.** run `run-published`.\n",
        encoding="utf-8",
    )
    (wiki / "Claim-Evidence-Matrix.md").write_text(
        "# Claim evidence matrix\n\nrun-published\n",
        encoding="utf-8",
    )
    (wiki / "References-and-Reproducibility.md").write_text(
        "# References reproducibility\n\nrun-published\n",
        encoding="utf-8",
    )
    return wiki


def test_verify_github_wiki_publication_passes_when_pages_are_reachable(tmp_path: Path) -> None:
    wiki = _seed_wiki(tmp_path)

    def fetch(url: str, timeout: float) -> tuple[int, str]:
        del timeout
        page = "Home.md" if url.endswith("/wiki") else url.rsplit("/", 1)[-1] + ".md"
        return 200, (wiki / page).read_text(encoding="utf-8")

    result = verify_github_wiki_publication(
        wiki / "WIKI_MANIFEST.json",
        base_url="https://example.test/repo/wiki",
        fetch=fetch,
    )

    assert result["status"] == "PASS"
    assert result["published_count"] == 3
    assert result["blocked_count"] == 0
    assert result["pages"][0]["url"] == "https://example.test/repo/wiki"


def test_verify_github_wiki_publication_blocks_missing_page_content(tmp_path: Path) -> None:
    wiki = _seed_wiki(tmp_path)

    def fetch(url: str, timeout: float) -> tuple[int, str]:
        del url, timeout
        return 200, "# unrelated stale wiki page\n"

    result = verify_github_wiki_publication(
        wiki / "WIKI_MANIFEST.json",
        base_url="https://example.test/repo/wiki",
        fetch=fetch,
    )

    assert result["status"] == "BLOCKED"
    assert result["blocked_count"] == 3
    assert "run-published" in result["pages"][0]["missing_snippets"]


def test_verify_github_wiki_publication_blocks_http_failures(tmp_path: Path) -> None:
    wiki = _seed_wiki(tmp_path)

    def fetch(url: str, timeout: float) -> tuple[int, str]:
        del url, timeout
        return 404, "not found"

    result = verify_github_wiki_publication(
        wiki / "WIKI_MANIFEST.json",
        base_url="https://example.test/repo/wiki",
        fetch=fetch,
    )

    assert result["status"] == "BLOCKED"
    assert result["blocked_count"] == 3
    assert result["pages"][0]["reason"] == "HTTP status 404; expected 200"
