// Verify T1/T2 in exported geometry
#include "TGeoManager.h"
#include "TGeoVolume.h"
#include "TGeoNode.h"
#include <iostream>

void verify_t1t2_export() {
    const char* geom = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/ccb-wt-1045-phase2/geant4/configs/krakow_109_8-38deg_4-71deg_T1T2.root";
    
    std::cout << "Loading: " << geom << std::endl;
    TGeoManager::Import(geom);
    std::cout << "Geometry: " << gGeoManager->GetName() << std::endl;
    
    TGeoVolume* mother = gGeoManager->GetTopVolume();
    std::cout << "Top: " << mother->GetName() << " daughters=" << mother->GetNdaughters() << std::endl;
    
    std::cout << "\n=== All daughters ===" << std::endl;
    for (int i = 0; i < mother->GetNdaughters(); i++) {
        TGeoNode* node = mother->GetNode(i);
        TGeoVolume* vol = node->GetVolume();
        const double* trans = node->GetMatrix()->GetTranslation();
        std::cout << i << ": " << node->GetName() 
                  << " (vol: " << vol->GetName() << ", mat: " << vol->GetMaterial()->GetName()
                  << ") pos=(" << trans[0] << ", " << trans[1] << ", " << trans[2] << ")" << std::endl;
    }
    
    std::cout << "\n=== Searching for T1/T2 ===" << std::endl;
    bool t1_found = false, t2_found = false;
    for (int i = 0; i < mother->GetNdaughters(); i++) {
        TGeoNode* node = mother->GetNode(i);
        TString vname = node->GetVolume()->GetName();
        if (vname.Contains("T1")) {
            t1_found = true;
            const double* trans = node->GetMatrix()->GetTranslation();
            std::cout << "T1 found: " << node->GetName() << " at (" 
                      << trans[0] << ", " << trans[1] << ", " << trans[2] << ") cm" << std::endl;
        }
        if (vname.Contains("T2")) {
            t2_found = true;
            const double* trans = node->GetMatrix()->GetTranslation();
            std::cout << "T2 found: " << node->GetName() << " at (" 
                      << trans[0] << ", " << trans[1] << ", " << trans[2] << ") cm" << std::endl;
        }
    }
    
    std::cout << "\nT1 verified: " << (t1_found ? "YES" : "NO") << std::endl;
    std::cout << "T2 verified: " << (t2_found ? "YES" : "NO") << std::endl;
    
    if (t1_found && t2_found) {
        std::cout << "\n=== VERIFICATION COMPLETE ===" << std::endl;
    } else {
        std::cout << "\n=== ERROR: T1/T2 missing ===" << std::endl;
    }
}
