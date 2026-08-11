#include "SteppingAction.hh"
#include "G4Exception.hh"
#include "EventAction.hh"
#include "DetectorConstruction.hh"
#include "SimData.hh"
#include "ccb/sipm/Geant4BoundaryCollector.hh"  // SIPM-P1-001

#include "G4Step.hh"
#include "G4Track.hh"
#include "G4OpticalPhoton.hh"
#include "G4StepPoint.hh"
#include "G4VPhysicalVolume.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4LossTableManager.hh"
#include "G4EmSaturation.hh"
#include "G4SystemOfUnits.hh"
#include "G4PhysicalConstants.hh"
#include "Randomize.hh"

#include <cmath>

SteppingAction::SteppingAction(const AppConfig& cfg, const OpticalTables& tables,
                               EventAction* event_action)
    : cfg_(cfg), tables_(tables), event_action_(event_action) {}

int SteppingAction::SensorIndexForVolume(const G4String& name) const {
  const auto& names = DetectorConstruction::SensorNames();
  for (int i = 0; i < kNSensors; ++i)
    if (name == names[i]) return i;
  return -1;
}

double SteppingAction::PdeAt(double wavelength_nm) const {
  const OpticalCurve& pde = tables_.Get("sipm_pde");
  double p = 0.0;
  if (pde.Empty()) {
    // Issue #996: never silently substitute 40% PDE in a strict/authorising run.
    if (cfg_.strict_optical || cfg_.authorising) {
      G4Exception("SteppingAction::PdeAt", "OPT_PDE_001", FatalException,
                  "sipm_pde table empty while strict/authorising optical mode "
                  "is active; refusing 40% fallback");
    }
    p = 0.40;  // explicit non-authorising development fallback only
  } else {
    p = pde.Interp(wavelength_nm);
  }
  p *= cfg_.pde_scale;
  if (p < 0) p = 0;
  if (p > 1) p = 1;
  return p;
}

