# Author: Alessandro Previti
"""Find numeric intervals and Boolean feasible-value sets for SMT formulas."""
from __future__ import annotations

from collections.abc import Callable, Iterable

import z3
import z3.z3util
from .utils import get_vars, _progress_stage, _TimeBudget, _validate_variable


def _is_concrete(val):
    """Check if a Z3 value is a concrete finite number (not epsilon/oo)."""
    return z3.is_int_value(val) or z3.is_rational_value(val)


def _parse_bound(val, ctx=None):
    """Parse a Z3 optimizer bound, handling epsilon and infinity.
    Returns (concrete_value_or_None, is_open).
    - For concrete values: (val, False)
    - For epsilon-based (e.g. 4+epsilon, 4-epsilon): (concrete_part, True)
    - For oo or -oo: (None, False)  — None signals infinity
    """
    if _is_concrete(val):
        return val, False

    s = val.sexpr()
    if s == 'oo' or s == '(* (- 1) oo)':
        return None, False

    # epsilon-based: pure 'epsilon' means concrete part is 0
    if s == 'epsilon':
        return z3.RatVal(0, 1, ctx=ctx), True

    # Expressions like (* 2.0 epsilon) — pure epsilon multiple, concrete part is 0
    if val.num_args() == 2 and s.startswith('(*') and 'epsilon' in s:
        return z3.RatVal(0, 1, ctx=ctx), True

    # Expressions like (+ 4.0 epsilon) or (+ 4.0 (* (- 1.0) epsilon))
    if val.num_args() == 2 and 'epsilon' in s:
        concrete = val.arg(0)
        if _is_concrete(concrete):
            return concrete, True

    # Fallback: treat as non-concrete / infinity
    return None, False


def _needs_bv_conversion(val, var):
    """Check if val is an integer that needs conversion to BitVec to match var's sort."""
    return val is not None and z3.is_bv(var) and not z3.is_bv_value(val)


def _gt(var, val):
    """var > val, using unsigned comparison for bitvectors."""
    if z3.is_bv(var):
        return z3.UGT(var, val)
    return var > val


def _lt(var, val):
    """var < val, using unsigned comparison for bitvectors."""
    if z3.is_bv(var):
        return z3.ULT(var, val)
    return var < val


class ValueInfo:

    def __init__(self, val, is_sat, v_type):
        self.val = val
        self.is_sat = is_sat
        self.v_type = v_type


class ValInterval:
    """A numeric domain interval with Z3 endpoints in the formula's context.

    Attributes:
        l_val: Lower endpoint; None denotes negative infinity.
        h_val: Upper endpoint; None denotes positive infinity.
        l_open, h_open: Whether the corresponding finite endpoint is excluded.
        l_sat, h_sat: Internal search flags distinguishing feasible boundaries
            from gap values; they are not part of the printed representation.

    Bit-vector endpoints use unsigned ordering. Infinite endpoints print with
    parentheses regardless of the open flags. Returned intervals describe one
    variable's feasible values, not joint assignments across variables.
    """

    l_val: z3.ExprRef | None
    h_val: z3.ExprRef | None
    l_open: bool
    h_open: bool
    l_sat: bool
    h_sat: bool

    def __init__(
        self, l_val: z3.ExprRef | None, h_val: z3.ExprRef | None,
        l_open: bool = False, h_open: bool = False,
        l_sat: bool = True, h_sat: bool = True,
    ) -> None:
        self.l_val = l_val      # None means -infinity
        self.h_val = h_val      # None means +infinity
        self.l_open = l_open    # True = exclusive (open bracket)
        self.h_open = h_open    # True = exclusive (open bracket)
        self.l_sat = l_sat
        self.h_sat = h_sat

    def __str__(self) -> str:
        l_brak = '(' if self.l_open or self.l_val is None else '['
        r_brak = ')' if self.h_open or self.h_val is None else ']'
        l_str = '-∞' if self.l_val is None else str(self.l_val)
        h_str = '+∞' if self.h_val is None else str(self.h_val)
        return f'{l_brak}{l_str}, {h_str}{r_brak}'


class ValIntervalManager:

    def __init__(self):
        self.stack = []

    def push(self, vi: ValInterval):
        self.stack.append(vi)

    def pop(self):
        return self.stack.pop()

    def last(self):
        return self.stack[-1]

    def empty(self):
        return len(self.stack) == 0


