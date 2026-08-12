#include "DetectorConstruction.hh"
#include "DetectorMessenger.hh"
#include "OpticalTables.hh"
#include "G4Exception.hh"

#include "G4NistManager.hh"
#include "G4Material.hh"
#include "G4MaterialPropertiesTable.hh"
#include "G4Box.hh"
#include "G4Tubs.hh"
#include "G4VSolid.hh"
#include "G4SubtractionSolid.hh"
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
#include <cstdlib>
#include "G4SolidStore.hh"

#include <array>
#include <iostream>
#include <sstream>
#include "CanonicalFormat.hh"
#include "Sha256.hh"  // SHA-256 geometry digest (defect #7)

// Coordinate convention: x=length(+-25cm), y=width(+-2.59cm), z=thickness(+-1cm).
// Primary travels +z through the 2 cm normal thickness. Fibres run along x
// (G4Tubs default axis is local z -> rotate +90 deg about y).

DetectorConstruction::DetectorConstruction(const AppConfig& cfg) : cfg_(cfg) {
  messenger_ = new DetectorMessenger(const_cast<AppConfig*>(&cfg_));
  // GEOMETRY_DIGEST_V2 (#986): named fields, .17g floats, no Birks/material ids.
  const double rCore = kFibreRadius * 0.94, rInner = kFibreRadius * 0.97,
               rOuter = kFibreRadius * 1.00;
  const auto mm = [](double q) { return q / CLHEP::mm; };
  std::ostringstream gs;
  gs << "schema_version=2.0.0"
     << ";stave_half_x_mm=" << CanonFloat(mm(kStaveHalfX))
     << ";stave_half_y_mm=" << CanonFloat(mm(kStaveHalfY))
     << ";stave_half_z_mm=" << CanonFloat(mm(kStaveHalfZ))
     << ";coating_thk_mm=" << CanonFloat(mm(kCoatingThk))
     << ";hole_radius_mm=" << CanonFloat(mm(kHoleRadius))
     << ";fibre_radius_mm=" << CanonFloat(mm(kFibreRadius))
     << ";fibre_half_x_mm=" << CanonFloat(mm(kFibreHalfX))
     << ";fibre_sep_mm=" << CanonFloat(mm(kFibreSep))
     << ";sensor_thk_mm=" << CanonFloat(mm(kSensorThk))
     << ";fibre_core_radius_mm=" << CanonFloat(mm(rCore))
     << ";fibre_inner_clad_radius_mm=" << CanonFloat(mm(rInner))
     << ";fibre_outer_clad_radius_mm=" << CanonFloat(mm(rOuter))
     << ";far_end_mode=" << cfg_.far_end_mode;
  geometry_hash_ = Sha256::hex(gs.str());

  std::ostringstream ps;
  ps << "schema=physics_v1"
     << ";birks_kB_mm_per_MeV=" << CanonFloat(cfg_.birks_kB_mm_per_MeV)
     << ";optical_interface_model=" << cfg_.optical_interface_model
     << ";scintillator_material=" << cfg_.scintillator_material
     << ";coating_material=" << cfg_.coating_material;
  physics_hash_ = Sha256::hex(ps.str());

  std::ostringstream os;
  os << "schema=optical_v1"
     << ";optical_interface_model=" << cfg_.optical_interface_model
     << ";wls_mean_number_photons=" << CanonFloat(cfg_.wls_mean_number_photons)
     << ";y11_direct_scint_yield_per_MeV="
     << CanonFloat(cfg_.y11_direct_scint_yield_per_MeV)
     << ";tio2_finish=" << cfg_.tio2_finish
     << ";tio2_specular_lobe=" << CanonFloat(cfg_.tio2_specular_lobe)
     << ";tio2_specular_spike=" << CanonFloat(cfg_.tio2_specular_spike)
     << ";tio2_backscatter=" << CanonFloat(cfg_.tio2_backscatter)
     << ";y11_attenuation_form=" << cfg_.y11_attenuation_form
     << ";strict_optical=" << (cfg_.strict_optical ? "true" : "false");
  optical_hash_ = Sha256::hex(os.str());
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

// G4-003: enforce optical-table presence + schema. In strict (production)
// mode a missing required table or a schema/unit/range violation aborts the
// run via a FatalException BEFORE the event loop (these builders run during
// Initialize()). In permissive (dev) mode violations are advisory warnings
// and the historic fail-open fallbacks apply.
void EnforceOpticalTables(const OpticalTables& tables, const AppConfig& cfg,
                          const std::vector<std::string>& required) {
  auto errs = tables.ValidateRequired(required);
  if (errs.empty()) return;
  std::string msg = "G4-003 optical-table validation failed:\n";
  for (const auto& e : errs) msg += "  - " + e + "\n";
  if (cfg.strict_optical) {
    msg += "Run aborted in strict optical mode (default; --strict-optical / "
           "CCB_STRICT_OPTICAL). Supply valid optical CSV tables, or pass "
           "--allow-optical-fallback for non-authorising development runs.";
    G4Exception("DetectorConstruction::Construct", "OPT_TABLES_001",
                FatalException, msg.c_str());
  } else {
    auto& mutable_cfg = const_cast<AppConfig&>(cfg);
    mutable_cfg.optical_fallback_used = true;
    mutable_cfg.authorising = false;
    std::cerr << "warning: " << msg
              << "Continuing in permissive fallback mode "
                 "(authorising=false; built-in fallbacks may apply).\n";
  }
}

}  // namespace

