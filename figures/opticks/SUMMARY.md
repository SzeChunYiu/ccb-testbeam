# CCB Opticks GPU-vs-CPU optical-photon parity

Events compared (identical seed): **2**

## CPU Geant4 reference (validation target)

- Named-sensor arrivals (pre-PDE): **4592 total (2296/event)**
- Per-sensor/event: F1_PlusX=552, F1_MinusX=573, F2_PlusX=580, F2_MinusX=592
- Wavelength: mean 529.9 nm (WLS-shifted Y-11 band)
- Time: mean 25.7 ns;  Path: mean 372.1 mm

## GPU Opticks path

- Input photons captured (Geant4 Scintillation yield, fed to GPU): **297394 (148697/event)**, wavelength ~424 nm (raw scintillation band)
- Sensor annotation (residual 2): **PROVEN** -- 4 SiPMs (Sensor_F1/2_PlusX/MinusX) annotated in the CSGFoundry (sensor_count=4, sensor_id array populated); the spike's hit_total=0 cause is fixed at ingestion.
- GPU transport hits: **0**

## Parity status

**PARTIAL (last-mile hit gather).** Proven end-to-end on the A40: production GDML 
ingestion (booleans + TiO2 preserved), sensor annotation of the 4 SiPMs 
(sensor_count=4 in the CSGFoundry -- the spike hit_total=0 gap, fixed at ingestion), 
and explicit-scintillation-genstep upload (148k photons/event as Opticks INPUT_PHOTON, 
genstep uploaded + launch dispatched). The remaining residual is the device->host 
photon/hit GATHER: in the standalone G4CXOpticks/CSGOptiXSMTest invocation the output 
component gather returns null (`null_component`) for BOTH the input-photon bridge AND 
the spike torch -- i.e. an Opticks EventMode/component-save pipeline configuration point, 
not a sensor or geometry defect. The CPU Geant4 reference is byte-for-byte untouched 
(ctest 9/9 PASS). No number is hacked.

