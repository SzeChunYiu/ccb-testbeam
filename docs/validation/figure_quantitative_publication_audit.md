# Quantitative paper-figure publication integrity audit

## Status

**FLAWED / PARTIAL** for the current production builder. The audit implementation,
focused regressions, machine-readable record, and visual evidence are validated.

Task: `AUD-FIG-003`

Policy:

`QUANTITATIVE_FIGURE_PUBLICATION_MUST_BE_ATOMIC_AND_FAILURE_SAFE`

## Repository observation

Current `main` was `cc0f39560f7e98b1c1c130748d268103ea08754a` at task selection.
The inspected production source is `tools/figure_registry/builder.py`, Git blob
`cc56e548b54fd8f2692182de6114ee3bcfe196c4`.

The current `_emit_quantitative` path:

1. creates and populates a Matplotlib figure;
2. assigns the final output path `out_dir / f"{entry.id}.png"`;
3. calls `fig.savefig(figure_path)` directly on that final path;
4. calls `plt.close(fig)` only after `savefig` returns;
5. reads and hashes the final path afterward.

This differs from the already remediated source-artifact and CSV paths, which use
retained bytes plus same-directory temporary publication and `os.replace`.

The executable current-source audit input is an exact connector-reconstructed
`_emit_quantitative` function excerpt. The full-file Git blob above binds that excerpt
to current repository history; the excerpt is not misrepresented as a byte-identical
checkout of the whole file.

## Confirmed failure mode

A deterministic control began with a previously validated target and injected a render
failure after opening the final target in write mode and writing partial bytes.

- previous target SHA-256:
  `ecceab87413dd631c1fc00a41fba8604cfeb1effcbc20ec138839f035ea96099`;
- post-failure SHA-256:
  `e32e4ac9d2e88987ca18b1ffe3331c1e64ff326d7780f5da24a2c2b8865e241d`;
- previous target preserved: `false`;
- post-failure bytes: `14`.

The direct-final-path pattern can therefore destroy or partially replace prior paper
evidence if rendering fails after target truncation. This is an artifact-integrity
result, not a claim that Matplotlib always fails in this way.

A corrected control rendered into a same-directory temporary file. The same injected
failure preserved the prior target byte-for-byte and left zero temporary files. A
successful control published complete replacement bytes with matching SHA-256:

`6dff689f32b725810bc49ca04fc688cbe2960613646c8060abb206209bdb0317`.

## Findings

The current contract returns `FLAWED` with three findings:

1. `QUANTITATIVE_RENDER_WRITES_FINAL_PATH_DIRECTLY`;
2. `QUANTITATIVE_FIGURE_HAS_NO_ATOMIC_PUBLICATION_BOUNDARY`;
3. `QUANTITATIVE_FIGURE_NOT_CLOSED_ON_RENDER_FAILURE`.

The third finding matters for long registry builds: because cleanup occurs after
`savefig`, a render exception can bypass `plt.close(fig)` and leak figure resources.

## Better method

The focused replacement contract is:

1. create a secure temporary file in the final target directory;
2. close its initial descriptor before Matplotlib opens the path;
3. call `fig.savefig(render_path, format="png")` so the temporary suffix cannot alter
   format inference;
4. close the Matplotlib figure in `finally`;
5. read the complete rendered bytes once and calculate byte count/SHA-256 from that
   retained snapshot;
6. atomically publish those bytes to the final path using the existing
   `_atomic_publish_snapshot` helper;
7. remove every render temporary on success or failure;
8. verify the final target digest and byte count;
9. add direct tests for save failure, replacement failure, previous-target preservation,
   temporary cleanup, and source-data identity.

Python documents `tempfile.mkstemp` as race-resistant creation with caller-managed
cleanup. Python documents successful `os.replace` as atomic, subject to the source and
destination being on a compatible filesystem; a same-directory temporary file satisfies
that design intent. Matplotlib documents that `Figure.savefig` writes to the supplied
path or file-like object and that an explicit `format` controls output independently of
the filename suffix.

Primary software references:

- https://docs.python.org/3/library/tempfile.html#tempfile.mkstemp
- https://docs.python.org/3/library/os.html#os.replace
- https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.savefig.html

## Validation

```text
python -m py_compile \
  tools/audit/audit_figure_quantitative_publication.py \
  tests/test_audit_figure_quantitative_publication.py \
  tools/audit/render_figure_quantitative_publication_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_audit_figure_quantitative_publication.py

7 passed in 1.38s
```

Additional checks:

- current-like fixture: `FLAWED`, three findings;
- corrected fixture: `VALIDATED`, zero findings;
- invalid UTF-8: controlled status 2;
- input/output alias: rejected without source modification;
- injected JSON `os.replace` failure: previous target preserved, temporary removed;
- validation JSON parsed;
- SVG parsed as XML;
- maximum changed Python line length: 96.

Environment: Python 3.13.5 and pytest 9.0.2.

## Files delivered

- `tools/audit/audit_figure_quantitative_publication.py`
- `tests/test_audit_figure_quantitative_publication.py`
- `tools/audit/render_figure_quantitative_publication_evidence.py`
- `docs/validation/figure_quantitative_publication_validation.json`
- `docs/validation/figure_quantitative_publication.svg`
- this report
- immutable `chatgpt_todo/archive/` handoff
- refreshed `chatgpt_todo/ACTIVE_TASK.md` and `HANDOFF.md`

## Acceptance boundary

The audit gate and evidence are validated. The production builder is deliberately not
modified in this audit unit and remains `FLAWED / PARTIAL` for quantitative PNG
publication.

No paper figure was regenerated. No scientific central value, uncertainty, calibration,
PID result, timing result, stopping profile, pile-up rate, or detector-performance claim
was validated or changed.

Repository-wide pytest and ruff, the complete shipped registry, the paper build, link
inventory, and GitHub Actions were not run. PR #868 remains closed and unmerged. Open
PR #939 was inspected but not modified or merged.