void SteppingAction::UserSteppingAction(const G4Step* step) {
  G4Track* track = step->GetTrack();
  EventData& d = event_action_->Data();

  const bool is_optical =
      track->GetDefinition() == G4OpticalPhoton::OpticalPhoton();

  if (!is_optical) {
    // Charged / non-optical: accumulate Edep + track length in scintillator.
    G4StepPoint* pre = step->GetPreStepPoint();
    G4VPhysicalVolume* vol = pre->GetPhysicalVolume();
    if (vol && vol->GetName() == "Scintillator") {
      const double edep_raw = step->GetTotalEnergyDeposit();
      d.edep_scint_raw_MeV += edep_raw / MeV;  // true raw (unquenched) deposit
      // Birks is NOT applied to GetTotalEnergyDeposit (it stays raw); Geant4
      // applies Birks to the scintillation yield. Record a dedicated visible
      // estimator via the EM saturation service (same Birks path as
      // G4Scintillation), using the material kB set in BuildScintillator. With
      // kB>0 this is strictly < raw for heavily ionising steps; kB==0 -> raw.
      const G4EmSaturation* em_sat =
          G4LossTableManager::Instance()->EmSaturation();
      const double edep_visible =
          em_sat ? em_sat->VisibleEnergyDepositionAtAStep(step) : edep_raw;
      d.edep_scint_MeV += edep_visible / MeV;  // Birks-visible
      d.track_len_scint_mm += step->GetStepLength() / mm;
      if (!d.has_entry) {
        d.has_entry = true;
        const G4ThreeVector& p = pre->GetPosition();
        d.entry[0] = p.x() / cm; d.entry[1] = p.y() / cm; d.entry[2] = p.z() / cm;
      }
      const G4ThreeVector& q = step->GetPostStepPoint()->GetPosition();
      d.exit[0] = q.x() / cm; d.exit[1] = q.y() / cm; d.exit[2] = q.z() / cm;
    }
    // GPU optical path: capture optical-photon secondaries created this step
    // (the scintillation yield from this Edep, authoritative) into the Opticks
    // sphoton layout. CPU tracking of these is suppressed in StackingAction, so
    // the GPU receives exactly the photons G4 would have transported.
    if (cfg_.gpu_optical) {
      const G4TrackVector* sec = step->GetSecondary();
      if (sec) {
        for (G4Track* t : *sec) {
          if (!t || t->GetDefinition() != G4OpticalPhoton::OpticalPhoton())
            continue;
          const G4ThreeVector& p = t->GetPosition();
          const G4ThreeVector& m = t->GetMomentumDirection();
          const G4ThreeVector& l = t->GetPolarization();
          const double energy = t->GetKineticEnergy();
          const double wl_nm = (energy > 0.0)
              ? ((h_Planck * c_light / energy) / nm) : 0.0;
          const double t_ns = t->GetGlobalTime() / ns;
          d.gpu_photons.push_back(static_cast<float>(p.x() / mm));
          d.gpu_photons.push_back(static_cast<float>(p.y() / mm));
          d.gpu_photons.push_back(static_cast<float>(p.z() / mm));
          d.gpu_photons.push_back(static_cast<float>(t_ns));
          d.gpu_photons.push_back(static_cast<float>(m.x()));
          d.gpu_photons.push_back(static_cast<float>(m.y()));
          d.gpu_photons.push_back(static_cast<float>(m.z()));
          d.gpu_photons.push_back(0.0f);
          d.gpu_photons.push_back(static_cast<float>(l.x()));
          d.gpu_photons.push_back(static_cast<float>(l.y()));
          d.gpu_photons.push_back(static_cast<float>(l.z()));
          d.gpu_photons.push_back(static_cast<float>(wl_nm));
          d.gpu_photons.push_back(0.0f);  // q3.x orient/boundary/flag
          d.gpu_photons.push_back(0.0f);  // q3.y identity
          d.gpu_photons.push_back(0.0f);  // q3.z index
          d.gpu_photons.push_back(0.0f);  // q3.w flagmask (input photon)
          ++d.n_gpu_photons;
        }
      }
    }
    return;
  }

  // Optical photon: detect a crossing INTO a named sensor volume.
  G4StepPoint* post = step->GetPostStepPoint();
  if (post->GetStepStatus() != fGeomBoundary) return;
  G4VPhysicalVolume* postVol = post->GetPhysicalVolume();
  if (!postVol) return;
  const int sid = SensorIndexForVolume(postVol->GetName());
  if (sid < 0) return;

  // Raw arrival recorded FIRST (before PDE), per the blueprint.
  const double energy = track->GetKineticEnergy();
  const double wavelength_nm =
      (energy > 0) ? (h_Planck * c_light / energy) / nm : 0.0;
  const double time_ns = post->GetGlobalTime() / ns;
  const double path_mm = track->GetTrackLength() / mm;

  ++d.n_end_arrival[sid];

  // Collect per-sensor SiPM boundary arrival for core consumption
  // (SIPM-P1-001). Local position, time, and wavelength extracted via the
  // submodule adapter so the ResponseSimulator gets exactly what it expects.
  auto boundary = ccb::sipm::Geant4BoundaryCollector::FromStep(
      *step, sid, postVol);
  if (boundary) {
    d.sipm_arrivals[sid].push_back(*boundary);
  }

  // Detection: PDE(wavelength) * post-transport collection efficiency.
  const double p_det = PdeAt(wavelength_nm) * cfg_.collection_efficiency;
  const bool detected = (G4UniformRand() < p_det);
  if (detected) ++d.n_detected[sid];

  if (cfg_.mode == SimMode::kOpticalCalibration) {
    PhotonHit h;
    h.sensor = sid; h.wavelength_nm = wavelength_nm; h.time_ns = time_ns;
    h.path_len_mm = path_mm; h.detected = detected;
    d.photons.push_back(h);
  }

  // Kill at the (absorbing) sensor to prevent double counting.
  track->SetTrackStatus(fStopAndKill);
}
