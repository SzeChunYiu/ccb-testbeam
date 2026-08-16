// ccb_setGeometry.cc - sensor-annotated GDML -> CSGFoundry ingest for CCB.
//
// Root-cause fix for the Opticks GPU "hit_total=0" symptom. The standalone
// G4CXOpticks_setGeometry_Test ingests with the DEFAULT sensor identifier
// (U4SensorIdentifierDefault, which matches the "PMT" volume-name prefix),
// so the 4 CCB SiPM discs ("Sensor_F1/2_PlusX/MinusX") are NOT recognised as
// sensors: the cached CSGFoundry reports sensor_count=0, no sensor boundary
// surfaces are created, and although GPU transport works (4.6M photons/s) the
// photon/hit GATHER returns null for every event.
//
// This binary installs CCBSensorIdentifier (matches "Sensor_F" by name +
// returns the Geant4 copyNo 0..3 as the Opticks sensor id) BEFORE SetGeometry,
// so the ingested CSGFoundry reports sensor_count=4 with a populated sensor_id
// array and the 4 sensor boundaries get detect surfaces. Run once to
// (re)generate the cached CSGFoundry; subsequent CSGOptiXSMTest / bridge runs
// load the sensor-annotated cache. See README "Residuals" -> gather.
#include "OPTICKS_LOG.hh"
#include "G4CXOpticks.hh"
#include "CCBSensorIdentifier.h"
int main(int argc, char** argv) {
  OPTICKS_LOG(argc, argv);
  G4CXOpticks::SetSensorIdentifier(new CCBSensorIdentifier());
  G4CXOpticks::SetGeometry();
  return 0;
}
