// OpticalTables.hh — versioned optical property tables loaded from CSV.
// Every table records the file path + sha256 so runs are reproducible and the
// PDE/reflectivity/attenuation curves are never bare hard-coded constants.
#ifndef CCB_OPTICALTABLES_HH
#define CCB_OPTICALTABLES_HH

#include <string>
#include <vector>
#include <map>

// One (x, y) curve read from a two-column CSV with a provenance header.
struct OpticalCurve {
  std::vector<double> x;       // e.g. wavelength [nm] or photon energy [eV]
  std::vector<double> y;       // e.g. PDE, reflectivity, attenuation length
  std::string path;            // source CSV path
  std::string sha256;          // content hash (provenance)
  std::string units_x, units_y;
  std::string source_note;     // free-text provenance from the CSV header

  // Linear interpolation; clamps to the endpoints outside the tabulated range.
  double Interp(double xq) const;
  bool Empty() const { return x.empty(); }
};

class OpticalTables {
 public:
  // Loads every *.csv in dir keyed by stem (e.g. "sipm_pde"). Missing files are
  // tolerated (curve is Empty); callers decide whether that is fatal.
  static OpticalTables LoadDir(const std::string& dir);

  const OpticalCurve& Get(const std::string& key) const;
  bool Has(const std::string& key) const { return curves_.count(key) > 0; }

  // Wavelength [nm] <-> photon energy [eV] helper (hc = 1239.841984 eV*nm).
  static double NmToEV(double nm) { return 1239.841984 / nm; }
  static double EVToNm(double eV) { return 1239.841984 / eV; }

  const std::map<std::string, OpticalCurve>& All() const { return curves_; }

 private:
  std::map<std::string, OpticalCurve> curves_;
  static OpticalCurve LoadCsv(const std::string& path);
};

#endif  // CCB_OPTICALTABLES_HH
