# Root-WIKI S10b live-time remediation audit

## Scope

This record closes the evidence and coordination gap left after commit
`0e32bf3f5956162d30259489d6d99295280e06fb` corrected the two public
`CL-011` claim sites in `WIKI.md` and added
`tests/test_wiki_tau_eff_public_remediation.py`.

The unit validates documentation and provenance. It does not rerun the S10b
waveform analysis and does not establish a detector-wide universal dead time,
an accepted numerical Rmax, a new uncertainty model, a calibration, or detector
performance.

## Exact remote inputs

- core remediation commit: `0e32bf3f5956162d30259489d6d99295280e06fb`;
- corrected WIKI blob: `001e091f82756f45339fe5e48256a951b6331295`;
- canonical ledger blob: `254dc5b64945260193d6b1bd4146bd6400ad28cf`;
- integration-test blob: `fb049a100501d5091f85daab7d4cd715a9107586`;
- linked Chapter 5 blob: `02a9ba538b1627e1ef3cda78594a4f08446fbffe`.

The exact GitHub excerpts used for the independent snapshot validation were:

- `WIKI.md` lines 54–75, containing the canonical results table;
- `WIKI.md` lines 198–235, containing the pile-up section;
- the 43-field ledger header and exact `CL-011` record.

## Canonical contract checked

The public claim is bound to the tracked S10b data-only estimand:

- central value `124.79018394263471 ns`;
- run-bootstrap 95% interval
  `[123.33094981246663, 126.35875117626817] ns`;
- 14 runs and 252266 selected pulses;
- `truth_type=data_measurement`;
- `status=DONE_DATA_ONLY`;
- blocker `BLK-S10B-001`;
- no separate statistical, systematic, or total uncertainty components.

The pile-up narrative also states that the result is threshold-, selection-, and
run-weighting-specific, is not a detector-wide universal dead time, and is used
by MV5 as an input rather than independently validated by MV5.

## Independent snapshot validation

A separate local checker parsed the exact fetched ledger row and exact fetched
WIKI section snapshots. It required one exact canonical row, one exact pile-up
row, all scientific caveats, the exact interval and sample counts, and absence
of the former stale phrases.

```text
python -m py_compile \
  tests/test_wiki_tau_eff_public_remediation.py \
  tools/validate_remediation_snapshot.py

python tools/validate_remediation_snapshot.py

status: VALIDATED
issues: 0
```

The exact committed integration-test source compiled successfully. Its local
SHA-256 was
`183b213b9abf03c8d46bfd98abb474fa0b902c5bff0852448cacd65180c46f88`,
and its longest line was 85 characters.

Snapshot SHA-256 values:

- canonical WIKI excerpt:
  `ff155d1676d8b1f6e621f77c1cb0df33e41cf2bd10772205248c66702afb67fa`;
- pile-up WIKI excerpt:
  `b9d8f0f5a2226c5f3462fee9b9696a65774328237cfaf30559039e882f410f9c`;
- ledger header plus `CL-011`:
  `efd028d22eed19c9a45b0e07a0bcc5d05a4e6205118e5ddeb5e72e997540af77`.

The Chapter 5 link target exists at
`docs/academic_chapters/05_pileup_analysis.md` and identifies the result as a
`DONE_DATA_ONLY` measurement while withholding numerical Rmax.

## Visual evidence

`docs/validation/wiki_tau_eff_public_remediation.svg` summarizes the two bound
public locations, the exact value and interval, validation status, and the
scientific boundary. The SVG parsed successfully as XML. It is explicitly
software/documentation evidence, not detector data.

## Checks not run

A complete network checkout was unavailable because the execution container
could not resolve `github.com`. Therefore this unit does not claim:

- repository-wide pytest or ruff;
- execution of the exact three-validator integration test in a full checkout;
- a repository-wide broken-link inventory;
- GitHub Actions success;
- ROOT waveform reprocessing or an S10b fit rerun.

No status checks were attached to the core remediation commit when inspected.

## Acceptance

The public-WIKI remediation and its evidence are **VALIDATED** as a focused
documentation/provenance unit. `AUD-WIKI-004` is complete. The cumulative
repository-wide WIKI audit remains open for unrelated claims and links.
