# Latest Handoff

## Session

- **Task ID:** `AUD-FIG-003`
- **Stamp:** `2026-07-26T110505Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `cc0f39560f7e98b1c1c130748d268103ea08754a`
- **Validated delivery head before this handoff:** `f814ef01170dc76f11df122cd72c8334cd9782c8`
- **Remote main after validated delivery:** `f814ef01170dc76f11df122cd72c8334cd9782c8`
- **Destination:** direct sequential commits to `main`; no task branch, pull-request transport, force-push, or history rewrite.
- **Push result:** GitHub contents API returned a successful direct-main commit SHA for every write. The connector does not return a conventional terminal `git push` transcript, and none is claimed.
- **Focused acceptance:** audit gate, tests, JSON, SVG, report, active-task record, and immutable archive `VALIDATED`; production quantitative PNG publication remains `FLAWED / PARTIAL` and unchanged.
- **Scientific acceptance:** no paper figure value, uncertainty, or detector-performance claim was authorized or changed.

## Finding

Policy:

`QUANTITATIVE_FIGURE_PUBLICATION_MUST_BE_ATOMIC_AND_FAILURE_SAFE`

Current builder blob `cc56e548b54fd8f2692182de6114ee3bcfe196c4` calls
`fig.savefig(figure_path)` on the final PNG and calls `plt.close(fig)` only afterward.
An injected partial-write failure changed a prior target from SHA-256
`ecceab87413dd631c1fc00a41fba8604cfeb1effcbc20ec138839f035ea96099` to
`e32e4ac9d2e88987ca18b1ffe3331c1e64ff326d7780f5da24a2c2b8865e241d`.
The post-failure artifact contained 14 partial bytes.

The corrected temporary-render control preserved the prior target, left zero temporary
files, and atomically published complete replacement bytes on success. The successful
replacement and final-target SHA-256 were both
`6dff689f32b725810bc49ca04fc688cbe2960613646c8060abb206209bdb0317`.

## Audit result

The current-like exact function excerpt returned `FLAWED` with:

1. `QUANTITATIVE_RENDER_WRITES_FINAL_PATH_DIRECTLY`;
2. `QUANTITATIVE_FIGURE_HAS_NO_ATOMIC_PUBLICATION_BOUNDARY`;
3. `QUANTITATIVE_FIGURE_NOT_CLOSED_ON_RENDER_FAILURE`.

A corrected fixture returned `VALIDATED` with zero findings.

## Validation

```text
python -m py_compile \
  tools/audit/audit_figure_quantitative_publication.py \
  tests/test_audit_figure_quantitative_publication.py \
  tools/audit/render_figure_quantitative_publication_evidence.py

PYTHONPATH=. pytest -q tests/test_audit_figure_quantitative_publication.py

7 passed in 1.38s
```

Additional checks:

- invalid UTF-8: controlled status 2;
- source/output alias: rejected without source modification;
- injected evidence `os.replace` failure: prior JSON preserved and temporary removed;
- validation JSON parsed;
- SVG parsed as XML;
- maximum changed Python line length: 96;
- environment: Python 3.13.5, pytest 9.0.2.

## Work delivered

- `tools/audit/audit_figure_quantitative_publication.py`
- `tests/test_audit_figure_quantitative_publication.py`
- `tools/audit/render_figure_quantitative_publication_evidence.py`
- `docs/validation/figure_quantitative_publication_validation.json`
- `docs/validation/figure_quantitative_publication.svg`
- `docs/validation/figure_quantitative_publication_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/archive/2026-07-26T110505Z_AUD-FIG-003_QUANTITATIVE_PUBLICATION.md`
- this handoff.

## Primary software sources

- Python `tempfile.mkstemp`: secure creation and caller-managed cleanup.
  https://docs.python.org/3/library/tempfile.html#tempfile.mkstemp
- Python `os.replace`: successful same-filesystem replacement is atomic.
  https://docs.python.org/3/library/os.html#os.replace
- Matplotlib `Figure.savefig`: supplied path/file-like destination and explicit format.
  https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.savefig.html

## Direct-main sequence

- `a2a6f49c23b3c3f3f7f00acb2cb40480969c618a` — audit gate;
- `eb404a466de3b5c07ca199331dba95e6d637ccb8` — focused regressions;
- `addb94fd51a5b494924a347baf9434b0a28ba353` — evidence renderer;
- `12d083d6b89a2e7cc6a879c43ab2baeb74a21fc0` — machine-readable evidence;
- `8950bf7df4e5e95314e7b89fdff486d7fa1d2291` — visual evidence;
- `59b92d8726c0ae4591cb8465cdceb468094d45fd` — audit report;
- `ebc5ce0b7457a462fd814332575296db016961b8` — immutable archive;
- `f814ef01170dc76f11df122cd72c8334cd9782c8` — active-task update and validated delivery head.

## Unrun checks and unresolved coordination

Repository-wide pytest and ruff, the complete shipped figure-registry build, the paper
build, repository-wide link inventory, and GitHub Actions were not run and are not
claimed as passing. The initial main commit had no attached status checks.

The runtime could not resolve `github.com`; repository reads and direct-main writes used
the authenticated connector. Focused tests ran on the committed new tool/test bytes and
an exact connector-reconstructed current `_emit_quantitative` excerpt bound to the full
builder Git blob.

`SESSION_LOG.md` was reviewed but not safely appended. The connector writes complete
file replacements while the append-only file is available only through paged reads; a
partial transcription could erase historical provenance. The immutable archive and this
handoff preserve the complete append-equivalent record. Shared backlog/index/matrix files
were not partially replaced for the same reason.

PR #939 remained open, non-mergeable, and unmerged. PR #868 remained closed,
non-mergeable, and unmerged. Neither was modified.

## Scientific boundary and next action

No paper figure was regenerated and no scientific value, uncertainty, calibration, PID,
timing, stopping profile, pile-up rate, or detector-performance claim was changed.

Next: render quantitative PNGs to a same-directory temporary path with explicit PNG
format, close figures in `finally`, retain complete rendered bytes, publish through the
existing atomic helper, verify the final target, and add direct production-path failure
regressions before running the complete shipped registry.
