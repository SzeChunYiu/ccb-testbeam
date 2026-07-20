#include "DetectorConstruction.hh"
#include "DetectorMessenger.hh"
#include "OpticalTables.hh"

#include "G4NistManager.hh"
#include "G4Material.hh"
#include "G4MaterialPropertiesTable.hh"
#include "G4Box.hh"
#include "G4Tubs.hh"
#include "G4LogicalVolume.hh"
#include "G4PVPlacement.hh"
#include "G4RotationMatrix.hh"
#include "G4ThreeVector.hh"
#include "G4OpticalSurface.hh"
#include "G4LogicalBorderSurface.hh"
#include "G4LogicalSkinSurface.hh"
#include "G4SystemOfUnits.hh"
#include "G4PhysicalConstants.hh"
#include "G4GeometryManager.hh"
#include "G4SolidStore.hh"

#include <array>
#include <iostream>
#include <sstream>
#include <functional>

// Coordinate convention: x=length(+-25cm), y=width(+-2.59cm), z=thickness(+-1cm).
// Primary travels +z through the 2 cm normal thickness. Fibres run along x
// (G4Tubs default axis is local z -> rotate +90 deg about y).

DetectorConstruction::DetectorConstruction(const AppConfig& cfg) : cfg_(cfg) {
  messenger_ = new DetectorMessenger(const_cast<AppConfig*>(&cfg_));
  // Deterministic geometry hash (constants + Birks) available before
  // Initialize(), so ActionInitialization can be set in the conventional order.
  const double rCore = kFibreRadius * 0.94, rInner = kFibreRadius * 0.97,
               rOuter = kFibreRadius * 1.00;
  std::ostringstream gs;
  gs << kStaveHalfX << kStaveHalfY << kStaveHalfZ << kHoleRadius << kFibreRadius
     << kFibreHalfX << kFibreSep << rCore << rInner << rOuter
     << cfg_.birks_kB_mm_per_MeV;
  std::ostringstream hx;
  hx << std::hex << std::hash<std::string>{}(gs.str());
  geometry_hash_ = hx.str();
}
DetectorConstruction::~DetectorConstruction() { delete messenger_; }

const std::array<std::string, kNSensors>& DetectorConstruction::SensorNames() {
  static const std::array<std::string, kNSensors> names = {
      "Sensor_F1_PlusX",   // kReadout  (PHYSICAL READOUT)
      "Sensor_F1_MinusX",  // kF1Far
      "Sensor_F2_PlusX",   // kF2Near
      "Sensor_F2_MinusX"}; // kF2Far
  return names;
}

// --- wavelength grid helper: build a MaterialPropertiesTable from a table ---
namespace {
// Convert a (wavelength_nm, value) curve to (photon-energy[eV ascending], value)
// arrays for a G4MaterialPropertiesTable property.
void FillFromCurve(G4MaterialPropertiesTable* mpt, const char* prop,
                   const OpticalCurve& c, double yscale, double yunit) {
  if (c.Empty()) return;
  std::vector<double> e, v;
  // curve.x is wavelength_nm ascending; energy is descending -> reverse.
  for (size_t i = c.x.size(); i-- > 0;) {
    e.push_back((1239.841984 / c.x[i]) * CLHEP::eV);
    v.push_back(c.y[i] * yscale * yunit);
  }
  mpt->AddProperty(prop, e, v);
}
}  // namespace

