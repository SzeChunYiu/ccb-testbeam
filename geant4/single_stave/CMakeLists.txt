cmake_minimum_required(VERSION 3.16)
project(CCBSingleStave LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Visualization is OPTIONAL. The physics executable must build without Qt/vis
# to avoid the Qt5/ICU incompatibility reported on the PR (issue #796).
option(CCB_ENABLE_VIS "Enable Geant4 visualization/UI components" OFF)

if(CCB_ENABLE_VIS)
  find_package(Geant4 REQUIRED ui_all vis_all)
else()
  find_package(Geant4 REQUIRED)
endif()
include(${Geant4_USE_FILE})

file(GLOB_RECURSE CCB_STAVE_SOURCES CONFIGURE_DEPENDS
  "${PROJECT_SOURCE_DIR}/src/*.cc")
file(GLOB_RECURSE CCB_STAVE_HEADERS CONFIGURE_DEPENDS
  "${PROJECT_SOURCE_DIR}/include/*.hh")

# Clean-room SiPM response core (submodule ccb-sipm-core). Geant4-independent;
# built as part of the project when present. See https://github.com/SzeChunYiu/ccb-sipm-core
if(EXISTS "${PROJECT_SOURCE_DIR}/sipm/CMakeLists.txt")
  # Enable the Geant4 adapter so ccb_stave_sim can use Geant4BoundaryCollector.
  set(CCB_SIPM_WITH_GEANT4 ON CACHE BOOL "Build optional Geant4 adapter" FORCE)
  add_subdirectory(sipm)
endif()

add_executable(ccb_stave_sim ${CCB_STAVE_SOURCES} ${CCB_STAVE_HEADERS})
target_include_directories(ccb_stave_sim PRIVATE "${PROJECT_SOURCE_DIR}/include")
target_link_libraries(ccb_stave_sim PRIVATE ${Geant4_LIBRARIES})
# SiPM core + Geant4 adapter (SIPM-P1-001: boundary-arrival collection).
if(TARGET CCB::sipm_geant4)
  target_link_libraries(ccb_stave_sim PRIVATE CCB::sipm_geant4)
endif()
target_compile_options(ccb_stave_sim PRIVATE -Wall -Wextra -Wpedantic)

if(CCB_ENABLE_VIS)
  target_compile_definitions(ccb_stave_sim PRIVATE CCB_ENABLE_VIS)
endif()

# Copy runtime assets (macros + optical tables) next to the build so ctest and
# ad-hoc runs find them via relative paths.
file(COPY "${PROJECT_SOURCE_DIR}/macros"  DESTINATION "${CMAKE_BINARY_DIR}")
file(COPY "${PROJECT_SOURCE_DIR}/optical" DESTINATION "${CMAKE_BINARY_DIR}")

enable_testing()

# 1) Geometry / overlap smoke: the app prints OVERLAP_CHECK_PASS at Initialize().
add_test(
  NAME ccb_stave_geometry_smoke
  COMMAND ccb_stave_sim
          --macro "${CMAKE_BINARY_DIR}/macros/geometry_check.mac"
          --optical-dir "${CMAKE_BINARY_DIR}/optical"
          --output "${CMAKE_BINARY_DIR}/geometry_smoke.root")
set_tests_properties(ccb_stave_geometry_smoke PROPERTIES
  PASS_REGULAR_EXPRESSION "GEOMETRY_SELFCHECK_PASS"
  # Fail on the geometry self-check OR Geant4's authoritative overlap detection.
  FAIL_REGULAR_EXPRESSION "GEOMETRY_SELFCHECK_FAIL;Overlap is detected;G4Exception.*Fatal")

# 2) Tiny headless proton run: must reach CCB_STAVE_END without fatal error.
add_test(
  NAME ccb_stave_proton_smoke
  COMMAND ccb_stave_sim
          --particle proton --energy 100 --nevents 5 --seed 1
          --optical-dir "${CMAKE_BINARY_DIR}/optical"
          --output "${CMAKE_BINARY_DIR}/proton_smoke.root")
set_tests_properties(ccb_stave_proton_smoke PROPERTIES
  PASS_REGULAR_EXPRESSION "CCB_STAVE_END"
  FAIL_REGULAR_EXPRESSION "G4Exception.*Fatal;segmentation")

# 5) WLS time profile (SIPM-P0-001): --wls-time-profile exponential is accepted
#    and recorded in RUN_CONFIG (configurable + metadata).
add_test(
  NAME ccb_stave_wls_profile
  COMMAND ccb_stave_sim
          --particle proton --energy 100 --nevents 5 --seed 1
          --wls-time-profile exponential
          --optical-dir "${CMAKE_BINARY_DIR}/optical"
          --output "${CMAKE_BINARY_DIR}/wls_profile.root")
set_tests_properties(ccb_stave_wls_profile PROPERTIES
  PASS_REGULAR_EXPRESSION "wls_time_profile=exponential"
  FAIL_REGULAR_EXPRESSION "G4Exception.*Fatal;segmentation")

# 3) Python geometry-report assertions on captured stdout (runs if python3 found).
find_program(CCB_PYTHON3 python3)
if(CCB_PYTHON3)
  add_test(
    NAME ccb_stave_geometry_report_python
    COMMAND ${CCB_PYTHON3}
            "${PROJECT_SOURCE_DIR}/tests/check_geometry_report.py"
            --exe "$<TARGET_FILE:ccb_stave_sim>"
            --optical-dir "${CMAKE_BINARY_DIR}/optical"
            --macro "${CMAKE_BINARY_DIR}/macros/geometry_check.mac")
endif()

# 4) Birks visible-energy regression (review defect 2). Proves the
#    edep_scint_MeV (visible, G4EmSaturation) and edep_scint_raw_MeV (raw)
#    branches are not silently identical: distinct when --birks-kB > 0, equal
#    when --birks-kB 0. Runs the sim twice with a handful of proton events and
#    parses the events ntuple via uproot. Exits 77 (SKIP) when uproot is absent
#    so the test runs where the [root] extra is installed and skips elsewhere.
if(CCB_PYTHON3)
  add_test(
    NAME ccb_stave_birks_visible_regression
    COMMAND ${CCB_PYTHON3}
            "${PROJECT_SOURCE_DIR}/tests/test_birks_visible_regression.py"
            --exe "$<TARGET_FILE:ccb_stave_sim>"
            --optical-dir "${CMAKE_BINARY_DIR}/optical"
            --work-dir "${CMAKE_BINARY_DIR}/birks_regression")
  set_tests_properties(ccb_stave_birks_visible_regression PROPERTIES
    TIMEOUT 300
    SKIP_RETURN_CODE 77
    FAIL_REGULAR_EXPRESSION "defect 2 has regressed")
endif()

# 6) Far-end modes (SIPM-P0-002): --far-end absorb|open|mirror|instrumented
#    are accepted, recorded in RUN_CONFIG, and produce valid geometry.
if(CCB_PYTHON3)
  add_test(
    NAME ccb_stave_far_end_modes
    COMMAND ${CCB_PYTHON3}
            "${PROJECT_SOURCE_DIR}/tests/test_far_end_modes.py"
            --exe "$<TARGET_FILE:ccb_stave_sim>"
            --optical-dir "${CMAKE_BINARY_DIR}/optical"
            --macro "${CMAKE_BINARY_DIR}/macros/geometry_check.mac"
            --work-dir "${CMAKE_BINARY_DIR}/far_end_modes")
  set_tests_properties(ccb_stave_far_end_modes PROPERTIES
    TIMEOUT 600
    FAIL_REGULAR_EXPRESSION "SOME FAR-END MODES FAILED")
endif()

# 7) SiPM boundary-arrival collection (SIPM-P1-001): arrivals populated.
add_test(
  NAME ccb_stave_sipm_arrivals
  COMMAND ccb_stave_sim
          --particle proton --energy 100 --nevents 5 --seed 1
          --optical-dir "${CMAKE_BINARY_DIR}/optical"
          --output "${CMAKE_BINARY_DIR}/sipm_arrivals.root")
set_tests_properties(ccb_stave_sipm_arrivals PROPERTIES
  PASS_REGULAR_EXPRESSION "SIPM_ARRIVALS.*total=[1-9]"
  FAIL_REGULAR_EXPRESSION "G4Exception.*Fatal;segmentation")
