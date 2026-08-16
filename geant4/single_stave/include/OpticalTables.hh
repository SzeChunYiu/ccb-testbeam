// OpticalTables.hh — versioned optical property tables loaded from CSV.
// Every table records the file path + sha256 so runs are reproducible and the
// PDE/reflectivity/attenuation curves are never bare hard-coded constants.
// Issues #978/#980: strict mode is semantically fail-closed on units, y-ranges,
// malformed rows, and duplicate wavelengths.
#ifndef CCB_OPTICALTABLES_HH
#define CCB_OPTICALTABLES_HH

#include <string>
#include <vector>
#include <map>

// One (x, y) curve read from a two-column CSV with a provenance header.
struct OpticalCurve {
  std::vector<double> x;       // e.g. wavelength [nm]
  std::vector<double> y;       // e.g. PDE, reflectivity, attenuation length
  std::string path;            // source CSV path
  std::string sha256;          // content hash (provenance)
  std::string units_x, units_y;
  std::string source_note;     // free-text provenance from the CSV header
  std::string status_note;     // from '# status:' header when present
  std::vector<std::string> parse_errors;  // malformed rows / extra tokens
  int skipped_malformed_rows = 0;
  std::string validation_status = "UNCHECKED";  // OK | FAILED | EMPTY

  // Linear interpolation; clamps to the endpoints outside the tabulated range.
  double Interp(double xq) const;
  bool Empty() const { return x.empty(); }
};

class OpticalTables {
 public:
  // Loads every *.csv in dir keyed by stem (e.g. "sipm_pde"). When ``strict``
  // is true, LoadCsv retains parse errors that ValidateRequired treats as
  // fatal; permissive mode still records them for metadata.
  static OpticalTables LoadDir(const std::string& dir, bool strict = false);

  // Validate required tables: presence, units, y-range, monotonicity, and
  // zero tolerance for malformed rows / extra tokens / duplicate x.
  std::vector<std::string> ValidateRequired(
      const std::vector<std::string>& required_keys) const;

  const OpticalCurve& Get(const std::string& key) const;
  bool Has(const std::string& key) const { return curves_.count(key) > 0; }

  static double NmToEV(double nm) { return 1239.841984 / nm; }
  static double EVToNm(double eV) { return 1239.841984 / eV; }

  const std::map<std::string, OpticalCurve>& All() const { return curves_; }

  // True if any loaded curve reported parse/schema problems.
  bool AnyInvalid() const;

 private:
  std::map<std::string, OpticalCurve> curves_;
  static OpticalCurve LoadCsv(const std::string& path);
};

#endif  // CCB_OPTICALTABLES_HH
