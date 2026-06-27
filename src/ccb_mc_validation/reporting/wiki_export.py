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
from ccb_mc_validation.reporting.open_questions import generate_open_question_registry
from ccb_mc_validation.reporting.question_closure import generate_question_closure_plan
from ccb_mc_validation.reporting.evidence_packets import generate_evidence_packets
from ccb_mc_validation.reporting.study_gap_audit import generate_study_gap_audit


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



def _reference_ids_for_claim(claim: dict[str, Any]) -> list[str]:
    """Return conservative reference anchors relevant to a claim.

    References provide terminology/context only; they never promote a blocked
    project claim to supported without frozen project evidence.
    """

    claim_id = str(claim.get("id", ""))
    if claim_id == "CLAIM-ARTIFACT-VALIDATION":
        return ["REF-VALIDATION-ARTIFACTS", "REF-GEANT4-2003", "REF-GEANT4-2006"]
    if claim_id.startswith("CLAIM-MV1-"):
        return ["REF-VALIDATION-ARTIFACTS", "REF-PDG-RPP-2024"]
    if claim_id.startswith("CLAIM-MV2-") or claim_id.startswith("CLAIM-MV3-"):
        return ["REF-VALIDATION-ARTIFACTS", "REF-GEANT4-2003", "REF-PDG-RPP-2024"]
    if claim_id.startswith(("CLAIM-MV4-", "CLAIM-MV5-", "CLAIM-MV6-", "CLAIM-MV7-", "CLAIM-MV8-")):
        return ["REF-FINAL-BIBLIOGRAPHY-AUDIT"]
    if claim_id == "CLAIM-FINAL-RELEASE":
        return ["REF-RUNBOOK", "REF-FINAL-BIBLIOGRAPHY-AUDIT"]
    return ["REF-FINAL-BIBLIOGRAPHY-AUDIT"]


def _claim_matrix_row(claim: dict[str, Any]) -> str:
    evidence = claim.get("evidence") or []
    evidence_text = ", ".join(f"`{item}`" for item in evidence) if evidence else "`BLOCKED: no production artifact yet`"
    references = ", ".join(f"`{item}`" for item in _reference_ids_for_claim(claim))
    status = claim.get("status", "")
    claim_id = claim.get("id", "")
    statement = str(claim.get("statement", "")).replace("|", "\\|")
    limitation = str(claim.get("limitations", "")).replace("|", "\\|")
    return f"| `{claim_id}` | {status} | {evidence_text} | {references} | {statement} | {limitation} |"


def _mermaid_id(raw: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in raw)
    return safe.strip("_") or "node"


def _claim_dependency_mermaid(claims: list[dict[str, Any]]) -> str:
    """Build a conservative Mermaid claim-dependency graph for the wiki.

    The graph is intentionally not a proof engine. It exposes which project
    evidence, literature anchors, and blockers each claim depends on so readers
    can audit the chain instead of relying on narrative prose alone.
    """

    lines = [
        "flowchart TD",
        '    FINAL["Final release claim"]',
        '    QA["QA release audit"]',
        '    WIKI["Wiki claim evidence matrix"]',
        '    FINAL --> QA',
        '    FINAL --> WIKI',
    ]
    for claim in claims:
        claim_id = str(claim.get("id", "CLAIM"))
        node_id = "C_" + _mermaid_id(claim_id)
        status = str(claim.get("status", "UNKNOWN"))
        lines.append(f'    {node_id}["{claim_id} ({status})"]')
        lines.append(f"    FINAL --> {node_id}")
        evidence = claim.get("evidence") or []
        if evidence:
            for item in evidence:
                ev_id = "E_" + _mermaid_id(str(item))
                lines.append(f'    {ev_id}["{item}"]')
                lines.append(f"    {node_id} --> {ev_id}")
        else:
            blocker_id = "B_" + _mermaid_id(claim_id)
            lines.append(f'    {blocker_id}["blocked: no production artifact yet"]')
            lines.append(f"    {node_id} --> {blocker_id}")
        for ref in _reference_ids_for_claim(claim):
            ref_id = "R_" + _mermaid_id(ref)
            lines.append(f'    {ref_id}["{ref}"]')
            lines.append(f"    {node_id} -. reference .-> {ref_id}")
    return "\n".join(lines)


