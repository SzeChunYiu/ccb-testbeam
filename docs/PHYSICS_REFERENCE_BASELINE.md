# Physics Reference Baseline

Status: **audit support, not scientific closure**. This file records authoritative starting points for #1612/#1602. A reference only authorizes the exact quantity/domain it supports; it does not validate a detector parameter merely because the device/material name matches.

## NIST PSTAR — proton stopping power and range

Primary source:
- NIST PSTAR: https://physics.nist.gov/PhysRefData/Star/Text/PSTAR.html
- NIST STAR introduction / ICRU basis: https://physics.nist.gov/PhysRefData/Star/Text/intro.html
- PSTAR/ASTAR material list: https://physics.nist.gov/PhysRefData/Star/Text/table2.html

Audit constraints:
- PSTAR is explicitly a **proton** stopping-power/range database.
- Material composition/density and kinetic-energy domain must match the comparison.
- A deuteron `E/2` lookup in a proton table is a model/proxy, not direct authoritative deuteron stopping-power evidence.
- The simulation observable compared to PSTAR must represent the intended projectile energy loss/stopping-power quantity; local detector deposit is not automatically equivalent.

## Geant4 — Birks/quenching and electromagnetic stopping tools

Primary software documentation:
- Birks quenching: https://geant4.web.cern.ch/documentation/pipelines/master/bfad_html/ForApplicationDevelopers/Detector/birks.html
- Physics/optical process documentation and `G4EmCalculator`/`G4EmSaturation`: https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/TrackingAndPhysics/physicsProcess.html
- EM reference-manual introduction (`G4EmCalculator`, `G4EmSaturation`): https://geant4.web.cern.ch/documentation/dev/prm_html/PhysicsReferenceManual/electromagnetic/introduction/introduction.html

Audit constraints:
- Birks response is phenomenological rather than a detector-independent first-principles constant.
- Geant4 documentation warns that the effective Birks coefficient depends on delta-ray treatment / production threshold.
- A kB fitted inside a simulation chain is therefore not automatically a measured scintillator constant.
- For stopping-power validation, prefer an observable provided/checked through the appropriate Geant4 energy-loss machinery (for example `G4EmCalculator`) or an explicitly closed projectile energy-loss accounting rather than assuming local sensitive-volume deposit equals projectile total stopping power.

## Hamamatsu S13360-3050CS SiPM

Manufacturer source:
- https://www.hamamatsu.com/jp/en/product/optical-sensors/mppc/mppc_mppc-array/S13360-3050CS.html

Manufacturer page identifies, among other product specifications:
- 3 mm × 3 mm active area;
- 50 µm pixel pitch;
- 3600 pixels;
- spectral response and a typical gain under stated measurement conditions.

Audit constraints:
- PDE, gain, dark count, crosstalk and timing/noise behavior depend on operating conditions such as overvoltage and temperature.
- Manufacturer typical values are **not** a calibration of the installed detector.
- Exact MC values need actual detector bias/temperature/bench provenance or a justified nuisance envelope.

## Kuraray Y-11 wavelength-shifting fibre

Manufacturer sources:
- https://methacrylate.kuraray.com/en/products/psf/wavelength-shiftingfiber/
- https://methacrylate.kuraray.com/en/products/psf/tech/

Audit constraints:
- Kuraray describes Y-11 as a blue-to-green wavelength-shifting fibre and publishes representative spectral/attenuation information.
- The manufacturer explicitly notes that displayed values are representative/condition-dependent and not guaranteed values.
- Installed-fibre attenuation, coupling, reflections, bending, diameter/cladding and propagation timing must therefore be tied to the actual detector geometry/lot or varied as nuisances.

## p+d differential scattering

**No accepting reference bound yet.** The legacy uniform centre-of-mass angle generator remains `UNJUSTIFIED` for quantitative stopping/acceptance transfer until an energy-appropriate authoritative p+d differential cross section is identified, implemented, and sensitivity-tested (#1608/#1606).

## Reference-use rule

For every equation or constant, the audit ledger must record:
1. exact source;
2. exact supported quantity and units;
3. material/device/energy/temperature/operating domain;
4. whether the source is measurement, manufacturer specification, software model or approximation;
5. parameter uncertainty/variation and downstream sensitivity;
6. evidence that the repository implementation uses the same convention.

A real citation with the wrong domain is still a failed justification.