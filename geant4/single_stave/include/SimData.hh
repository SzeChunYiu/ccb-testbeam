// SimData.hh — per-event accumulators shared between the user actions.
// Owned by EventAction; TrackingAction and SteppingAction fill it.
#ifndef CCB_SIMDATA_HH
#define CCB_SIMDATA_HH

#include "DetectorConstruction.hh"  // kNSensors, SensorId
#include "ccb/sipm/Types.hh"  // PhotonArrival (SIPM-P1-001)
#include <array>
#include <vector>

// One detected/arriving photon at a fibre end (kept in calibration mode).
struct PhotonHit {
  int sensor = -1;       // SensorId
  double wavelength_nm = 0.0;
  double time_ns = 0.0;
  double path_len_mm = 0.0;
  bool detected = false; // passed PDE * coupling
};

struct EventData {
  // Charged / non-optical energy accounting in the scintillator.
  double edep_scint_MeV = 0.0;        // Birks-quenched visible energy
  double edep_scint_raw_MeV = 0.0;    // unquenched deposit
  double track_len_scint_mm = 0.0;    // primary path length inside scintillator
  bool   has_entry = false;
  double entry[3] = {0, 0, 0};
  double exit[3]  = {0, 0, 0};

  // Photon generation counters (by creator process).
  long n_scint_generated = 0;         // scintillation photons created
  long n_wls_generated   = 0;         // OpWLS re-emitted photons created
  long n_cerenkov_generated = 0;

  // Per-sensor: photons reaching the end, and detected PE after PDE+coupling.
  std::array<long, kNSensors> n_end_arrival{{0, 0, 0, 0}};
  std::array<long, kNSensors> n_detected{{0, 0, 0, 0}};

  // SiPM saturation-corrected detected PE per sensor (occupancy model).
  std::array<double, kNSensors> pe_saturated{{0, 0, 0, 0}};

  // Per-sensor photon arrivals for the ccb-sipm-core ResponseSimulator
  // (SIPM-P1-001). Filled in SteppingAction; consumed in TASK 3.
  std::array<std::vector<ccb::sipm::PhotonArrival>, kNSensors> sipm_arrivals;

  // Optional per-photon detail (calibration mode only; guarded by config).
  std::vector<PhotonHit> photons;

  void Reset() {
    edep_scint_MeV = edep_scint_raw_MeV = track_len_scint_mm = 0.0;
    has_entry = false;
    for (int i = 0; i < 3; ++i) entry[i] = exit[i] = 0.0;
    n_scint_generated = n_wls_generated = n_cerenkov_generated = 0;
    n_end_arrival.fill(0);
    n_detected.fill(0);
    pe_saturated.fill(0.0);
    for (int i = 0; i < kNSensors; ++i) sipm_arrivals[i].clear();
    photons.clear();
  }
};

#endif  // CCB_SIMDATA_HH
