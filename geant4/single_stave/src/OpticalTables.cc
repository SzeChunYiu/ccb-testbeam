#include "OpticalTables.hh"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>

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
}  // namespace

double OpticalCurve::Interp(double xq) const {
  if (x.empty()) return 0.0;
  if (xq <= x.front()) return y.front();
  if (xq >= x.back()) return y.back();
  auto it = std::upper_bound(x.begin(), x.end(), xq);
  size_t hi = it - x.begin();
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
  while (std::getline(f, line)) {
    std::string t = trim(line);
    if (t.empty()) continue;
    if (t[0] == '#') {
      // Provenance header lines, e.g. "# units_x: nm" / "# source: <ref>".
      if (t.find("units_x:") != std::string::npos)
        c.units_x = trim(t.substr(t.find("units_x:") + 8));
      else if (t.find("units_y:") != std::string::npos)
        c.units_y = trim(t.substr(t.find("units_y:") + 8));
      else if (t.find("source:") != std::string::npos)
        c.source_note += trim(t.substr(t.find("source:") + 7)) + "; ";
      continue;
    }
    // Accept comma or whitespace separated two-column rows.
    for (char& ch : t) if (ch == ',') ch = ' ';
    std::istringstream is(t);
    double xv, yv;
    if (is >> xv >> yv) { c.x.push_back(xv); c.y.push_back(yv); }
  }
  // Ensure ascending x for interpolation.
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
    // G4-003: do NOT throw here. Returning empty curves lets the caller
    // (DetectorConstruction::EnforceOpticalTables) convert the resulting
    // "required table missing" errors into a clean G4Exception(FatalException)
    // abort in strict mode, or a warning in dev mode. Throwing here would
    // bypass Geant4 and terminate the process uncleanly.
    std::cerr << (strict ? "error[strict]: " : "warning: ")
              << "optical table directory not found: " << dir << "\n";
    return t;
  }
  for (const auto& e : fs::directory_iterator(dir)) {
    if (e.path().extension() == ".csv") {
      std::string key = e.path().stem().string();
      t.curves_[key] = LoadCsv(e.path().string());
    }
  }
  return t;
}

namespace {
// G4-003 schema checks for one loaded curve. x is wavelength [nm] per the
// documented table contract; catches missing/empty tables, missing unit
// provenance, non-finite points, gross unit/range errors (table given in
// meters or Angstrom instead of nm), and non-monotonic x.
std::vector<std::string> CurveSchemaErrors(const OpticalCurve& c,
                                           const std::string& key) {
  std::vector<std::string> errs;
  if (c.Empty()) {
    errs.push_back("required optical table '" + key +
                   "' is missing or empty (no usable rows)");
    return errs;
  }
  if (c.units_x.empty())
    errs.push_back("table '" + key +
                   "' has no '# units_x:' provenance header (x units ambiguous)");
  if (c.units_y.empty())
    errs.push_back("table '" + key +
                   "' has no '# units_y:' provenance header (y units ambiguous)");
  for (size_t i = 0; i < c.x.size(); ++i) {
    if (!std::isfinite(c.x[i]) || !std::isfinite(c.y[i])) {
      errs.push_back("table '" + key + "' has a non-finite point at row " +
                     std::to_string(i));
      break;
    }
  }
  // Wavelength [nm] physical window. Header documents x as wavelength_nm;
  // values outside [100, 2000] nm signal a unit/range error (meters ~1e-7,
  // Angstrom ~1e4, or a stray zero/negative).
  for (double xv : c.x) {
    if (xv < 100.0 || xv > 2000.0) {
      errs.push_back("table '" + key + "' x=" + std::to_string(xv) +
                     " nm is outside the valid wavelength range [100,2000] "
                     "(unit/range error)");
      break;
    }
  }
  // LoadCsv normalizes a descending grid to ascending; non-monotonic x here
  // is a schema violation that would corrupt interpolation.
  for (size_t i = 1; i < c.x.size(); ++i) {
    if (c.x[i] <= c.x[i - 1]) {
      errs.push_back("table '" + key +
                     "' x is not strictly ascending at row " + std::to_string(i));
      break;
    }
  }
  return errs;
}
}  // namespace

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

const OpticalCurve& OpticalTables::Get(const std::string& key) const {
  static const OpticalCurve empty;
  auto it = curves_.find(key);
  return it == curves_.end() ? empty : it->second;
}
