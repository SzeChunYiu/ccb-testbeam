# Paper completion audit addendum — public Hugging Face HRD dataset

**Date:** 2026-08-14

## Correction to the parent audit

The parent completion audit stated that no obvious public CCB/HIBEAM test-beam dataset was discoverable through the available Hugging Face search. That statement is superseded by the exact dataset URL supplied by the project owner:

`https://huggingface.co/datasets/billyyiu747/ccb-testbeam`

The public dataset card identifies the repository as **CCB Testbeam — HRD data**, states that it is an HRD subset of `/projects/hep/fs10/shared/nnbar/ccb_data` from LUNARC, and lists:

- `ccb_data_hrd.zip` — HRD `lmd` + `root` runs (`hrda` / `hrdb`);
- total repository file size approximately 5.89 GB.

The Hugging Face dataset viewer is not available because the repository is packaged as an archive rather than one of the viewer-supported tabular formats. This is not evidence that the data are inaccessible.

The earlier discovery failure was a tooling failure: the Hugging Face connector returned an upstream 502 during the audit, while the exact public dataset URL resolves successfully through the web path. The parent audit must therefore not be read as evidence that no public mirror exists.

## Publication consequence

This dataset should become a first-class external provenance surface for the paper data lane, subject to byte-level verification. It can materially strengthen reproducibility because an independent reviewer need not rely only on the LUNARC filesystem path.

Before treating it as an authorising mirror, verify:

1. download or stream the exact `ccb_data_hrd.zip` bytes and record repository revision/commit, byte size and SHA-256;
2. enumerate archive members and bind every included `hrda`/`hrdb` ROOT/LMD file by path, byte size and SHA-256;
3. compare the mirrored ROOT-file digest set with the 33 raw-input digests expected by the current LUNARC provenance surface;
4. prove that the archive contains the exact paper run population used by the final 8x16 analysis, not merely a related HRD export;
5. rerun the raw schema/event-identity checks directly from the public mirror;
6. regenerate the pre-threshold B2/B4/B6/B8 event product and #1318 longitudinal profile from the mirror, or prove byte-equivalence to the LUNARC inputs before reusing a LUNARC-derived reduced table;
7. add the Hugging Face repository URL, revision and archive SHA-256 to the final data/code-availability statement and machine-readable result manifests.

## Failure conditions

Do not call the Hugging Face copy authorising merely because the archive name and total size look plausible. If any raw-file digest differs from the LUNARC authorising set, treat the two sources as distinct datasets and investigate the difference before physics comparison.

Do not use the absence of the Hugging Face dataset viewer as a data-quality objection; archive contents must be validated from the actual bytes.

## Parent-audit update

For all future work, replace the parent audit's statement "no obvious public CCB/HIBEAM test-beam dataset was discoverable" with:

> A public HRD mirror exists at `billyyiu747/ccb-testbeam` on Hugging Face. Its `ccb_data_hrd.zip` archive should be byte-verified against the LUNARC authorising raw-file set and then used as the external reproducibility source for the final paper data analysis.