G4Material* DetectorConstruction::BuildScintillator() {
  auto* nist = G4NistManager::Instance();
  // Material identity is a named hypothesis until CCB hardware evidence closes
  // issue #1000. polystyrene_legacy preserves the historic transport host;
  // vinyltoluene_pvt_hypothesis uses NIST plastic scintillator (PVT) as a
  // BC-408-class prior. Neither is authorised as verified stave composition.
  G4Material* ps = nullptr;
  if (cfg_.scintillator_material == "vinyltoluene_pvt_hypothesis") {
    ps = nist->BuildMaterialWithNewDensity(
        "CCB_Scintillator", "G4_PLASTIC_SC_VINYLTOLUENE",
        1.032 * CLHEP::g / CLHEP::cm3);
  } else {
    ps = nist->BuildMaterialWithNewDensity(
        "CCB_Scintillator", "G4_POLYSTYRENE", 1.06 * CLHEP::g / CLHEP::cm3);
  }
  auto tables = OpticalTables::LoadDir(cfg_.optical_dir, cfg_.strict_optical);
  auto* mpt = new G4MaterialPropertiesTable();

  std::vector<double> e = {1.5 * eV, 4.0 * eV};
  std::vector<double> rindex = {cfg_.scintillator_rindex, cfg_.scintillator_rindex};
  mpt->AddProperty("RINDEX", e, rindex);

  EnforceOpticalTables(tables, cfg_, {"scintillator_emission", "scintillator_absorption"});
  FillFromCurve(mpt, "SCINTILLATIONCOMPONENT1", tables.Get("scintillator_emission"), 1.0, 1.0);
  FillFromCurve(mpt, "ABSLENGTH", tables.Get("scintillator_absorption"),
                cfg_.scintillator_absorption_scale, CLHEP::cm);

  // Yield/timing from the versioned optical-constants ledger (#979).
  mpt->AddConstProperty("SCINTILLATIONYIELD", cfg_.scintillation_yield_per_MeV / MeV);
  mpt->AddConstProperty("RESOLUTIONSCALE", 1.0);
  mpt->AddConstProperty("SCINTILLATIONTIMECONSTANT1", cfg_.scintillation_time_ns * ns);
  mpt->AddConstProperty("SCINTILLATIONYIELD1", 1.0);
  ps->SetMaterialPropertiesTable(mpt);

  ps->GetIonisation()->SetBirksConstant(cfg_.birks_kB_mm_per_MeV * mm / MeV);
  return ps;
}

