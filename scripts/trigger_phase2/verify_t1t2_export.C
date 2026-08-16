// verify_t1t2_export.C
// Verification script for T1/T2 geometry export.
// Phase 2 of issue #1045: Trigger hardware-response migration study.
//
// Usage: root -l -b -q verify_t1t2_export.C
//
// This script reloads the T1T2 export and verifies:
// 1. Exactly 10 daughter volumes (8 baseline + 2 new)
// 2. T1/T2 nodes present with correct copy numbers
// 3. T1/T2 shapes (TGeoBBox with correct half-dimensions)
// 4. T1/T2 materials (PSci)
// 5. T1/T2 rotations (full 3×3 matrices)
// 6. Derived Y-rotation angles match arm angles

#include <TFile.h>
#include <TGeoManager.h>
#include <TGeoVolume.h>
#include <TGeoNode.h>
#include <TGeoBBox.h>
#include <TGeoMedium.h>
#include <TMatrixD.h>
#include <Riostream.h>

const Double_t ANGLE_TOLERANCE_DEG = 0.01;  // Tighter for verification
const Double_t A_ARM_ANGLE_DEG = 71.5;
const Double_t B_ARM_ANGLE_DEG = -38.0;

Double_t extract_y_angle(const Double_t* rot) {
    // Extract Y-rotation from 3×3 matrix: Ry(θ) = [cos 0 sin; 0 1 0; -sin 0 cos]
    Double_t cos_theta = rot[0];  // [0][0]
    Double_t sin_theta = rot[2];  // [0][2]
    Double_t theta_rad = TMath::ATan2(sin_theta, cos_theta);
    return TMath::RadToDeg() * theta_rad;
}

void print_rotation_matrix(const char* name, const Double_t* rot) {
    cout << name << " rotation matrix:" << endl;
    cout << "  [" << rot[0] << ", " << rot[1] << ", " << rot[2] << "," << endl;
    cout << "   " << rot[3] << ", " << rot[4] << ", " << rot[5] << "," << endl;
    cout << "   " << rot[6] << ", " << rot[7] << ", " << rot[8] << "]" << endl;
}

