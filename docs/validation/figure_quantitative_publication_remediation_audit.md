# Quantitative paper-figure publication remediation

## Scope

Task `AUD-FIG-003-R1` remediates the artifact-publication defect established by
`AUD-FIG-003`. It validates how quantitative PNG bytes are rendered, retained,
published, and recorded. It does not validate the scientific value or uncertainty
shown in any figure.

Policy:

`QUANTITATIVE_FIGURE_PUBLICATION_MUST_BE_ATOMIC_AND_FAILURE_SAFE`

Initial remote `main` was
`1c1e17958568d336b667304c651054ff88d03393`.

## Former failure

The former `_emit_quantitative` called `fig.savefig(figure_path)` on the final
artifact. A render exception after opening the destination could truncate or
partially replace a previously validated PNG. Figure cleanup also occurred only
after `savefig` returned.

The prior audit's injected control wrote 14 partial bytes and demonstrated that
the previous target was not preserved.

## Remediation

Commit `31a81736be727e7decd555ae53655cf7465aaba8` changes the production path to:

1. create a same-directory temporary render path with `tempfile.mkstemp`;
2. close the returned file descriptor before Matplotlib opens the path;
3. render with explicit `format="png"`;
4. read the completed temporary file once into a `ByteSnapshot`;
5. publish those retained bytes through `_atomic_publish_snapshot`, which flushes,
   `fsync`s, uses `os.replace`, and independently verifies final byte count and
   SHA-256;
6. close the Matplotlib figure in `finally`;
7. remove the render temporary file on every exit path;
8. record the render snapshot and publication contracts in source-data CSV.

The committed builder is Git blob
`822572726b65bb116f3f275af84312b526da4b23`, 17,571 bytes, SHA-256
`fe001a5b2ddef15fcfbe3a33d50909dfea57dee8b41ac2251442d6788b18fe56`.

## Regression evidence

Commit `98d8a4fdf691cc46cc4cf679c74569a43af07d1d` adds direct production-path
regressions. The exact committed test file is Git blob
`5fdb48f3b56c22aa7f19049648b1c6242864ab8a`, 4,242 bytes, SHA-256
`b4e0f81f0d221d59066e0713ed84474f79787470b37569f7354de917a15e2234`.

The controls establish:

- injected partial `savefig` failure preserves the prior final target;
- the Matplotlib figure is closed after that failure;
- no render temporary remains;
- injected final `os.replace` failure preserves the prior final target;
- no publication temporary remains;
- successful output has the PNG signature, and source-data SHA-256 and byte count
  match the final target exactly;
- the existing exact-source publication audit has zero findings.

## Validation

Executed on byte-exact local reconstructions of the two committed Git blobs:

```text
python -m py_compile \
  tools/figure_registry/builder.py \
  tests/test_figure_registry_quantitative_publication_remediation.py

PYTHONPATH=. pytest -q \
  tests/test_figure_registry_snapshot_remediation.py \
  tests/test_figure_registry_quantitative_publication_remediation.py

8 passed in 0.56s
```

Environment:

- Python 3.13.5
- pytest 9.0.2
- Matplotlib 3.10.8
- PyYAML 6.0.3

Changed Python line lengths are at most 100 characters. The validation JSON parsed,
and the generated SVG parsed as XML.

A synthetic one-entry successful build produced a 21,772-byte PNG with SHA-256
`9ab29f98f32314acee01d9125f2028a3f297b5d33cfe7ab22f371ab4040bf09b`.
This digest is environment-specific and is evidence of internal metadata closure,
not a physics result.

## Method choice

Rendering directly to an in-memory buffer would also avoid final-path truncation,
but a same-directory temporary PNG was selected because it exercises Matplotlib's
normal path-based encoder, keeps memory bounded for larger figures, and permits
atomic same-filesystem publication. Post-render hashing of the final path alone was
rejected because it cannot preserve a prior artifact when rendering itself fails.

Primary software documentation:

- Python `tempfile.mkstemp`: https://docs.python.org/3/library/tempfile.html#tempfile.mkstemp
- Python `os.replace`: https://docs.python.org/3/library/os.html#os.replace
- Matplotlib `Figure.savefig`: https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.savefig.html

## Acceptance boundary

The focused software remediation is `VALIDATED` and `COMPLETE` for
`AUD-FIG-003-R1`.

Not run or claimed: repository-wide pytest, repository-wide ruff, complete shipped
figure-registry build, paper build, repository-wide link inventory, or GitHub
Actions. No paper figure, central value, uncertainty, timing result, calibration,
PID result, stopping profile, pile-up rate, or detector-performance claim was
regenerated or accepted.
