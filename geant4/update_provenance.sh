#!/bin/bash
# Update provenance manifest with run completion data

OUTPUT_FILE="/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M_authorising.root"
MANIFEST="/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/ccb-wt-1045b/geant4/manifests/cmc_1M_authorising_1045b.json"

if [ ! -f "$OUTPUT_FILE" ]; then
    echo "Output file not found: $OUTPUT_FILE"
    exit 1
fi

# Get output file hash
OUTPUT_HASH=$(sha256sum $OUTPUT_FILE | awk '{print $1}')
FILE_SIZE=$(stat -c%s $OUTPUT_FILE)

# Get current commit from ccb-testbeam
cd /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/ccb-wt-1045b
SUPERPROJECT_COMMIT=$(git rev-parse HEAD)

# Update manifest
cat > $MANIFEST << EOJ
{
  "schema_version": "1.0",
  "campaign_id": "cmc_1M_authorising_1045b",
  "campaign_type": "authorising_corrected_source_mc",
  "issue": "#1045",
  "generation_date": "$(date -I)",
  "completion_date": "$(date -Iseconds)",
  "superproject_commit": "$SUPERPROJECT_COMMIT",
  "output_file": {
    "path": "geant4/data/output_krakow_1M_authorising.root",
    "expected_events": 1000000,
    "sha256": "$OUTPUT_HASH",
    "size_bytes": $FILE_SIZE
  },
  "source_provenance": {
    "hibeam_g4_repo": "https://github.com/HIBEAM-NNBAR/hibeam_g4.git",
    "hibeam_g4_commit": "b73ea2a1bd2419e7c4a25a3bf23a419ad619234c",
    "scatter_patch_cc": "d3ed8b8b2475e5d3783cbd10bff5a778bf873497c2b4ab3d1c0dbdd7c5e5dc00",
    "scatter_patch_hh": "afe240e906ed381d637ddfe92b8450f8ea8b4fc125ad865bb31a5471cc14bb30",
    "patch_script": "geant4/src_patch/patch_scatter.py"
  },
  "build_provenance": {
    "build_dir": "/projects/hep/fs10/shared/nnbar/billy/HIBEAM/Detector_simulation/hibeam_g4_build_1045b",
    "executable_hash": "51acee3549f0857e9a785c28a2c5f2531197ff125783c9d37afbc52f8e186f95",
    "compiler": "/sw/easybuild_milan/software/GCCcore/11.3.0/bin/g++",
    "root_version": "6.32",
    "root_path": "/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env",
    "vgm_version": "5.4.0",
    "geant4_version": "11.2.2",
    "cmake_prefix_path": "/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env"
  },
  "input_digests": {
    "cross_section_table": {
      "path": "geant4/configs/sigma_pd_cm_190.txt",
      "sha256": "0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc",
      "n_points": 28,
      "source": "Ermisch et al. PRC 71 064004 (2005) Table VI, 190 MeV p-d",
      "units": "mb/sr"
    },
    "stopping_power": {
      "path": "geant4/configs/dedx_p_in_CD2.txt"
    },
    "geometry": {
      "path": "geant4/configs/krakow_109_8-38deg_4-71deg.root",
      "source": "hibeam_g4_geobuilder"
    },
    "macro": {
      "path": "geant4/macros/run_krakow_1M.mac"
    },
    "config": {
      "path": "geant4/configs/krakow.config"
    }
  },
  "source_measure": {
    "generator_measure_mode": "MODE_DIRECT_UNIT",
    "adapter_mode_id": "direct_sampling_unit_weight_v1",
    "cross_section_interpolation_mode": "linear_node_pdf_exact_inverse_v1",
    "cross_section_support_mode": "measured_table_support_truncate_v1",
    "target_distribution": "p(theta) = sigma(theta) * sin(theta) / Z over measured support",
    "weight_semantics": "unit event weight (direct sampling from target distribution)",
    "beam_energy_mev": 190.0,
    "target_thickness_mm": 2.3,
    "beamspot_mm": 10.0
  },
  "uncertainty_contract": {
    "propagation_status": "not_propagated_issue_1179",
    "statistical_uncertainty": "encoded in table col 3, not propagated",
    "systematic_uncertainty": "3% point-to-point + <4.5% total, not propagated"
  },
  "geant4_environment": {
    "version": "11.2.2",
    "physics_list": "QGSP_BIC_HP (default for hibeam_g4)"
  },
  "random_seed": "Geant4 default engine",
  "runtime_host": "LUNARC",
  "job_id": "3506900",
  "claim_status": "authorising",
  "references": [
    "#1045: Phase 1B authorising MC",
    "#1178: Direct-CDF sampler contract",
    "#1179: Source uncertainty closure"
  ]
}
EOJ

echo "Manifest updated: $MANIFEST"
echo "Output hash: $OUTPUT_HASH"
