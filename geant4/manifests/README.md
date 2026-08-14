# Regenerated MC Campaign Manifests

This directory contains manifests for regenerated paper MC campaigns that
address the provenance gap identified in #1311.

## cmc_100k_regenerated_20260814

- Campaign ID: cmc_100k_regenerated_20260814
- Events: 100,000
- Sampler: linear_node_pdf_exact_inverse_v1 + measured_table_support_truncate_v1
- Weight: Unit event weight (direct_sampling_unit_weight_v1)
- Output: geant4/data/output_krakow_100k_regenerated.root (not yet generated)

### Provenance

The manifest records:
- Git commit: ecc3a15587ebc016811947f3389e22b430042efd
- Cross-section table: sigma_pd_cm_190.txt (SHA: 0ca33e76...)
- Source: Ermisch et al. PRC 71 064004 (2005) Table VI

### Execution

To generate the MC (requires hibeam_g4 executable):



### Status

- Manifest: COMPLETE
- Macro: COMPLETE
- Job script: COMPLETE (hibeam_g4 build required)
- Output file: GENERATED 2026-08-14 (SLURM 3498666, first successful regeneration; 35,760,505 bytes, sha256 efb40aa09a5fdae1520e9d92b5a8c28f1c6283681f3b2b416fcbaf4a9404ca6c). Full digests in cmc_100k_regenerated_20260814.json (output_receipt / production / executable_receipt).

### Known Limitations

1. Executable build receipt: hibeam_g4 not yet available in conda env
2. Geometry digest: not bound in this manifest
3. Uncertainty propagation: not propagated (issue #1179)

## References

- Issue #1311: MC provenance gap
- Issue #1178: Direct-CDF sampler
- Issue #1179: Source uncertainty
- PR #1333: Forensic investigation
