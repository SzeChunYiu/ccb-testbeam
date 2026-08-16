# AUD-DOC-003 — Markdown Link-Checker Fail-Closed Audit

## Session identity

- UTC stamp: `2026-07-25T010711Z`
- Initial remote `main`: `bf46fe4ef69a5fdf24d39f264d90218b0335f491`
- Owner: scheduled scientific-review session
- Destination: direct sequential commits to `main`; no force-push or task branch
- Acceptance: **COMPLETE** for the focused documentation-integrity unit

## Start-of-run review

Authenticated GitHub reads inspected repository metadata and permissions, latest `main`
history, open pull requests, current status checks, PR #868, the mandatory
`chatgpt_todo/` protocol, active task, backlog, latest handoff, session history,
Chapter 9, and the current Markdown link checker.

The repository had no attached status checks on initial head
`bf46fe4ef69a5fdf24d39f264d90218b0335f491`. PR #868 remained closed, unmerged,
and non-mergeable and was not modified. Open PR #883 proposed a partial link-checker
fix, but its Chapter 9 change is stale against the rewritten current chapter.

## Confirmed defects

The exact former script was Git blob
`0cc64c1e54291af0eed70ce3d4cfada976250e75`, 1,534 bytes, SHA-256
`2da08281f4a600358cdf239f1c4c4c711e32c70e1f711bf5c2831ede5821d9fa`.

Independent synthetic negative controls reproduced:

1. a missing local target printed one `BROKEN` line and then raised
   `NameError: name 'boken' is not defined`;
2. a Markdown file containing byte `0xa3` at offset 6 raised an uncaught
   `UnicodeDecodeError`;
3. relative paths were not constrained to the repository root, so an unrelated
   outside file could satisfy a link.

Using `errors="replace"`, as proposed by PR #883, would avoid the crash but hide the
invalid byte. The accepted method instead reports strict-decoding failure while
preserving source bytes.

## Work delivered

`scripts/broken_link_checker.py` is now validator version `2.0.0` with policy:

`MARKDOWN_LINK_TARGETS_MUST_BE_UTF8_AND_REPOSITORY_LOCAL`

It provides deterministic file and finding order, strict UTF-8 findings, percent-decoded
local target resolution, repository-root containment, missing-target findings, explicit
return codes, and optional atomic JSON publication.

Added:

- `tests/test_broken_link_checker.py`;
- `tools/audit/render_broken_link_checker_evidence.py`;
- `docs/validation/broken_link_checker_validation.json`;
- `docs/validation/broken_link_checker.svg`;
- `docs/validation/broken_link_checker_audit.md`.

Updated `chatgpt_todo/ACTIVE_TASK.md` and the latest handoff.

## Validation

Exact commands:

```text
python -m py_compile \
  scripts/broken_link_checker.py \
  tests/test_broken_link_checker.py \
  tools/audit/render_broken_link_checker_evidence.py

pytest -q tests/test_broken_link_checker.py

6 passed in 2.55s
```

Covered cases:

- valid local target plus skipped external/fragment-only links;
- missing target with status 1 and `MISSING_TARGET`;
- invalid UTF-8 with status 1 and `INVALID_UTF8`;
- existing target outside the root with `TARGET_ESCAPES_ROOT`;
- percent-encoded local path resolution;
- deterministic atomic JSON publication.

Committed bytes match local validation:

- script blob `0076b5cfdfbcbb6db322c9ae4ca01d7e2686651b`, SHA-256
  `f198f4cb5521343da1e541641c704cab6b53d4f3865868b89d99de0f83ba99e0`;
- test blob `327469c6c8299ec20825148a8040f93e09079c6c`, SHA-256
  `359dc28a5f17d8e6e7058ed2897a1ecf49e04ccba3be76f7f421b175f4699414`;
- renderer blob `4b7f19e0fde3cb2e10f3df53c041afd7846d63c9`.

Validation JSON parsed, SVG XML parsed, and changed Python lines were at most 100
characters. Runtime was Python 3.13.5 with pytest 9.0.2. Ruff was not installed, and
no repository-wide test, full repository link inventory, or GitHub Actions success is
claimed.

## Direct-main commits before archive

- `95421705ea9a9606433c3b047e31d78d0378cc01` — task claim;
- `74333e8a97712c9007de38b70baa49aaa75f688b` — fail-closed implementation;
- `b993128fdfd6976ecad3932a41391a6be6c9d75b` — focused tests;
- `1038c5dbae72dd28c830f4cacb6762583dbdb633` — evidence renderer;
- `634560d83be831d592900a84e5a76d361ba99379` — validation JSON;
- `7614347d89af030952a9e564d5e16cece8eff83f` — SVG evidence;
- `925ae74bcebba8bb2ad671043c4d80d718312706` — validation audit;
- `1f06250b0be54daef915b2fe5c111ba4cc4def28` — active-task completion.

## Limitations and next work

The checker does not parse reference-style definitions, verify heading anchors, check
case-sensitive portability across filesystems, or request external URLs. Those should be
added only with focused parser and portability regressions. Link validity remains a
provenance property, not scientific validation of the linked content.

`BACKLOG.md`, `MASTER_INDEX.md`, and aggregate matrices were reviewed but not replaced in
this unit because their long shared rows were concurrently maintained and the connector
provides whole-file replacement rather than patch semantics. The immutable archive and
latest handoff preserve the complete session record. `SESSION_LOG.md` append remains an
explicit coordination limitation for the same reason.
