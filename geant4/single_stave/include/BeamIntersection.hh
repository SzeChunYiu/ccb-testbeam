// BeamIntersection.hh — geometry-aware primary preflight (issue #999 / ADR-0003).
// Uses DetectorConstruction half-extents; does NOT duplicate geometry limits in
// AppConfig.
#ifndef CCB_BEAMINTERSECTION_HH
#define CCB_BEAMINTERSECTION_HH

#include "AppConfig.hh"
#include "DetectorConstruction.hh"

#include "G4SystemOfUnits.hh"

#include <cmath>
#include <string>

struct BeamIntersectionResult {
  bool intersects = false;
  bool enters_neg_z_face = false;
  double entry_cm[3] = {0, 0, 0};
  double exit_cm[3] = {0, 0, 0};
  double path_length_cm = 0;
  double launch_cm[3] = {0, 0, 0};
  double direction[3] = {0, 0, 1};
  std::string reason = "ok";
};

namespace ccb {
namespace detail {

inline bool ray_aabb(const double o[3], const double d[3], const double half[3],
                     double& t_enter, double& t_exit) {
  const double eps = 1e-12;
  double tmin = -1.0e300;
  double tmax = 1.0e300;
  for (int i = 0; i < 3; ++i) {
    if (std::fabs(d[i]) < eps) {
      if (std::fabs(o[i]) > half[i]) return false;
      continue;
    }
    const double inv = 1.0 / d[i];
    double t1 = (-half[i] - o[i]) * inv;
    double t2 = (half[i] - o[i]) * inv;
    if (t1 > t2) {
      const double tmp = t1;
      t1 = t2;
      t2 = tmp;
    }
    if (t1 > tmin) tmin = t1;
    if (t2 < tmax) tmax = t2;
    if (tmin > tmax) return false;
  }
  if (tmax < 0.0) return false;
  t_enter = (tmin >= 0.0) ? tmin : 0.0;
  t_exit = tmax;
  return true;
}

}  // namespace detail

// Analytical preflight matching PrimaryGeneratorAction launch convention.
inline BeamIntersectionResult ValidatePrimaryAgainstStave(const AppConfig& cfg) {
  BeamIntersectionResult r;
  const double hx = DetectorConstruction::kStaveHalfX / CLHEP::cm;
  const double hy = DetectorConstruction::kStaveHalfY / CLHEP::cm;
  const double hz = DetectorConstruction::kStaveHalfZ / CLHEP::cm;
  const double half[3] = {hx, hy, hz};

  const double th = cfg.theta_deg * deg;
  const double ph = cfg.phi_deg * deg;
  r.direction[0] = std::sin(th) * std::cos(ph);
  r.direction[1] = std::sin(th) * std::sin(ph);
  r.direction[2] = std::cos(th);

  // PrimaryGeneratorAction: z0 = -kStaveHalfZ - 1 mm
  r.launch_cm[0] = cfg.hit_x_cm;
  r.launch_cm[1] = cfg.hit_y_cm;
  r.launch_cm[2] = -hz - 0.1;  // 1 mm in cm

  const bool outside_face =
      (std::fabs(cfg.hit_x_cm) > hx) || (std::fabs(cfg.hit_y_cm) > hy);

  double t_enter = 0.0;
  double t_exit = 0.0;
  r.intersects = detail::ray_aabb(r.launch_cm, r.direction, half, t_enter, t_exit);
  if (r.intersects) {
    for (int i = 0; i < 3; ++i) {
      r.entry_cm[i] = r.launch_cm[i] + t_enter * r.direction[i];
      r.exit_cm[i] = r.launch_cm[i] + t_exit * r.direction[i];
    }
    const double dx = r.exit_cm[0] - r.entry_cm[0];
    const double dy = r.exit_cm[1] - r.entry_cm[1];
    const double dz = r.exit_cm[2] - r.entry_cm[2];
    r.path_length_cm = std::sqrt(dx * dx + dy * dy + dz * dz);
    r.enters_neg_z_face =
        (std::fabs(r.entry_cm[2] + hz) <= 1e-6) &&
        (std::fabs(r.entry_cm[0]) <= hx + 1e-6) &&
        (std::fabs(r.entry_cm[1]) <= hy + 1e-6);
  }

  if (cfg.theta_deg >= 90.0) {
    r.reason = "theta_deg >= 90 (primary not toward +z face)";
  } else if (outside_face) {
    r.reason = "hit_x/hit_y outside stave face";
  } else if (!r.intersects) {
    r.reason = "ray_misses_scintillator_aabb";
  } else if (!r.enters_neg_z_face) {
    r.reason = "intersection_does_not_enter_neg_z_face";
  } else {
    r.reason = "ok";
  }
  return r;
}

}  // namespace ccb

#endif  // CCB_BEAMINTERSECTION_HH
