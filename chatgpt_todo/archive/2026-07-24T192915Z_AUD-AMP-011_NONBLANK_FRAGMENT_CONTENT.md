# AUD-AMP-011 — Nonblank amplitude evidence fragments

- UTC stamp: `2026-07-24T192915Z`
- Initial remote main: `e215a4cd44ca6ed2eff3ec45921fcc72faa1e115`
- Task status: `COMPLETE`
- Policy: `EVIDENCE_LINE_FRAGMENT_MUST_CONTAIN_NONWHITESPACE_CONTENT`

## Finding

`validate_amplitude_evidence_map.py` v1.3.0 checked canonical line syntax, whole-file SHA-256, and line-range existence, but accepted a range containing only whitespace. It also did not retain the exact selected fragment digest.

## Delivered

- validator v1.4.0 rejects zero-nonblank-line selections;
- exact selected fragment byte count, nonblank-line count, and SHA-256 are retained;
- focused tests cover accepted exact bytes and whitespace-only rejection;
- Markdown, JSON, and SVG validation evidence are version controlled.

## Validation

```text
old-source negative control: 2 failed, 6 passed in 0.10s
current focused suites: 23 passed in 0.05s
py_compile: PASS
changed Python maximum line length: 100
```

## Commits before archive

- `8df26b33253b7364a8caf9afa6dab35148260f12` — implementation
- `7abe8871c6fa5f782d2bbbf009ab0aa0d69ee716` — regression tests
- `20f65542e203ab4161b4e0ffe8834ac8baaa7932` — validation JSON
- `a9fe61ddd66c8e5666d9e4fcf98e13939d8ccd2e` — audit report
- `29369505632cf707be7cd0d9d1fdcb16c05aa3df` — visual evidence
- `ca69c2f8e9cc705777000d09a8e3e4e76bb497d3` — active-task completion

## Boundary

No real A-002 table, amplitude convention, pulse polarity, pedestal distribution, stopping profile, DeltaE-E output, or detector-performance claim was validated. `AUD-AMP-009`, `AUD-DELTAE-001`, and `AUD-DELTAE-002` remain blocked or partial pending exact data and supporting evidence bytes.
