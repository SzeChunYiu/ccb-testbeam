# AUD-LEDGER-001 — CL-022 anomaly-rate semantics repair

## Session identity

- **UTC stamp:** `2026-07-24T111232Z`
- **Task:** `AUD-LEDGER-001`
- **Unit:** source-backed reconstruction of malformed `CL-022`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial remote main:** `5085866208586443d7ccdb9004e6d0898a2d20a0`
- **Validated implementation/evidence head before this archive:** `8e74ff357fd359b743524316ac360703d52deb7e`
- **Destination:** direct sequential commits to `main`; no branch, PR, force-push, or history rewrite
- **Acceptance:** the CL-022 unit is `VALIDATED`; ledger-wide `AUD-LEDGER-001` remains `PARTIAL`

## Start-of-run review

Authenticated GitHub reads inspected recent main history, repository metadata,
current status/workflow attachments, PR #868, repository instructions, the
mandatory `chatgpt_todo/` records, the claim ledger and schema evidence, the MV6
report/summary/producer, README/WIKI/Chapter 9 public wording, and the historical
C12 synchronization tool and tests.

PR #868 was closed, unmerged, and non-mergeable and was not modified. The
initial commit had no attached status checks or workflow runs; no GitHub Actions
success is inferred.

## Confirmed defects

The former CL-022 row:

- had 39 fields under the canonical 43-column header, so late-field
  interpretation was unsafe;
- called `283/87555` a “C12 anomaly fraction”, although it is the total
  early-peak morphology rate among all selected truth-labelled MC tracks;
- had no confidence interval despite exact source counts;
- cited nonexistent `scripts/mv6_anomaly.py` and
  `reports/mv6_representation_1782678362/results.json` paths;
- did not distinguish the overall early-peak rate, the C12 composition within
  the selected class, and the early-peak rate within C12-labelled tracks.

README repeated the ambiguous wording and separately advertised numerical Rmax
as `VALIDATED`, despite exact-width CL-010 withholding it pending S-STAT-003.
The exact-match synchronization helper still encoded the obsolete README rows.

## Source evidence and independent calculations

Tracked sources:

- `reports/mv6_representation_1782678362/REPORT.md`
  - Git blob `2c531703755b28a0c576e978531b81374edf8ab4`
  - 2,822 bytes
  - SHA-256 `01c9dc9b27de46d1057420e7161d727db413481987d7fb1fd6f3e4310df92577`
- `reports/mv6_representation_1782678362/mv6_representation_summary.json`
  - Git blob `26c187cbe05d8dadbe588c6ed9062d25658a80a9`
  - 5,069 bytes
  - SHA-256 `eda47b436430b7663ad88bd87b2ed2b027b3ac1568bc82d899a51c55dc669720`
- `scripts/mv6_representation_study.py`
  - Git blob `f965823518b22908f3e8974f280bff5c970368d0`
  - source commit `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`

Source counts:

- 220,000 generated events;
- 87,555 selected B-arm charged MC tracks;
- morphology counts: 51,918 saturated, 35,354 normal, 283 early peak;
- no `low_area` entry, interpreted as zero by the producer/report convention;
- 7,302 C12-labelled tracks in the full selected sample;
- 156 C12-labelled tracks in the 283-track early-peak class.

Independent Wilson score intervals using `z = 1.959963984540054`:

| Quantity | Counts | Estimate | Wilson 95% interval |
|---|---:|---:|---:|
| Total early-peak rate | 283 / 87,555 | 0.003232254011764034 | [0.002877452112691542, 0.003630645177388446] |
| C12 share of early-peak class | 156 / 283 | 0.5512367491166078 | [0.4929885941153212, 0.6081125511627331] |
| Early-peak rate within C12 | 156 / 7,302 | 0.021364009860312245 | [0.018290520583369645, 0.024940838952822255] |

These denominators and scientific meanings are not interchangeable.

## Correction delivered

Updated:

- `docs/claim_ledger.csv`
  - CL-022 is exactly 43 columns;
  - names the stored quantity “Early-peak anomaly fraction in truth-labelled
    MC”;
  - records exact counts, Wilson interval, correct tracked source paths, source
    commit, and explicit limitations;
  - remains `TRUTH_LEVEL_MC_ONLY` and blocked by `AUD-ANOM-001` for data transfer.
- `README.md`
  - withholds Rmax pending `S-STAT-003`;
  - reports `283/87555` as the overall early-peak rate and `156/283` separately
    as C12 composition;
  - states that real-data identity is unvalidated.
- `scripts/sync_c12_public_claims.py`
  - current README migration is exact, idempotent, and scientifically scoped.
- `tests/test_sync_c12_public_claims.py`.
- `docs/validation/claim_ledger_schema_validation.json` and `.svg`
  - current state is 8/26 exact-width rows and 18 malformed/withheld rows.
- `chatgpt_todo/ACTIVE_TASK.md`.

Added:

