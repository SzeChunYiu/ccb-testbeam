#include "NeutronTimecutPolicy.hh"

#include <cmath>

namespace {
struct KnownPolicy {
  const char* id;
  double time_cut_us;
  const char* status;
  const char* adr;
  bool claims_authorized;
};

// Values mirror configs/transport/neutron_timecut_registry.json (ADR-0005).
constexpr KnownPolicy kPolicies[] = {
    {"pin_qgsp_bic_default_10us", 10.0, "PINNED_REFERENCE_DEFAULT",
     "docs/adr/ADR-0005-g4-step-convergence-neutron-timecut.md", false},
    {"diagnostic_extended_or_disabled", 1.0e9, "HYPOTHESIS",
     "docs/adr/ADR-0005-g4-step-convergence-neutron-timecut.md", false},
    {"wiring_test_1ns", 1.0e-3, "WIRING_TEST",
     "docs/adr/ADR-0005-g4-step-convergence-neutron-timecut.md", false},
};
}  // namespace

bool NeutronTimecutPolicy::Resolve(const std::string& policy_id,
                                   NeutronTimecutPolicy& out,
                                   std::string& error) {
  if (policy_id.empty()) {
    error = "neutron_timecut_policy_id is unset (issue #1091 fail-closed)";
    return false;
  }
  for (const auto& p : kPolicies) {
    if (policy_id == p.id) {
      out.policy_id = policy_id;
      out.time_cut_us = p.time_cut_us;
      out.status = p.status;
      out.adr = p.adr;
      out.claims_authorized = p.claims_authorized;
      if (!std::isfinite(out.time_cut_us) || out.time_cut_us <= 0.0) {
        error = "policy " + policy_id + " has invalid neutron_time_cut_us";
        return false;
      }
      return true;
    }
  }
  error = "unknown neutron_timecut_policy_id: " + policy_id;
  return false;
}
