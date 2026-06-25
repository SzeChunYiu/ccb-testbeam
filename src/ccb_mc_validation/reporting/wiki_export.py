"""GitHub-wiki-ready draft export for MC validation artifacts."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccb_mc_validation.io.artifact_store import atomic_write_json
from ccb_mc_validation.reporting.reference_registry import generate_reference_registry
from ccb_mc_validation.reporting.notation_registry import generate_notation_registry


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing required wiki-export input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"missing required wiki-export input: {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _metric(row: dict[str, str]) -> str:
    if row.get("hgb_auc"):
        return f"AUC = {row['hgb_auc']}"
    if row.get("proton_ekin_recon_res68"):
        return f"proton 68% energy residual = {row['proton_ekin_recon_res68']}"
    if row.get("n_sample_I"):
        return f"Sample-I support = {row['n_sample_I']}"
    return "metric unavailable"


def generate_wiki_export(run_root: Path) -> dict[str, Any]:
    """Generate a GitHub-wiki-ready draft bundle from frozen artifacts."""
    run_root = Path(run_root)
    validation = _load_json(run_root / "VALIDATION.json")
    audit = _load_json(run_root / "QA_RELEASE_AUDIT.json")
    claims = _load_json(run_root / "reports" / "mc_validation" / "claims" / "CLAIM_LEDGER.json")
    publication = _load_json(run_root / "publication" / "PUBLICATION_MANIFEST.json")
    references = generate_reference_registry(run_root)
    notation = generate_notation_registry(run_root)
    figure_manifest = _load_json(run_root / "figures" / "summary" / "FIGURE_MANIFEST.json")
    rows = _load_rows(run_root / "reports" / "mc_validation" / "summary" / "metrics_table.csv")
    run_id = str(validation.get("run_id") or run_root.name)
    out_dir = run_root / "wiki"
    generated = datetime.now(tz=timezone.utc).isoformat()
    blocked = [c for c in audit.get("checks", []) if c.get("status") != "PASS"]

    metric_table = "\n".join(
        ["| Study | Status | Support | Headline artifact metric |", "|---|---:|---:|---|"]
        + [f"| {r.get('study','')} | {r.get('status','')} | {r.get('n_tracks','')} | {_metric(r)} |" for r in rows]
    )
    figure_rows = "\n".join(
        ["| Figure | Title | PNG | SVG | Data sidecar |", "|---|---|---|---|---|"]
        + [
            f"| {fig.get('id')} | {fig.get('title')} | `{next((f.get('relative_path') for f in fig.get('formats', []) if f.get('format') == 'png'), '')}` | `{next((f.get('relative_path') for f in fig.get('formats', []) if f.get('format') == 'svg'), '')}` | `{fig.get('data_sidecar')}` |"
            for fig in figure_manifest.get("figures", [])
        ]
    )
    supported_claims = [c for c in claims.get("claims", []) if c.get("status") == "SUPPORTED"]
    blocked_claims = [c for c in claims.get("claims", []) if c.get("status") != "SUPPORTED"]

    home = "\n".join([
        "# CCB testbeam MC validation wiki draft",
        "",
        f"> **Draft / not final release.** This wiki export is generated from frozen artifacts for run `{run_id}`. Release audit status is `{audit.get('status')}` with `release_ready={audit.get('release_ready')}`. Do not treat this as a final publication until all blockers are cleared.",
        "",
        "## Navigation",
        "",
        "- [Scientific introduction](Scientific-Introduction)",
        "- [Methods and mathematical definitions](Methods-and-Mathematics)",
        "- [Notation and equations](Notation-and-Equations)",
        "- [Results and figures](Results-and-Figures)",
        "- [Discussion, limitations, and blockers](Discussion-and-Limitations)",
        "- [References and reproducibility](References-and-Reproducibility)",
        "",
        "## Current artifact status",
        "",
        f"- Validation: `{validation.get('status')}`",
        f"- Publication index: `{publication.get('status')}` / `release_ready={publication.get('release_ready')}`",
        f"- Claim ledger: release claims allowed = `{claims.get('release_claims_allowed')}`",
        f"- Generated: `{generated}`",
        "",
        "## Headline artifact metrics",
        "",
        metric_table,
    ])
    intro = "\n".join([
        "# Scientific introduction",
        "",
        f"This wiki draft introduces the CCB testbeam MC validation status for run `{run_id}`. The goal is to compare frozen MC validation artifacts against detector-analysis questions while keeping production, fixture, blocked, and release states distinct.",
        "",
        "The current package is not final-release ready. It is a curated navigation surface for validated artifacts, plots, claim ledgers, and limitations.",
    ])
    methods = "\n".join([
        "# Methods and mathematical definitions",
        "",
        "## Populations and estimands",
        "",
        f"The current artifact-summary scope covers MV1, MV2, MV3, and MV9 frozen outputs for run `{run_id}`. MV4-MV8 and systematic arrays are blocked pending calibrated digitized MC.",
        "",
        "## Core formulas",
        "",
        "For a binary particle-identification score `s(x)` and threshold `t`, efficiency and purity are recorded conceptually as",
        "",
        "```math",
        r"\epsilon(t) = \frac{N_{\mathrm{true\,signal}}(s(x) \ge t)}{N_{\mathrm{true\,signal}}}, \qquad",
        r"P(t) = \frac{N_{\mathrm{true\,signal}}(s(x) \ge t)}{N_{\mathrm{selected}}(s(x) \ge t)}.",
        "```",
        "",
        "For energy/range closure summaries, the robust 68% residual scale is represented as",
        "",
        "```math",
        r"R_{68} = \frac{1}{2}\left(Q_{84}[r] - Q_{16}[r]\right), \qquad r = \frac{E_{\mathrm{reco}} - E_{\mathrm{truth}}}{E_{\mathrm{truth}}}.",
        "```",
        "",
        "For stopping-depth support, sample counts are reported as frozen artifact supports and are not final physics cross sections:",
        "",
        "```math",
        r"N_{\mathrm{Sample\,I}},\; N_{\mathrm{Sample\,II}}.",
        "```",
        "",
        "## Leakage and provenance guardrails",
        "",
        "Truth labels, event identifiers, and future information are not publication features. Current wiki pages are generated from frozen summary artifacts and do not rerun ROOT scans, GEANT4, digitization, or training.",
    ])
    results = "\n".join([
        "# Results and figures",
        "",
        "## Artifact metric table",
        "",
        metric_table,
        "",
        "## Figure catalog excerpt",
        "",
        figure_rows,
        "",
        "## Supported claims",
        "",
        *[f"- `{c.get('id')}`: {c.get('statement')}" for c in supported_claims],
    ])
    discussion = "\n".join([
        "# Discussion, limitations, and blockers",
        "",
        "## Interpretation",
        "",
        "The frozen artifacts support only a partial MC-validation narrative: MV1-MV3/MV9 artifact summaries are internally consistent, while release claims remain blocked.",
        "",
        "## Blocked release claims",
        "",
        *[f"- `{c.get('id')}`: {c.get('limitations')}" for c in blocked_claims],
        "",
        "## Release-audit blockers",
        "",
        *[f"- `{c.get('name')}`: {c.get('reason') or c.get('status')}" for c in blocked],
    ])

    notation_page = "\n".join([
        "# Notation and equations",
        "",
        f"Notation registry status: `{notation.get('status')}`; final notation status: `{notation.get('final_notation_status')}`.",
        "",
        "| ID | Symbol | Equation | Meaning |",
        "|---|---|---|---|",
        *[f"| {record.get('id')} | `{record.get('symbol')}` | `${record.get('latex')}` | {record.get('meaning')} |" for record in notation.get('records', [])],
        "",
        "These equations are used for artifact-summary interpretation and do not replace the final thesis derivations or systematic uncertainty treatment.",
    ])
    refs = "\n".join([
        "# References and reproducibility",
        "",
        "## Artifact paths",
        "",
        "- Validation summary: `VALIDATION_SUMMARY.md`",
        "- Claim ledger: `reports/mc_validation/claims/CLAIM_LEDGER.md`",
        "- Publication index: `publication/index.html`",
        "- Thesis draft: `reports/mc_validation/thesis_draft/THESIS_DRAFT.md`",
        "- Reference registry: `reports/mc_validation/references/REFERENCE_REGISTRY.md`",
        "- Notation registry: `reports/mc_validation/notation/NOTATION_REGISTRY.md`",
        "",
        "## Reproduction command",
        "",
        "```bash",
        f"python scripts/mc_validation/run_pipeline.py --run-id {run_id} release",
        f"python scripts/mc_validation/run_pipeline.py --run-id {run_id} qa",
        "```",
        "",
        "## References",
        "",
        f"Reference registry status: `{references.get('status')}`, final bibliography status: `{references.get('final_bibliography_status')}`.",
        "",
        "| ID | Status | Citation |",
        "|---|---:|---|",
        *[f"| {record.get('id')} | {record.get('status')} | {record.get('citation')} |" for record in references.get('records', [])],
        "",
        "Formal literature/citation entries still need final curation before publication-grade release. This draft intentionally leaves citation completion as a release blocker rather than inventing references.",
    ])
    pages = {
        "Home.md": home,
        "Scientific-Introduction.md": intro,
        "Methods-and-Mathematics.md": methods,
        "Notation-and-Equations.md": notation_page,
        "Results-and-Figures.md": results,
        "Discussion-and-Limitations.md": discussion,
        "References-and-Reproducibility.md": refs,
    }
    for name, text in pages.items():
        _write(out_dir / name, text)
    manifest = {
        "status": "PASS",
        "scope": "github-wiki-draft",
        "final_wiki_status": "BLOCKED",
        "release_ready": bool(audit.get("release_ready")),
        "run_id": run_id,
        "pages": sorted(pages),
        "page_count": len(pages),
        "blocked_count": len(blocked),
        "generated_at": generated,
        "reason": "Generated GitHub-wiki-ready draft pages from frozen artifacts; final wiki publication remains blocked until release audit passes and citations are curated.",
    }
    atomic_write_json(out_dir / "WIKI_MANIFEST.json", manifest)
    return manifest
