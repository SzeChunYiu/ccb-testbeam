# Chapter 9 MV6 source-consistency audit

## Scope

This validation unit compares the academic anomaly chapter with the tracked MV6
producer, summary, historical report, and canonical `CL-022` claim. It does not
rerun the ROOT input or establish transfer to beam data.

Policy: `CHAPTER9_MUST_MATCH_TRACKED_MV6_PRODUCER_AND_SUMMARY`.

## Confirmed defects in the pre-change chapter

The pre-change Chapter 9 described an eight-dimensional, `K = 7`, BIC-selected
GMM with 99.7% cumulative variance at eight PCs, a 127-iteration convergence
result, named physical meanings for every PC, alternative-method benchmarks,
manual-review studies, production-rate calculations, SRIM/Birks tables, optical
response calculations, and veto-performance numbers.

The tracked producer instead:

- fits PCA to peak-normalised 18-sample waveforms;
- records cumulative explained variance 0.745517570480533 at four PCs and
  0.821883926913117 at eight PCs;
- fits exactly one `GaussianMixture` with four components on the first four PCs;
- does not execute a BIC scan;
- records no version-controlled eigenvector interpretation, manual-review study,
  alternative-detector benchmark, SRIM/Birks closure, or beam-data veto study.

The pre-change chapter therefore mixed repository facts, unsupported
reconstructions, and hypotheses as if they were one validated analysis.

## Source-backed numerical reconstruction

| Quantity | Counts | Estimate | Wilson 95% interval |
|---|---:|---:|---:|
| Early-peak rate among retained MC tracks | 283 / 87,555 | 0.003232254011764034 | [0.002877452112691542, 0.003630645177388446] |
| Carbon-12 share of early-peak class | 156 / 283 | 0.5512367491166078 | [0.4929885941153212, 0.6081125511627331] |
| Early-peak rate within carbon-12 | 156 / 7,302 | 0.021364009860312245 | [0.018290520583369645, 0.024940838952822255] |

These are distinct binomial estimands. The historical producer's `binom_ci`
returns a normal-approximate half-width, not Wilson bounds. This audit uses exact
source counts and an independent Wilson calculation.

## Corrective method

The chapter was replaced with a compact source-backed account that:

- documents the exact event selection, waveform constants, and taxonomy;
- states the actual PCA and GMM implementation;
- separates cluster composition from selected-class composition;
- reports independently reconstructed confidence intervals;
- quarantines unsupported BIC, PC-interpretation, manual-review, physical-rate,
  detector-response, and veto-performance claims;
- specifies the matched data/MC closure required under `AUD-ANOM-001`.

## Validation commands

```text
python -m py_compile \
  tools/audit/validate_chapter9_mv6_claims.py \
  tests/test_validate_chapter9_mv6_claims.py

python -m pytest tests/test_validate_chapter9_mv6_claims.py -q

6 passed in 1.15s
```

The executable regression uses controlled source-contract fixtures and covers a
valid chapter, the former K=7/BIC claim, the former 99.7% claim, a changed PCA
summary, a missing producer contract, and invalid UTF-8. The exact repository
source facts were independently inspected through authenticated GitHub reads.

## Provenance

- pre-change chapter blob: `409abcdefe686edf9c2ac5c5c6ba02aae9c9a331`;
- tracked producer blob: `f965823518b22908f3e8974f280bff5c970368d0`;
- tracked summary blob: `26c187cbe05d8dadbe588c6ed9062d25658a80a9`;
- historical report blob: `2c531703755b28a0c576e978531b81374edf8ab4`;
- canonical ledger blob: `e489555f3a520c7cc64b8a7d858a0e93622b9de6`;
- corrected chapter SHA-256 before commit:
  `d91effd7b4a6a210591832a8c57443da12e55c46897884c0adba007491183d23`;
- validator SHA-256 before commit:
  `f5f42a8a28a331958bd787e40ddfb26315c30861b5cb10544af352d4287246f5`;
- test SHA-256 before commit:
  `645014b7df8a92da2d98e288a7e4e907c51f5f4f0455ca9317e524aad69dd4c1`.

## Scientific boundary

This correction validates documentation and software-to-result traceability. It
does not identify the beam-data anomaly as carbon-12, quantify empirical
performance, validate a veto, or remove simulation-model uncertainty.
