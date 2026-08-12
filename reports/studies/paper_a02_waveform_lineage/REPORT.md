# PAPER-A02 / issue #993 — HRD waveform product lineage

**Verdict:** `DISTINCT_SCHEMAS`
**Authorising schema for paper amplitude/timing on LUNARC raw:** `hrd_raw_8x16_v1`

## Immutable raw manifest

- Paper runs: `[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65]`
- Digest records: `33`; missing runs: `[]`
- Complete manifest: `True`

## Width census (LUNARC ccb_data)

Every scanned event on every located paper run contains exactly `8 × 16 = 128` HRDv words.
The historical `8 × 18 = 144` contract fails on every event without exception.

## Event / channel / sample closure

- Records spot-checked from canonical S00 table: `500`
- Baseline/amplitude/peak mismatches: `45`
- Disputed samples 16–17: **absent** in LUNARC raw rows (indices 0–15 only).

## Transform hypotheses

- `padding_or_truncation_to_18`: accepted=False — all scanned events are 128 words on every paper run
- `batch_reshape_9x128_to_8x144`: accepted=False — 144-word contract fails on every event; 128-word contract passes
- `identical_byte_stream_as_laptop_root`: accepted=False — {'lunarc_run31_sha256': '0986c8263d7445eda3633578fc606902d487a6c8ffb4b4ccd68336e6d140c268', 'laptop_run31_sha256': '9921aa75c062d0b8994573299a201cbe2725673319fdf1b8cffb711fb9adcea7', 'equal': False}
- `reversible_16_to_18_without_external_producer`: accepted=False — samples 16–17 absent; sorted-b 18-sample producer not on data host
- `distinct_acquisition_or_storage_products`: accepted=True — different immutable SHA-256 for run 31; LUNARC exclusively 128-word events; historical configs/manifests declare 144-word reshape on different mounts

## Publication consequence

- Historical 18-sample timing configurations and sub-ns ledger values remain **non-authorising** for the located 8×16 LUNARC product.
- Cross-schema timing transfer is **quarantined** until a byte-level producer is demonstrated on immutable inputs.
- The ~38 ns B4–B6 residual stays **format-limited / NOT DETECTOR RESOLUTION** only.