G4Material* DetectorConstruction::BuildFibreCore() {
  auto* nist = G4NistManager::Instance();
  G4Material* core = nist->BuildMaterialWithNewDensity(
      "CCB_Y11Core", "G4_POLYSTYRENE", 1.05 * CLHEP::g / CLHEP::cm3);  // distinct Y-11 PS host
  auto tables = OpticalTables::LoadDir(cfg_.optical_dir, cfg_.strict_optical);
  auto* mpt = new G4MaterialPropertiesTable();
  std::vector<double> e = {1.5 * eV, 4.0 * eV};
  std::vector<double> rindex = {cfg_.y11_core_rindex, cfg_.y11_core_rindex};
  mpt->AddProperty("RINDEX", e, rindex);
  EnforceOpticalTables(tables, cfg_, {"y11_absorption", "y11_emission", "y11_bulk_attenuation"});
  // WLS absorption/emission + long-component bulk attenuation (#1085 form tag in metadata).
  FillFromCurve(mpt, "WLSABSLENGTH", tables.Get("y11_absorption"), 1.0, CLHEP::mm);
  FillFromCurve(mpt, "WLSCOMPONENT", tables.Get("y11_emission"), 1.0, 1.0);
  FillFromCurve(mpt, "ABSLENGTH", tables.Get("y11_bulk_attenuation"),
                cfg_.y11_bulk_attenuation_scale, CLHEP::cm);
  mpt->AddConstProperty("WLSTIMECONSTANT", cfg_.wls_time_constant_ns * ns);
  // Explicit fluorescence multiplicity contract (#1088). Geant4 samples Poisson(mu)
  // when WLSMEANNUMBERPHOTONS is set; mu=1 documents the historic unit-yield assumption.
  mpt->AddConstProperty("WLSMEANNUMBERPHOTONS", cfg_.wls_mean_number_photons);
  // Optional direct charged-particle scintillation in the fibre core (#1035).
  // Default 0 keeps the historic WLS-only omission; nonzero is a named hypothesis.
  if (cfg_.y11_direct_scint_yield_per_MeV > 0.0) {
    FillFromCurve(mpt, "SCINTILLATIONCOMPONENT1", tables.Get("y11_emission"), 1.0, 1.0);
    mpt->AddConstProperty("SCINTILLATIONYIELD",
                          cfg_.y11_direct_scint_yield_per_MeV / MeV);
    mpt->AddConstProperty("RESOLUTIONSCALE", 1.0);
    mpt->AddConstProperty("SCINTILLATIONTIMECONSTANT1", cfg_.wls_time_constant_ns * ns);
    mpt->AddConstProperty("SCINTILLATIONYIELD1", 1.0);
  }
  core->SetMaterialPropertiesTable(mpt);
  return core;
}

G4Material* DetectorConstruction::BuildFibreInnerClad() {
  auto* nist = G4NistManager::Instance();
  G4Material* pmma = nist->BuildMaterialWithNewDensity("CCB_FibreInnerClad", "G4_PLEXIGLASS", 1.19 * CLHEP::g / CLHEP::cm3);  // distinct PMMA instance (n~1.49)
  auto* mpt = new G4MaterialPropertiesTable();
  std::vector<double> e = {1.5 * eV, 4.0 * eV};
  std::vector<double> n = {cfg_.clad_inner_rindex, cfg_.clad_inner_rindex};
  mpt->AddProperty("RINDEX", e, n);
  pmma->SetMaterialPropertiesTable(mpt);
  return pmma;
}