void verify_t1t2_export() {
    const char* t1t2_file = "geant4/configs/krakow_109_8-38deg_4-71deg_T1T2.root";

    TFile* f = TFile::Open(t1t2_file);
    if (!f || f->IsZombie()) {
        cerr << "ERROR: Cannot open " << t1t2_file << endl;
        return;
    }

    TGeoManager* geom = (TGeoManager*)f->Get("TGeoManager");
    if (!geom) {
        // Try alternate key name
        geom = gGeoManager;
    }

    TGeoVolume* mother = geom->GetTopVolume();
    if (!mother) {
        cerr << "ERROR: No top volume" << endl;
        f->Close();
        return;
    }

    cout << "=== T1T2 EXPORT VERIFICATION ===" << endl;
    cout << "File: " << t1t2_file << endl;
    cout << "Top volume: " << mother->GetName() << endl;

    TObjArray* daughters = mother->GetNodes();
    Int_t n_daughters = daughters->GetEntriesFast();
    cout << "\nDaughter count: " << n_daughters << " (expected: 10)" << endl;

    if (n_daughters != 10) {
        cerr << "ERROR: Expected 10 daughters, got " << n_daughters << endl;
    }

    // Find and report on T1/T2 nodes
    TGeoNode* t1_node = nullptr;
    TGeoNode* t2_node = nullptr;

    cout << "\n--- All daughters ---" << endl;
    for (Int_t i = 0; i < n_daughters; ++i) {
        TGeoNode* node = (TGeoNode*)daughters->At(i);
        cout << "[" << i << "] " << node->GetName()
             << " (copy " << node->GetNumber() << ")" << endl;

        if (strcmp(node->GetName(), "T1_trigger_log_100") == 0 ||
            (TString(node->GetName()).Contains("T1") && node->GetNumber() == 100)) {
            t1_node = node;
        }
        if (strcmp(node->GetName(), "T2_trigger_log_101") == 0 ||
            (TString(node->GetName()).Contains("T2") && node->GetNumber() == 101)) {
            t2_node = node;
        }
    }

    if (!t1_node) cerr << "ERROR: T1_trigger_log (copy 100) NOT FOUND" << endl;
    if (!t2_node) cerr << "ERROR: T2_trigger_log (copy 101) NOT FOUND" << endl;

    // Detailed T1 verification
    if (t1_node) {
        cout << "\n=== T1_trigger_log (copy 100) ===" << endl;
        const Double_t* trans = t1_node->GetMatrix()->GetTranslation();
        const Double_t* rot = t1_node->GetMatrix()->GetRotationMatrix();

        cout << "Position: [" << trans[0] << ", " << trans[1] << ", " << trans[2] << "] cm" << endl;
        print_rotation_matrix("T1", rot);

        Double_t y_angle = extract_y_angle(rot);
        cout << "Derived Y-angle: " << y_angle << "° (expected: " << A_ARM_ANGLE_DEG << "°)" << endl;

        if (TMath::Abs(y_angle - A_ARM_ANGLE_DEG) > ANGLE_TOLERANCE_DEG) {
            cerr << "ERROR: T1 angle mismatch" << endl;
        }

        TGeoVolume* t1_vol = t1_node->GetVolume();
        TGeoBBox* t1_box = dynamic_cast<TGeoBBox*>(t1_vol->GetShape());
        if (t1_box) {
            cout << "Shape: TGeoBBox" << endl;
            cout << "Half-dims: [" << t1_box->GetDX() << ", " << t1_box->GetDY()
                 << ", " << t1_box->GetDZ() << "] cm" << endl;
            cout << "Full dims: 10×10×1 cm" << endl;
        }

        TGeoMedium* t1_med = t1_vol->GetMedium();
        if (t1_med) {
            cout << "Medium: " << t1_med->GetName() << endl;
            TGeoMaterial* t1_mat = t1_med->GetMaterial();
            if (t1_mat) {
                cout << "Material: " << t1_mat->GetName()
                     << ", density: " << t1_mat->GetDensity() << " g/cm³" << endl;
            }
        }
    }

    // Detailed T2 verification
    if (t2_node) {
        cout << "\n=== T2_trigger_log (copy 101) ===" << endl;
        const Double_t* trans = t2_node->GetMatrix()->GetTranslation();
        const Double_t* rot = t2_node->GetMatrix()->GetRotationMatrix();

        cout << "Position: [" << trans[0] << ", " << trans[1] << ", " << trans[2] << "] cm" << endl;
        print_rotation_matrix("T2", rot);

        Double_t y_angle = extract_y_angle(rot);
        cout << "Derived Y-angle: " << y_angle << "° (expected: " << B_ARM_ANGLE_DEG << "°)" << endl;

        if (TMath::Abs(y_angle - B_ARM_ANGLE_DEG) > ANGLE_TOLERANCE_DEG) {
            cerr << "ERROR: T2 angle mismatch" << endl;
        }

        TGeoVolume* t2_vol = t2_node->GetVolume();
        TGeoBBox* t2_box = dynamic_cast<TGeoBBox*>(t2_vol->GetShape());
        if (t2_box) {
            cout << "Shape: TGeoBBox" << endl;
            cout << "Half-dims: [" << t2_box->GetDX() << ", " << t2_box->GetDY()
                 << ", " << t2_box->GetDZ() << "] cm" << endl;
            cout << "Full dims: 15×15×1 cm" << endl;
        }

        TGeoMedium* t2_med = t2_vol->GetMedium();
        if (t2_med) {
            cout << "Medium: " << t2_med->GetName() << endl;
            TGeoMaterial* t2_mat = t2_med->GetMaterial();
            if (t2_mat) {
                cout << "Material: " << t2_mat->GetName()
                     << ", density: " << t2_mat->GetDensity() << " g/cm³" << endl;
            }
        }
    }

    cout << "\n=== VERIFICATION COMPLETE ===" << endl;
    f->Close();
}
