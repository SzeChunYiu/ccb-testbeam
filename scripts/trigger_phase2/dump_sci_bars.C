// Dump Sci_stack/Sci_bar node layout with GLOBAL transforms from baseline geometry
#include "TGeoManager.h"
#include "TGeoNode.h"
#include "TGeoVolume.h"
#include "TGeoBBox.h"
#include "TGeoMatrix.h"
#include <iostream>

void walk(TGeoNode* node, TGeoHMatrix accum, int depth) {
    TGeoHMatrix m = accum;
    m.Multiply(node->GetMatrix());
    TString name = node->GetName();
    TString volname = node->GetVolume()->GetName();
    if (name.Contains("Sci_stack") || name.Contains("Sci_bar") ||
        volname.Contains("Sci_stack") || volname.Contains("Sci_bar") ||
        name.Contains("T1_") || name.Contains("T2_")) {
        const double* tr = m.GetTranslation();
        const double* rot = m.GetRotationMatrix();
        TGeoBBox* box = dynamic_cast<TGeoBBox*>(node->GetVolume()->GetShape());
        std::cout << "NODE|" << depth << "|" << name << "|" << volname << "|"
                  << node->GetNumber() << "|"
                  << tr[0] << "," << tr[1] << "," << tr[2] << "|"
                  << box->GetDX() << "," << box->GetDY() << "," << box->GetDZ() << "|"
                  << rot[0] << "," << rot[1] << "," << rot[2] << ";"
                  << rot[3] << "," << rot[4] << "," << rot[5] << ";"
                  << rot[6] << "," << rot[7] << "," << rot[8] << "|"
                  << node->GetVolume()->GetMedium()->GetName() << std::endl;
    }
    TGeoVolume* vol = node->GetVolume();
    for (int i = 0; i < vol->GetNdaughters(); i++) {
        walk(vol->GetNode(i), m, depth + 1);
    }
}

void dump_sci_bars() {
    const char* input = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/configs/krakow_109_8-38deg_4-71deg.root";
    TGeoManager::Import(input);
    TGeoVolume* top = gGeoManager->GetTopVolume();
    std::cout << "TOP|" << top->GetName() << "|daughters=" << top->GetNdaughters() << std::endl;
    TGeoHMatrix identity;
    for (int i = 0; i < top->GetNdaughters(); i++) {
        TGeoNode* node = top->GetNode(i);
        const double* tr = node->GetMatrix()->GetTranslation();
        std::cout << "DAUGHTER|" << node->GetName() << "|" << tr[0] << "," << tr[1] << "," << tr[2] << std::endl;
        walk(node, identity, 1);
    }
}
