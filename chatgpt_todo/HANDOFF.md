# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-25T010711Z`
- **Task:** `AUD-DOC-003`
- **Unit:** fail-closed Markdown link-checker correction
- **Initial remote `main`:** `bf46fe4ef69a5fdf24d39f264d90218b0335f491`
- **Validated implementation/evidence head:** `24208f68995c84555969e6c0a514b8f05501ba89`
- **Complete delivery handoff:** `1475422c30f07c4a97e25ec70fc973d129bfc5d2` was confirmed as remote `main` head; this update records confirmation metadata only
- **Destination:** direct sequential commits to remote `main`; no force-push, history rewrite, task branch, or PR transport
- **Acceptance:** **COMPLETE** for the focused software/documentation-provenance unit

## Start-of-run review

Authenticated GitHub reads inspected repository metadata and permissions, current `main`,
recent history, open pull requests, attached status checks, PR #868, repository-local
coordination records, Chapter 9, and `scripts/broken_link_checker.py`.

Initial facts:

- remote `main`: `bf46fe4ef69a5fdf24d39f264d90218b0335f491`;
- former link-checker blob: `0cc64c1e54291af0eed70ce3d4cfada976250e75`;
- no status checks were attached to the initial main head;
- PR #868 was closed, unmerged, and non-mergeable and was not modified;
- open PR #883 contained a partial link-checker change, but its Chapter 9 patch was stale
  against current `main`; it was not merged or modified.

## Confirmed defects

The exact former 1,534-byte script, SHA-256
`2da08281f4a600358cdf239f1c4c4c711e32c70e1f711bf5c2831ede5821d9fa`,
was reconstructed byte-for-byte.

Negative controls reproduced:

1. a missing local link printed one `BROKEN` line and then raised
   `NameError: name 'boken' is not defined`;
2. invalid UTF-8 byte `0xa3` at offset 6 raised an uncaught
   `UnicodeDecodeError`;
3. local targets were not required to remain beneath the repository root.

Replacing undecodable bytes, as proposed in PR #883, would allow the scan to continue but
would hide the source-byte defect. Strict decoding with a controlled finding was selected
as the more traceable method.

## Correction delivered

`scripts/broken_link_checker.py` is now version `2.0.0` and implements policy:

`MARKDOWN_LINK_TARGETS_MUST_BE_UTF8_AND_REPOSITORY_LOCAL`

The tool now reads exact bytes, reports strict UTF-8 failures without altering source,
resolves percent-encoded paths, rejects outside-root targets, reports missing targets,
sorts results deterministically, writes optional JSON atomically, and returns controlled
status codes 0/1/2.

Added:

- `tests/test_broken_link_checker.py`;
- `tools/audit/render_broken_link_checker_evidence.py`;
- `docs/validation/broken_link_checker_validation.json`;
- `docs/validation/broken_link_checker.svg`;
- `docs/validation/broken_link_checker_audit.md`;
- `chatgpt_todo/archive/2026-07-25T010711Z_AUD-DOC-003_MARKDOWN_LINK_CHECKER.md`.

Updated `chatgpt_todo/ACTIVE_TASK.md` and this handoff.

## Validation

```text
python -m py_compile \
  scripts/broken_link_checker.py \
  tests/test_broken_link_checker.py \
  tools/audit/render_broken_link_checker_evidence.py

pytest -q tests/test_broken_link_checker.py

6 passed in 2.55s
```

Coverage includes valid links, missing targets, invalid UTF-8, root escapes,
percent-encoded paths, and deterministic atomic JSON publication.

Committed bytes match local validation:

- script blob `0076b5cfdfbcbb6db322c9ae4ca01d7e2686651b`, SHA-256
  `f198f4cb5521343da1e541641c704cab6b53d4f3865868b89d99de0f83ba99e0`;
- test blob `327469c6c8299ec20825148a8040f93e09079c6c`, SHA-256
  `359dc28a5f17d8e6e7058ed2897a1ecf49e04ccba3be76f7f421b175f4699414`;
- renderer blob `4b7f19e0fde3cb2e10f3df53c041afd7846d63c9`.

Validation JSON parsed, SVG XML parsed, and changed Python lines were no longer than 100
characters. Runtime was Python 3.13.5 with pytest 9.0.2. Ruff was unavailable. No full
repository pytest, Python 3.11 CI, complete repository link inventory, ROOT processing,
Geant4 execution, or detector-data regeneration is claimed.

## Direct-main commit sequence

- `95421705ea9a9606433c3b047e31d78d0378cc01` — claim task;
- `74333e8a97712c9007de38b70baa49aaa75f688b` — implementation;
- `b993128fdfd6976ecad3932a41391a6be6c9d75b` — tests;
- `1038c5dbae72dd28c830f4cacb6762583dbdb633` — renderer;
- `634560d83be831d592900a84e5a76d361ba99379` — validation JSON;
- `7614347d89af030952a9e564d5e16cece8eff83f` — SVG evidence;
- `925ae74bcebba8bb2ad671043c4d80d718312706` — audit report;
- `1f06250b0be54daef915b2fe5c111ba4cc4def28` — task completion;
- `24208f68995c84555969e6c0a514b8f05501ba89` — immutable archive;
- `1475422c30f07c4a97e25ec70fc973d129bfc5d2` — complete handoff, confirmed on remote `main`.

The connector returned successful commit SHAs instead of conventional textual `git push`
stdout. Post-write history confirmed the complete delivery handoff on remote `main`.

## Scientific boundary

This validates documentation-path and source-byte handling only. Link existence does not
establish that a linked scientific claim, dataset, simulation, plot, table, or conclusion
is correct. Reference-style link definitions, heading anchors, case-sensitive portability,
and external URL availability remain outside this unit.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and aggregate matrices were reviewed
but not replaced because the connector provides whole-file replacement rather than
byte-safe append/patch semantics for these shared long-lived files. The immutable archive
and this handoff preserve the complete append-equivalent record. This remains an explicit
unmet aggregate-synchronization requirement.

## Next action

Add separately tested support for reference-style links, heading anchors, and
case-sensitive portability, then run a complete checkout-wide inventory in the
repository's Python 3.11 CI environment. Keep external URL checks separate from
deterministic repository-local provenance validation.
