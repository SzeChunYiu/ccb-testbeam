#include "TGeoManager.h"
#include "TGeoNode.h"
#include "TGeoVolume.h"
#include "TGeoBBox.h"
#include "TGeoMatrix.h"
#include <iostream>

void walk(TGeoNode* node, TGeoHMatrix accum, int depth) {
    TGeoHMatrix m = accum;
    m.Multiply(node->GetMatrix());
    const double* tr = m.GetTranslation();
    const double* rot = m.GetRotationMatrix();
    TGeoBBox* box = dynamic_cast<TGeoBBox*>(node->GetVolume()->GetShape());
    std::cout << "NODE|" << depth << "|" << node->GetName() << "|" << node->GetVolume()->GetName()
              << "|" << node->GetNumber() << "|"
              << tr[0] << "," << tr[1] << "," << tr[2] << "|"
              << (box ? box->GetDX() : -1) << "," << (box ? box->GetDY() : -1) << "," << (box ? box->GetDZ() : -1) << "|"
              << rot[0] << "," << rot[1] << "," << rot[2] << ";"
              << rot[3] << "," << rot[4] << "," << rot[5] << ";"
              << rot[6] << "," << rot[7] << "," << rot[8] << "|"
              << node->GetVolume()->GetMedium()->GetMaterial()->GetName() << std::endl;
    TGeoVolume* vol = node->GetVolume();
    for (int i = 0; i < vol->GetNdaughters(); i++) walk(vol->GetNode(i), m, depth + 1);
}

void dump_trig_stacks() {
    const char* input = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/configs/krakow_109_8-38deg_4-71deg.root";
    TGeoManager::Import(input);
    TGeoVolume* top = gGeoManager->GetTopVolume();
    TGeoHMatrix identity;
    for (int i = 0; i < top->GetNdaughters(); i++) {
        TGeoNode* node = top->GetNode(i);
        TString name = node->GetName();
        if (name.Contains("Trig_stack")) {
            walk(node, identity, 1);
        }
    }
}
