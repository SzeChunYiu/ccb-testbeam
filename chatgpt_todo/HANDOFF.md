# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T111232Z`
- **Task:** `AUD-LEDGER-001`
- **Unit:** source-backed reconstruction of `CL-022`
- **Initial remote `main`:** `5085866208586443d7ccdb9004e6d0898a2d20a0`
- **Validated delivery head before this handoff:** `14e1b2570edc189c8b8913d4c612ea586404fe21`
- **Destination:** direct sequential commits to `main`
- **Acceptance:** this CL-022 unit is `VALIDATED`; ledger-wide work remains `PARTIAL`

## Review and concurrency

Authenticated GitHub reads inspected recent main history, PR #868, status/workflow
attachments, repository instructions, mandatory `chatgpt_todo/` records, the
claim ledger/schema audit, the MV6 report/summary/producer, README, WIKI,
Chapter 9, and the public-claim synchronization code. No concurrent commit
appeared during this focused sequence.

PR #868 remains closed and unmerged and was not modified. No status checks or
workflow runs were attached to the initial or validated delivery head, so no
GitHub Actions success is inferred. A local checkout could not reach GitHub;
repository reads/writes used the authenticated connector.

## Confirmed defects

The former CL-022 row had 39 fields under the canonical 43-column header. It
called `283/87555` a C12 anomaly fraction, although these counts are the total
early-peak morphology rate among all selected truth-labelled MC tracks. It had
no confidence interval and cited nonexistent `scripts/mv6_anomaly.py` and
`reports/mv6_representation_1782678362/results.json` paths.

README repeated the ambiguous wording and still advertised numerical Rmax as
validated despite exact-width CL-010 withholding it pending `S-STAT-003`.

## Source evidence and calculations

Tracked source facts:

- events: `220000`;
- selected MC tracks: `87555`;
- early-peak tracks: `283`;
- `low_area`: `0`;
- C12-labelled tracks: `7302`;
- C12-labelled early-peak tracks: `156`.

Independent Wilson 95% intervals:

| Quantity | Counts | Estimate | Interval |
|---|---:|---:|---:|
| Total early-peak rate | 283 / 87555 | 0.003232254011764034 | [0.002877452112691542, 0.003630645177388446] |
| C12 share of early-peak class | 156 / 283 | 0.5512367491166078 | [0.4929885941153212, 0.6081125511627331] |
| Early-peak rate within C12 | 156 / 7302 | 0.021364009860312245 | [0.018290520583369645, 0.024940838952822255] |

These are three different binomial quantities and cannot be interchanged.

Source provenance:

- report blob `2c531703755b28a0c576e978531b81374edf8ab4`, SHA-256 `01c9dc9b27de46d1057420e7161d727db413481987d7fb1fd6f3e4310df92577`;
- summary blob `26c187cbe05d8dadbe588c6ed9062d25658a80a9`, SHA-256 `eda47b436430b7663ad88bd87b2ed2b027b3ac1568bc82d899a51c55dc669720`;
- producer blob `f965823518b22908f3e8974f280bff5c970368d0`, source commit `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`.

## Delivered changes

Updated:

- `docs/claim_ledger.csv`: CL-022 is exactly 43 columns, has correct source
  paths/counts/Wilson interval, and remains `TRUTH_LEVEL_MC_ONLY`;
- `README.md`: Rmax is withheld; total early-peak rate and C12 composition are
  reported separately; real-data identity remains unvalidated;
- `scripts/sync_c12_public_claims.py` and its regression;
- repository-wide schema JSON/SVG, now 8/26 exact rows and 18 withheld rows;
- `chatgpt_todo/ACTIVE_TASK.md`.

Added:

- `tools/audit/validate_claim_ledger_cl022.py`;
- `tests/test_validate_claim_ledger_cl022.py`;
- `docs/validation/claim_ledger_cl022_audit.md`;
- `docs/validation/claim_ledger_cl022_validation.json`;
- `docs/validation/claim_ledger_cl022.svg`;
- `chatgpt_todo/archive/2026-07-24T111232Z_AUD-LEDGER-001_CL022_SEMANTICS.md`.

Policy: `SEPARATE_EARLY_PEAK_RATE_FROM_C12_COMPOSITION`.

## Validation

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

Also passed: corrected-state validator (`VALIDATED`, zero issues), former
39-column negative control, README synchronization check, JSON parsing, SVG XML
parsing, and changed-Python line-length checks. Ruff, full repository pytest,
ROOT processing, model reruns, matched data/MC closure, and Actions were not run.

Exact corrected artifacts:

- ledger blob `e489555f3a520c7cc64b8a7d858a0e93622b9de6`, 12264 bytes, SHA-256 `9a099f76609c51b7400c8615a46c5e873058ac00e0fa9e3a0e2877a1d5e5db5c`;
- README blob `cd54ede2a63b9ae5ddafafc98f7c5d612fe080d0`, 4967 bytes, SHA-256 `ebf79ebc9ca4d56907d35f36472bc145fbf14b7c4338a45bdc02da8c7a315916`;
- validator blob `fe576c3a4539de9db94533677b7611238af9db32`.

## Direct-main commits

1. `bb41b2d24dae6fe4a28f23551ef21174cc701f95` — initial ledger repair
2. `65200b2238dfbccd938def676af9125db360434e` — restored one accidentally changed CL-015 path
3. `3849b2952ed5b6f905c33a7cfc16f7d8edb28560` — README correction
4. `a4bef49f0d2b7ef00652075bbdd9fbb746cc8aa2` — synchronizer correction
5. `27a3e442fa9107dc1de1d3f18770dac3f0ee96b9` — synchronizer tests
6. `0967f1b83bc5aff268f0679f8873a6c581352219` — CL-022 validator
7. `b0eda31c06fe0295acfca64f56542e3f0c4bc4d0` — CL-022 tests
8. `f24d8e3e3b0769b1e9add23a0adf2654a7ff69a0` — audit report
9. `b732c0cfb3ba9bc703f3f173bd5d4fcc878607a0` — validation JSON
10. `5af6ad490da53156f7238471440aa9f3326fc96b` — CL-022 SVG
11. `29b9b1d3239de5c1e7504f86517e5ed299057c08` — schema JSON
12. `68a6381e6ea4fd692cd0b6f05be99a9cb7e025d1` — schema SVG
13. `2b88dcb730f82e390e70d51f4a5474b632a1ca18` — aligned regression fixture
14. `8e74ff357fd359b743524316ac360703d52deb7e` — active-task record
15. `14e1b2570edc189c8b8913d4c612ea586404fe21` — immutable archive

The connector returns commit SHAs rather than textual push output. Remote history
was re-read and confirmed the archive commit as the delivery head before this
handoff.

## Boundary and next work

This unit does not identify the real-data anomaly as C12, validate a data
species tag, establish efficiency/false-positive rate/veto impact, or regenerate
detector results. `AUD-ANOM-001` and ledger-wide `AUD-LEDGER-001` remain
`PARTIAL`.

Chapter 9 remains method-inconsistent: it describes an eight-dimensional/K=7
BIC-selected GMM and 99.7% PCA coverage, while the tracked producer uses K=4 on
four PCs and the summary records 82.188% cumulative variance at eight PCs. That
requires a separate source-backed correction.

`SESSION_LOG.md` was not replaced because only paged/truncated reads and
whole-file replacement are available; replacing the append-only provenance file
would risk data loss. The complete record is retained in the immutable archive
and this handoff.