def generate_wiki_export(run_root: Path) -> dict[str, Any]:
    """Generate a GitHub-wiki-ready draft bundle from frozen artifacts."""
    run_root = Path(run_root)
    validation = _load_json(run_root / "VALIDATION.json")
    audit = _load_json(run_root / "QA_RELEASE_AUDIT.json")
    claims = _load_json(run_root / "reports" / "mc_validation" / "claims" / "CLAIM_LEDGER.json")
    publication = _load_json(run_root / "publication" / "PUBLICATION_MANIFEST.json")
    references = generate_reference_registry(run_root)
    notation = generate_notation_registry(run_root)
    open_questions = generate_open_question_registry(run_root)
    closure_plan = generate_question_closure_plan(run_root)
    evidence_packets = generate_evidence_packets(run_root)
    study_gap_audit = generate_study_gap_audit(run_root)
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
    claim_matrix_rows = "\n".join(
        ["| Claim | Status | Evidence artifacts | Reference anchors | Statement | Limitation |", "|---|---:|---|---|---|---|"]
        + [_claim_matrix_row(c) for c in claims.get("claims", [])]
    )
    claim_dependency_graph = _claim_dependency_mermaid(claims.get("claims", []))

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
        "- [Open questions and recursive study plan](Open-Questions)",
        "- [Claim evidence matrix](Claim-Evidence-Matrix)",
        "- [Claim dependency tree](Claim-Dependency-Tree)",
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
        "",
        "## Reference anchors",
        "",
        "- `REF-GEANT4-2003` and `REF-GEANT4-2006` justify standard Geant4 toolkit terminology only; they do not by themselves prove the CCB geometry, digitizer, or production macro alignment.",
        "- `REF-PDG-RPP-2024` anchors particle and passage-through-matter vocabulary; any numerical efficiency, energy, or range claim must still cite frozen project artifacts.",
        "- `REF-BIRKS-1964` and `REF-KNOLL-2010` anchor scintillation-detector language; the current artifact package does not claim a fitted Birks constant or final detector calibration.",
        "- `REF-ROOT-1997` anchors ROOT analysis-file context; raw selector-count reproduction remains governed by project S00/S00c/S00d guards, not by the external ROOT reference.",
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
        "## Claim support discipline",
        "",
        "External references define standard methods and notation; project claims require project evidence. The wiki therefore pairs literature reference IDs with frozen validation artifacts, claim-ledger rows, and QA gates before promoting any release claim.",
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


    study_gap_rows = "\n".join(
        [
            "| Study | Status | Current state | Required next artifact |",
            "|---|---:|---|---|",
        ]
        + [
            f"| {gap.get('study')} | {gap.get('status')} | {gap.get('current_state')} | `{gap.get('required_next_artifact')}` |"
            for gap in study_gap_audit.get("studies", [])
        ]
    )
    study_coverage_page = "\n".join([
        "# Study coverage and remaining gaps",
        "",
        f"Run `{run_id}` is not a complete scientific closure package. This page makes every currently unstudied or under-studied topic explicit instead hiding it in prose.",
        "",
        f"All study implementations ready: `{study_gap_audit.get('all_study_implementations_ready')}`; blocked study count: `{study_gap_audit.get('blocked_count')}`.",
        "",
        "## Fail-closed coverage table",
        "",
        study_gap_rows,
        "",
        "## Recursive closure rule",
        "",
        "A topic is not considered understood merely because a placeholder module, fixture artifact, or literature reference exists. It remains open until production artifacts, QA gates, plots, uncertainty accounting, claim-ledger evidence, and wiki explanations all agree.",
        "",
        "For each blocked study the recursive closure chain is:",
        "",
        "```mermaid",
        "flowchart TD",
        "  Q[Open scientific question] --> M[Method and mathematical model]",
        "  M --> A[Production LUNARC artifact]",
        "  A --> U[Uncertainty and systematic checks]",
        "  U --> F[Figures, tables, data sidecars]",
        "  F --> C[Claim ledger evidence row]",
        "  C --> W[Wiki/report explanation]",
        "  W --> R[Release QA gate]",
        "```",
        "",
        "Until that chain is complete for MV4-MV8 and every open-question evidence packet, the release remains blocked and no final physics conclusion is claimed.",
    ])

    claim_matrix_page = "\n".join([
        "# Claim evidence matrix",
        "",
        "This table is the wiki-facing traceability bridge from each claim-ledger row to frozen artifact evidence and curated reference anchors.",
        "External references explain terminology or standard methods; only project artifacts and QA gates support project-specific claims.",
        "Blocked claims intentionally keep empty evidence as `BLOCKED: no production artifact yet` so missing MV4-MV8/final-release evidence cannot be hidden.",
        "",
        claim_matrix_rows,
    ])

    claim_dependency_page = "\n".join([
        "# Claim dependency tree",
        "",
        "This graph recursively exposes how the final-release claim depends on QA gates, wiki traceability, individual claim-ledger rows, frozen evidence artifacts, curated references, and explicit blockers.",
        "Reference edges are dashed because literature anchors explain terminology or standard methods; they do not promote project-specific claims without project artifacts.",
        "",
        "```mermaid",
        claim_dependency_graph,
        "```",
    ])

    questions_page = "\n".join([
        "# Open questions and recursive study plan",
        "",
        f"All questions closed: `{open_questions.get('all_questions_closed')}`; open count: `{open_questions.get('open_count')}`.",
        "",
        "| ID | Status | Priority | Question | Needed evidence |",
        "|---|---:|---:|---|---|",
        *[f"| {record.get('id')} | {record.get('status')} | {record.get('priority')} | {record.get('question')} | {record.get('needed_evidence')} |" for record in open_questions.get('records', [])],
        "",
        "## Closure DAG",
        "",
        "```mermaid",
        closure_plan.get('dag_mermaid', ''),
        "```",
        "",
        "## Evidence packet templates",
        "",
        f"All packets closed: `{evidence_packets.get('all_packets_closed')}`; open packet count: `{evidence_packets.get('open_packet_count')}`.",
        "",
        "| Question | Packet status | Required artifacts |",
        "|---|---:|---|",
        *[f"| {packet.get('question_id')} | {packet.get('packet_status')} | {', '.join(packet.get('required_artifacts', []))} |" for packet in evidence_packets.get('packets', [])],
        "",
        "The project should recursively reduce this table until every question has direct evidence, every packet is closed, and `all_questions_closed=true`.",
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
        "Open-Questions.md": questions_page,
        "Study-Coverage-and-Remaining-Gaps.md": study_coverage_page,
        "Claim-Evidence-Matrix.md": claim_matrix_page,
        "Claim-Dependency-Tree.md": claim_dependency_page,
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
