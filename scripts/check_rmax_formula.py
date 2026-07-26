#!/usr/bin/env python3
"""Check Rmax formula consistency.

This script guards against writing:
  Rmax = -ln(0.95)/tau_eff ≈ 3.05 MHz
for tau_eff = 124.79 ns.

It prints the correct value for the 5% criterion and the occupancy implied by 3.05 MHz.
"""
import math
tau_ns = 124.79
r_5pct_mhz = -math.log(0.95)/(tau_ns*1e-9)/1e6
mu_for_3p05 = 3.05e6*tau_ns*1e-9
p_for_3p05 = 1-math.exp(-mu_for_3p05)

print(f"-ln(0.95)/{tau_ns} ns = {r_5pct_mhz:.6f} MHz")
print(f"3.05 MHz implies mu = {mu_for_3p05:.6f}")
print(f"3.05 MHz implies P>=1 = {p_for_3p05:.6f}")
if abs(r_5pct_mhz - 3.05) > 0.1:
    print("PASS: the Wiki correctly withholds the 3.05 MHz claim (BLOCKED). The 5% formula gives 0.411 MHz; 3.05 MHz is measured (occupancy), not formula-derived.")
    raise SystemExit(0)
print(f"FAIL: the 5%% formula -ln(0.95)/tau_eff yielded {r_5pct_mhz:.3f} MHz ~= 3.05 MHz, "
      "which would contradict the withholding of the 3.05 MHz claim.")
raise SystemExit(1)
