// Add T1/T2 trigger volumes to krakow ROOT geometry
#include "TGeoManager.h"
#include "TGeoVolume.h"
#include "TGeoNode.h"
#include "TGeoMedium.h"
#include "TGeoMaterial.h"
#include "TGeoBBox.h"
#include "TGeoMatrix.h"
#include "TMath.h"
#include "TObjArray.h"
#include <iostream>
#include <tuple>

void add_t1t2_tgeo() {
    const char* input = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/configs/krakow_109_8-38deg_4-71deg.root";
    const char* output = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/ccb-wt-1045-phase2/geant4/configs/krakow_109_8-38deg_4-71deg_T1T2.root";
    
    std::cout << "Loading: " << input << std::endl;
    TGeoManager::Import(input);
    std::cout << "Geometry: " << gGeoManager->GetName() << std::endl;
    
    TGeoVolume* mother = gGeoManager->GetTopVolume();
    std::cout << "Top: " << mother->GetName() << " daughters=" << mother->GetNdaughters() << std::endl;
    
    // Get PSci medium from existing list
    TGeoMedium* psci_medium = nullptr;
    TList* media = gGeoManager->GetListOfMedia();
    TIter next(media);
    TObject* obj;
    while ((obj = next())) {
        TGeoMedium* med = (TGeoMedium*)obj;
        if (strcmp(med->GetMaterial()->GetName(), "PSci") == 0) {
            psci_medium = med;
            std::cout << "PSci medium: " << med->GetName() << std::endl;
            break;
        }
    }
    
    if (!psci_medium) {
        TGeoMaterial* psci_mat = gGeoManager->GetMaterial("PSci");
        if (!psci_mat) {
            std::cout << "ERROR: PSci material not found!" << std::endl;
            return;
        }
        psci_medium = new TGeoMedium("PSci_medium", 1, psci_mat);
    }
    
    // Find Sci_stack positions
    double sci_stack1_pos[3] = {0};
    double sci_stack2_pos[3] = {0};
    
    TObjArray* nodes = gGeoManager->GetListOfNodes();
    for (int i = 0; i < nodes->GetEntries(); i++) {
        TGeoNode* node = (TGeoNode*)nodes->At(i);
        TString name = node->GetName();
        if (name.Contains("Sci_stack1")) {
            const double* trans = node->GetMatrix()->GetTranslation();
            sci_stack1_pos[0] = trans[0];
            sci_stack1_pos[1] = trans[1];
            sci_stack1_pos[2] = trans[2];
            std::cout << "Sci_stack1: (" << trans[0] << ", " << trans[1] << ", " << trans[2] << ")" << std::endl;
        } else if (name.Contains("Sci_stack2")) {
            const double* trans = node->GetMatrix()->GetTranslation();
            sci_stack2_pos[0] = trans[0];
            sci_stack2_pos[1] = trans[1];
            sci_stack2_pos[2] = trans[2];
            std::cout << "Sci_stack2: (" << trans[0] << ", " << trans[1] << ", " << trans[2] << ")" << std::endl;
        }
    }
    
    // Calculate unit vectors (rotation around Y axis)
    auto unit_vector_yrot = [](double angle_deg) -> std::tuple<double,double,double> {
        double rad = angle_deg * TMath::Pi() / 180.0;
        return std::make_tuple(std::sin(rad), 0.0, std::cos(rad));
    };
    
    double t1_angle = 71.5;
    auto [t1_ux, t1_uy, t1_uz] = unit_vector_yrot(t1_angle);
    double t1_pos[3] = {
        sci_stack2_pos[0] - 30.0 * t1_ux,
        sci_stack2_pos[1] - 30.0 * t1_uy,
        sci_stack2_pos[2] - 30.0 * t1_uz
    };
    std::cout << "T1 pos: (" << t1_pos[0] << ", " << t1_pos[1] << ", " << t1_pos[2] << ")" << std::endl;
    
    double t2_angle = -38.0;
    auto [t2_ux, t2_uy, t2_uz] = unit_vector_yrot(t2_angle);
    double t2_pos[3] = {
        sci_stack1_pos[0] - 30.0 * t2_ux,
        sci_stack1_pos[1] - 30.0 * t2_uy,
        sci_stack1_pos[2] - 30.0 * t2_uz
    };
    std::cout << "T2 pos: (" << t2_pos[0] << ", " << t2_pos[1] << ", " << t2_pos[2] << ")" << std::endl;
    
    // Create volumes
    TGeoBBox* t1_box = new TGeoBBox(5.0, 5.0, 0.5);  // 10x10x1 cm
    TGeoVolume* t1_vol = new TGeoVolume("T1_trigger_log", t1_box, psci_medium);
    std::cout << "T1: 10x10x1 cm PSci" << std::endl;
    
    TGeoBBox* t2_box = new TGeoBBox(7.5, 7.5, 0.5);  // 15x15x1 cm
    TGeoVolume* t2_vol = new TGeoVolume("T2_trigger_log", t2_box, psci_medium);
    std::cout << "T2: 15x15x1 cm PSci" << std::endl;
    
    // Create translations and add nodes
    TGeoTranslation* t1_trans = new TGeoTranslation(t1_pos[0], t1_pos[1], t1_pos[2]);
    TGeoTranslation* t2_trans = new TGeoTranslation(t2_pos[0], t2_pos[1], t2_pos[2]);
    
    std::cout << "Adding T1/T2 to MOTHER..." << std::endl;
    mother->AddNode(t1_vol, 100, t1_trans);
    mother->AddNode(t2_vol, 101, t2_trans);
    std::cout << "Daughters after: " << mother->GetNdaughters() << std::endl;
    
    // Export
    std::cout << "Exporting to: " << output << std::endl;
    gGeoManager->Export(output);
    std::cout << "=== SUCCESS ===" << std::endl;
}
