#pragma once

#include <cstdint>
#include <string>

namespace ccb::build {

struct BuildIdentity {
  std::string schema;
  std::string superproject_commit;
  std::string sipm_core_commit;
  bool source_tree_clean_at_configure = false;
  std::string cmake_version;
  std::string cxx_compiler_id;
  std::string cxx_compiler_version;
  std::string cxx_compiler_path;
  std::string geant4_version;
  std::string executable_sha256;
  std::uint64_t executable_bytes = 0;
  std::string executable_identity_status;
};

// Observe the exact running executable plus compile-time source/toolchain labels.
// This is build/execution provenance only; it does not validate detector physics.
BuildIdentity CurrentBuildIdentity();

// Canonical compact JSON suitable for a pre-event runtime provenance probe.
std::string RenderBuildIdentityJson();

}  // namespace ccb::build
