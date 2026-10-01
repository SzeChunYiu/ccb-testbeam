# Detector Construction Patch for Phase 2

To register the T1/T2 trigger sensitive detectors, modify `WasaDetectorConstruction.cc`:

## 1. Add include at top of file (around line 50):
```cpp
#include "TriggerSensitiveDetector.hh"
```

## 2. Add to `ConstructSDandField()` method (around line 150):

```cpp
void WasaDetectorConstruction::ConstructSDandField()
{
    // Existing TPC sensitive detector registration
    // ...
    
    // === Register T1/T2 trigger sensitive detectors ===
    G4SDManager* sdManager = G4SDManager::GetSDMpointer();
    
    // Find T1 and T2 logical volumes
    G4LogicalVolume* T1_log = nullptr;
    G4LogicalVolume* T2_log = nullptr;
    
    // Search through logical volume store
    G4LogicalVolumeStore* lvStore = G4LogicalVolumeStore::GetInstance();
    for (auto lv : *lvStore) {
        if (lv->GetName() == "T1_trigger_log") {
            T1_log = lv;
        } else if (lv->GetName() == "T2_trigger_log") {
            T2_log = lv;
        }
    }
    
    // Create and register sensitive detectors
    if (T1_log) {
        TriggerSensitiveDetector* T1_sd = new TriggerSensitiveDetector("T1_trigger_SD");
        sdManager->AddNewDetector(T1_sd);
        T1_log->SetSensitiveDetector(T1_sd);
        std::cout << "!> Registered T1 trigger sensitive detector" << std::endl;
    } else {
        std::cout << "!> WARNING: T1_trigger_log not found" << std::endl;
    }
    
    if (T2_log) {
        TriggerSensitiveDetector* T2_sd = new TriggerSensitiveDetector("T2_trigger_SD");
        sdManager->AddNewDetector(T2_sd);
        T2_log->SetSensitiveDetector(T2_sd);
        std::cout << "!> Registered T2 trigger sensitive detector" << std::endl;
    } else {
        std::cout << "!> WARNING: T2_trigger_log not found" << std::endl;
    }
}
```

## 3. Recompile:
```bash
cd /projects/hep/fs10/shared/nnbar/billy/HIBEAM/Detector_simulation/hibeam_g4_build
mkdir -p build && cd build
cmake ..
make -j4
```
