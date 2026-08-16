// DetectorConstruction.hh — CCB single-stave geometry (Issue #796)
//
// Coordinate convention (detector-local), per the handoff blueprint:
//   x : stave / fibre length   (+-25 cm, 50 cm total)
//   y : width                  (+-2.59 cm, 5.18 cm total)
//   z : normal thickness       (+-1 cm, 2.0 cm total)  <-- primary travels +z
//
// The primary enters at (hit_x, hit_y, z = -half_z - eps) with direction +z so
// it crosses the 2.0 cm NORMAL thickness (fixing the prototype defect where the
// gun traversed the 50 cm long axis).
//
// Two Y-11 fibres run ALONG x (G4Tubs default axis is local z, so each fibre is
// rotated by +90 deg about y). Fibre centres at (x=0, y = +-1 cm) -> 2.0 cm
// separation. Only fibre 1 at the +x end is the physical readout; all four
// (2 fibres x 2 ends) sensor channels are instrumented as simulation controls.
#ifndef CCB_DETECTORCONSTRUCTION_HH
#define CCB_DETECTORCONSTRUCTION_HH

#include "G4VUserDetectorConstruction.hh"
#include "G4SystemOfUnits.hh"
#include "globals.hh"
#include "AppConfig.hh"

#include <array>
#include <string>

class G4LogicalVolume;
class G4VPhysicalVolume;
class G4Material;
class DetectorMessenger;

// Named sensor identifiers. Index into the per-event photon counters.
//   0: fibre1 +x end  == PHYSICAL READOUT
//   1: fibre1 -x end
//   2: fibre2 +x end
//   3: fibre2 -x end
enum SensorId { kReadout = 0, kF1Far = 1, kF2Near = 2, kF2Far = 3, kNSensors = 4 };

class DetectorConstruction : public G4VUserDetectorConstruction {
 public:
  explicit DetectorConstruction(const AppConfig& cfg);
  ~DetectorConstruction() override;

  G4VUserDetectorConstruction* Clone() const = delete;
  G4VPhysicalVolume* Construct() override;

  // --- Geometry constants (half-lengths where noted) ---
  static constexpr double kStaveHalfX = 25.0 * CLHEP::cm;   // 50 cm length
  static constexpr double kStaveHalfY = 2.59 * CLHEP::cm;   // 5.18 cm width
  static constexpr double kStaveHalfZ = 1.0  * CLHEP::cm;   // 2.0 cm thickness
  static constexpr double kCoatingThk = 0.25 * CLHEP::mm;   // TiO2 coating shell
  static constexpr double kHoleRadius = 1.0  * CLHEP::mm;   // 2.0 mm hole
  static constexpr double kFibreRadius = 0.90 * CLHEP::mm;  // 1.8 mm fibre
  static constexpr double kFibreHalfX  = 26.0 * CLHEP::cm;  // fibre protrudes 1 cm past each bar face for external readout
  static constexpr double kFibreSep    = 2.0  * CLHEP::cm;  // centre-to-centre
  static constexpr double kSensorThk   = 0.10 * CLHEP::mm;  // endcap sensor disc

  // Names used by SteppingAction to recognise boundary crossings.
  static const std::array<std::string, kNSensors>& SensorNames();

  // A machine-readable geometry + overlap report printed after Construct().
  // Emits "OVERLAP_CHECK_PASS" (or FAIL) which the ctest greps for.
  void PrintGeometryReport() const;

  // Recorded provenance the RunAction writes to output metadata (#986).
  const std::string& GeometryHash() const { return geometry_hash_; }
  const std::string& PhysicsHash() const { return physics_hash_; }
  const std::string& OpticalHash() const { return optical_hash_; }

 private:
  G4Material* BuildScintillator();     // polystyrene + optical + Birks
  G4Material* BuildFibreCore();        // PS core (Y-11 host)
  G4Material* BuildFibreInnerClad();   // PMMA
  G4Material* BuildFibreOuterClad();   // fluorinated PMMA
  G4Material* BuildOpticalGap();       // air gap in the hole
  void BuildCoatingSurface(G4VPhysicalVolume* scintPV,
                           G4VPhysicalVolume* worldPV);  // TiO2 border surface

  const AppConfig cfg_;
  DetectorMessenger* messenger_ = nullptr;
  std::string geometry_hash_;
  std::string physics_hash_;
  std::string optical_hash_;
  bool overlaps_found_ = false;
};

#endif  // CCB_DETECTORCONSTRUCTION_HH
