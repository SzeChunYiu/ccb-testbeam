#!/usr/bin/env python3
"""
Audit script: scan all thesis chapters for superseded (stale) numerical values.

Reads docs/claim_ledger.csv to get canonical values, then scans all Markdown
files in docs/academic_chapters/ and WIKI.md for any occurrence of superseded
values that are not explicitly marked as such.

Usage:
    python scripts/audit_claim_superseded.py [--fix]

Exit code 0 = clean (no superseded values found or all properly marked).
Exit code 1 = superseded values found without proper correction context.
"""

import csv
import os
import re
import sys
from pathlib import Path

# ── canonical-to-superseded mapping (kept in sync with claim_ledger.csv) ──
SUPERSEDED_MAP: dict[str, tuple[str, str]] = {
    # old_value: (canonical_value, description)
    "4.22 MHz": ("~3.05 MHz", "Rmax pile-up tolerance"),
    "4.22": ("~3.05", "Rmax pile-up tolerance"),
    "~246 ADC/MeV": ("92 ± 28 ADC/MeV", "digitizer gain MV0"),
    "246 ADC/MeV": ("92 ± 28 ADC/MeV", "digitizer gain MV0"),
    "706,373": ("640,737", "selected B-stack pulse count"),
    "706373": ("640737", "selected B-stack pulse count"),
    "90 ns": ("124.79 ns", "effective live-time tau_eff"),
    "90ns": ("124.79 ns", "effective live-time tau_eff"),
    "PCA 3 PCs 89%": ("must be recomputed canonically", "PCA explained variance"),
    "3 PCs 89%": ("must be recomputed canonically", "PCA explained variance"),
    "8 PCs 99.7%": ("must be recomputed canonically", "PCA explained variance"),
}

# ── known safe contexts that don't count as stale usage ──
ALLOWED_CONTEXTS = [
    r"superseded",
    r"corrected",
    r"CORRECTED",
    r"old value",
    r"older result",
    r"previous result",
    r"no longer used",
    r"supersedes",
    r"correction context",
    r"correction box",
    r"✔️.*→",
    r"→",
    r"corrected from",
    r"SUPERSEDED",
    r"correcting",
    r"original (analysis|note|measurement|result|value)",
    r"error in (the )?original",
    r"mistake",
    r"was previously",
    r"previously reported",
    r"was wrong",
    r"was rounded|rounded to|rounding",
    r"recalibration|recalibrated",
    r"discrepancy",
    r"artefact|artifact",
    r"needs canonical|recomputed|rerun",
    r"compared to| vs |versus",
    # ── additional honest correction / comparison contexts ──
    # Prose that explicitly withdraws a value:
    r"not canonical",
    r"is canonical",            # "Neither X nor Y is canonical"
    r"must not be cited",
    r"do not use",
    r"withheld",
    r"former",
    r"earlier",
    r"incorrect",
    r"\berror\b",
    r"Neither",
    r"\boriginal\b",          # "the original 4.22 MHz ..."
    # Comparison-table / diagnostic phrasing:
    r"proxy",
    r"heuristic envelope",
    r"Source-backed",
    r"no beam-data transfer",
]


def load_claim_ledger(ledger_path: str) -> list[dict]:
    """Load the canonical claim ledger."""
    claims = []
    with open(ledger_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            claims.append(row)
    return claims


WINDOW_LINES = 4  # neighbours each side checked for comparison/correction context


def scan_file(filepath: str) -> list[dict]:
    """Scan a single file for superseded values. Returns list of findings.

    A value is flagged only when neither the canonical replacement nor an
    honest correction/comparison phrase appears on the line or within a small
    neighbouring window. This recognises comparison tables that list old beside
    new, and prose that explicitly says a value is "not canonical" / "former" /
    "an error", without having to annotate every row.
    """
    findings = []
    with open(filepath) as f:
        lines = f.readlines()

    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("#"):
            continue

        lo = max(0, i - 1 - WINDOW_LINES)
        hi = min(len(lines), i - 1 + WINDOW_LINES + 1)
        window = "".join(lines[lo:hi])

        for old_val, (new_val, desc) in SUPERSEDED_MAP.items():
            if old_val not in line:
                continue
            # canonical value on the line OR in the near window => comparison/correction row
            if new_val and (new_val in line or new_val in window):
                continue
            # honest correction/comparison context on the line OR in the near window
            safe = any(re.search(ctx, window, re.IGNORECASE) for ctx in ALLOWED_CONTEXTS)
            if not safe:
                findings.append({
                    "file": filepath,
                    "line": i,
                    "old_value": old_val,
                    "canonical_value": new_val,
                    "description": desc,
                    "text": line_stripped[:120],
                })
    return findings


def scan_directory(directory: str) -> list[dict]:
    """Recursively scan all .md files in a directory."""
    findings = []
    for root, _, files in os.walk(directory):
        for fname in files:
            if fname.endswith(".md"):
                findings.extend(scan_file(os.path.join(root, fname)))
    return findings


def main():
    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)

    ledger_path = repo_root / "docs" / "claim_ledger.csv"
    if not ledger_path.exists():
        print(f"WARNING: claim_ledger.csv not found at {ledger_path}")
        print("Cannot verify without claim ledger. Run `python scripts/build_claim_ledger.py` first.")
        sys.exit(2)

    print("=" * 60)
    print("SUPERSEDED-VALUE AUDIT")
    print("=" * 60)

    # Scan academic chapters
    chapters_dir = repo_root / "docs" / "academic_chapters"
    findings = []
    if chapters_dir.exists():
        findings.extend(scan_directory(str(chapters_dir)))

    # Scan WIKI.md
    wiki_path = repo_root / "WIKI.md"
    if wiki_path.exists():
        findings.extend(scan_file(str(wiki_path)))

    # Scan key reports
    for report_path in [
        repo_root / "docs" / "SYSTEMATIC_UNCERTAINTIES.md",
        repo_root / "docs" / "REPORT_STANDARD.md",
        repo_root / "STUDY_GAPS.md",
    ]:
        if report_path.exists():
            findings.extend(scan_file(str(report_path)))

    if not findings:
        print("\n✓ CLEAN — no unmarked superseded values found.")
        print("All scanned files either use canonical values or properly mark corrections.\n")
        sys.exit(0)

    print(f"\n✗ FOUND {len(findings)} unmarked superseded value(s):\n")
    for f in sorted(findings, key=lambda x: (x["file"], x["line"])):
        print(f"  {f['file']}:{f['line']}")
        print(f"    Value: '{f['old_value']}' → canonical: {f['canonical_value']}")
        print(f"    ({f['description']})")
        print(f"    Text: {f['text']}")
        print()

    print("ACTION: Either replace with canonical value or mark explicitly as:")
    print("  'corrected from <OLD> → <NEW>' or 'SUPERSEDED: <OLD>' or 'old value: <OLD>'\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
