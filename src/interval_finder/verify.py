# Author: Alessandro Previti
"""Check reported numeric intervals and Boolean feasible-value sets."""
from __future__ import annotations

from collections.abc import Iterable
from .core import ValInterval

import z3
import z3.z3util
from .utils import _TimeBudget, _validate_variable


def _is_finite(val):
    """Check if a z3 value is a concrete finite number (not ±oo or None)."""
    if val is None:
        return False
    return z3.is_int_value(val) or z3.is_rational_value(val) or z3.is_bv_value(val)


def _ge(var, val):
    return z3.UGE(var, val) if z3.is_bv(var) else var >= val

def _le(var, val):
    return z3.ULE(var, val) if z3.is_bv(var) else var <= val

def _gt(var, val):
    return z3.UGT(var, val) if z3.is_bv(var) else var > val

def _lt(var, val):
    return z3.ULT(var, val) if z3.is_bv(var) else var < val


def _interval_constraint(var, iv):
    """Build a constraint for var being inside an interval, handling open bounds and ±oo."""
    lo = iv.l_val
    hi = iv.h_val
    parts = []
    if _is_finite(lo):
        parts.append(_gt(var, lo) if iv.l_open else _ge(var, lo))
    if _is_finite(hi):
        parts.append(_lt(var, hi) if iv.h_open else _le(var, hi))
    return z3.And(parts) if parts else z3.BoolVal(True, ctx=var.ctx)


def verify_intervals(
    formula: z3.BoolRef | z3.AstVector,
    variables: Iterable[z3.ExprRef] | None,
    var: z3.ArithRef | z3.BitVecRef,
    intervals: Iterable[ValInterval], *, timeout: float | None = None,
) -> tuple[bool, str]:
    """Check that the interval union equals the target's feasible domain.

    Searches for an infeasible value inside the union and a feasible value
    outside it. Does not check interval ordering or minimal merging.

    Args:
        formula: Boolean formula or parsed assertions.
        variables: Complete free-variable list, including Booleans/non-targets,
            or None for discovery. Completeness is trusted, not checked.
        var: Numeric constant variable in the formula's Z3 context.
        intervals: Candidate intervals with endpoints in the same context;
            bit-vector endpoints use unsigned ordering.
        timeout: Positive finite budget in seconds shared by both checks,
            including setup in this function; None means unlimited.

    Returns:
        (True, message) when both checks prove correctness, or (False, message)
        describing a counterexample. Empty intervals are valid only for UNSAT.

    Raises:
        ValueError: Invalid timeout.
        RuntimeError: A check returns UNKNOWN; correctness is not certified.
        TimeoutError: The cooperative budget expires; no verdict is returned.
    """
    budget = _TimeBudget(timeout)
    ctx = formula.ctx
    if isinstance(formula, z3.AstVector):
        formula = z3.And(formula) if len(formula) else z3.BoolVal(True, ctx=ctx)
    variables_set = set(z3.z3util.get_vars(formula) if variables is None else variables)
    remaining_vars = list(variables_set - {var})

    inside_constraint = (z3.Or([_interval_constraint(var, iv) for iv in intervals])
                         if intervals else z3.BoolVal(False, ctx=ctx))

    # 1) Check no value inside the intervals is unsatisfiable
    if remaining_vars:
        no_sat_inside = z3.And(inside_constraint, z3.ForAll(remaining_vars, z3.Not(formula)))
    else:
        no_sat_inside = z3.And(inside_constraint, z3.Not(formula))

    s1 = z3.Solver(ctx=ctx)
    s1.add(no_sat_inside)
    result = budget.check(s1)
    if result == z3.unknown:
        raise RuntimeError(f"Inside-interval verification returned unknown: {s1.reason_unknown()}")
    if result == z3.sat:
        bad_val = s1.model()[var]
        return False, f"Value {bad_val} is inside intervals but has no satisfying assignment"

    # 2) Check no value outside the intervals is satisfiable
    s2 = z3.Solver(ctx=ctx)
    s2.add(formula)
    s2.add(z3.Not(inside_constraint))
    result = budget.check(s2)
    if result == z3.unknown:
        raise RuntimeError(f"Outside-interval verification returned unknown: {s2.reason_unknown()}")
    if result == z3.sat:
        bad_val = s2.model()[var]
        return False, f"Value {bad_val} is outside intervals but has a satisfying assignment"

    return True, "Intervals are correct"


def verify_boolean_domain(
    formula: z3.BoolRef | z3.AstVector, var: z3.BoolRef,
    values: Iterable[bool], *, timeout: float | None = None,
) -> tuple[bool, str]:
    """Verify a Boolean domain by checking both possible target values.

    Args:
        formula: Boolean formula or parsed assertions.
        var: Bool constant variable in the formula's context.
        values: Reported Python bool values; an empty set represents UNSAT.
        timeout: Positive finite overall budget in seconds for both checks,
            or None for unlimited. Cancellation by Z3 is cooperative.

    Returns:
        (True, message) for an exact domain, or (False, message) for a mismatch.

    Raises:
        ValueError: Invalid target, context, domain values, or timeout.
        RuntimeError: Z3 returns UNKNOWN; correctness is not certified.
        TimeoutError: The time budget expires; no verdict is returned.
    """
    _validate_variable(var, formula.ctx)
    if not z3.is_bool(var):
        raise ValueError('Boolean domain target must be a Bool variable')
    values = set(values)
    if any(type(value) is not bool for value in values):
        raise ValueError('Boolean domains must contain Python bool values')
    budget = _TimeBudget(timeout)
    for value in (False, True):
        solver = z3.Solver(ctx=formula.ctx)
        solver.add(formula)
        solver.add(var == value)
        result = budget.check(solver)
        if result == z3.unknown:
            raise RuntimeError(f'Boolean domain verification returned unknown: {solver.reason_unknown()}')
        if (result == z3.sat) != (value in values):
            return False, f'Boolean value {str(value).lower()} is incorrectly included or omitted'
    return True, 'Boolean domain is correct'
