// NeutronTimecutPolicy.hh — QGSP_BIC neutron tracking-time cut resolver (#1091).
#ifndef CCB_NEUTRON_TIMECUT_POLICY_HH
#define CCB_NEUTRON_TIMECUT_POLICY_HH

#include <string>

struct NeutronTimecutPolicy {
  std::string policy_id;
  double time_cut_us = 0.0;
  std::string status;
  std::string adr;
  bool claims_authorized = false;

  static bool Resolve(const std::string& policy_id, NeutronTimecutPolicy& out,
                      std::string& error);
};

#endif  // CCB_NEUTRON_TIMECUT_POLICY_HH
