// Canonical float serialization for provenance digests (#986 GEOMETRY_DIGEST_V2).
#ifndef CCB_CANONICAL_FORMAT_HH
#define CCB_CANONICAL_FORMAT_HH

#include <iomanip>
#include <sstream>
#include <string>

inline std::string CanonFloat(double v) {
  std::ostringstream os;
  os << std::setprecision(17) << std::defaultfloat << v;
  return os.str();
}

#endif  // CCB_CANONICAL_FORMAT_HH
