#include "OpticalTables.hh"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <cctype>
#include <stdexcept>
#include <unordered_map>

namespace fs = std::filesystem;

namespace {
// Minimal, dependency-free SHA-256 so table provenance is recorded even without
// linking a crypto library. Reference implementation (public-domain style).
class Sha256 {
 public:
  Sha256() { Reset(); }
  void Update(const unsigned char* data, size_t len) {
    for (size_t i = 0; i < len; ++i) {
      buffer_[buflen_++] = data[i];
      if (buflen_ == 64) { Transform(); bitlen_ += 512; buflen_ = 0; }
    }
  }
  std::string HexDigest() {
    unsigned char hash[32];
    Final(hash);
    std::ostringstream os;
    for (int i = 0; i < 32; ++i)
      os << std::hex << std::setw(2) << std::setfill('0') << (int)hash[i];
    return os.str();
  }

 private:
  uint32_t state_[8];
  unsigned char buffer_[64];
  uint32_t buflen_ = 0;
  uint64_t bitlen_ = 0;
  static uint32_t Rotr(uint32_t x, uint32_t n) { return (x >> n) | (x << (32 - n)); }
  void Reset() {
    buflen_ = 0; bitlen_ = 0;
    state_[0]=0x6a09e667; state_[1]=0xbb67ae85; state_[2]=0x3c6ef372;
    state_[3]=0xa54ff53a; state_[4]=0x510e527f; state_[5]=0x9b05688c;
    state_[6]=0x1f83d9ab; state_[7]=0x5be0cd19;
  }
  void Transform() {
    static const uint32_t k[64] = {
      0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
      0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
      0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
      0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
      0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
      0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
      0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
      0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
    uint32_t m[64], a,b,c,d,e,f,g,h;
    for (int i = 0, j = 0; i < 16; ++i, j += 4)
      m[i] = (buffer_[j]<<24)|(buffer_[j+1]<<16)|(buffer_[j+2]<<8)|(buffer_[j+3]);
    for (int i = 16; i < 64; ++i) {
      uint32_t s0 = Rotr(m[i-15],7)^Rotr(m[i-15],18)^(m[i-15]>>3);
      uint32_t s1 = Rotr(m[i-2],17)^Rotr(m[i-2],19)^(m[i-2]>>10);
      m[i] = m[i-16]+s0+m[i-7]+s1;
    }
    a=state_[0];b=state_[1];c=state_[2];d=state_[3];
    e=state_[4];f=state_[5];g=state_[6];h=state_[7];
    for (int i = 0; i < 64; ++i) {
      uint32_t S1 = Rotr(e,6)^Rotr(e,11)^Rotr(e,25);
      uint32_t ch = (e&f)^((~e)&g);
      uint32_t t1 = h+S1+ch+k[i]+m[i];
      uint32_t S0 = Rotr(a,2)^Rotr(a,13)^Rotr(a,22);
      uint32_t maj = (a&b)^(a&c)^(b&c);
      uint32_t t2 = S0+maj;
      h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
    }
    state_[0]+=a;state_[1]+=b;state_[2]+=c;state_[3]+=d;
    state_[4]+=e;state_[5]+=f;state_[6]+=g;state_[7]+=h;
  }
  void Final(unsigned char* hash) {
    uint64_t total = bitlen_ + (uint64_t)buflen_ * 8;
    buffer_[buflen_++] = 0x80;
    if (buflen_ > 56) { while (buflen_ < 64) buffer_[buflen_++] = 0; Transform(); buflen_ = 0; }
    while (buflen_ < 56) buffer_[buflen_++] = 0;
    for (int i = 7; i >= 0; --i) buffer_[buflen_++] = (total >> (i * 8)) & 0xff;
    Transform();
    for (int i = 0; i < 8; ++i)
      for (int j = 0; j < 4; ++j)
        hash[i*4+j] = (state_[i] >> (24 - j*8)) & 0xff;
  }
};

std::string HashFile(const std::string& path) {
  std::ifstream f(path, std::ios::binary);
  if (!f) return "";
  Sha256 h;
  char buf[8192];
  while (f) {
    f.read(buf, sizeof(buf));
    h.Update(reinterpret_cast<unsigned char*>(buf), f.gcount());
  }
  return h.HexDigest();
}

std::string trim(const std::string& s) {
  size_t a = s.find_first_not_of(" \t\r\n");
  if (a == std::string::npos) return "";
  size_t b = s.find_last_not_of(" \t\r\n");
  return s.substr(a, b - a + 1);
}

std::string lower(std::string s) {
  for (char& c : s) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
  return s;
}

enum class YPolicy { NonNegative, UnitInterval, PositiveLength };

struct PropSchema {
  const char* units_x;   // required exact token after normalize
  const char* units_y;   // required exact token after normalize
  YPolicy y_policy;
};

// Canonical unit tokens consumers assume (FillFromCurve / PdeAt).
const std::unordered_map<std::string, PropSchema>& Schemas() {
  static const std::unordered_map<std::string, PropSchema> s = {
      {"scintillator_emission", {"nm", "rel", YPolicy::NonNegative}},
      {"scintillator_absorption", {"nm", "cm", YPolicy::PositiveLength}},
      {"y11_emission", {"nm", "rel", YPolicy::NonNegative}},
      {"y11_absorption", {"nm", "mm", YPolicy::PositiveLength}},
      {"y11_bulk_attenuation", {"nm", "cm", YPolicy::PositiveLength}},
      {"tio2_reflectivity", {"nm", "frac", YPolicy::UnitInterval}},
      {"sipm_pde", {"nm", "frac", YPolicy::UnitInterval}},
  };
  return s;
}

std::string NormalizeUnit(std::string u) {
  u = lower(trim(u));
  // Strip parenthetical notes: "frac  (PDE in [0,1])" -> "frac"
  auto sp = u.find_first_of(" \t(");
  if (sp != std::string::npos) u = u.substr(0, sp);
  if (u == "fraction" || u == "probability") u = "frac";
  if (u == "relative" || u == "a.u." || u == "au") u = "rel";
  return u;
}

std::vector<std::string> CurveSchemaErrors(const OpticalCurve& c,
                                           const std::string& key) {
  std::vector<std::string> errs;
  if (c.Empty()) {
    errs.push_back("required optical table '" + key +
                   "' is missing or empty (no usable rows)");
    return errs;
  }
  for (const auto& pe : c.parse_errors) errs.push_back(pe);
  if (c.skipped_malformed_rows > 0) {
    errs.push_back("table '" + key + "' silently discarded " +
                   std::to_string(c.skipped_malformed_rows) +
                   " malformed row(s); strict mode forbids row dropping");
  }
  if (c.units_x.empty())
    errs.push_back("table '" + key +
                   "' has no '# units_x:' provenance header (x units ambiguous)");
  if (c.units_y.empty())
    errs.push_back("table '" + key +
                   "' has no '# units_y:' provenance header (y units ambiguous)");
  if (c.status_note.empty())
    errs.push_back("table '" + key +
                   "' has no '# status:' provenance header");

  auto it = Schemas().find(key);
  if (it != Schemas().end()) {
    const auto& sch = it->second;
    const std::string ux = NormalizeUnit(c.units_x);
    const std::string uy = NormalizeUnit(c.units_y);
    if (!c.units_x.empty() && ux != sch.units_x) {
      errs.push_back("table '" + key + "' units_x='" + c.units_x +
                     "' is not the required '" + sch.units_x +
                     "' (no silent unit conversion)");
    }
    if (!c.units_y.empty() && uy != sch.units_y) {
      errs.push_back("table '" + key + "' units_y='" + c.units_y +
                     "' is not the required '" + sch.units_y +
                     "' (no silent percent/fraction conversion)");
    }
    for (size_t i = 0; i < c.y.size(); ++i) {
      const double yv = c.y[i];
      if (sch.y_policy == YPolicy::UnitInterval && (yv < 0.0 || yv > 1.0)) {
        errs.push_back("table '" + key + "' y=" + std::to_string(yv) +
                       " outside required fraction range [0,1] at row " +
                       std::to_string(i));
        break;
      }
      if (sch.y_policy == YPolicy::NonNegative && yv < 0.0) {
        errs.push_back("table '" + key + "' y=" + std::to_string(yv) +
                       " is negative (relative intensity must be >=0) at row " +
                       std::to_string(i));
        break;
      }
      if (sch.y_policy == YPolicy::PositiveLength && !(yv > 0.0)) {
        errs.push_back("table '" + key + "' y=" + std::to_string(yv) +
                       " is not a strictly positive attenuation/absorption "
                       "length at row " + std::to_string(i));
        break;
      }
    }
  }

  for (size_t i = 0; i < c.x.size(); ++i) {
    if (!std::isfinite(c.x[i]) || !std::isfinite(c.y[i])) {
      errs.push_back("table '" + key + "' has a non-finite point at row " +
                     std::to_string(i));
      break;
    }
  }
  for (double xv : c.x) {
    if (xv < 100.0 || xv > 2000.0) {
      errs.push_back("table '" + key + "' x=" + std::to_string(xv) +
                     " nm is outside the valid wavelength range [100,2000] "
                     "(unit/range error)");
      break;
    }
  }
  for (size_t i = 1; i < c.x.size(); ++i) {
    if (c.x[i] < c.x[i - 1]) {
      errs.push_back("table '" + key +
                     "' x is not ascending at row " + std::to_string(i));
      break;
    }
    if (c.x[i] == c.x[i - 1]) {
      errs.push_back("table '" + key +
                     "' has duplicate wavelength at row " + std::to_string(i));
      break;
    }
  }
  return errs;
}
}  // namespace

double OpticalCurve::Interp(double xq) const {
  if (x.empty()) return 0.0;
  if (xq <= x.front()) return y.front();
  if (xq >= x.back()) return y.back();
  auto it = std::upper_bound(x.begin(), x.end(), xq);
  size_t hi = static_cast<size_t>(it - x.begin());
  size_t lo = hi - 1;
  double t = (xq - x[lo]) / (x[hi] - x[lo]);
  return y[lo] + t * (y[hi] - y[lo]);
}

OpticalCurve OpticalTables::LoadCsv(const std::string& path) {
  OpticalCurve c;
  c.path = path;
  std::ifstream f(path);
  if (!f) return c;  // empty curve; caller decides
  std::string line;
  size_t line_no = 0;
  while (std::getline(f, line)) {
    ++line_no;
    std::string t = trim(line);
    if (t.empty()) continue;
    if (t[0] == '#') {
      if (t.find("units_x:") != std::string::npos)
        c.units_x = trim(t.substr(t.find("units_x:") + 8));
      else if (t.find("units_y:") != std::string::npos)
        c.units_y = trim(t.substr(t.find("units_y:") + 8));
      else if (t.find("source:") != std::string::npos)
        c.source_note += trim(t.substr(t.find("source:") + 7)) + "; ";
      else if (t.find("status:") != std::string::npos)
        c.status_note = trim(t.substr(t.find("status:") + 7));
      continue;
    }
    for (char& ch : t) if (ch == ',') ch = ' ';
    std::istringstream is(t);
    double xv, yv;
    std::string extra;
    if (!(is >> xv >> yv)) {
      c.skipped_malformed_rows += 1;
      c.parse_errors.push_back("table '" + path + "' line " +
                               std::to_string(line_no) +
                               " is not two numeric columns: '" + t + "'");
      continue;
    }
    if (is >> extra) {
      c.parse_errors.push_back("table '" + path + "' line " +
                               std::to_string(line_no) +
                               " has extra token(s) after two columns: '" + t + "'");
      continue;
    }
    c.x.push_back(xv);
    c.y.push_back(yv);
  }
  if (c.x.size() > 1 && c.x.front() > c.x.back()) {
    std::reverse(c.x.begin(), c.x.end());
    std::reverse(c.y.begin(), c.y.end());
  }
  c.sha256 = HashFile(path);
  return c;
}

OpticalTables OpticalTables::LoadDir(const std::string& dir, bool strict) {
  OpticalTables t;
  if (!fs::exists(dir)) {
    std::cerr << (strict ? "error[strict]: " : "warning: ")
              << "optical table directory not found: " << dir << "\n";
    return t;
  }
  for (const auto& e : fs::directory_iterator(dir)) {
    if (e.path().extension() == ".csv") {
      std::string key = e.path().stem().string();
      OpticalCurve curve = LoadCsv(e.path().string());
      auto errs = CurveSchemaErrors(curve, key);
      curve.validation_status = errs.empty() ? "OK" : (curve.Empty() ? "EMPTY" : "FAILED");
      t.curves_[key] = std::move(curve);
    }
  }
  return t;
}

std::vector<std::string> OpticalTables::ValidateRequired(
    const std::vector<std::string>& required_keys) const {
  std::vector<std::string> errs;
  for (const auto& key : required_keys) {
    auto it = curves_.find(key);
    if (it == curves_.end()) {
      errs.push_back("required optical table '" + key +
                     "' is missing (no '" + key + ".csv' was loaded)");
    } else {
      auto ce = CurveSchemaErrors(it->second, key);
      errs.insert(errs.end(), ce.begin(), ce.end());
    }
  }
  return errs;
}

bool OpticalTables::AnyInvalid() const {
  for (const auto& kv : curves_) {
    if (kv.second.validation_status == "FAILED" ||
        !kv.second.parse_errors.empty() ||
        kv.second.skipped_malformed_rows > 0) {
      return true;
    }
  }
  return false;
}

const OpticalCurve& OpticalTables::Get(const std::string& key) const {
  static const OpticalCurve empty;
  auto it = curves_.find(key);
  return it == curves_.end() ? empty : it->second;
}
