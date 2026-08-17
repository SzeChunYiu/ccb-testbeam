# Data lineage and integrity contract

> **GLOBAL REVALIDATION #1594 / RAW FOUNDATION #1603.** Raw data are not stored in git. A path appearing in a report is not, by itself, evidence that the bytes are the authoritative analysis product. Scientific use requires byte identity, waveform-width identity, and lineage identity.

## Current authoritative status

The historical S00 reproduction is registered against an **8-channel × 18-sample HRDv product (144 ADC words/event)**. Its exact expected-count gate (`640737` selected B-stave pulses) is now explicitly scoped in `configs/s00_reproduction.yaml` to `HRDv_8x18_S00_HISTORICAL`; that count must not be transferred to another waveform product.

A separate LUNARC staging copy at

`/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/`

is recorded by `configs/channel_polarity_v2.json` as a **truncated 128-word/event product**. Reading those 128 words as 8×16 channels desynchronizes the original channel-major 8×18 frame. The polarity inference made from that staging product was therefore retracted on 2026-08-16. **The 8×16 staging copy is non-authorizing for detector waveform physics.**

The intended canonical fleet archive remains

`/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam-data/`

and is recorded as **not yet populated**. Populating and verifying that archive is an external action tracked by #1617.

## Historical/local 144-word copies

Repository records mention more than one local working-copy path:

- `/home/billy/Desktop/test_beam/data/` — historical path in this manifest;
- `/home/billy/ccb-data/data/extracted/root/root/` — 144-word extraction cited in the 2026-08-16 polarity-map retraction.

These paths must be treated as **candidate copies of the historical 8×18 product until their bytes are matched to the committed S00 checksum manifest**. Do not choose a path by recency or by whether it reproduces an expected headline.

## Required canonical archive layout

When populated, the fleet archive should preserve immutable archives separately from extracted products:

```text
/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam-data/
├── raw/
│   ├── CCB Data.zip
│   ├── CCB Data/
│   │   ├── sorted-a.zip
│   │   ├── sorted-b.zip
│   │   └── root.zip
│   └── root.zip.tar
└── extracted/
    ├── root/root/          # hrda_run_NNNN.root / hrdb_run_NNNN.root
    ├── sorted-a/
    └── sorted-b/
```

The authoritative bytes must be verified against `reports/S00_data_integrity_pipeline_reproduction/input_sha256.csv`. That file contains archive and per-run hashes; for example, `hrdb_run_0031.root` is registered as SHA-256 `9921aa75c062d0b8994573299a201cbe2725673319fdf1b8cffb711fb9adcea7` with 11,638,901 bytes. The manifest, not a path name, is the byte-identity reference.

## Registered archive hashes

| Historical artifact | SHA-256 | Bytes |
|---|---:|---:|
| `data/raw/CCB Data.zip` | `01365d81479efbfc6fe4f975ee460be1db554ae21891ec7fa594ed8906e009eb` | 6,370,375,114 |
| `data/raw/CCB Data/root.zip` | `19ba847cfbeb46d2944cf8d5c304afb52da6fcad991d1d402a6fd3e9a432efc1` | 809,855,166 |
| `data/raw/CCB Data/sorted-a.zip` | `5504642819482198bc7f2cc4198fc91a4f7bcfdc538304c8759c090cf7578e7c` | 2,684,983,533 |
| `data/raw/CCB Data/sorted-b.zip` | `f77835459bb1d797b8da74e6ac2fc88eab2402dd84b29965dc4f1dadcee1db94` | 2,874,563,960 |
| `data/raw/root.zip.tar` | `5fdfa62223a4219c61d2bf15dd5480bcb144435f80f546f807452b298d019b68` | 543,196,672 |

These hashes establish historical file identity only. They do not, by themselves, prove channel mapping, polarity, trigger semantics, calibration, or detector performance.

## Historical extracted layout

The historical extraction was recorded as approximately 6.1 GB and included:

- 57 A-stack per-run ROOT files;
- 53 B-stack per-run ROOT files;
- sorted A/B products;
- run numbers spanning 0012–0065.

Historical run groups used by S00 are encoded in `configs/s00_reproduction.yaml`. Their exact scientific interpretation is under #1603; trigger/run-quality semantics require hardware/run records rather than prose inheritance.

## S00 waveform contract

The S00 builder now performs a **per-event width validation before stacking/reshaping**, preventing a batch-total coincidence from silently converting 8×16 events into pseudo-8×18 events. The historical exact-count configuration additionally declares:

- `n_channels = 8`;
- `samples_per_channel = 18`;
- `expected_words_per_event = 144`;
- `expected_counts_scope = THIS_EXACT_8X18_PRODUCT_ONLY`;
- `authorising_detector_claims = false` until archive lineage is independently bound.

`python scripts/check_s00_data_product_scope.py` machine-checks this scope in the global audit workflow.

## Polarity status

`configs/channel_polarity_v1.json` previously treated a duplicate-readout analysis convention as authorizing. Under the global audit this is no longer accepted as independent upstream evidence. The v1 map is now `GATED_FROM_DUPLICATE_READOUT_CONVENTION`, and foundational amplitude/timing claims require an independently measured/source-bound polarity status.

The retracted v2 map must **not** be restored merely because its per-run votes were internally consistent: those votes were performed on the truncated/desynchronized 128-word staging product.

## What is safe to do now

- Use the committed checksum manifest to test candidate raw copies byte-for-byte.
- Use the 8×18 product contract to reject width-incompatible data.
- Run diagnostic/sensitivity code that clearly remains non-authorizing.
- Audit code, equations, statistics, and simulation assumptions without pretending missing hardware evidence exists.

## What remains externally blocked

Issue #1617 contains only the evidence/actions that cannot be manufactured from git: populate/verify the canonical archive, confirm hardware channel/polarity/trigger semantics, provide detector/electronics calibration and material survey, provide/approve the p+d scattering reference/model and new MC production, identify an untouched validation sample, and provide beam-rate logs if available.

A mismatch between candidate data and the committed S00 manifest is a **hard stop**, not an invitation to adjust expected counts or waveform interpretation.
