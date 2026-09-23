// Verify T1/T2 export: reload geometry and check T1/T2 with rotations
#include "TGeoManager.h"
#include "TGeoVolume.h"
#include "TGeoNode.h"
#include "TGeoMatrix.h"
#include "TMath.h"
#include "TList.h"
#include "TObjArray.h"
#include <iostream>
#include <cmath>

void verify_t1t2_export_v2() {
    const char* input = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/ccb-wt-1045-phase2/geant4/configs/krakow_109_8-38deg_4-71deg_T1T2.root";

    std::cout << "=== VERIFICATION OF T1T2 EXPORT ===" << std::endl;
    std::cout << "Loading: " << input << std::endl;
    TGeoManager::Import(input);
    std::cout << "Geometry: " << gGeoManager->GetName() << std::endl;

    TGeoVolume* mother = gGeoManager->GetTopVolume();
    int n_daughters = mother->GetNdaughters();
    std::cout << "Top: " << mother->GetName() << " daughters=" << n_daughters << std::endl;

    if (n_daughters != 10) {
        std::cerr << "FAIL: Expected 10 daughters, got " << n_daughters << std::endl;
        std::exit(1);
    }
    std::cout << "PASS: 10 daughters present" << std::endl;

    std::cout << "\n--- ALL DAUGHTERS ---" << std::endl;
    for (int i = 0; i < n_daughters; i++) {
        TGeoNode* node = mother->GetNode(i);
        TGeoVolume* vol = node->GetVolume();
        const double* trans = node->GetMatrix()->GetTranslation();
        const double* rot = node->GetMatrix()->GetRotationMatrix();

        std::cout << i << ": " << node->GetName() << " (vol: " << vol->GetName()
                  << ", copy: " << node->GetNumber() << ")" << std::endl;
        std::cout << "    pos: (" << trans[0] << ", " << trans[1] << ", " << trans[2] << ")" << std::endl;
        std::cout << "    mat: [" << rot[0] << " " << rot[1] << " " << rot[2] << "]"
                  << " [" << rot[3] << " " << rot[4] << " " << rot[5] << "]"
                  << " [" << rot[6] << " " << rot[7] << " " << rot[8] << "]" << std::endl;

        // Compute Y-rotation angle from matrix: cos(theta)=R[0], sin(theta)=-R[6]
        double cos_theta = rot[0];
        double sin_theta = -rot[6];
        double theta = std::atan2(sin_theta, cos_theta) * 180.0 / TMath::Pi();
        std::cout << "    Y-angle: " << theta << " deg" << std::endl;

        // For T1/T2, check material is PSci
        if (std::string(node->GetName()).find("T1_trigger_log") != std::string::npos ||
            std::string(node->GetName()).find("T2_trigger_log") != std::string::npos) {
            TGeoMedium* med = vol->GetMedium();
            if (med) {
                std::cout << "    medium: " << med->GetName()
                          << " (material: " << med->GetMaterial()->GetName() << ")" << std::endl;
            }
        }
        std::cout << std::endl;
    }

    std::cout << "\n=== T1/T2 VERIFICATION COMPLETE ===" << std::endl;
}
