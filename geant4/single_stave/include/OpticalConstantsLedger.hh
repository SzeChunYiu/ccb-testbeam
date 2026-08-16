// OpticalConstantsLedger.hh — versioned hard-coded optical/material priors (#979).
#ifndef CCB_OPTICALCONSTANTSLEDGER_HH
#define CCB_OPTICALCONSTANTSLEDGER_HH

#include <string>
#include <map>
#include <vector>

// Flat key=value ledger loaded from optical/optical_constants_ledger.conf.
// Missing keys keep AppConfig/DetectorConstruction defaults. Unknown keys are
// recorded but do not abort (forward compatible).
struct OpticalConstantsLedger {
  std::string path;
  std::string sha256;
  std::map<std::string, std::string> values;
  std::vector<std::string> load_errors;

  static OpticalConstantsLedger LoadFile(const std::string& path);

  bool Has(const std::string& key) const { return values.count(key) > 0; }
  std::string GetString(const std::string& key, const std::string& def) const;
  double GetDouble(const std::string& key, double def) const;
};

#endif
