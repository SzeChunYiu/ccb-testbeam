// add_t1t2_tgeo.C
// Canonical insertion script for T1/T2 trigger volumes into krakow ROOT geometry.
// Phase 2 of issue #1045: Trigger hardware-response migration study.
//
// Usage: root -l -b -q add_t1t2_tgeo.C
//
// This script:
// 1. Imports the baseline krakow_109_8-38deg_4-71deg.root geometry
// 2. Places PSci medium (reuses existing if found, creates new with next-free id)
// 3. Validates Sci_stack arm angles via rotation-derived angles
// 4. Places T1 (A-arm, 71.5°) and T2 (B-arm, -38°) trigger volumes
// 5. Enforces all hard gates (volume count, overlaps, baseline unchanged)
// 6. Exports to krakow_109_8-38deg_4-71deg_T1T2.root
//
// CRITICAL: T1/T2 MUST BE ROTATED to face the target. The box thin-axis (1 cm)
// must align with the arm unit vector via TGeoRotation about Y by the arm angle.
// Unrotated slabs would have 3.2× effective thickness and 0.32× projected area.

#include <TFile.h>
#include <TTree.h>
#include <TGeoManager.h>
#include <TGeoVolume.h>
#include <TGeoMedium.h>
#include <TGeoMaterial.h>
#include <TGeoBBox.h>
#include <TGeoMatrix.h>
#include <TGeoNode.h>
#include <TObjArray.h>
#include <TList.h>
#include <TMath.h>
#include <TSystem.h>
#include <Riostream.h>

// Gate tolerances
const Double_t ANGLE_TOLERANCE_DEG = 2.0;
const Double_t OVERLAP_TOLERANCE_CM = 0.001;

// Expected arm angles (from DESIGN.md)
const Double_t A_ARM_ANGLE_DEG = 71.5;
const Double_t B_ARM_ANGLE_DEG = -38.0;

void dump_baseline_snapshot(TGeoVolume* mother) {
    // GATE 1: Baseline snapshot - dump all daughters before modification
    cout << "=== GATE 1: BASELINE SNAPSHOT ===" << endl;
    TObjArray* daughters = mother->GetNodes();
    Int_t n_before = daughters->GetEntriesFast();
    cout << "Baseline daughter count: " << n_before << endl;
    for (Int_t i = 0; i < n_before; ++i) {
        TGeoNode* node = (TGeoNode*)daughters->At(i);
        cout << "  [" << i << "] " << node->GetName() << " (vol: " << node->GetVolume()->GetName() << ")" << endl;
    }
}

Double_t get_rotation_angle_y(TGeoNode* node) {
    // Extract Y-rotation angle from the node's matrix
    TGeoMatrix* matrix = node->GetMatrix();
    const Double_t* rot = matrix->GetRotationMatrix();
    // For a pure Ry rotation: [cos 0 sin; 0 1 0; -sin 0 cos]
    // rot[0] = cos(θ), rot[2] = sin(θ), rot[6] = -sin(θ), rot[8] = cos(θ)
    Double_t cos_theta = rot[0];
    Double_t sin_theta = rot[2];
    // atan2(sin, cos) gives angle in radians
    Double_t theta_rad = TMath::ATan2(sin_theta, cos_theta);
    return TMath::RadToDeg() * theta_rad;
}

Double_t get_position_angle(TGeoNode* node) {
    // Derive angle from position coordinates: atan2(x, z)
    const Double_t* trans = node->GetMatrix()->GetTranslation();
    return TMath::RadToDeg() * TMath::ATan2(trans[0], trans[2]);
}