G4Material* DetectorConstruction::BuildFibreOuterClad() {
  // Fluorinated PMMA n~1.42. Approximate as a custom low-index acrylic.
  auto* nist = G4NistManager::Instance();
  G4Material* fclad = nist->BuildMaterialWithNewDensity("CCB_FibreOuterClad", "G4_PLEXIGLASS", 1.19 * CLHEP::g / CLHEP::cm3);  // distinct fluorinated-PMMA instance (n~1.42)
  auto* mpt = new G4MaterialPropertiesTable();
  std::vector<double> e = {1.5 * eV, 4.0 * eV};
  std::vector<double> n = {cfg_.clad_outer_rindex, cfg_.clad_outer_rindex};
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
  // TiO2 reflective coating as dielectric_metal + UNIFIED (#1086).
  // Finish must be polished|ground for dielectric_metal; groundfrontpainted is
  // not a valid metal finish and previously collapsed to unintended Lambertian.
  auto tables = OpticalTables::LoadDir(cfg_.optical_dir, cfg_.strict_optical);
  auto* surf = new G4OpticalSurface("TiO2_Coating");
  surf->SetType(dielectric_metal);
  surf->SetModel(unified);
  if (cfg_.tio2_finish == "polished") surf->SetFinish(polished);
  else surf->SetFinish(ground);
  surf->SetSigmaAlpha(cfg_.tio2_sigma_alpha);
  EnforceOpticalTables(tables, cfg_, {"tio2_reflectivity"});
  auto* mpt = new G4MaterialPropertiesTable();
  const OpticalCurve& refl = tables.Get("tio2_reflectivity");
  if (!refl.Empty()) {
    std::vector<double> e, r;
    for (size_t i = refl.x.size(); i-- > 0;) {
      e.push_back((1239.841984 / refl.x[i]) * eV);
      // Strict mode already rejects out-of-range y; permissive may still clamp.
      double rv = refl.y[i] * cfg_.reflectivity_scale;
      if (!cfg_.strict_optical) rv = std::min(1.0, std::max(0.0, rv));
      r.push_back(rv);
    }
    mpt->AddProperty("REFLECTIVITY", e, r);
  } else {
    if (cfg_.strict_optical) {
      G4Exception("DetectorConstruction::BuildCoatingSurface", "OPT_TABLES_002",
                  FatalException,
                  "tio2_reflectivity missing in strict mode");
    }
    std::vector<double> e = {1.5 * eV, 4.0 * eV};
    const double r_fb = std::min(1.0, 0.90 * cfg_.reflectivity_scale);
    std::vector<double> r = {r_fb, r_fb};
    mpt->AddProperty("REFLECTIVITY", e, r);
  }
  // Explicit UNIFIED constants so Lambertian is intentional provenance, not default.
  std::vector<double> eU = {1.5 * eV, 4.0 * eV};
  std::vector<double> lobe = {cfg_.tio2_specular_lobe, cfg_.tio2_specular_lobe};
  std::vector<double> spike = {cfg_.tio2_specular_spike, cfg_.tio2_specular_spike};
  std::vector<double> back = {cfg_.tio2_backscatter, cfg_.tio2_backscatter};
  mpt->AddProperty("SPECULARLOBECONSTANT", eU, lobe);
  mpt->AddProperty("SPECULARSPIKECONSTANT", eU, spike);
  mpt->AddProperty("BACKSCATTERCONSTANT", eU, back);
  surf->SetMaterialPropertiesTable(mpt);
  new G4LogicalBorderSurface("TiO2_Border", scintPV, worldPV, surf);
}

