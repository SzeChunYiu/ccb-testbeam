# Markdown Link-Checker Fail-Closed Audit

## Scope and status

- Task: `AUD-DOC-003`
- Session: `2026-07-25T010711Z`
- Initial remote `main`: `bf46fe4ef69a5fdf24d39f264d90218b0335f491`
- Former script blob: `0cc64c1e54291af0eed70ce3d4cfada976250e75`
- Policy: `MARKDOWN_LINK_TARGETS_MUST_BE_UTF8_AND_REPOSITORY_LOCAL`
- Acceptance: **VALIDATED** for the focused software/provenance correction

This is documentation-integrity validation. It is not detector data, a simulation result,
a calibration, or evidence that a linked scientific statement is correct.

## Confirmed defects

The former `scripts/broken_link_checker.py` had two independently reproduced failure
modes:

1. after identifying a missing target, it referenced undefined variable `boken` and
   raised `NameError` instead of emitting a stable finding count and controlled exit;
2. it used implicit text decoding, so a Markdown byte sequence containing invalid UTF-8
   raised an uncaught `UnicodeDecodeError` before the repository scan could complete.

The former implementation also joined relative paths without enforcing the repository
root. A link such as `../outside.md` could pass if the target happened to exist outside
the checkout, even though it was not a repository-contained artifact.

Open PR #883 proposed replacing invalid bytes during decoding and fixing the typo. Its
Chapter 9 patch is stale against current `main`, and replacement decoding would conceal
the exact byte defect rather than report it. The PR was not merged or modified.

## Corrective method

Validator version `2.0.0` now:

- reads Markdown as exact bytes and decodes strict UTF-8;
- converts invalid UTF-8 into a deterministic `INVALID_UTF8` finding without modifying
  source bytes;
- resolves percent-encoded local paths;
- rejects paths resolving outside the repository root with `TARGET_ESCAPES_ROOT`;
- reports absent targets as `MISSING_TARGET`;
- sorts files and findings deterministically;
- writes optional machine-readable JSON through same-directory temporary publication;
- returns 0 for no findings, 1 for validated findings, and 2 for audit I/O failure.

The current declared limitations are explicit: reference-style Markdown links and
heading-anchor existence are not parsed, and external URLs are not requested.

## Reproducible validation

Exact former-source negative controls:

```text
missing target -> BROKEN line, then NameError: name 'boken' is not defined
invalid UTF-8 -> uncaught UnicodeDecodeError at byte 6
```

Focused commands on the corrected implementation:

```text
python -m py_compile \
  scripts/broken_link_checker.py \
  tests/test_broken_link_checker.py \
  tools/audit/render_broken_link_checker_evidence.py

pytest -q tests/test_broken_link_checker.py

6 passed in 2.55s
```

The regression covers:

- valid local, external, and fragment-only examples;
- missing-target structured output and clean summary;
- controlled invalid-UTF-8 handling;
- repository-root escape rejection even when the outside target exists;
- percent-encoded local paths;
- deterministic atomic JSON output.

The locally validated implementation and tests matched the committed Git blobs:

- script: `0076b5cfdfbcbb6db322c9ae4ca01d7e2686651b`;
- tests: `327469c6c8299ec20825148a8040f93e09079c6c`.

Validation JSON parsed, the SVG parsed as XML, and changed Python lines were no longer
than 100 characters. The execution container had Python 3.13.5 and pytest 9.0.2; ruff
was not installed. The repository declares Python 3.11 in CI, so no broader supported-
environment claim is made from this focused run.

## Better-method comparison

Silently decoding with `errors="replace"` allows a scan to continue, but it erases the
location and identity of invalid source bytes. Strict decoding with a controlled finding
has slightly higher operational friction but preserves provenance and prevents corrupted
Markdown from being treated as clean. Likewise, root containment checks prevent a local
machine's unrelated filesystem from satisfying a repository evidence link.

## Remaining risks

A full repository-wide link scan was not executed because the automation container could
not clone the repository over the network. Reference definitions, heading anchors,
case-sensitive portability, and external URL availability remain outside this unit. These
limitations should be addressed in later, separately tested extensions rather than by
weakening the current fail-closed byte and path policy.