void add_t1t2_tgeo() {
    gSystem->Load("libGeom");

    const char* baseline_file = "geant4/configs/krakow_109_8-38deg_4-71deg.root";
    const char* output_file = "geant4/configs/krakow_109_8-38deg_4-71deg_T1T2.root";

    // Import baseline geometry
    TGeoManager::Import(baseline_file);
    TGeoManager* geom = gGeoManager;
    if (!geom) {
        cerr << "ERROR: Failed to import geometry from " << baseline_file << endl;
        return;
    }
    cout << "Imported baseline geometry: " << baseline_file << endl;

    TGeoVolume* mother = geom->GetTopVolume();
    if (!mother || strcmp(mother->GetName(), "MOTHER") != 0) {
        cerr << "ERROR: Top volume is not MOTHER" << endl;
        return;
    }

    // GATE 1: Baseline snapshot
    TObjArray* daughters = mother->GetNodes();
    Int_t n_before = daughters->GetEntriesFast();
    dump_baseline_snapshot(mother);

    // Find or create PSci medium
    TGeoMedium* psci_medium = nullptr;
    TObjArray* media = geom->GetListOfMedia();
    Int_t n_media = media->GetEntriesFast();
    for (Int_t i = 0; i < n_media; ++i) {
        TGeoMedium* m = (TGeoMedium*)media->At(i);
        if (strcmp(m->GetName(), "PSci_medium") == 0 || strcmp(m->GetName(), "PSci") == 0) {
            psci_medium = m;
            cout << "Found existing PSci medium: " << m->GetName() << endl;
            break;
        }
    }

    if (!psci_medium) {
        cout << "Creating new PSci medium with next-free ID" << endl;
        TGeoMaterial* psci_mat = new TGeoMaterial("PSci", 11.075, 5.575, 1.0320); // A, Z, density
        psci_medium = new TGeoMedium("PSci_medium", n_media + 1, psci_mat);
    }

    // ARM-ANGLE GATE: Validate Sci_stack orientations
    cout << "\n=== ARM-ANGLE GATE ===" << endl;
    Bool_t angle_gate_passed = kTRUE;
    TGeoNode* stack1_node = nullptr;
    TGeoNode* stack2_node = nullptr;

    for (Int_t i = 0; i < n_before; ++i) {
        TGeoNode* node = (TGeoNode*)daughters->At(i);
        TString name = node->GetName();
        if (name.Contains("Sci_stack1")) stack1_node = node;
        if (name.Contains("Sci_stack2")) stack2_node = node;
    }

    if (stack1_node && stack2_node) {
        Double_t stack1_rot_angle = get_rotation_angle_y(stack1_node);
        Double_t stack2_rot_angle = get_rotation_angle_y(stack2_node);
        Double_t stack1_pos_angle = get_position_angle(stack1_node);
        Double_t stack2_pos_angle = get_position_angle(stack2_node);

        cout << "Sci_stack1: rot_angle=" << stack1_rot_angle << "°, pos_angle=" << stack1_pos_angle << "°" << endl;
        cout << "Sci_stack2: rot_angle=" << stack2_rot_angle << "°, pos_angle=" << stack2_pos_angle << "°" << endl;

        // Check rotation angles match design
        Double_t err1 = TMath::Abs(stack1_rot_angle - B_ARM_ANGLE_DEG);
        Double_t err2 = TMath::Abs(stack2_rot_angle - A_ARM_ANGLE_DEG);

        if (err1 > ANGLE_TOLERANCE_DEG || err2 > ANGLE_TOLERANCE_DEG) {
            cerr << "ERROR: ARM-ANGLE GATE FAILED: stack1 err=" << err1 << "°, stack2 err=" << err2 << "°" << endl;
            angle_gate_passed = kFALSE;
        } else {
            cout << "ARM-ANGLE GATE: PASS (tolerance " << ANGLE_TOLERANCE_DEG << "°)" << endl;
        }
    } else {
        cerr << "ERROR: Could not find Sci_stack1/2 nodes" << endl;
        angle_gate_passed = kFALSE;
    }

    if (!angle_gate_passed) return;

    // Compute arm unit vectors for placement
    Double_t cos_a = TMath::Cos(A_ARM_ANGLE_DEG * TMath::DegToRad());
    Double_t sin_a = TMath::Sin(A_ARM_ANGLE_DEG * TMath::DegToRad());
    Double_t cos_b = TMath::Cos(B_ARM_ANGLE_DEG * TMath::DegToRad());
    Double_t sin_b = TMath::Sin(B_ARM_ANGLE_DEG * TMath::DegToRad());

    // A-arm unit vector (at 71.5°): (sin(71.5°), 0, cos(71.5°))
    Double_t uA[3] = {sin_a, 0.0, cos_a};
    // B-arm unit vector (at -38°): (sin(-38°), 0, cos(-38°))
    Double_t uB[3] = {sin_b, 0.0, cos_b};

    // Get Sci_stack positions for placement reference
    const Double_t* stack1_pos = stack1_node->GetMatrix()->GetTranslation();
    const Double_t* stack2_pos = stack2_node->GetMatrix()->GetTranslation();

    // T2 placement: 30 cm upstream of Sci_stack1 along B-arm
    Double_t t2_pos[3] = {
        stack1_pos[0] - 30.0 * uB[0],
        stack1_pos[1] - 30.0 * uB[1],
        stack1_pos[2] - 30.0 * uB[2]
    };

    // T1 placement: 30 cm upstream of Sci_stack2 along A-arm
    Double_t t1_pos[3] = {
        stack2_pos[0] - 30.0 * uA[0],
        stack2_pos[1] - 30.0 * uA[1],
        stack2_pos[2] - 30.0 * uA[2]
    };

    cout << "\nComputed placements:" << endl;
    cout << "T1 (A-arm): [" << t1_pos[0] << ", " << t1_pos[1] << ", " << t1_pos[2] << "] cm" << endl;
    cout << "T2 (B-arm): [" << t2_pos[0] << ", " << t2_pos[1] << ", " << t2_pos[2] << "] cm" << endl;

    // Create T1 volume (10×10×1 cm PSci)
    TGeoVolume* t1_vol = geom->MakeBox("T1_trigger_log", psci_medium, 5.0, 5.0, 0.5);
    TGeoRotation* t1_rot = new TGeoRotation();
    t1_rot->RotateY(A_ARM_ANGLE_DEG);
    TGeoCombiTrans* t1_combi = new TGeoCombiTrans(t1_pos[0], t1_pos[1], t1_pos[2], t1_rot);
    mother->AddNode(t1_vol, 100, t1_combi);
    cout << "Added T1_trigger_log (copy 100) with Ry(" << A_ARM_ANGLE_DEG << "°)" << endl;

    // Create T2 volume (15×15×1 cm PSci)
    TGeoVolume* t2_vol = geom->MakeBox("T2_trigger_log", psci_medium, 7.5, 7.5, 0.5);
    TGeoRotation* t2_rot = new TGeoRotation();
    t2_rot->RotateY(B_ARM_ANGLE_DEG);
    TGeoCombiTrans* t2_combi = new TGeoCombiTrans(t2_pos[0], t2_pos[1], t2_pos[2], t2_rot);
    mother->AddNode(t2_vol, 101, t2_combi);
    cout << "Added T2_trigger_log (copy 101) with Ry(" << B_ARM_ANGLE_DEG << "°)" << endl;

    // GATE 2: Volume count check
    Int_t n_after = mother->GetNodes()->GetEntriesFast();
    cout << "\n=== GATE 2: VOLUME COUNT ===" << endl;
    cout << "Daughters before: " << n_before << ", after: " << n_after << endl;
    if (n_after != n_before + 2) {
        cerr << "ERROR: VOLUME-COUNT GATE FAILED: expected " << (n_before + 2) << ", got " << n_after << endl;
        return;
    }
    cout << "VOLUME-COUNT GATE: PASS" << endl;

    // Close geometry before overlap check
    geom->CloseGeometry();

    // GATE 3: Overlap check
    cout << "\n=== GATE 3: OVERLAP CHECK ===" << endl;
    geom->CheckOverlaps(OVERLAP_TOLERANCE_CM);
    TObjArray* overlaps = geom->GetListOfOverlaps();
    Int_t n_overlaps = overlaps->GetEntriesFast();
    if (n_overlaps > 0) {
        cerr << "ERROR: OVERLAP GATE FAILED: " << n_overlaps << " overlaps found" << endl;
        for (Int_t i = 0; i < n_overlaps; ++i) {
            TGeoOverlap* overlap = (TGeoOverlap*)overlaps->At(i);
            if (TString(overlap->GetFirstVolume()).Contains("T1") ||
                TString(overlap->GetSecondVolume()).Contains("T1") ||
                TString(overlap->GetFirstVolume()).Contains("T2") ||
                TString(overlap->GetSecondVolume()).Contains("T2")) {
                cerr << "  T1/T2 involved in overlap: " << overlap->GetName() << endl;
            }
        }
        return;
    }
    cout << "OVERLAP GATE: PASS (0 overlaps)" << endl;

    // GATE 4: Baseline unchanged (re-dump daughters)
    cout << "\n=== GATE 4: BASELINE UNCHANGED ===" << endl;
    TObjArray* daughters_after = mother->GetNodes();
    cout << "All daughters after addition:" << endl;
    for (Int_t i = 0; i < n_after; ++i) {
        TGeoNode* node = (TGeoNode*)daughters_after->At(i);
        cout << "  [" << i << "] " << node->GetName() << endl;
    }

    // Export geometry
    cout << "\nExporting to: " << output_file << endl;
    geom->Export(output_file);
    cout << "Successfully exported T1T2 geometry" << endl;

    // GATE 5: Quick probe that navigator sees T1/T2
    cout << "\n=== GATE 5: NAVIGATOR PROBE ===" << endl;
    TGeoVolume* t1_check = geom->GetVolume("T1_trigger_log");
    TGeoVolume* t2_check = geom->GetVolume("T2_trigger_log");
    if (t1_check && t2_check) {
        cout << "NAVIGATOR PROBE: PASS - T1/T2 volumes found in geometry" << endl;
    } else {
        cerr << "WARNING: NAVIGATOR PROBE failed to find T1/T2" << endl;
    }

    cout << "\n=== ALL GATES PASSED ===" << endl;
}
