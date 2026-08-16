#pragma once

namespace ccb::build {

// Exact ccb-sipm-core gitlink compiled into ccb_stave_sim.
// tests/test_sipm_compiled_core_provenance.py requires this literal to match
// the superproject gitlink, so advancing the submodule without updating the
// executable provenance fails closed in protected CI.
inline constexpr char kSipmCoreCommit[] =
    "3627dc87137a9f33f511a755671414b11853c0a0";

}  // namespace ccb::build
