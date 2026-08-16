#!/usr/bin/env python3
"""Generate the wiki/gallery surfaces from the canonical figure manifest."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
from typing import Any

BEGIN = "<!-- BEGIN GENERATED PAPER-GRADE FIGURES -->"
END = "<!-- END GENERATED PAPER-GRADE FIGURES -->"


def _section(figures: list[dict[str, Any]], *, prefix: str) -> str:
    lines = [
        BEGIN,
        "### Paper-grade figure set",
        "",
        "These figures are generated from tracked evidence, not hand-entered headline values. "
        "Each caption states the applicable evidence class; simulation closure is not presented "
        "as a beam-data measurement.",
        "",
    ]
    for item in figures:
        stem = item["stem"]
        lines.extend(
            [
                f"#### {item['title']}",
                "",
                f"![{item['title']}]({prefix}{stem}.png)",
                "",
                f"**{item['status']} · {item['evidence_class']}.** {item['caption']}",
                "",
            ]
        )
    lines.extend(
        [
            "Source tables, vector files and hashes: "
            "[`docs/figures/paper/manifest.json`](docs/figures/paper/manifest.json).",
            END,
        ]
    )
    return "\n".join(lines)


def _replace_or_insert(text: str, section: str) -> str:
    if BEGIN in text or END in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1:
            raise ValueError("WIKI.md contains malformed generated-figure markers")
        before, tail = text.split(BEGIN, 1)
        _, after = tail.split(END, 1)
        return before.rstrip() + "\n\n" + section + after
    anchor = "### MC method closure — proven on Monte Carlo (clusters A–D + Opticks)"
    if anchor not in text:
        raise ValueError(f"cannot find WIKI.md insertion anchor: {anchor}")
    return text.replace(anchor, section + "\n\n" + anchor, 1)


def _gallery(figures: list[dict[str, Any]], *, prefix: str, title: str) -> str:
    lines = [
        f"# {title}",
        "",
        "Generated from `docs/figures/paper/manifest.json`. Captions are external to the image "
        "so the plot area remains uncluttered. PDF and SVG versions sit beside every PNG.",
        "",
    ]
    for item in figures:
        lines.extend(
            [
                f"## {item['figure_id']} — {item['title']}",
                "",
                f"**Question:** {item['question']}",
                "",
                f"![{item['title']}]({prefix}{item['stem']}.png)",
                "",
                f"**Status:** `{item['status']}` · **Evidence:** `{item['evidence_class']}`",
                "",
                item["caption"],
                "",
                f"[PDF]({prefix}{item['stem']}.pdf) · "
                f"[SVG]({prefix}{item['stem']}.svg) · "
                f"[source CSV]({prefix}source_tables/{item['stem']}_source.csv)",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _manifest_csv(figures: list[dict[str, Any]]) -> str:
    fields = [
        "figure_id",
        "stem",
        "title",
        "question",
        "status",
        "evidence_class",
        "source_table",
        "source_table_sha256",
        "width_mm",
        "height_mm",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for item in figures:
        writer.writerow({field: item.get(field, "") for field in fields})
    return stream.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path, default=Path("docs/figures/paper/manifest.json"))
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    figures = payload.get("figures")
    if not isinstance(figures, list) or len(figures) != 11:
        raise ValueError("expected the canonical eleven-figure manifest")

    wiki_path = root / "WIKI.md"
    wiki_text = wiki_path.read_text(encoding="utf-8")
    wiki_path.write_text(
        _replace_or_insert(wiki_text, _section(figures, prefix="docs/figures/paper/")),
        encoding="utf-8",
    )

    (root / "docs/FIGURE_GALLERY.md").write_text(
        _gallery(figures, prefix="figures/paper/", title="CCB paper-grade figure gallery"),
        encoding="utf-8",
    )
    (root / "docs/wiki_plot_manifest.csv").write_text(_manifest_csv(figures), encoding="utf-8")

    raw_prefix = (
        "https://raw.githubusercontent.com/SzeChunYiu/ccb-testbeam/main/docs/figures/paper/"
    )
    wiki_dir = root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "Figure-Gallery.md").write_text(
        _gallery(figures, prefix=raw_prefix, title="CCB paper-grade figure gallery"),
        encoding="utf-8",
    )
    (wiki_dir / "Home.md").write_text(
        "# CCB test-beam wiki\n\n"
        "The controlled repository synthesis is maintained in "
        "[`WIKI.md`](https://github.com/SzeChunYiu/ccb-testbeam/blob/main/WIKI.md).\n\n"
        "The redesigned publication figures are collected in "
        "[[Figure Gallery|Figure-Gallery]]. Claim states remain governed by "
        "`docs/claim_ledger.csv`; visual polish does not promote gated or blocked results.\n",
        encoding="utf-8",
    )
    (wiki_dir / "_Sidebar.md").write_text(
        "* [[Home]]\n* [[Figure Gallery|Figure-Gallery]]\n",
        encoding="utf-8",
    )
    print("updated WIKI.md, docs gallery, plot manifest and staged GitHub Wiki pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
