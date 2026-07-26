# Latest Handoff

## Session

- **Task ID:** `AUD-FIG-003-R1`
- **Stamp:** `2026-07-26T120901Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `1c1e17958568d336b667304c651054ff88d03393`
- **Validated implementation/evidence head before handoff:** `d5ab93afbe022e24f73b3199d0e696a7c8e97f02`
- **Destination:** direct sequential commits to `main`; no task branch, pull-request transport, force-push, or history rewrite.
- **Push result:** each GitHub contents write returned a successful direct-main commit SHA. The connector does not return a conventional terminal `git push` transcript, and none is claimed.
- **Focused acceptance:** quantitative PNG publication remediation, direct regressions, JSON, SVG, report, active-task record, and immutable archive are `VALIDATED / COMPLETE`.
- **Scientific acceptance:** no paper-figure value, uncertainty, timing result, calibration, PID result, stopping profile, pile-up rate, or detector-performance claim was authorized or changed.

## Defect and remediation

Policy:

`QUANTITATIVE_FIGURE_PUBLICATION_MUST_BE_ATOMIC_AND_FAILURE_SAFE`

The former `_emit_quantitative` rendered directly to the final PNG. An exception
after truncation could destroy a prior validated artifact, and `plt.close(fig)` was
bypassed when `savefig` failed.

The production path now:

1. creates a same-directory temporary render path with `tempfile.mkstemp`;
2. renders with explicit `format="png"`;
3. reads the completed render bytes once into a content-addressed snapshot;
4. atomically publishes those retained bytes through the existing flush/fsync/
   `os.replace` helper;
5. verifies final byte count and SHA-256;
6. closes the Matplotlib figure in `finally`;
7. removes render temporaries on every exit path;
8. records render-snapshot and publication contracts in source-data CSV.

Implementation identity:

- commit `31a81736be727e7decd555ae53655cf7465aaba8`;
- builder blob `822572726b65bb116f3f275af84312b526da4b23`;
- 17,571 bytes;
- SHA-256 `fe001a5b2ddef15fcfbe3a33d50909dfea57dee8b41ac2251442d6788b18fe56`.

Regression identity:

- commit `98d8a4fdf691cc46cc4cf679c74569a43af07d1d`;
- test blob `5fdb48f3b56c22aa7f19049648b1c6242864ab8a`;
- 4,242 bytes;
- SHA-256 `b4e0f81f0d221d59066e0713ed84474f79787470b37569f7354de917a15e2234`.

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
The two changed source/test files were reconstructed byte-for-byte from their
committed Git blobs before execution. Maximum changed Python line length was 100.
Validation JSON parsed and the SVG parsed as XML.

Behavioral controls:

- injected partial `savefig` failure preserved the prior final target;
- the Matplotlib figure closed after that failure;
- render temporary count after failure was zero;
- injected final `os.replace` failure preserved the prior target;
- publication temporary count after failure was zero;
- successful PNG had signature `89504e470d0a1a0a` and exact digest/size closure in
  source-data metadata;
- existing result/source snapshot race regressions remained passing;
- exact-source publication contract returned zero findings.

Synthetic successful output was 21,772 bytes with SHA-256
`9ab29f98f32314acee01d9125f2028a3f297b5d33cfe7ab22f371ab4040bf09b`.
That digest is environment-specific software evidence, not a physics result.

## Work delivered

- `tools/figure_registry/builder.py`
- `tests/test_figure_registry_quantitative_publication_remediation.py`
- `tools/audit/render_figure_quantitative_publication_remediation_evidence.py`
- `docs/validation/figure_quantitative_publication_remediation_validation.json`
- `docs/validation/figure_quantitative_publication_remediation.svg`
- `docs/validation/figure_quantitative_publication_remediation_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/archive/2026-07-26T120901Z_AUD-FIG-003-R1_QUANTITATIVE_PUBLICATION_REMEDIATION.md`
- this handoff.

## Direct-main sequence

- `31a81736be727e7decd555ae53655cf7465aaba8` — production remediation;
- `98d8a4fdf691cc46cc4cf679c74569a43af07d1d` — direct regressions;
- `e885c2f465420c9f7ce9a7d40af4c938c1d04b60` — evidence renderer;
- `1070035f06189a23da1251f40cc2e9d54c8e0471` — machine-readable evidence;
- `c77554cd65e6517d24f08cff44244c68d0da0dfe` — visual evidence;
- `22a3ac9b45cbf6ac0e5b43a01c0e4de65dcc2970` — audit report;
- `6eaf854bbb895759697498cf4e601d6e596dfc45` — immutable archive;
- `d5ab93afbe022e24f73b3199d0e696a7c8e97f02` — active-task completion.

## Repository and PR state

At run start, `main` was `1c1e17958568d336b667304c651054ff88d03393`
and had no attached combined status checks. PR #939 was open, non-mergeable, and had
no attached status checks; it was not modified or merged. PR #868 remained closed,
unmerged, and non-mergeable; it was not modified.

No concurrent remote-main commit appeared between the initial read and the focused
implementation/test writes.

## Unrun checks and coordination limitation

Repository-wide pytest, repository-wide ruff, the complete shipped figure registry,
the paper build, repository-wide link inventory, and GitHub Actions were not run and
are not claimed as passing. The runtime could not resolve `github.com`, so the full
repository could not be cloned; authenticated connector reads and writes were used.

`SESSION_LOG.md` and long aggregate ledgers were reviewed but not safely appended.
The connector exposes paged reads while writes replace the entire file; reconstructing
a partial append-only file could erase unrelated history. The immutable archive and
this handoff retain the complete append-equivalent record without claiming the
mandatory append succeeded.

## Next action

Run the complete shipped figure registry and paper build in a full checkout, inspect
all generated quantitative/source artifacts and build reports, and resolve any
remaining registry/build failures before broader paper integration is accepted.
