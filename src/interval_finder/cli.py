#!/usr/bin/env python
# Author: Alessandro Previti

import z3
from .core import VarIntervalFinder
from .verify import verify_intervals, verify_boolean_domain
from .utils import get_vars
import argparse
from .utils import _progress_stage, _TimeBudget


class _OnceAction(argparse.Action):
    """Require a target-selection option to occur at most once."""

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is not None:
            parser.error(f'{option_string} may only be specified once; use --vars for multiple targets')
        setattr(namespace, self.dest, values)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=float, help='Overall interval computation and verification budget in seconds (default: unlimited)')
    parser.add_argument('--verify', action='store_true', help='Verify correctness of computed intervals')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--var', action=_OnceAction, metavar='NAME',
                           help='Select one target variable; may only be supplied once')
    selection.add_argument('--vars', action=_OnceAction, nargs='+', metavar='NAME',
                           help='Select a space-separated list of targets; put the input filename first')
    parser.add_argument('infile')
    args = parser.parse_args()

    try:
        _TimeBudget(args.timeout)
    except ValueError as error:
        parser.error(str(error))

    instance_file = args.infile
    print('\nc INIT\n', flush=True)
    with _progress_stage('Parsing formula'):
        formula = z3.parse_smt2_file(instance_file)
    with _progress_stage('Collecting variables'):
        variables = get_vars(instance_file, ctx=formula.ctx)
        bb_finder = VarIntervalFinder(formula, variables)
    variables = bb_finder.variables
    by_name = {str(var): var for var in variables}
    names = args.vars if args.vars is not None else ([args.var] if args.var is not None else None)
    targets = [] if names is not None else variables
    for name in dict.fromkeys(names or []):
        if name not in by_name:
            parser.error(f"Variable {name!r} is not declared in the input")
        var = by_name[name]
        if not (z3.is_int(var) or z3.is_real(var) or z3.is_bv(var) or z3.is_bool(var)):
            parser.error(f"Variable {name!r} must be Int, Real, BitVec, or Bool")
        targets.append(var)
    print(f"c #Var: {len(variables)}")
    print('c Variables collected; starting interval computation.', flush=True)

    print()

    verification_failed = False
    budget = _TimeBudget(args.timeout)
    try:
        for var in targets:
            if z3.is_bool(var):
                values = bb_finder.get_boolean_domain(var, timeout=budget.remaining())
                rendered = ', '.join(str(value).lower() for value in sorted(values))
                print(f'Var {var} (Bool) domain: {{{rendered}}}', flush=True)
                if args.verify:
                    ok, msg = verify_boolean_domain(formula, var, values, timeout=budget.remaining())
                    print(f'  c verify: {msg}')
                    if not ok:
                        verification_failed = True
                budget.remaining()
                continue
            print(f"Var {var} ({var.sort()}) intervals:", end='', flush=True)
            domain_intervals = bb_finder.get_intervals(var, timeout=budget.remaining())
            print()

            if args.verify:
                ok, msg = verify_intervals(formula, variables, var, domain_intervals, timeout=budget.remaining())
                print(f"  c verify: {msg}")
                if not ok:
                    verification_failed = True
            budget.remaining()

    except TimeoutError as error:
        print(f'\nc INCOMPLETE: {error}. Printed intervals may be partial.', flush=True)
        return 124

    print('\nc END')
    return 1 if verification_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