class VarIntervalFinder:
    """Compute individual variable domains while keeping the formula fixed.

    Use get_intervals() for Int/Real/BitVec variables and get_boolean_domain()
    for Bool variables. Numeric domains may require infinitely many intervals;
    use an optional timeout when termination is not known in advance.
    """

    def __init__(
        self, _formula: z3.BoolRef | z3.AstVector,
        _variables: Iterable[z3.ExprRef] | None = None, *,
        show_progress: bool = True,
    ) -> None:
        """Prepare the formula and its complete free-variable list.

        Args:
            _formula: A Boolean formula or assertions from parse_smt2_file().
            _variables: All free variables, including Booleans and non-targets,
                in the same Z3 context. None requests automatic discovery.
                A supplied list is trusted for completeness to avoid traversal.
            show_progress: Show timing/spinner during automatic discovery only.

        Raises:
            ValueError: A supplied/discovered entry is not a supported variable
                or uses a different Z3 context. Missing entries are not detected.

        Query timeouts do not cover this constructor's variable discovery.
        """
        self.ctx = _formula.ctx
        self.formula = _formula
        if _variables is None:
            if show_progress:
                print('c No variable list was supplied; extracting variables automatically. '
                      'This may take some time.', flush=True)
                with _progress_stage('Collecting variables'):
                    self.variables = z3.z3util.get_vars(z3.And(_formula))
                print(f'c {len(self.variables)} variables collected; ready for interval computation.',
                      flush=True)
            else:
                self.variables = z3.z3util.get_vars(z3.And(_formula))
        else:
            self.variables = list(_variables)
        for variable in self.variables:
            _validate_variable(variable, self.ctx)
        self.interval_variables = [var for var in self.variables if not z3.is_bool(var)]
        self.variables_set = set(self.variables)
        self._falsifying_assignment = None  # The falsifying assignment of the latest call
        self._budget = _TimeBudget()


    def is_bb_var(self, var: z3.ExprRef) -> bool:
        """Test whether some target value cannot satisfy the formula.

        Other free variables are quantified. UNKNOWN raises RuntimeError.
        """
        solver = z3.Solver(ctx=self.ctx)
        remaining_vars = list(self.variables_set - {var})
        neg_formula = z3.Not(z3.And(self.formula))
        if remaining_vars:
            neg_formula = z3.ForAll(remaining_vars, neg_formula)
        working_formula = z3.Exists([var], neg_formula)
        solver.add(working_formula)
        result = self._budget.check(solver)
        if result == z3.unknown:
            raise RuntimeError(f"Backbone check returned unknown: {solver.reason_unknown()}")
        return result == z3.sat

    def get_lb(
        self, var: z3.ExprRef, fa: z3.ExprRef | None = None,
    ) -> tuple[z3.ExprRef | None, bool]:
        """Return the lower bound and whether it is open.

        If fa is supplied, restrict the target to values strictly greater than
        fa. None as a returned endpoint denotes infinity in this direction.
        Bit-vector comparisons are unsigned. UNSAT raises ValueError; UNKNOWN
        raises RuntimeError. Uses the active get_intervals() time budget.
        """
        optimizer = z3.Optimize(ctx=self.ctx)
        optimizer.set('priority', 'box')
        optimizer.add(self.formula)
        if fa is not None:
            optimizer.add(_gt(var, fa))
        handle = optimizer.minimize(var)
        result = self._budget.check(optimizer)
        if result == z3.unknown:
            raise RuntimeError(f"Lower-bound optimization returned unknown: {optimizer.reason_unknown()}")
        if result == z3.unsat:
            raise ValueError("Lower-bound optimization constraints are unsatisfiable")
        raw = optimizer.lower(handle)
        val, is_open = _parse_bound(raw, ctx=self.ctx)
        if _needs_bv_conversion(val, var):
            val = z3.BitVecVal(val.as_long(), var.size(), ctx=self.ctx)
        return val, is_open

    def get_ub(
        self, var: z3.ExprRef, fa: z3.ExprRef | None = None,
    ) -> tuple[z3.ExprRef | None, bool]:
        """Return the upper bound and whether it is open.

        If fa is supplied, restrict the target to values strictly less than
        fa. None as a returned endpoint denotes infinity in this direction.
        Bit-vector comparisons are unsigned. UNSAT raises ValueError; UNKNOWN
        raises RuntimeError. Uses the active get_intervals() time budget.
        """
        optimizer = z3.Optimize(ctx=self.ctx)
        optimizer.set('priority', 'box')
        optimizer.add(self.formula)
        if fa is not None:
            optimizer.add(_lt(var, fa))
        handle = optimizer.maximize(var)
        result = self._budget.check(optimizer)
        if result == z3.unknown:
            raise RuntimeError(f"Upper-bound optimization returned unknown: {optimizer.reason_unknown()}")
        if result == z3.unsat:
            raise ValueError("Upper-bound optimization constraints are unsatisfiable")
        raw = optimizer.upper(handle)
        val, is_open = _parse_bound(raw, ctx=self.ctx)
        if _needs_bv_conversion(val, var):
            val = z3.BitVecVal(val.as_long(), var.size(), ctx=self.ctx)
        return val, is_open

    def has_falsifying_assignment(
        self, var: z3.ExprRef, l_val: z3.ExprRef | None,
        h_val: z3.ExprRef | None, l_open: bool = False, h_open: bool = False,
    ) -> bool:
        """Find an infeasible target value strictly between the bounds.

        A successful call stores a value for get_falsifying_assignment(). None
        bounds are unbounded. Search excludes endpoints regardless of the open
        flags; callers must already know their boundary status. UNKNOWN raises
        RuntimeError and the active interval-search timeout applies.
        """
        self._falsifying_assignment = None
        solver = z3.Solver(ctx=self.ctx)
        remaining_vars = list(self.variables_set - {var})
        if remaining_vars:
            working_formula = z3.ForAll(remaining_vars, z3.Not(z3.And(self.formula)))
        else:
            working_formula = z3.Not(z3.And(self.formula))
        solver.add(working_formula)
        # Always use strict inequalities: the endpoints are either known-sat (closed)
        # or already excluded from the domain (open), so we search strictly inside.
        if l_val is not None:
            solver.add(_gt(var, l_val))
        if h_val is not None:
            solver.add(_lt(var, h_val))
        result = self._budget.check(solver)
        if result == z3.unknown:
            raise RuntimeError(f"Falsifying-assignment search returned unknown: {solver.reason_unknown()}")
        if result == z3.sat:
            self._falsifying_assignment = solver.model().eval(var, model_completion=True)
            return True
        return False

    def get_falsifying_assignment(self) -> z3.ExprRef:
        """Return the last gap-search witness, or raise ValueError if absent."""
        if self._falsifying_assignment is not None:
            return self._falsifying_assignment
        raise ValueError(f"The falsifying assignment is not available")

    @staticmethod
    def _default_print_interval(iv):
        """Default callback that prints intervals as they are found."""
        print(f" {iv}", end=';', flush=True)

    def get_boolean_domain(
        self, var: z3.BoolRef, *, timeout: float | None = None,
    ) -> set[bool]:
        """Return the feasible values of a Boolean constant variable.

        The result is set(), {False}, {True}, or {False, True}. Two SAT checks
        fix the target to each value; UNSAT formulas yield an empty set.
        timeout is one positive finite budget in seconds for this call, or
        None for unlimited. The budget is shared by both checks.

        Raises:
            ValueError: Invalid target, context, or timeout.
            RuntimeError: Z3 returns UNKNOWN.
            TimeoutError: The budget expires; no partial set is returned.
        """
        _validate_variable(var, self.ctx)
        if not z3.is_bool(var):
            raise ValueError('Boolean domain target must be a Bool variable')
        budget = _TimeBudget(timeout)
        solver = z3.Solver(ctx=self.ctx)
        solver.add(self.formula)
        values = set()
        for value in (False, True):
            solver.push()
            try:
                solver.add(var == value)
                result = budget.check(solver)
                if result == z3.unknown:
                    raise RuntimeError(f'Boolean domain check returned unknown: {solver.reason_unknown()}')
                if result == z3.sat:
                    values.add(value)
            finally:
                solver.pop()
        budget.remaining()
        return values

    def get_intervals(
        self, var: z3.ArithRef | z3.BitVecRef,
        on_interval_found: Callable[[ValInterval], object] | None = None, *,
        timeout: float | None = None,
    ) -> list[ValInterval]:
        """Return disjoint intervals covering the target's feasible values.

        Args:
            var: An Int, Real, or BitVec constant variable, not an expression.
            on_interval_found: Called as each interval is completed. None
                prints intervals immediately; use lambda iv: None to silence.
            timeout: Positive finite overall budget in seconds for this call;
                None means unlimited. Cancellation by Z3 is cooperative.

        Returns:
            Intervals in ascending order (unsigned for bit-vectors), or []
            when the formula is UNSAT. Endpoints belong to the formula context.

        Raises:
            ValueError: Invalid target, context, or timeout.
            RuntimeError: Z3 returns UNKNOWN.
            TimeoutError: The budget expires. Already emitted intervals may
                be partial; no completed domain list is returned.

        Domains needing infinitely many intervals may not terminate without a
        timeout. The constructor's discovery time is outside this call's budget.
        """
        _validate_variable(var, self.ctx, target=True)
        previous = self._budget
        self._budget = _TimeBudget(timeout)
        try:
            result = self._get_intervals(var, on_interval_found)
            self._budget.remaining()
            return result
        finally:
            self._budget = previous

    def _get_intervals(self, var, on_interval_found=None):
        """Compute the domain intervals for var.
        Returns an empty list if the formula is unsatisfiable.
        Args:
            var: Z3 variable to compute intervals for.
            on_interval_found: callback function(ValInterval) called each time
                a complete interval is found. Defaults to printing each interval.
        """
        if z3.is_bool(var):
            raise ValueError("Interval targets must be numeric; Boolean variables are only quantified")
        solver = z3.Solver(ctx=self.ctx)
        solver.add(self.formula)
        result = self._budget.check(solver)
        if result == z3.unsat:
            return []
        if result != z3.sat:
            raise RuntimeError(f"Satisfiability check returned unknown: {solver.reason_unknown()}")

        if on_interval_found is None:
            on_interval_found = self._default_print_interval
        domain_intervals = []

        vim = ValIntervalManager()
        lb, lb_open = self.get_lb(var)
        ub, ub_open = self.get_ub(var)

        vim.push(ValInterval(lb, ub, lb_open, ub_open, l_sat=True, h_sat=True))

        while not vim.empty():
            self._budget.remaining()
            vi = vim.pop()
            l_val, h_val = vi.l_val, vi.h_val
            l_open, h_open = vi.l_open, vi.h_open

            if vi.l_sat and vi.h_sat:

                if self.has_falsifying_assignment(var, l_val, h_val, l_open, h_open):
                    in_val = self.get_falsifying_assignment()
                    vim.push(ValInterval(in_val, h_val, False, h_open, l_sat=False, h_sat=vi.h_sat))
                    vim.push(ValInterval(l_val, in_val, l_open, False, l_sat=vi.l_sat, h_sat=False))
                else:
                    domain_intervals.append(vi)
                    if on_interval_found:
                        on_interval_found(vi)

            elif vi.l_sat and not vi.h_sat:
                sat_h_val, sat_h_open = self.get_ub(var, h_val)
                if sat_h_val is None:
                    iv = ValInterval(l_val, None, l_open, False)
                    domain_intervals.append(iv)
                    if on_interval_found:
                        on_interval_found(iv)
                else:
                    vim.push(ValInterval(l_val, sat_h_val, l_open, sat_h_open, l_sat=vi.l_sat, h_sat=True))

            else:
                if vi.l_sat or not vi.h_sat:
                    raise ValueError(f"Unexpected interval l_sat={vi.l_sat}, h_sat={vi.h_sat}")

                sat_l_val, sat_l_open = self.get_lb(var, l_val)
                if sat_l_val is None:
                    iv = ValInterval(None, h_val, False, h_open)
                    domain_intervals.append(iv)
                    if on_interval_found:
                        on_interval_found(iv)
                else:
                    vim.push(ValInterval(sat_l_val, h_val, sat_l_open, h_open, l_sat=True, h_sat=vi.h_sat))

        return domain_intervals


def is_formula_sat(
    formula: z3.BoolRef | z3.AstVector, ctx: z3.Context | None = None,
) -> bool:
    """Return SAT/UNSAT as True/False; UNKNOWN raises RuntimeError.

    An explicit context must match the formula; otherwise its context is used.
    This standalone helper does not accept a timeout.
    """
    ctx = ctx if ctx is not None else formula.ctx
    solver = z3.Solver(ctx=ctx)
    solver.add(formula)
    is_sat = solver.check()
    if is_sat == z3.sat:
        return True
    elif is_sat == z3.unsat:
        return False
    else:
        raise RuntimeError(f"Satisfiability check returned unknown: {solver.reason_unknown()}")