// GPU-only SiPM detect surface. Opticks classifies a boundary by the FIRST CHAR
// of its OpticalSurfaceName: a '#' prefix -> Surface_zplus_sensor_A, the Opticks
// sensor-detection surface type, so photons crossing into the SiPM are flagged
// (SURFACE_DETECT / EFFICIENCY_COLLECT). The CPU Geant4 reference detects via
// SteppingAction boundary-crossing counting and does NOT need (nor define) this
// surface, so it is gated behind CCB_GPU_GEOM (set only for the --dump-gdml GPU
// export) -> the CPU path and ctest 9/9 are bit-for-bit unchanged. The EFFICIENCY
// property (1.0) also populates the Opticks icdf texture used by EC gathering.
static void AttachGpuSensorDetect(G4LogicalVolume* sensLV, const std::string& sname) {
  if (!sensLV || !std::getenv("CCB_GPU_GEOM")) return;
  auto* detSurf = new G4OpticalSurface("#" + sname + "_Detect");
  detSurf->SetType(dielectric_dielectric);
  detSurf->SetModel(unified);
  detSurf->SetFinish(polished);
  auto* mpt = new G4MaterialPropertiesTable();
  std::vector<double> e = {1.5 * eV, 4.0 * eV};
  std::vector<double> eff = {1.0, 1.0};  // ideal SiPM detection (parity reference)
  mpt->AddProperty("EFFICIENCY", e, eff);
  detSurf->SetMaterialPropertiesTable(mpt);
  new G4LogicalSkinSurface("#" + sname + "_DetectSkin", sensLV, detSurf);
}


