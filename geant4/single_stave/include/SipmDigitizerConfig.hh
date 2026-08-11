#ifndef CCB_SIPM_DIGITIZER_CONFIG_HH
#define CCB_SIPM_DIGITIZER_CONFIG_HH

#include "AppConfig.hh"
#include "OpticalTables.hh"
#include "ccb/sipm/Config.hh"

// Shared Geant4 ↔ ccb-sipm-core configuration builder (#974/#976/#977/#981/#1072).
// Used by EventAction (event loop) and RunAction (master metadata sidecar).
ccb::sipm::ModelConfig BuildSipmDigitizerConfig(const AppConfig& cfg,
                                                const OpticalTables& tables);

#endif  // CCB_SIPM_DIGITIZER_CONFIG_HH
