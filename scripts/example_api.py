# Author: Alessandro Previti
"""Run with: python scripts/example_api.py (after installing Interval Finder)."""
import z3
from interval_finder import VarIntervalFinder, verify_intervals

x = z3.Int("x")
formula = z3.Or(z3.And(x >= 0, x <= 2), x == 5)

# Omit the variable list to use automatic discovery.
finder = VarIntervalFinder(formula)
print("Domain of x:", flush=True)
intervals = finder.get_intervals(x, timeout=10)
print()

correct, message = verify_intervals(formula, None, x, intervals, timeout=10)
print(f"Verification: {message}")
if not correct:
    raise SystemExit(1)