G4VPhysicalVolume* DetectorConstruction::Construct() {
  G4Material* air = BuildOpticalGap();  // air w/ RINDEX (world + fibre-hole gaps)

  // Fibre geometry (concentric): core < inner clad < outer clad < hole.
  const double rCore  = kFibreRadius * 0.94;
  const double rInner = kFibreRadius * 0.97;
  const double rOuter = kFibreRadius * 1.00;
  const double rHole  = kHoleRadius;
  const std::array<double, 2> yc = {+kFibreSep / 2.0, -kFibreSep / 2.0};

  // --- World: wide enough in x for the protruding fibres + external sensors ---
  const double wx = kFibreHalfX + 3 * cm;   // fibres reach +-26 cm
  const double wy = kStaveHalfY + 5 * cm;
  const double wz = kStaveHalfZ + 5 * cm;
  auto* worldSolid = new G4Box("World", wx, wy, wz);
  auto* worldLV = new G4LogicalVolume(worldSolid, air, "World");
  auto* worldPV = new G4PVPlacement(nullptr, {}, worldLV, "World", nullptr,
                                    false, 0, false);

  // Fibre rotation: G4Tubs axis is local z -> rotate +90 deg about y to lie on x.
  auto* fibreRot = new G4RotationMatrix();
  fibreRot->rotateY(90.0 * deg);

  // One long cutting cylinder per fibre channel; longer than every solid so the
  // Boolean subtraction cleanly removes the channel from coating AND scintillator.
  const double cutHalf = kFibreHalfX + 1 * cm;
  auto* cutTub = new G4Tubs("HoleCut", 0, rHole, cutHalf, 0, twopi);

  // --- Coating shell (bar + margin) with both holes subtracted. It hosts the
  //     TiO2 reflector on the OUTER faces only; the hole walls stay open. ---
  G4VSolid* coatSolid = new G4Box("CoatBox", kStaveHalfX + kCoatingThk,
                                  kStaveHalfY + kCoatingThk,
                                  kStaveHalfZ + kCoatingThk);
  coatSolid = new G4SubtractionSolid("Coat_h1", coatSolid, cutTub, fibreRot,
                                     G4ThreeVector(0, yc[0], 0));
  coatSolid = new G4SubtractionSolid("Coating", coatSolid, cutTub, fibreRot,
                                     G4ThreeVector(0, yc[1], 0));
  // Coating charged-particle material (#1005). Default remains the historic
  // massless air placeholder and is BLOCKED for material-budget claims.
  G4Material* coatMat = air;
  if (cfg_.coating_material == "tio2_paint_hypothesis") {
    // Provisional TiO2-pigment hypothesis only (#1005). Not CCB paint assay truth;
    // binder fraction/density remain UNKNOWN_EXTERNAL / BLOCKED.
    auto* nist = G4NistManager::Instance();
    auto* elTi = nist->FindOrBuildElement("Ti");
    auto* elO = nist->FindOrBuildElement("O");
    coatMat = new G4Material("CCB_TiO2PaintHypothesis",
                             cfg_.tio2_paint_density_g_cm3 * CLHEP::g / CLHEP::cm3,
                             2);
    coatMat->AddElement(elTi, 1);
    coatMat->AddElement(elO, 2);
    std::cerr << "warning: coating_material=tio2_paint_hypothesis uses provisional density/composition; NOT CCB paint truth (#1005)\n";
  }
  auto* coatLV = new G4LogicalVolume(coatSolid, coatMat, "Coating");
  auto* coatPV = new G4PVPlacement(nullptr, {}, coatLV, "Coating", worldLV,
                                   false, 0, true);

  // --- Scintillator box with both holes subtracted, placed inside the coating.
  G4VSolid* scintSolid = new G4Box("ScintBox", kStaveHalfX, kStaveHalfY, kStaveHalfZ);
  scintSolid = new G4SubtractionSolid("Scint_h1", scintSolid, cutTub, fibreRot,
                                      G4ThreeVector(0, yc[0], 0));
  scintSolid = new G4SubtractionSolid("Scintillator", scintSolid, cutTub, fibreRot,
                                      G4ThreeVector(0, yc[1], 0));
  auto* scintLV = new G4LogicalVolume(scintSolid, BuildScintillator(), "Scintillator");
  auto* scintPV = new G4PVPlacement(nullptr, {}, scintLV, "Scintillator", coatLV,
                                    false, 0, true);

  // TiO2 reflector on the scint<->coating border (outer faces only). The hole
  // walls are scint<->world(air) and stay optically open so scintillation
  // photons can cross into the fibres.
  BuildCoatingSurface(scintPV, coatPV);

  // --- Fibres as WORLD daughters: they pass through the holes and PROTRUDE past
  //     the bar faces so the readout sensors sit outside the scintillator. ---
  G4Material* mCore  = BuildFibreCore();
  G4Material* mInner = BuildFibreInnerClad();
  G4Material* mOuter = BuildFibreOuterClad();

  // Fibre-hole coupling fill (#1036). UNKNOWN_EXTERNAL/dry_* keep the historic
  // air annulus with explicit provenance. grease/epoxy/bonded install a named
  // refractive-index hypothesis tube (catalogue priors, not CCB adhesive truth).
  G4Material* coupleMat = nullptr;
  double couple_n = 1.0;
  const std::string& iface = cfg_.optical_interface_model;
  if (iface == "grease") {
    couple_n = cfg_.coupling_grease_rindex;
  } else if (iface == "epoxy" || iface == "bonded") {
    couple_n = cfg_.coupling_epoxy_rindex;
  }
  if (iface == "grease" || iface == "epoxy" || iface == "bonded") {
    auto* nist = G4NistManager::Instance();
    coupleMat = nist->BuildMaterialWithNewDensity(
        "CCB_FibreCouplingFill", "G4_PLEXIGLASS", 1.18 * CLHEP::g / CLHEP::cm3);
    auto* cmpt = new G4MaterialPropertiesTable();
    std::vector<double> ce = {1.5 * eV, 4.0 * eV};
    std::vector<double> cn = {couple_n, couple_n};
    cmpt->AddProperty("RINDEX", ce, cn);
    coupleMat->SetMaterialPropertiesTable(cmpt);
    std::cerr << "warning: optical_interface_model=" << iface
              << " uses hypothesis coupling n=" << couple_n
              << " (NOT verified CCB adhesive; #1036)\n";
  }

  for (int f = 0; f < 2; ++f) {
    std::ostringstream tag; tag << (f == 0 ? "F1" : "F2");
    auto* outSolid = new G4Tubs("OuterClad_" + tag.str(), 0, rOuter, kFibreHalfX, 0, twopi);
    auto* outLV = new G4LogicalVolume(outSolid, mOuter, "OuterClad_" + tag.str());
    new G4PVPlacement(fibreRot, G4ThreeVector(0, yc[f], 0), outLV,
                      "OuterClad_" + tag.str(), worldLV, false, f, true);

    if (coupleMat) {
      auto* fillSolid = new G4Tubs("CoupleFill_" + tag.str(), rOuter, rHole,
                                   kFibreHalfX, 0, twopi);
      auto* fillLV = new G4LogicalVolume(fillSolid, coupleMat,
                                         "CoupleFill_" + tag.str());
      new G4PVPlacement(fibreRot, G4ThreeVector(0, yc[f], 0), fillLV,
                        "CoupleFill_" + tag.str(), worldLV, false, f, true);
    }

    auto* inSolid = new G4Tubs("InnerClad_" + tag.str(), 0, rInner, kFibreHalfX, 0, twopi);
    auto* inLV = new G4LogicalVolume(inSolid, mInner, "InnerClad_" + tag.str());
    new G4PVPlacement(nullptr, {}, inLV, "InnerClad_" + tag.str(), outLV,
                      false, f, true);

    auto* coreSolid = new G4Tubs("Core_" + tag.str(), 0, rCore, kFibreHalfX, 0, twopi);
    auto* coreLV = new G4LogicalVolume(coreSolid, mCore, "Core_" + tag.str());
    new G4PVPlacement(nullptr, {}, coreLV, "Core_" + tag.str(), inLV,
                      false, f, true);

    // Endcap sensors / terminations just beyond the protruding fibre ends.
    auto* sensSolid = new G4Tubs("Sensor_" + tag.str(), 0, rOuter, kSensorThk / 2.0, 0, twopi);

    // +x (readout) sensor — ALWAYS present (physical readout channel).
    {
      const double xpos = kFibreHalfX + kSensorThk / 2.0 + 10 * um;
      const int sid = f * 2;  // F1+x=0(readout) F2+x=2(near)
      const std::string sname = SensorNames()[sid];
      auto* sensLV = new G4LogicalVolume(sensSolid, mCore, sname);
      new G4PVPlacement(fibreRot, G4ThreeVector(xpos, yc[f], 0), sensLV, sname,
                        worldLV, false, sid, true);
      AttachGpuSensorDetect(sensLV, sname);
    }

    // -x (far) end — CONDITIONAL on far_end_mode (SIPM-P0-002).
    {
      const double xpos = -(kFibreHalfX + kSensorThk / 2.0 + 10 * um);
      const int sid = f * 2 + 1;  // F1-x=1(far) F2-x=3(far)

      if (cfg_.far_end_mode == "instrumented") {
        // Sensor at the far end (simulation control channel).
        const std::string sname = SensorNames()[sid];
        auto* sensLV = new G4LogicalVolume(sensSolid, mCore, sname);
        new G4PVPlacement(fibreRot, G4ThreeVector(xpos, yc[f], 0), sensLV, sname,
                          worldLV, false, sid, true);
        AttachGpuSensorDetect(sensLV, sname);
      } else if (cfg_.far_end_mode == "mirror" ||
                 cfg_.far_end_mode == "absorb") {
        // Reflective / absorbing cap: thin disc with dielectric-metal surface.
        const bool is_mirror = (cfg_.far_end_mode == "mirror");
        const double reflectivity = is_mirror ? 1.0 : 0.0;
        const std::string capName =
            (is_mirror ? "MirrorCap_" : "AbsorbCap_") + tag.str();
        auto* capSolid =
            new G4Tubs(capName, 0, rOuter, kSensorThk / 2.0, 0, twopi);
        auto* capLV = new G4LogicalVolume(capSolid, air, capName);
        new G4PVPlacement(fibreRot, G4ThreeVector(xpos, yc[f], 0), capLV,
                          capName, worldLV, false, sid, true);

        // Optical surface: dielectric-metal so photons either reflect or absorb.
        auto* capSurf = new G4OpticalSurface(capName + "_Surf");
        capSurf->SetType(dielectric_metal);
        capSurf->SetModel(unified);
        capSurf->SetFinish(polished);
        auto* capMpt = new G4MaterialPropertiesTable();
        std::vector<double> capEnergy = {1.5 * eV, 4.0 * eV};
        std::vector<double> capRefl = {reflectivity, reflectivity};
        capMpt->AddProperty("REFLECTIVITY", capEnergy, capRefl);
        capSurf->SetMaterialPropertiesTable(capMpt);
        new G4LogicalSkinSurface(capName + "_Skin", capLV, capSurf);
      }
      // "open": no volume at the far end — fibre terminates into world air.
    }
  }

  // geometry_hash_ computed in the constructor (deterministic).
  PrintGeometryReport();
  return worldPV;
}

