#include "OpticalConstantsLedger.hh"
#include "Sha256.hh"

#include <cctype>
#include <fstream>
#include <iostream>
#include <sstream>

namespace {
std::string trim(const std::string& s) {
  size_t a = s.find_first_not_of(" \t\r\n");
  if (a == std::string::npos) return "";
  size_t b = s.find_last_not_of(" \t\r\n");
  return s.substr(a, b - a + 1);
}
}  // namespace

OpticalConstantsLedger OpticalConstantsLedger::LoadFile(const std::string& path) {
  OpticalConstantsLedger led;
  led.path = path;
  std::ifstream f(path);
  if (!f) {
    led.load_errors.push_back("optical constants ledger not found: " + path);
    return led;
  }
  std::ostringstream raw;
  std::string line;
  while (std::getline(f, line)) {
    raw << line << '\n';
    std::string t = trim(line);
    if (t.empty() || t[0] == '#') continue;
    auto eq = t.find('=');
    if (eq == std::string::npos) {
      led.load_errors.push_back("ledger line missing '=': " + t);
      continue;
    }
    std::string key = trim(t.substr(0, eq));
    std::string val = trim(t.substr(eq + 1));
    if (key.empty()) {
      led.load_errors.push_back("ledger empty key in: " + t);
      continue;
    }
    led.values[key] = val;
  }
  led.sha256 = Sha256::hex(raw.str());
  return led;
}

std::string OpticalConstantsLedger::GetString(const std::string& key,
                                              const std::string& def) const {
  auto it = values.find(key);
  return it == values.end() ? def : it->second;
}

double OpticalConstantsLedger::GetDouble(const std::string& key, double def) const {
  auto it = values.find(key);
  if (it == values.end()) return def;
  try {
    size_t idx = 0;
    double v = std::stod(it->second, &idx);
    if (idx != it->second.size()) return def;
    return v;
  } catch (...) {
    return def;
  }
}