- `tools/audit/validate_claim_ledger_cl022.py`;
- `tests/test_validate_claim_ledger_cl022.py`;
- `docs/validation/claim_ledger_cl022_audit.md`;
- `docs/validation/claim_ledger_cl022_validation.json`;
- `docs/validation/claim_ledger_cl022.svg`.

Policy: `SEPARATE_EARLY_PEAK_RATE_FROM_C12_COMPOSITION`.

## Validation

Executed on exact local candidates corresponding to the committed core files:

```text
python -m py_compile \
  tools/audit/validate_claim_ledger_cl022.py \
  scripts/sync_c12_public_claims.py \
  tests/test_validate_claim_ledger_cl022.py \
  tests/test_sync_c12_public_claims.py

python -m pytest \
  tests/test_validate_claim_ledger_cl022.py \
  tests/test_sync_c12_public_claims.py -q

19 passed in 0.06s
```

Additional validated checks:

- corrected-state CL-022 validator returned `VALIDATED`, zero issues;
- former 39-column CL-022 row returned status 1 with
  `LEDGER_ROW_WIDTH_MISMATCH`;
- README synchronizer check found zero pending replacements;
- machine-readable validation JSON parsed;
- both CL-022 and schema SVGs parsed as XML;
- changed Python candidates compiled and had no line longer than 100
  characters;
- corrected ledger and README committed Git blobs matched the validated
  candidates.

Ruff was unavailable. Full repository pytest, ROOT processing, model reruns,
matched data/MC closure, and GitHub Actions were not run.

## Direct-to-main commit sequence

1. `bb41b2d24dae6fe4a28f23551ef21174cc701f95` — `fix(ledger): separate CL-022 anomaly rate and C12 composition`
2. `65200b2238dfbccd938def676af9125db360434e` — `fix(ledger): restore CL-015 config path after CL-022 repair`
3. `3849b2952ed5b6f905c33a7cfc16f7d8edb28560` — `fix(docs): distinguish MV6 rate from C12 composition`
4. `a4bef49f0d2b7ef00652075bbdd9fbb746cc8aa2` — `fix(docs): keep C12 public synchronizer scientifically scoped`
5. `27a3e442fa9107dc1de1d3f18770dac3f0ee96b9` — `test(docs): cover exact MV6 public-claim migration`
6. `0967f1b83bc5aff268f0679f8873a6c581352219` — `feat(audit): validate CL-022 source counts and semantics`
7. `b0eda31c06fe0295acfca64f56542e3f0c4bc4d0` — `test(audit): cover CL-022 semantic separation`
8. `f24d8e3e3b0769b1e9add23a0adf2654a7ff69a0` — `docs(validation): record CL-022 semantics audit`
9. `b732c0cfb3ba9bc703f3f173bd5d4fcc878607a0` — `docs(validation): add CL-022 machine-readable record`
10. `5af6ad490da53156f7238471440aa9f3326fc96b` — `docs(validation): visualize CL-022 denominator separation`
11. `29b9b1d3239de5c1e7504f86517e5ed299057c08` — `docs(validation): refresh ledger schema after CL-022 repair`
12. `68a6381e6ea4fd692cd0b6f05be99a9cb7e025d1` — `docs(validation): visualize eight exact ledger rows`
13. `2b88dcb730f82e390e70d51f4a5474b632a1ca18` — `test(audit): align CL-022 regression bytes with validated fixture`
14. `8e74ff357fd359b743524316ac360703d52deb7e` — `docs(audit): track CL-022 semantics repair`

The first ledger update unintentionally changed one CL-015 config-path character;
this was detected through exact diff review and repaired immediately by the
second commit before downstream acceptance. No history was rewritten.

The authenticated contents API returns each direct-main commit SHA but not
textual `git push` stdout. Remote-main history was re-read after the sequence and
showed `8e74ff357fd359b743524316ac360703d52deb7e` as head before this archive.

## Scientific boundary and next actions

This unit establishes source-backed truth-labelled-MC proportions only. It does
not identify the related real-data anomaly as C12, validate a species tag in
data, establish classifier efficiency or false-positive rate, authorize a veto,
or produce a detector-performance result.

`AUD-ANOM-001` remains open for the preregistered matched data/MC closure.
`AUD-LEDGER-001` remains partial with 18 malformed rows withheld.

A separate confirmed documentation risk remains: Chapter 9 describes an
eight-dimensional/K=7 BIC-selected GMM and 99.7% PCA coverage, while the tracked
MV6 producer uses K=4 on four PCs and the summary records 82.188% cumulative
variance at eight PCs. Reconcile Chapter 9 against exact producer/result bytes
before treating those method claims as canonical.

`SESSION_LOG.md` was not replaced because the connector exposes whole-file
replacement rather than a byte-safe append operation and only paged/truncated
reads were available. Reconstructing and replacing the append-only file would
risk provenance loss. This immutable archive and the latest handoff contain the
complete run record.