void DetectorConstruction::PrintGeometryReport() const {
  // Machine-readable SELF-CHECK of the driving constants. This is NOT an
  // overlap check: Geant4's real CheckOverlaps runs via pSurfChk=true on every
  // placement (and /geometry/test/run in the macro) and prints "Overlap is
  // detected" on failure, which the ctest treats as a hard failure. Do not
  // conflate this self-check with Geant4's authoritative overlap result.
  const double norm_path_cm = 2.0 * kStaveHalfZ / cm;             // 2.0 cm
  const double sep_cm = kFibreSep / cm;                           // 2.0 cm
  const double rOuter = kFibreRadius;                             // fibre outer radius
  const double fibre_within = (rOuter < kHoleRadius) ? 1 : 0;     // fibre fits the hole
  const double fibre_protrudes = (kFibreHalfX > kStaveHalfX) ? 1 : 0;  // reads out externally
  const double holes_in_y =
      (kFibreSep / 2.0 + kHoleRadius <= kStaveHalfY) ? 1 : 0;
  const double holes_in_z = (kHoleRadius <= kStaveHalfZ) ? 1 : 0;

  std::cout << "GEOMETRY_REPORT_BEGIN\n"
            << "stave_length_cm " << 2 * kStaveHalfX / cm << "\n"
            << "stave_width_cm " << 2 * kStaveHalfY / cm << "\n"
            << "stave_thickness_cm " << 2 * kStaveHalfZ / cm << "\n"
            << "normal_path_cm " << norm_path_cm << "\n"
            << "fibre_diameter_mm " << 2 * kFibreRadius / mm << "\n"
            << "hole_diameter_mm " << 2 * kHoleRadius / mm << "\n"
            << "fibre_separation_cm " << sep_cm << "\n"
            << "fibre_within_hole " << fibre_within << "\n"
            << "fibre_protrudes_for_readout " << fibre_protrudes << "\n"
            << "holes_contained_y " << holes_in_y << "\n"
            << "holes_contained_z " << holes_in_z << "\n"
            << "geometry_hash " << geometry_hash_ << "\n"
            << "physics_hash " << physics_hash_ << "\n"
            << "optical_hash " << optical_hash_ << "\n"
            << "GEOMETRY_REPORT_END\n";

  const bool ok = fibre_within && fibre_protrudes && holes_in_y && holes_in_z &&
                  std::abs(norm_path_cm - 2.0) < 1e-6 &&
                  std::abs(sep_cm - 2.0) < 1e-6;
  // Distinct token: geometry-constant self-check, NOT the Geant4 overlap verdict.
  std::cout << (ok ? "GEOMETRY_SELFCHECK_PASS" : "GEOMETRY_SELFCHECK_FAIL")
            << std::endl;
}
