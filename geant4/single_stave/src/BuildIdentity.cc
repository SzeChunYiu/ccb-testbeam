#include "BuildIdentity.hh"
#include "SipmBuildProvenance.hh"

#include "ccb/sipm/Digest.hh"

#include <cstdint>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>

#ifndef CCB_BUILD_SUPERPROJECT_COMMIT
#define CCB_BUILD_SUPERPROJECT_COMMIT "unconfigured"
#endif
#ifndef CCB_BUILD_SOURCE_CLEAN_AT_CONFIGURE
#define CCB_BUILD_SOURCE_CLEAN_AT_CONFIGURE 0
#endif
#ifndef CCB_BUILD_CMAKE_VERSION
#define CCB_BUILD_CMAKE_VERSION "unconfigured"
#endif
#ifndef CCB_BUILD_CXX_COMPILER_ID
#define CCB_BUILD_CXX_COMPILER_ID "unconfigured"
#endif
#ifndef CCB_BUILD_CXX_COMPILER_VERSION
#define CCB_BUILD_CXX_COMPILER_VERSION "unconfigured"
#endif
#ifndef CCB_BUILD_CXX_COMPILER_PATH
#define CCB_BUILD_CXX_COMPILER_PATH "unconfigured"
#endif
#ifndef CCB_BUILD_GEANT4_VERSION
#define CCB_BUILD_GEANT4_VERSION "unconfigured"
#endif

namespace ccb::build {
namespace {

std::string JsonString(const std::string& value) {
  std::ostringstream os;
  os << '"';
  for (unsigned char c : value) {
    switch (c) {
      case '"': os << "\\\""; break;
      case '\\': os << "\\\\"; break;
      case '\b': os << "\\b"; break;
      case '\f': os << "\\f"; break;
      case '\n': os << "\\n"; break;
      case '\r': os << "\\r"; break;
      case '\t': os << "\\t"; break;
      default:
        if (c < 0x20U) {
          os << "\\u" << std::hex << std::setw(4) << std::setfill('0')
             << static_cast<unsigned>(c) << std::dec;
        } else {
          os << static_cast<char>(c);
        }
    }
  }
  os << '"';
  return os.str();
}

bool ReadSelfExecutable(std::vector<std::uint8_t>* bytes) {
#if defined(__linux__)
  std::ifstream stream("/proc/self/exe", std::ios::binary);
  if (!stream) return false;
  std::vector<char> buffer(1024 * 1024);
  while (stream) {
    stream.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
    const auto count = stream.gcount();
    if (count > 0) {
      const auto* begin = reinterpret_cast<const std::uint8_t*>(buffer.data());
      bytes->insert(bytes->end(), begin, begin + count);
    }
  }
  return stream.eof() && !bytes->empty();
#else
  (void)bytes;
  return false;
#endif
}

}  // namespace

BuildIdentity CurrentBuildIdentity() {
  BuildIdentity result;
  result.schema = "ccb-single-stave-runtime-build-identity/1";
  result.superproject_commit = CCB_BUILD_SUPERPROJECT_COMMIT;
  result.sipm_core_commit = kSipmCoreCommit;
  result.source_tree_clean_at_configure =
      (CCB_BUILD_SOURCE_CLEAN_AT_CONFIGURE != 0);
  result.cmake_version = CCB_BUILD_CMAKE_VERSION;
  result.cxx_compiler_id = CCB_BUILD_CXX_COMPILER_ID;
  result.cxx_compiler_version = CCB_BUILD_CXX_COMPILER_VERSION;
  result.cxx_compiler_path = CCB_BUILD_CXX_COMPILER_PATH;
  result.geant4_version = CCB_BUILD_GEANT4_VERSION;

  std::vector<std::uint8_t> executable;
  if (ReadSelfExecutable(&executable)) {
    result.executable_sha256 = ccb::sipm::Sha256Hex(executable);
    result.executable_bytes = static_cast<std::uint64_t>(executable.size());
    result.executable_identity_status = "PASS_SELF_SHA256";
  } else {
    result.executable_sha256.clear();
    result.executable_bytes = 0;
    result.executable_identity_status = "BLOCKED_SELF_EXECUTABLE_UNAVAILABLE";
  }
  return result;
}

std::string RenderBuildIdentityJson() {
  const auto id = CurrentBuildIdentity();
  std::ostringstream os;
  os << '{'
     << "\"schema\":" << JsonString(id.schema) << ','
     << "\"superproject_commit\":" << JsonString(id.superproject_commit) << ','
     << "\"sipm_core_commit\":" << JsonString(id.sipm_core_commit) << ','
     << "\"source_tree_clean_at_configure\":"
     << (id.source_tree_clean_at_configure ? "true" : "false") << ','
     << "\"cmake_version\":" << JsonString(id.cmake_version) << ','
     << "\"cxx_compiler_id\":" << JsonString(id.cxx_compiler_id) << ','
     << "\"cxx_compiler_version\":" << JsonString(id.cxx_compiler_version) << ','
     << "\"cxx_compiler_path\":" << JsonString(id.cxx_compiler_path) << ','
     << "\"geant4_version\":" << JsonString(id.geant4_version) << ','
     << "\"executable_sha256\":" << JsonString(id.executable_sha256) << ','
     << "\"executable_bytes\":" << id.executable_bytes << ','
     << "\"executable_identity_status\":"
     << JsonString(id.executable_identity_status)
     << '}';
  return os.str();
}

}  // namespace ccb::build
