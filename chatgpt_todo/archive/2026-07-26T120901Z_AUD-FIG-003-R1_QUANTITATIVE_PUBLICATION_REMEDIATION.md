# AUD-FIG-003-R1 quantitative publication remediation

## Session

- **Stamp:** `2026-07-26T120901Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `1c1e17958568d336b667304c651054ff88d03393`
- **Task:** remediate the fail-open quantitative PNG publication path identified by `AUD-FIG-003`.
- **Policy:** `QUANTITATIVE_FIGURE_PUBLICATION_MUST_BE_ATOMIC_AND_FAILURE_SAFE`
- **Status:** `COMPLETE` for the focused software remediation.

## Repository and concurrency review

Remote `main`, recent commits, repository permissions, open PRs, PR #868, current
commit checks, repository instructions, and the current `chatgpt_todo/` handoff were
reviewed before the change. PR #939 was open, non-mergeable, and had no attached
status checks. PR #868 was closed, unmerged, and non-mergeable. Neither PR was
modified or merged.

No concurrent remote-main commit landed between the initial read and the focused
implementation/test writes.

## Confirmed defect

The previous `_emit_quantitative` passed the final PNG path directly to
`Figure.savefig` and closed the figure only after rendering returned. The prior
audit demonstrated that a render exception after truncation replaced a previous
validated artifact with 14 partial bytes.

## Remediation

The production builder now:

1. creates a same-directory render temporary with `tempfile.mkstemp`;
2. renders with explicit PNG format;
3. reads the completed temporary bytes into a content-addressed snapshot;
4. publishes the retained snapshot through the existing flush/fsync/`os.replace`
   helper;
5. verifies final byte count and SHA-256 independently;
6. closes the Matplotlib figure in `finally`;
7. removes the render temporary on every exit path;
8. records snapshot and publication contracts in source-data CSV.

Implementation:

- commit `31a81736be727e7decd555ae53655cf7465aaba8`;
- file `tools/figure_registry/builder.py`;
- Git blob `822572726b65bb116f3f275af84312b526da4b23`;
- 17,571 bytes;
- SHA-256 `fe001a5b2ddef15fcfbe3a33d50909dfea57dee8b41ac2251442d6788b18fe56`.

## Regression evidence

Focused regression commit:

- `98d8a4fdf691cc46cc4cf679c74569a43af07d1d`;
- file `tests/test_figure_registry_quantitative_publication_remediation.py`;
- Git blob `5fdb48f3b56c22aa7f19049648b1c6242864ab8a`;
- 4,242 bytes;
- SHA-256 `b4e0f81f0d221d59066e0713ed84474f79787470b37569f7354de917a15e2234`.

The tests inject partial `savefig` failure and final `os.replace` failure, verify
prior-target preservation and temporary cleanup, verify figure closure, validate a
successful PNG signature and exact digest/size metadata, and require the source
audit to return zero findings.

## Validation

```text
python -m py_compile \
  tools/figure_registry/builder.py \
  tests/test_figure_registry_quantitative_publication_remediation.py

PYTHONPATH=. pytest -q \
  tests/test_figure_registry_snapshot_remediation.py \
  tests/test_figure_registry_quantitative_publication_remediation.py

8 passed in 0.56s
```

Environment: Python 3.13.5, pytest 9.0.2, Matplotlib 3.10.8, PyYAML 6.0.3.
The builder and new test were reconstructed byte-for-byte from their committed Git
blobs before execution. Maximum changed Python line length was 100. Validation JSON
and SVG parsed successfully.

Synthetic successful output: 21,772-byte PNG, SHA-256
`9ab29f98f32314acee01d9125f2028a3f297b5d33cfe7ab22f371ab4040bf09b`,
with zero temporary files remaining and exact source-data digest closure. This hash
is environment-specific software evidence, not a physics result.

## Evidence files and commits

- `e885c2f465420c9f7ce9a7d40af4c938c1d04b60` — evidence renderer;
- `1070035f06189a23da1251f40cc2e9d54c8e0471` — machine-readable evidence;
- `c77554cd65e6517d24f08cff44244c68d0da0dfe` — SVG evidence;
- `22a3ac9b45cbf6ac0e5b43a01c0e4de65dcc2970` — audit report.

Paths:

- `tools/audit/render_figure_quantitative_publication_remediation_evidence.py`
- `docs/validation/figure_quantitative_publication_remediation_validation.json`
- `docs/validation/figure_quantitative_publication_remediation.svg`
- `docs/validation/figure_quantitative_publication_remediation_audit.md`

## Unrun checks

Repository-wide pytest, repository-wide ruff, complete shipped registry build, paper
build, repository-wide link inventory, and GitHub Actions were not run and are not
claimed as passing. The complete repository could not be cloned because the runtime
could not resolve `github.com`; authenticated connector reads and writes were used.

## Scientific boundary

This unit validates artifact publication integrity only. It does not validate or
change any paper-figure value, uncertainty, timing result, calibration, PID result,
stopping profile, pile-up rate, or detector-performance claim.

## Coordination limitation

`SESSION_LOG.md` and the long shared aggregate ledgers were reviewed but could not be
safely appended through the available connector because reads are paged while writes
replace the complete file. Reconstructing a partial append-only file could erase
unrelated history. This immutable record and the current `HANDOFF.md` retain the
complete append-equivalent session evidence without claiming that the mandatory
append succeeded.
