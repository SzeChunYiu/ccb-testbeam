# Optional Opticks GPU bridge.
#
# The bridge (ccb_opticks_gpu) links against the out-of-tree Opticks install.
# The spike's Opticks install is not cleanly consumable via find_package(G4CX)
# from an external project (Opticks-internal MODULE deps + custom FindG4), so
# the bridge is built by INJECTING its two source files into the configured
# Opticks g4cx build tree -- exactly how Opticks' own tests (e.g.
# G4CXOpticks_setGeometry_Test) build. Opticks source is NOT vendored into
# ccb-testbeam; the bridge sources are canonical here and copied in by env/path
# at build time. See build_bridge.sh.
#
# This subdirectory is a no-op for cmake (the CPU target/ctest never depend on
# the bridge). Build the bridge with: opticks/build_bridge.sh
message(STATUS "CCB Opticks GPU bridge: build out-of-tree via opticks/build_bridge.sh")
