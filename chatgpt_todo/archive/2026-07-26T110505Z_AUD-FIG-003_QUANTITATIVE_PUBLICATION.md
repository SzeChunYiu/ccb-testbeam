# Immutable handoff — AUD-FIG-003 quantitative publication integrity

## Session

- Stamp: `2026-07-26T110505Z`
- Owner: scheduled scientific-review session
- Initial remote main: `cc0f39560f7e98b1c1c130748d268103ea08754a`
- Task: `AUD-FIG-003`
- Policy: `QUANTITATIVE_FIGURE_PUBLICATION_MUST_BE_ATOMIC_AND_FAILURE_SAFE`

## Repository facts inspected

- Current builder blob: `cc56e548b54fd8f2692182de6114ee3bcfe196c4`.
- `_emit_quantitative` writes `fig.savefig(figure_path)` directly to the final PNG.
- `plt.close(fig)` executes only after `savefig` returns.
- Existing source-artifact and CSV publication already use retained snapshots and atomic
  replacement, so the remaining gap is specifically the quantitative rendered PNG.
- Current main had no attached status checks.
- PR #868 was closed, unmerged, and non-mergeable.
- PR #939 was open, non-mergeable, and not modified.

## Measured behavioral controls

Former direct-target injected failure:

- previous SHA-256: `ecceab87413dd631c1fc00a41fba8604cfeb1effcbc20ec138839f035ea96099`;
- post-failure SHA-256: `e32e4ac9d2e88987ca18b1ffe3331c1e64ff326d7780f5da24a2c2b8865e241d`;
- previous target preserved: `false`;
- post-failure bytes: `14`.

Corrected temporary-file injected failure:

- previous target preserved: `true`;
- temporary files remaining: `0`.

Corrected success:

- retained replacement and final target SHA-256:
  `6dff689f32b725810bc49ca04fc688cbe2960613646c8060abb206209bdb0317`.

## Audit result

`FLAWED`, three findings:

- `QUANTITATIVE_RENDER_WRITES_FINAL_PATH_DIRECTLY`
- `QUANTITATIVE_FIGURE_HAS_NO_ATOMIC_PUBLICATION_BOUNDARY`
- `QUANTITATIVE_FIGURE_NOT_CLOSED_ON_RENDER_FAILURE`

## Validation

```text
python -m py_compile \
  tools/audit/audit_figure_quantitative_publication.py \
  tests/test_audit_figure_quantitative_publication.py \
  tools/audit/render_figure_quantitative_publication_evidence.py

PYTHONPATH=. pytest -q tests/test_audit_figure_quantitative_publication.py

7 passed in 1.38s
```

JSON and SVG parsed. Maximum changed Python line length was 96. Invalid UTF-8 and
output/source aliasing failed closed. Injected evidence-publication failure preserved the
prior JSON and removed the temporary file.

## Primary software references

- Python `tempfile.mkstemp`: secure creation and caller-managed cleanup.
  https://docs.python.org/3/library/tempfile.html#tempfile.mkstemp
- Python `os.replace`: successful same-filesystem replacement is atomic.
  https://docs.python.org/3/library/os.html#os.replace
- Matplotlib `Figure.savefig`: supplied path/file-like destination and explicit format.
  https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.savefig.html

## Delivered files

- `tools/audit/audit_figure_quantitative_publication.py`
- `tests/test_audit_figure_quantitative_publication.py`
- `tools/audit/render_figure_quantitative_publication_evidence.py`
- `docs/validation/figure_quantitative_publication_validation.json`
- `docs/validation/figure_quantitative_publication.svg`
- `docs/validation/figure_quantitative_publication_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- this immutable record
- refreshed `chatgpt_todo/HANDOFF.md`

## Acceptance and blockers

Audit implementation and evidence: `VALIDATED`.
Production quantitative PNG publication: `FLAWED / PARTIAL`, unchanged in this unit.

Required remediation: render to a same-directory temporary PNG with explicit format,
close the figure in `finally`, snapshot the complete temporary bytes, publish through the
existing atomic helper, verify the final target, and add direct failure regressions.

Unrun: repository-wide pytest/ruff, complete registry build, paper build, link inventory,
and GitHub Actions. No paper scientific value or detector-performance claim changed.

`SESSION_LOG.md` was reviewed but is not replaced in this connector-only run: writes are
whole-file replacements while the append-only file is available only through paged reads.
A partial reconstruction could erase provenance. This immutable record and the latest
handoff provide the append-equivalent session record without claiming the mandatory log
append was completed.
