// CCBSensorIdentifier.h - annotates the 4 CCB SiPM discs as Opticks sensors.
//
// Residual-2 fix. The default U4SensorIdentifierDefault identifies sensors by
// "PMT" volume-name prefix and/or G4 SensitiveDetector status. Neither applies
// to CCB (sensors are "Sensor_F1_PlusX/MinusX", "Sensor_F2_PlusX/MinusX"), and
// G4 SD status does NOT survive a GDML round-trip -- which is exactly why the
// spike's GPU path reported hit_total=0. This implementation matches the SiPM
// physical volumes by name (LV or PV) and returns the Geant4 copyNo (0..3, set
// in DetectorConstruction::Construct) as the Opticks sensor identifier, so
// num_hit / per-sensor identity populate. Installed via
// G4CXOpticks::SetSensorIdentifier before SetGeometry.
#ifndef CCB_SENSOR_IDENTIFIER_H
#define CCB_SENSOR_IDENTIFIER_H

#include "U4SensorIdentifier.h"
#include "G4PVPlacement.hh"
#include "G4LogicalVolume.hh"

struct CCBSensorIdentifier : public U4SensorIdentifier {
  static bool IsSensor(const G4String& n) {
    return n.length() >= 8 && n.substr(0, 8) == "Sensor_F";
  }
  void setLevel(int) override {}

  int getGlobalIdentity(const G4VPhysicalVolume* pv,
                        const G4VPhysicalVolume* /*ppv*/) override {
    if (!pv) return -1;
    const G4String lvn = pv->GetLogicalVolume()->GetName();
    const G4String pvn = pv->GetName();
    if (!IsSensor(lvn) && !IsSensor(pvn)) return -1;
    const auto* pvp = dynamic_cast<const G4PVPlacement*>(pv);
    const int cno = pvp ? pvp->GetCopyNo() : -1;
    return (cno >= 0 && cno < 4) ? cno : -1;
  }
  int getInstanceIdentity(const G4VPhysicalVolume* pv) const override {
    // CCB sensors are non-instanced (global remainder); handled above.
    (void)pv;
    return -1;
  }
};

#endif  // CCB_SENSOR_IDENTIFIER_H