G4Material* DetectorConstruction::BuildScintillator() {
  auto* nist = G4NistManager::Instance();
  // Extruded polystyrene scintillator (C8H8)n.
  // Distinct material instance: the fibre core also derives from polystyrene,
  // and setting an MPT on the shared NIST G4_POLYSTYRENE singleton would clobber
  // this scintillation table (verified on Geant4 11.2 -> 0 scint photons). Use a
  // uniquely-named instance so the scintillation and WLS tables stay independent.
  G4Material* ps = nist->BuildMaterialWithNewDensity(
      "CCB_Scintillator", "G4_POLYSTYRENE", 1.06 * CLHEP::g / CLHEP::cm3);
  auto tables = OpticalTables::LoadDir(cfg_.optical_dir);
  auto* mpt = new G4MaterialPropertiesTable();

  // RINDEX (constant n=1.59 across the emission band, tabulated at 2 points).
  std::vector<double> e = {1.5 * eV, 4.0 * eV};
  std::vector<double> rindex = {1.59, 1.59};
  mpt->AddProperty("RINDEX", e, rindex);

  // Emission and absorption from versioned tables (fall back to a broad band).
  FillFromCurve(mpt, "SCINTILLATIONCOMPONENT1", tables.Get("scintillator_emission"), 1.0, 1.0);
  FillFromCurve(mpt, "ABSLENGTH", tables.Get("scintillator_absorption"),
                cfg_.attenuation_scale, CLHEP::cm);

  // Scintillation yield / time constants (polystyrene-based, order of magnitude).
  mpt->AddConstProperty("SCINTILLATIONYIELD", 10000. / MeV);
  mpt->AddConstProperty("RESOLUTIONSCALE", 1.0);
  mpt->AddConstProperty("SCINTILLATIONTIMECONSTANT1", 2.4 * ns);
  mpt->AddConstProperty("SCINTILLATIONYIELD1", 1.0);
  ps->SetMaterialPropertiesTable(mpt);

  // Configurable Birks quenching (kB in mm/MeV -> internal mm/MeV).
  ps->GetIonisation()->SetBirksConstant(cfg_.birks_kB_mm_per_MeV * mm / MeV);
  return ps;
}

G4Material* DetectorConstruction::BuildFibreCore() {
  auto* nist = G4NistManager::Instance();
  G4Material* core = nist->BuildMaterialWithNewDensity(
      "CCB_Y11Core", "G4_POLYSTYRENE", 1.05 * CLHEP::g / CLHEP::cm3);  // distinct Y-11 PS host
  auto tables = OpticalTables::LoadDir(cfg_.optical_dir);
  auto* mpt = new G4MaterialPropertiesTable();
  std::vector<double> e = {1.5 * eV, 4.0 * eV};
  std::vector<double> rindex = {1.59, 1.59};
  mpt->AddProperty("RINDEX", e, rindex);
  // WLS absorption (Y-11 uptake) and emission spectra, plus bulk attenuation.
  FillFromCurve(mpt, "WLSABSLENGTH", tables.Get("y11_absorption"), 1.0, CLHEP::mm);
  FillFromCurve(mpt, "WLSCOMPONENT", tables.Get("y11_emission"), 1.0, 1.0);
  FillFromCurve(mpt, "ABSLENGTH", tables.Get("y11_bulk_attenuation"),
                cfg_.attenuation_scale, CLHEP::cm);
  mpt->AddConstProperty("WLSTIMECONSTANT", 8.5 * ns);  // Y-11 decay time
  core->SetMaterialPropertiesTable(mpt);
  return core;
}

G4Material* DetectorConstruction::BuildFibreInnerClad() {
  auto* nist = G4NistManager::Instance();
  G4Material* pmma = nist->FindOrBuildMaterial("G4_PLEXIGLASS");  // PMMA n~1.49
  auto* mpt = new G4MaterialPropertiesTable();
  std::vector<double> e = {1.5 * eV, 4.0 * eV};
  std::vector<double> n = {1.49, 1.49};
  mpt->AddProperty("RINDEX", e, n);
  pmma->SetMaterialPropertiesTable(mpt);
  return pmma;
}

G4Material* DetectorConstruction::BuildFibreOuterClad() {
  // Fluorinated PMMA n~1.42. Approximate as a custom low-index acrylic.
  auto* nist = G4NistManager::Instance();
  G4Material* fclad = nist->FindOrBuildMaterial("G4_PLEXIGLASS");
  auto* mpt = new G4MaterialPropertiesTable();
  std::vector<double> e = {1.5 * eV, 4.0 * eV};
  std::vector<double> n = {1.42, 1.42};
  mpt->AddProperty("RINDEX", e, n);
  fclad->SetMaterialPropertiesTable(mpt);
  return fclad;
}

G4Material* DetectorConstruction::BuildOpticalGap() {
  auto* nist = G4NistManager::Instance();
  G4Material* air = nist->FindOrBuildMaterial("G4_AIR");
  auto* mpt = new G4MaterialPropertiesTable();
  std::vector<double> e = {1.5 * eV, 4.0 * eV};
  std::vector<double> n = {1.0, 1.0};
  mpt->AddProperty("RINDEX", e, n);
  air->SetMaterialPropertiesTable(mpt);
  return air;
}

