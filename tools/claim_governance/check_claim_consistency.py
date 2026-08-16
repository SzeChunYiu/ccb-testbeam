#!/usr/bin/env python3
"""Claim-governance consistency checker (issue #1304).

Enforces that `docs/claim_ledger.csv` is the single canonical claim-truth
surface and that no parallel surface (paper/figures.yaml, WIKI.md, the
manuscript, quality_report.json) promotes a claim beyond its canonical
status.

Exit codes (fail-closed, distinct "could not check"):
    0 = all surfaces consistent with the canonical ledger
    1 = one or more consistency failures (printed as FAIL lines)
    2 = could-not-check: required input missing/malformed (printed as SCOPE)

Config tables (relative to --repo-root):
    docs/claim_governance/forbidden_promotions.csv
    publication/claims/manuscript_claim_tokens.csv
Both must exist and parse; a missing table is a SCOPE error, never a pass.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - pyyaml is a core dependency
    print("SCOPE: PyYAML is not importable; cannot check paper/figures.yaml")
    sys.exit(2)

REQUIRED_LEDGER_COLUMNS = ("claim_id", "status", "allowed_status_validated")

# Canonical statuses that must never back a VALIDATED token on any surface.
NON_AUTHORISING_STATUSES = {
    "GATED",
    "BLOCKED",
    "SUPERSEDED",
    "REOPENED",
    "WITHHELD",
    "PARTIAL",
}

VALIDATED_RE = re.compile(r"\bVALIDATED\b")
CLAIM_ID_RE = re.compile(r"\bCL-(\d+)\b")
CLAIM_RANGE_RE = re.compile(r"^CL-(\d+)\.\.(\d+)$")
CLAIM_SINGLE_RE = re.compile(r"^CL-(\d+)$")


def scope(msg: str) -> None:
    print("SCOPE: {}".format(msg))


def fail(lines: list, msg: str) -> None:
    lines.append("FAIL: {}".format(msg))


def load_csv_table(path: Path, required_cols, lines: list, missing_is_scope: bool):
    """Load a CSV config table. Returns (rows, ok)."""
    if not path.is_file():
        if missing_is_scope:
            scope("{}: required config table is missing".format(path))
            return None, False
        return [], True
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = [r for r in reader if r.get("regex", "").strip()]
            missing = [c for c in required_cols if c not in (reader.fieldnames or [])]
            if missing:
                scope("{}: missing column(s) {}".format(path, ",".join(missing)))
                return None, False
            for r in rows:
                try:
                    re.compile(r["regex"])
                except re.error as exc:
                    scope("{}: bad regex in row {}: {}".format(path, r.get("pattern_id") or r.get("token_id"), exc))
                    return None, False
            return rows, True
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        scope("{}: unreadable ({})".format(path, exc))
        return None, False


def load_canonical_ledger(path: Path):
    """Parse the canonical ledger. Returns (claims, ok); ok=False => scope error."""
    if not path.is_file():
        scope("{}: canonical claim ledger is missing".format(path))
        return None, False
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            missing = [c for c in REQUIRED_LEDGER_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                scope("{}: missing column(s) {}".format(path, ",".join(missing)))
                return None, False
            claims = {}
            dup = set()
            for row in reader:
                cid = (row.get("claim_id") or "").strip()
                if not cid:
                    continue
                if cid in claims:
                    dup.add(cid)
                status = (row.get("status") or "").strip()
                allowed = (row.get("allowed_status_validated") or "").strip().upper()
                if allowed not in ("YES", "NO"):
                    scope("{}: claim {} has allowed_status_validated={!r} (want YES/NO)".format(path, cid, allowed))
                    return None, False
                if not status:
                    scope("{}: claim {} has empty status".format(path, cid))
                    return None, False
                claims[cid] = {
                    "status": status,
                    "allowed": allowed,
                    "authorising": status not in NON_AUTHORISING_STATUSES and allowed == "YES",
                }
            if dup:
                scope("{}: duplicate claim_id(s): {}".format(path, ",".join(sorted(dup))))
                return None, False
            if not claims:
                scope("{}: canonical ledger has no claim rows".format(path))
                return None, False
            return claims, True
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        scope("{}: unreadable ({})".format(path, exc))
        return None, False


def claim_ids_from_token(token: str):
    """Expand a claim_id field ('CL-001', 'CL-002..006', or non-ledger id)."""
    token = token.strip()
    m = CLAIM_RANGE_RE.match(token)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo > hi or hi - lo > 200:
            return None
        return ["CL-{:03d}".format(i) for i in range(lo, hi + 1)]
    m = CLAIM_SINGLE_RE.match(token)
    if m:
        return ["CL-{:03d}".format(int(m.group(1)))]
    return None  # not a canonical-ledger claim reference (e.g. clusterA/#921)


def check_publication_ledger_copy(root: Path, claims: dict, lines: list) -> None:
    canonical = root / "docs" / "claim_ledger.csv"
    copy_path = root / "publication" / "tables" / "claim_ledger.csv"
    if not copy_path.is_file():
        fail(lines, "publication/tables/claim_ledger.csv is missing (must be a byte-equal copy of docs/claim_ledger.csv)")
        return
    if canonical.read_bytes() != copy_path.read_bytes():
        fail(lines, "publication/tables/claim_ledger.csv differs from docs/claim_ledger.csv "
                    "(must be byte-equal; regenerate the copy, never hand-edit it)")


def check_parallel_paper_ledger(root: Path, lines: list) -> None:
    legacy = root / "paper" / "claims_ledger.csv"
    if legacy.is_file():
        fail(lines, "paper/claims_ledger.csv exists: parallel claim-truth surface is forbidden "
                    "(docs/claim_ledger.csv is canonical; delete this file)")


def check_stray_ledger_copies(root: Path, lines: list) -> None:
    """Any sibling of the canonical ledger (backups, -old copies) is a stale
    parallel claim-truth surface; git history already preserves prior states."""
    canonical = root / "docs" / "claim_ledger.csv"
    seen = set()
    for pattern in ("claim_ledger.csv*", "claim_ledger*.csv"):
        for path in sorted((root / "docs").glob(pattern)):
            if path == canonical or path in seen:
                continue
            seen.add(path)
            fail(lines, "{}: stray copy of the canonical claim ledger (git history preserves "
                        "prior states; never commit backups/siblings)".format(
                            path.relative_to(root).as_posix()))


def check_figures_yaml(root: Path, claims: dict, lines: list, fp_table: list) -> None:
    path = root / "paper" / "figures.yaml"
    if not path.is_file():
        return  # nothing published yet; nothing to promote
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        scope("{}: unparseable ({})".format(path, exc))
        return
    if not isinstance(data, dict):
        scope("{}: expected top-level mapping".format(path))
        return
    for name, entry in sorted(data.items()):
        if not isinstance(entry, dict):
            continue
        caption = str(entry.get("caption") or "")
        # Captions are multi-line YAML scalars: apply the forbidden-promotion
        # table to the joined caption (the line-based scan skips this file).
        for row in fp_table:
            if not re.compile(row["regex"]).search(caption):
                continue
            allow = [t.strip().lower() for t in (row.get("allow_if_line_contains") or "").split("|") if t.strip()]
            if any(t in caption.lower() for t in allow):
                continue
            fail(lines, "figures.yaml entry {} caption forbidden promotion {} (claim {}) "
                        "without a quarantining qualifier".format(
                            name, row.get("pattern_id") or row["regex"][:24], row.get("claim_id") or "-"))
        raw_claim = entry.get("claim_id")
        if not isinstance(raw_claim, str):
            continue
        cids = claim_ids_from_token(raw_claim)
        if cids is None:
            continue  # issue-cluster or free-form reference, not a ledger claim
        unknown = [c for c in cids if c not in claims]
        if unknown:
            fail(lines, "figures.yaml entry {} references unknown claim(s) {} "
                        "via claim_id {!r}".format(name, ",".join(unknown), raw_claim))
            continue
        non_auth = [c for c in cids if not claims[c]["authorising"]]
        status = entry.get("status")
        if non_auth and status == "VALIDATED":
            fail(lines, "figures.yaml entry {} status=VALIDATED but canonical claim(s) {} "
                        "are non-authorising ({})".format(
                            name, ",".join(non_auth),
                            ";".join("{}={}".format(c, claims[c]["status"]) for c in non_auth)))
        if non_auth and VALIDATED_RE.search(caption):
            fail(lines, "figures.yaml entry {} caption says VALIDATED but canonical claim(s) {} "
                        "are non-authorising ({})".format(
                            name, ",".join(non_auth),
                            ";".join("{}={}".format(c, claims[c]["status"]) for c in non_auth)))


def iter_text_lines(root: Path, file_glob: str):
    """Yield (relpath, lineno, line) for files matching a ';'-separated glob list."""
    for pattern in [p.strip() for p in file_glob.split(";") if p.strip()]:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                yield path.relative_to(root).as_posix(), i, line


def check_wiki_claim_lines(root: Path, claims: dict, lines: list) -> None:
    path = root / "WIKI.md"
    if not path.is_file():
        return
    # A line that already states a canonical gating status is quarantining
    # itself ("Zero rows are VALIDATED; CL-001 is GATED"): not a promotion.
    gating_word_re = re.compile(r"GATED|BLOCKED|SUPERSEDED|WITHHELD|non-authorising")
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not VALIDATED_RE.search(line):
            continue
        if gating_word_re.search(line):
            continue
        mentioned = []
        for m in CLAIM_ID_RE.finditer(line):
            cid = "CL-{:03d}".format(int(m.group(1)))
            if cid in claims and not claims[cid]["authorising"]:
                mentioned.append(cid)
        if mentioned:
            fail(lines, "WIKI.md:{} says VALIDATED for non-authorising claim(s) {} ({})".format(
                i, ",".join(mentioned),
                ";".join("{}={}".format(c, claims[c]["status"]) for c in mentioned)))


def check_forbidden_promotions(root: Path, claims: dict, table: list, lines: list) -> None:
    for row in table:
        pattern = re.compile(row["regex"])
        allow = [t.strip().lower() for t in (row.get("allow_if_line_contains") or "").split("|") if t.strip()]
        for rel, i, line in iter_text_lines(root, row.get("file_glob") or ""):
            if rel == "paper/figures.yaml":
                continue  # multi-line YAML captions are checked structurally
            if not pattern.search(line):
                continue
            lowered = line.lower()
            if any(t in lowered for t in allow):
                continue
            fail(lines, "{}:{} forbidden promotion {} (claim {}) without a quarantining qualifier "
                        "(allowed qualifiers: {})".format(
                            rel, i, row.get("pattern_id") or row["regex"][:24],
                            row.get("claim_id") or "-", "|".join(allow) or "none"))


def check_manuscript_tokens(root: Path, claims: dict, table: list, lines: list) -> None:
    for row in table:
        pattern = re.compile(row["regex"])
        qualifier = re.compile(row["required_qualifier_regex"], re.IGNORECASE)
        cids = claim_ids_from_token(row.get("claim_id") or "")
        non_auth = cids is not None and any(c in claims and not claims[c]["authorising"] for c in cids)
        if not non_auth:
            continue  # token bound to an authorising claim needs no qualifier
        for rel, i, line in iter_text_lines(root, row.get("file_glob") or "publication/**/*.tex;paper/**/*.tex"):
            if pattern.search(line) and not qualifier.search(line):
                fail(lines, "{}:{} manuscript token {} for non-authorising claim {} lacks required "
                            "qualifier /{}/".format(rel, i, row.get("token_id") or row["regex"][:24],
                                                    row.get("claim_id"), row["required_qualifier_regex"]))


def check_quality_report_scope(root: Path, lines: list) -> None:
    path = root / "docs" / "figures" / "paper" / "quality_report.json"
    if not path.is_file():
        return  # generated artifact; absent = nothing to misread
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        fail(lines, "docs/figures/paper/quality_report.json is not valid JSON ({})".format(exc))
        return
    if not isinstance(report, dict):
        fail(lines, "docs/figures/paper/quality_report.json: expected a JSON object")
        return
    if report.get("report_scope") != "TECHNICAL_RENDERING_QA_ONLY":
        fail(lines, "docs/figures/paper/quality_report.json: report_scope must be "
                    "TECHNICAL_RENDERING_QA_ONLY (technical rendering QA is not scientific validation)")
    if report.get("scientific_authorisation") is not False:
        fail(lines, "docs/figures/paper/quality_report.json: scientific_authorisation must be false")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo-root", default=None, help="repository root (default: parent of this file's tools/ dir)")
    args = ap.parse_args(argv)
    root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[2]

    lines = []
    fp_table, ok1 = load_csv_table(
        root / "docs" / "claim_governance" / "forbidden_promotions.csv",
        ("pattern_id", "regex", "file_glob", "allow_if_line_contains"), lines, missing_is_scope=True)
    mt_table, ok2 = load_csv_table(
        root / "publication" / "claims" / "manuscript_claim_tokens.csv",
        ("token_id", "regex", "claim_id", "required_qualifier_regex"), lines, missing_is_scope=True)
    if not (ok1 and ok2):
        return 2

    claims, ok = load_canonical_ledger(root / "docs" / "claim_ledger.csv")
    if not ok:
        return 2

    check_publication_ledger_copy(root, claims, lines)
    check_parallel_paper_ledger(root, lines)
    check_stray_ledger_copies(root, lines)
    check_figures_yaml(root, claims, lines, fp_table)
    check_wiki_claim_lines(root, claims, lines)
    check_forbidden_promotions(root, claims, fp_table, lines)
    check_manuscript_tokens(root, claims, mt_table, lines)
    check_quality_report_scope(root, lines)

    if lines:
        for l in lines:
            print(l)
        print("CLAIM-CONSISTENCY FAIL: {} divergence(s) vs canonical docs/claim_ledger.csv".format(len(lines)))
        return 1
    print("CLAIM-CONSISTENCY OK: {} canonical claims; all surfaces consistent".format(len(claims)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
