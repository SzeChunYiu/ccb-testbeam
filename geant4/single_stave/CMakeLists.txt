cmake_minimum_required(VERSION 3.16)
project(CCBSingleStave LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Visualization is OPTIONAL. The physics executable must build without Qt/vis
# to avoid the Qt5/ICU incompatibility reported on the PR (issue #796).
option(CCB_ENABLE_VIS "Enable Geant4 visualization/UI components" OFF)
option(CCB_ENABLE_OPTICKS "Build the OPTIONAL Opticks GPU optical bridge (needs OPTICKS_PREFIX)" OFF)
option(CCB_AUTHORISING_BUILD_RECEIPT
  "Fail closed on dirty source and emit a content-bound ccb_stave_sim build receipt"
  OFF)

if(CCB_ENABLE_VIS)
  find_package(Geant4 REQUIRED ui_all vis_all)
else()
  find_package(Geant4 REQUIRED)
endif()
include(${Geant4_USE_FILE})
find_package(Git QUIET)
find_program(CCB_PYTHON3 python3)

# Compile source intent into the executable.  This is independent of the
# ccb-sipm-core gitlink literal bound by SipmBuildProvenance.hh.  Scientific
# campaign builds additionally require a clean source tree and a post-build
# executable receipt; ordinary development builds remain possible but are
# explicitly non-authorising at the receipt layer.
get_filename_component(CCB_REPO_ROOT "${PROJECT_SOURCE_DIR}/../.." ABSOLUTE)
set(CCB_BUILD_SUPERPROJECT_COMMIT "unconfigured")
set(CCB_BUILD_SOURCE_CLEAN 0)
if(GIT_FOUND)
  execute_process(
    COMMAND "${GIT_EXECUTABLE}" -C "${CCB_REPO_ROOT}" rev-parse HEAD
    RESULT_VARIABLE CCB_GIT_HEAD_STATUS
    OUTPUT_VARIABLE CCB_GIT_HEAD
    ERROR_QUIET
    OUTPUT_STRIP_TRAILING_WHITESPACE)
  if(CCB_GIT_HEAD_STATUS EQUAL 0 AND CCB_GIT_HEAD MATCHES "^[0-9a-f][0-9a-f]+$")
    set(CCB_BUILD_SUPERPROJECT_COMMIT "${CCB_GIT_HEAD}")
  endif()
  execute_process(
    COMMAND "${GIT_EXECUTABLE}" -C "${CCB_REPO_ROOT}" status --porcelain=v1 --untracked-files=all
    RESULT_VARIABLE CCB_GIT_STATUS_RESULT
    OUTPUT_VARIABLE CCB_GIT_STATUS
    ERROR_QUIET
    OUTPUT_STRIP_TRAILING_WHITESPACE)
  if(CCB_GIT_STATUS_RESULT EQUAL 0 AND CCB_GIT_STATUS STREQUAL "")
    set(CCB_BUILD_SOURCE_CLEAN 1)
  endif()
endif()
if(CCB_AUTHORISING_BUILD_RECEIPT)
  if(NOT GIT_FOUND OR NOT CCB_BUILD_SOURCE_CLEAN)
    message(FATAL_ERROR
      "CCB_AUTHORISING_BUILD_RECEIPT requires Git and a completely clean source repository")
  endif()
  if(CCB_BUILD_SUPERPROJECT_COMMIT STREQUAL "unconfigured")
    message(FATAL_ERROR
      "CCB_AUTHORISING_BUILD_RECEIPT could not resolve the superproject commit")
  endif()
  if(NOT CCB_PYTHON3)
    message(FATAL_ERROR
      "CCB_AUTHORISING_BUILD_RECEIPT requires python3 for receipt creation")
  endif()
endif()

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
target_compile_definitions(ccb_stave_sim PRIVATE
  CCB_BUILD_SUPERPROJECT_COMMIT="${CCB_BUILD_SUPERPROJECT_COMMIT}"
  CCB_BUILD_SOURCE_CLEAN_AT_CONFIGURE=${CCB_BUILD_SOURCE_CLEAN}
  CCB_BUILD_CMAKE_VERSION="${CMAKE_VERSION}"
  CCB_BUILD_CXX_COMPILER_ID="${CMAKE_CXX_COMPILER_ID}"
  CCB_BUILD_CXX_COMPILER_VERSION="${CMAKE_CXX_COMPILER_VERSION}"
  CCB_BUILD_CXX_COMPILER_PATH="${CMAKE_CXX_COMPILER}"
  CCB_BUILD_GEANT4_VERSION="${Geant4_VERSION}")

if(CCB_ENABLE_VIS)
  target_compile_definitions(ccb_stave_sim PRIVATE CCB_ENABLE_VIS)
endif()

# Authorising builds freeze a receipt only after the final executable exists.
# The receipt tool re-observes clean source, the Gitlink, CMake/toolchain
# sentinels and the exact executable SHA-256; campaign launchers require it.
if(CCB_AUTHORISING_BUILD_RECEIPT)
  add_custom_command(TARGET ccb_stave_sim POST_BUILD
    COMMAND "${CCB_PYTHON3}"
            "${CCB_REPO_ROOT}/scripts/single_stave/sipm_build_receipt.py"
            create
            --repo-root "${CCB_REPO_ROOT}"
            --build-dir "${CMAKE_BINARY_DIR}"
            --executable "$<TARGET_FILE:ccb_stave_sim>"
            --receipt "${CMAKE_BINARY_DIR}/ccb_stave_sim.build.json"
            --digest-file "${CMAKE_BINARY_DIR}/ccb_stave_sim.build.sha256"
    COMMENT "Creating content-bound ccb_stave_sim build receipt"
    VERBATIM)
endif()

# Copy runtime assets (macros + optical tables) next to the build so ctest and
# ad-hoc runs find them via relative paths.
file(COPY "${PROJECT_SOURCE_DIR}/macros"  DESTINATION "${CMAKE_BINARY_DIR}")
file(COPY "${PROJECT_SOURCE_DIR}/optical" DESTINATION "${CMAKE_BINARY_DIR}")

enable_testing()

# Optional out-of-tree Opticks GPU bridge (CCB_ENABLE_OPTICKS). Built only
# when explicitly enabled AND OPTICKS_PREFIX is set. Never a dependency of
# the CPU physics target or ctest.
add_subdirectory(opticks)

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
# 4) GDML export option (--dump-gdml): production geometry -> GDML.
add_test(
  NAME ccb_stave_gdml_export
  COMMAND ccb_stave_sim
          --dump-gdml "${CMAKE_BINARY_DIR}/exported.gdml"
          --optical-dir "${CMAKE_BINARY_DIR}/optical"
          --output "${CMAKE_BINARY_DIR}/gdml_export.root"
          --nevents 1)
set_tests_properties(ccb_stave_gdml_export PROPERTIES
  PASS_REGULAR_EXPRESSION "CCB_GDML_WROTE"
  FAIL_REGULAR_EXPRESSION "G4Exception.*Fatal;segmentation")

# 5) GPU optical path (CCB_GPU_OPTICAL=1): scintillation photons are
#    captured to npy and CPU optical transport is skipped (proton-only).
add_test(
  NAME ccb_stave_gpu_optical_capture
  COMMAND ${CMAKE_COMMAND} -E env CCB_GPU_OPTICAL=1 ccb_stave_sim
          --particle proton --energy 100 --nevents 1 --seed 1
          --optical-dir "${CMAKE_BINARY_DIR}/optical"
          --output "${CMAKE_BINARY_DIR}/gpu_optical.root"
          --optical-out "${CMAKE_BINARY_DIR}/optical_gpu_ctest")
set_tests_properties(ccb_stave_gpu_optical_capture PROPERTIES
  PASS_REGULAR_EXPRESSION "CCB_GPU_PHOTONS"
  FAIL_REGULAR_EXPRESSION "G4Exception.*Fatal;segmentation")

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

# 11) Cladding distinction regression (issue #1303). Proves inner/outer cladding are
#     distinct G4Material/MPT objects with intended RINDEX values.
if(CCB_PYTHON3)
  add_test(
    NAME ccb_stave_cladding_distinction
    COMMAND ${CCB_PYTHON3}
            "${PROJECT_SOURCE_DIR}/tests/test_cladding_distinction.py"
            --exe "$<TARGET_FILE:ccb_stave_sim>"
            --optical-dir "${CMAKE_BINARY_DIR}/optical")
  set_tests_properties(ccb_stave_cladding_distinction PROPERTIES
    TIMEOUT 300
    PASS_REGULAR_EXPRESSION "CLADDING_DISTINCTION_PASS")
endif()

# 1088) WLS fluorescence multiplicity known-answer (issue #1088). Runs the sim
#       in three multiplicity modes on the same seed and asserts the
#       n_wls_generated / n_wls_absorbed ratio equals the mode mean (1, mu, q).
#       Reads the events ntuple via uproot; exits 77 (SKIP) when uproot absent.
if(CCB_PYTHON3)
  add_test(
    NAME ccb_stave_wls_multiplicity
    COMMAND ${CCB_PYTHON3}
            "${PROJECT_SOURCE_DIR}/tests/test_wls_multiplicity.py"
            --exe "$<TARGET_FILE:ccb_stave_sim>"
            --optical-dir "${CMAKE_BINARY_DIR}/optical")
  set_tests_properties(ccb_stave_wls_multiplicity PROPERTIES
    TIMEOUT 3600
    SKIP_RETURN_CODE 77
    FAIL_REGULAR_EXPRESSION "WLS_MULTIPLICITY_FAIL")
endif()

# 1089) Production-cut regression (issue #1089). Proves --production-cut is
#    wired through the CLI, the RUN_CONFIG line, and the .meta.json sidecar, and
#    that it changes the explicit secondary population enough to move the
#    Birks-suppressed visible energy (the cut x kB coupling). Runs the sim twice
#    (fine and coarse cut) and parses the events ntuple via uproot. Exits 77
#    (SKIP) when uproot is absent.
if(CCB_PYTHON3)
  add_test(
    NAME ccb_stave_production_cut_regression
    COMMAND ${CCB_PYTHON3}
            "${PROJECT_SOURCE_DIR}/tests/test_production_cut_regression.py"
            --exe "$<TARGET_FILE:ccb_stave_sim>"
            --optical-dir "${CMAKE_BINARY_DIR}/optical"
            --work-dir "${CMAKE_BINARY_DIR}/production_cut_regression")
  set_tests_properties(ccb_stave_production_cut_regression PROPERTIES
    TIMEOUT 300
    SKIP_RETURN_CODE 77
    FAIL_REGULAR_EXPRESSION "issue #1089 may have regressed")
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

# 8) SiPM core ADC output (SIPM-P1-002): adc_* columns populated.
add_test(
  NAME ccb_stave_sipm_adc
  COMMAND ccb_stave_sim
          --particle proton --energy 100 --nevents 5 --seed 1
          --optical-dir "${CMAKE_BINARY_DIR}/optical"
          --output "${CMAKE_BINARY_DIR}/sipm_adc.root")
set_tests_properties(ccb_stave_sipm_adc PROPERTIES
  TIMEOUT 300
  PASS_REGULAR_EXPRESSION "SIPM_ADC.*readout=[1-9]"
  FAIL_REGULAR_EXPRESSION "G4Exception.*Fatal;segmentation")


# 9) SiPM env fail-closed + zero-control effectiveness (#975/#976).
if(CCB_PYTHON3)
  add_test(
    NAME ccb_stave_sipm_env_fail_closed
    COMMAND ${CCB_PYTHON3}
            "${PROJECT_SOURCE_DIR}/tests/test_sipm_env_fail_closed.py"
            --exe "$<TARGET_FILE:ccb_stave_sim>"
            --optical-dir "${CMAKE_BINARY_DIR}/optical")
  set_tests_properties(ccb_stave_sipm_env_fail_closed PROPERTIES
    TIMEOUT 300
    PASS_REGULAR_EXPRESSION "SIPM_ENV_FAIL_CLOSED_PASS")
endif()

# 10) Non-square --sipm-n-cells must abort before authorising output (#974).
add_test(
  NAME ccb_stave_sipm_n_cells_nonsquare_fail
  COMMAND ccb_stave_sim
          --particle proton --energy 100 --nevents 1 --seed 1
          --sipm-n-cells 1800
          --optical-dir "${CMAKE_BINARY_DIR}/optical"
          --output "${CMAKE_BINARY_DIR}/sipm_nonsquare.root")
set_tests_properties(ccb_stave_sipm_n_cells_nonsquare_fail PROPERTIES
  TIMEOUT 120
  WILL_FAIL TRUE)

# Wave A / Lane 02: semantic optical-table schema (#978/#980) — no Geant4 needed.
if(CCB_PYTHON3)
  add_test(
    NAME ccb_stave_optical_schema
    COMMAND ${CCB_PYTHON3}
            "${PROJECT_SOURCE_DIR}/tests/test_optical_table_schema.py"
            --optical-dir "${CMAKE_BINARY_DIR}/optical")
  set_tests_properties(ccb_stave_optical_schema PROPERTIES
    PASS_REGULAR_EXPRESSION "OPTICAL_SCHEMA_PASS")
endif()

# Strict mode must abort when a required table is removed (#978/#980).
add_test(
  NAME ccb_stave_strict_optical_missing_table
  COMMAND ${CMAKE_COMMAND} -E env
          bash -c "set -e; tmp=$(mktemp -d); cp -R ${CMAKE_BINARY_DIR}/optical/* $tmp/; rm -f $tmp/sipm_pde.csv; $<TARGET_FILE:ccb_stave_sim> --particle proton --energy 100 --nevents 1 --seed 1 --optical-dir $tmp --strict-optical --output $tmp/out.root; ec=$?; rm -rf $tmp; exit $ec")
set_tests_properties(ccb_stave_strict_optical_missing_table PROPERTIES
  WILL_FAIL TRUE)

# Wrong units_x must fail closed in strict mode (#980).
add_test(
  NAME ccb_stave_strict_optical_bad_units
  COMMAND ${CMAKE_COMMAND} -E env
          bash -c "set -e; tmp=$(mktemp -d); cp -R ${CMAKE_BINARY_DIR}/optical/* $tmp/; printf '%s\n' '# units_x: angstrom' '# units_y: frac' '# status: BAD' '450, 0.4' > $tmp/sipm_pde.csv; $<TARGET_FILE:ccb_stave_sim> --particle proton --energy 100 --nevents 1 --seed 1 --optical-dir $tmp --strict-optical --output $tmp/out.root; ec=$?; rm -rf $tmp; exit $ec")
set_tests_properties(ccb_stave_strict_optical_bad_units PROPERTIES
  WILL_FAIL TRUE)