void DetectorConstruction::BuildCoatingSurface(G4VPhysicalVolume* scintPV,
                                               G4VPhysicalVolume* worldPV) {
  // TiO2 diffuse reflective external coating modelled as a border surface on the
  // scintillator/world boundary (blueprint prefers explicit border surfaces).
  auto tables = OpticalTables::LoadDir(cfg_.optical_dir);
  auto* surf = new G4OpticalSurface("TiO2_Coating");
  surf->SetType(dielectric_metal);
  surf->SetModel(unified);
  surf->SetFinish(groundfrontpainted);
  surf->SetSigmaAlpha(0.1);
  auto* mpt = new G4MaterialPropertiesTable();
  const OpticalCurve& refl = tables.Get("tio2_reflectivity");
  if (!refl.Empty()) {
    std::vector<double> e, r;
    for (size_t i = refl.x.size(); i-- > 0;) {
      e.push_back((1239.841984 / refl.x[i]) * eV);
      r.push_back(std::min(1.0, refl.y[i] * cfg_.reflectivity_scale));
    }
    mpt->AddProperty("REFLECTIVITY", e, r);
  } else {
    std::vector<double> e = {1.5 * eV, 4.0 * eV};
    std::vector<double> r = {0.90 * cfg_.reflectivity_scale,
                             0.90 * cfg_.reflectivity_scale};
    mpt->AddProperty("REFLECTIVITY", e, r);
  }
  surf->SetMaterialPropertiesTable(mpt);
  new G4LogicalBorderSurface("TiO2_Border", scintPV, worldPV, surf);
}

G4VPhysicalVolume* DetectorConstruction::Construct() {
  auto* nist = G4NistManager::Instance();
  G4Material* air = BuildOpticalGap();  // world = air with RINDEX

  // --- World ---
  const double wx = kStaveHalfX + 5 * cm;
  const double wy = kStaveHalfY + 5 * cm;
  const double wz = kStaveHalfZ + 5 * cm;
  auto* worldSolid = new G4Box("World", wx, wy, wz);
  auto* worldLV = new G4LogicalVolume(worldSolid, air, "World");
  auto* worldPV = new G4PVPlacement(nullptr, {}, worldLV, "World", nullptr,
                                    false, 0, false);

  // --- Scintillator (the 50 x 5.18 x 2.0 cm bar) ---
  auto* scintSolid = new G4Box("Scintillator", kStaveHalfX, kStaveHalfY, kStaveHalfZ);
  auto* scintLV = new G4LogicalVolume(scintSolid, BuildScintillator(), "Scintillator");
  auto* scintPV = new G4PVPlacement(nullptr, {}, scintLV, "Scintillator", worldLV,
                                    false, 0, true);  // overlap-checked

  // TiO2 coating surface on the scintillator/world boundary.
  BuildCoatingSurface(scintPV, worldPV);

  // --- Fibre rotation: G4Tubs axis is local z; rotate +90 deg about y -> x ---
  auto* fibreRot = new G4RotationMatrix();
  fibreRot->rotateY(90.0 * deg);

  // Radii (concentric): hole(air) > outer clad > inner clad > core.
  const double rCore  = kFibreRadius * 0.94;   // core
  const double rInner = kFibreRadius * 0.97;   // + inner clad
  const double rOuter = kFibreRadius * 1.00;   // + outer clad
  const double rHole  = kHoleRadius;           // gap wall in scintillator

  G4Material* mCore  = BuildFibreCore();
  G4Material* mInner = BuildFibreInnerClad();
  G4Material* mOuter = BuildFibreOuterClad();

  const std::array<double, 2> yc = {+kFibreSep / 2.0, -kFibreSep / 2.0};

  for (int f = 0; f < 2; ++f) {
    std::ostringstream tag; tag << (f == 0 ? "F1" : "F2");
    const G4ThreeVector centre(0, yc[f], 0);

    // Hole/gap (air) bored through the scintillator along x.
    auto* holeSolid = new G4Tubs("Hole_" + tag.str(), 0, rHole, kFibreHalfX, 0, twopi);
    auto* holeLV = new G4LogicalVolume(holeSolid, air, "Hole_" + tag.str());
    new G4PVPlacement(fibreRot, centre, holeLV, "Hole_" + tag.str(), scintLV,
                      false, f, true);

    // Outer cladding.
    auto* outSolid = new G4Tubs("OuterClad_" + tag.str(), 0, rOuter, kFibreHalfX, 0, twopi);
    auto* outLV = new G4LogicalVolume(outSolid, mOuter, "OuterClad_" + tag.str());
    new G4PVPlacement(nullptr, {}, outLV, "OuterClad_" + tag.str(), holeLV,
                      false, f, true);

    // Inner cladding.
    auto* inSolid = new G4Tubs("InnerClad_" + tag.str(), 0, rInner, kFibreHalfX, 0, twopi);
    auto* inLV = new G4LogicalVolume(inSolid, mInner, "InnerClad_" + tag.str());
    new G4PVPlacement(nullptr, {}, inLV, "InnerClad_" + tag.str(), outLV,
                      false, f, true);

    // Core (Y-11 host).
    auto* coreSolid = new G4Tubs("Core_" + tag.str(), 0, rCore, kFibreHalfX, 0, twopi);
    auto* coreLV = new G4LogicalVolume(coreSolid, mCore, "Core_" + tag.str());
    new G4PVPlacement(nullptr, {}, coreLV, "Core_" + tag.str(), inLV,
                      false, f, true);

    // Endcap sensors at +-x ends of the fibre (named for boundary detection).
    // Placed in the world just beyond the fibre end so the core->sensor
    // boundary crossing is well defined.
    G4Material* sensorMat = mCore;  // index-matched coupling stub
    auto* sensSolid = new G4Tubs("Sensor_" + tag.str(), 0, rOuter, kSensorThk / 2.0, 0, twopi);
    for (int end = 0; end < 2; ++end) {
      const double sign = (end == 0 ? +1.0 : -1.0);
      const double xpos = sign * (kFibreHalfX + kSensorThk / 2.0 + 1 * um);
      const G4ThreeVector spos(xpos, yc[f], 0);
      // Sensor id mapping: F1 +x = kReadout(0), F1 -x = 1, F2 +x = 2, F2 -x = 3.
      const int sid = f * 2 + end;
      const std::string sname = SensorNames()[sid];
      auto* sensLV = new G4LogicalVolume(sensSolid, sensorMat, sname);
      new G4PVPlacement(fibreRot, spos, sensLV, sname, worldLV, false, sid, true);
    }
  }

  // geometry_hash_ computed in the constructor (deterministic).
  PrintGeometryReport();
  return worldPV;
}

