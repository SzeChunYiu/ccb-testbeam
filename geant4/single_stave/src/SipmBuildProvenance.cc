#include "SipmBuildProvenance.hh"

#include <cstdlib>

namespace {

// Run before main().  The sidecar writer historically read
// CCB_SIPM_CORE_COMMIT from the process environment, which allowed a missing or
// caller-supplied value to masquerade as execution provenance.  Overwrite it
// from a literal compiled into the same executable instead.  A failed setenv
// is a provenance-authorisation failure, so abort before event 0.
const int kBindSipmCoreCommit = []() {
  if (::setenv("CCB_SIPM_CORE_COMMIT", ccb::build::kSipmCoreCommit, 1) != 0) {
    std::abort();
  }
  return 0;
}();

}  // namespace
