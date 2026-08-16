// ActionInitialization.hh — wires the user actions together (master + worker).
#ifndef CCB_ACTIONINITIALIZATION_HH
#define CCB_ACTIONINITIALIZATION_HH

#include "G4VUserActionInitialization.hh"
#include "AppConfig.hh"
#include "OpticalTables.hh"

class ActionInitialization : public G4VUserActionInitialization {
 public:
  ActionInitialization(const AppConfig& cfg, const OpticalTables& tables,
                       const std::string& geometry_hash,
                       const std::string& physics_hash,
                       const std::string& optical_hash);
  void Build() const override;
  void BuildForMaster() const override;

 private:
  AppConfig cfg_;
  OpticalTables tables_;
  std::string geometry_hash_;
  std::string physics_hash_;
  std::string optical_hash_;
};

#endif  // CCB_ACTIONINITIALIZATION_HH