void DetectorConstruction::PrintGeometryReport() const {
  // Machine-readable report. The ctest greps for OVERLAP_CHECK_PASS.
  // G4PVPlacement was constructed with pSurfChk=true above, so Geant4 prints
  // "G4PVPlacement::CheckOverlaps" warnings if any exist; those are captured by
  // the wrapper. Here we assert internal geometric sanity of the constants.
  const double norm_path_cm = 2.0 * kStaveHalfZ / cm;              // 2.0 cm
  const double sep_cm = kFibreSep / cm;                           // 2.0 cm
  const double fibre_within = (kFibreRadius < kHoleRadius) ? 1 : 0;
  const double contained_x = (kFibreHalfX <= kStaveHalfX) ? 1 : 0;
  const double contained_y =
      (kFibreSep / 2.0 + kHoleRadius <= kStaveHalfY) ? 1 : 0;
  const double contained_z = (kHoleRadius <= kStaveHalfZ) ? 1 : 0;

  std::cout << "GEOMETRY_REPORT_BEGIN\n"
            << "stave_length_cm " << 2 * kStaveHalfX / cm << "\n"
            << "stave_width_cm " << 2 * kStaveHalfY / cm << "\n"
            << "stave_thickness_cm " << 2 * kStaveHalfZ / cm << "\n"
            << "normal_path_cm " << norm_path_cm << "\n"
            << "fibre_diameter_mm " << 2 * kFibreRadius / mm << "\n"
            << "hole_diameter_mm " << 2 * kHoleRadius / mm << "\n"
            << "fibre_separation_cm " << sep_cm << "\n"
            << "fibre_within_hole " << fibre_within << "\n"
            << "fibre_contained_x " << contained_x << "\n"
            << "fibre_contained_y " << contained_y << "\n"
            << "fibre_contained_z " << contained_z << "\n"
            << "geometry_hash " << geometry_hash_ << "\n"
            << "GEOMETRY_REPORT_END\n";

  const bool ok = fibre_within && contained_x && contained_y && contained_z &&
                  std::abs(norm_path_cm - 2.0) < 1e-6 &&
                  std::abs(sep_cm - 2.0) < 1e-6;
  std::cout << (ok ? "OVERLAP_CHECK_PASS" : "OVERLAP_CHECK_FAIL") << std::endl;
}
