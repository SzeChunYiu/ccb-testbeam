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
  // Event-total over all non-optical tracks in the scintillator (#1007).
  double edep_scint_MeV = 0.0;        // Birks-quenched visible energy (all non-optical)
  double edep_scint_raw_MeV = 0.0;    // unquenched deposit (all non-optical)
  double track_len_scint_mm = 0.0;    // path length sum (all non-optical)
  double primary_edep_scint_MeV = 0.0;
  double primary_edep_scint_raw_MeV = 0.0;
  double primary_track_len_scint_mm = 0.0;
  int primary_track_id = -1;
  int primary_pdg = 0;
  bool   has_entry = false;
  double entry[3] = {0, 0, 0};
  double exit[3]  = {0, 0, 0};

  // Photon generation counters (by creator process).
  long n_scint_generated = 0;         // scintillation photons created
  long n_wls_generated   = 0;         // OpWLS re-emitted photons created
  long n_wls_absorbed    = 0;         // optical photons ended by OpWLS (#1088)
  long n_cerenkov_generated = 0;

  // Per-sensor: photons reaching the end, and detected PE after PDE+coupling.
  // n_detected is an INDEPENDENT_DIAGNOSTIC_DRAW (#1084), not the core ADC latent state.
  std::array<long, kNSensors> n_end_arrival{{0, 0, 0, 0}};
  std::array<long, kNSensors> n_detected{{0, 0, 0, 0}};

  // Legacy analytic occupancy saturation of n_detected (diagnostic only, #1084).
  std::array<double, kNSensors> pe_saturated{{0, 0, 0, 0}};

  // Peak ADC above baseline from the ccb-sipm-core ResponseSimulator
  // (SIPM-P1-002). Canonical production detector-response path.
  std::array<double, kNSensors> adc{{0, 0, 0, 0}};

  // Per-sensor photon arrivals for the ccb-sipm-core ResponseSimulator
  // (SIPM-P1-001). Filled in SteppingAction; consumed in TASK 3.
  std::array<std::vector<ccb::sipm::PhotonArrival>, kNSensors> sipm_arrivals;

  // Optional per-photon detail (calibration mode only; guarded by config).
  std::vector<PhotonHit> photons;

  // GPU optical path: optical-photon secondaries captured from the Geant4
  // Scintillation process, in Opticks sphoton layout (16 floats/photon):
  // q0(pos.xyz,time_ns) q1(mom.xyz,0) q2(pol.xyz,wavelength_nm) q3(0,0,0,0).
  // Positions in mm, time in ns, wavelength in nm (matches the GDML/CSGFoundry).
  std::vector<float> gpu_photons;
  long n_gpu_photons = 0;

  void Reset() {
    edep_scint_MeV = edep_scint_raw_MeV = track_len_scint_mm = 0.0;
    primary_edep_scint_MeV = primary_edep_scint_raw_MeV = primary_track_len_scint_mm = 0.0;
    primary_track_id = -1;
    primary_pdg = 0;
    has_entry = false;
    for (int i = 0; i < 3; ++i) entry[i] = exit[i] = 0.0;
    n_scint_generated = n_wls_generated = n_wls_absorbed = n_cerenkov_generated = 0;
    n_end_arrival.fill(0);
    n_detected.fill(0);
    pe_saturated.fill(0.0);
    adc.fill(0.0);
    for (int i = 0; i < kNSensors; ++i) sipm_arrivals[i].clear();
    photons.clear();
    gpu_photons.clear();
    n_gpu_photons = 0;
  }
};

#endif  // CCB_SIMDATA_HH
