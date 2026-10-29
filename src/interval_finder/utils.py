# Author: Alessandro Previti
"""Shared Interval Finder utilities: declaration parsing, progress, and time budgets."""

from __future__ import annotations

from os import PathLike
from contextlib import contextmanager
from itertools import cycle
import math
import re
import sys
import threading
from time import perf_counter
import z3


def get_vars(f_inst_name: str | PathLike[str], ctx: z3.Context | None = None) -> list[z3.ExprRef]:
    """Read Int/Real/Bool/BitVec constants without traversing the formula DAG.

    Reads all supported constant declarations, including unused ones, in file
    order. Int, Real, Bool, and positive-width BitVec sorts are supported.
    The supplied context is used for every returned variable; None uses Z3's
    default context. The input is assumed to have a single declaration scope.

    Supports multiline declarations, comments and quoted symbols. Duplicate
    names, nonconstant functions, unsupported sorts (including aliases), and
    malformed declarations raise ValueError. File errors propagate as OSError.
    Z3 remains responsible for validating the complete SMT2 formula.
    """
    token_pattern = re.compile(r'\s+|;[^\n]*|\|[^|]*\||"(?:[^"]|"")*"|[()]|[^\s();|\"]+|.', re.DOTALL)
    variables = []
    names = set()
    depth = 0
    command = None
    declaration = []
    with open(f_inst_name, 'r') as file:
        text = file.read()
    for match in token_pattern.finditer(text):
        token = match.group()
        if token.isspace() or token.startswith(';'):
            continue
        if token in ('|', '"'):
            raise ValueError("Unterminated SMT2 quoted symbol or string")
        if token == '(':
            depth += 1
        elif token == ')':
            depth -= 1
            if depth < 0:
                raise ValueError("Unbalanced SMT2 parentheses")
        elif depth == 1 and command is None:
            command = token
        if command in ('declare-const', 'declare-fun'):
            declaration.append(token)
        if depth != 0:
            continue
        if declaration:
            kind, name, *sort_tokens = declaration[:-1]
            if kind == 'declare-fun':
                if sort_tokens[:2] != ['(', ')']:
                    raise ValueError(f"Nonconstant function {name!r} is not supported")
                sort_tokens = sort_tokens[2:]
            name = name[1:-1] if name.startswith('|') else name
            if name in names:
                raise ValueError(f"Duplicate declaration for {name!r}")
            constructors = {'Int': z3.IntSort, 'Real': z3.RealSort, 'Bool': z3.BoolSort}
            if len(sort_tokens) == 1 and sort_tokens[0] in constructors:
                sort = constructors[sort_tokens[0]](ctx=ctx)
            elif (len(sort_tokens) == 5 and sort_tokens[:3] == ['(', '_', 'BitVec']
                  and sort_tokens[-1] == ')' and sort_tokens[3].isdigit()
                  and int(sort_tokens[3]) > 0):
                sort = z3.BitVecSort(int(sort_tokens[3]), ctx=ctx)
            else:
                raise ValueError(f"Unsupported sort for {name!r}: {' '.join(sort_tokens)}")
            variables.append(z3.Const(name, sort))
            names.add(name)
        command = None
        declaration = []
    if depth:
        raise ValueError("Unbalanced SMT2 parentheses")
    return variables


@contextmanager
def _progress_stage(label):
    """Show elapsed setup time; animate only on an interactive terminal."""
    stream = sys.stdout
    interactive = stream.isatty()
    start = perf_counter()
    stopped = threading.Event()
    worker = None
    print(f"c {label}...", end='', file=stream, flush=True)

    def animate():
        for frame in cycle('|/-\\'):
            if stopped.wait(0.1):
                return
            print(f"\rc {label}... {frame} {perf_counter() - start:.1f}s",
                  end='', file=stream, flush=True)

    if interactive:
        worker = threading.Thread(target=animate, daemon=True)
        worker.start()
    try:
        yield
    except BaseException:
        status = 'stopped'
        raise
    else:
        status = 'done'
    finally:
        stopped.set()
        if worker is not None:
            worker.join()
        if interactive:
            print('\r\033[2K', end='', file=stream)
            prefix = f'c {label}... '
        else:
            prefix = ' '
        print(f"{prefix}{status} in {perf_counter() - start:.3f}s",
              file=stream, flush=True)



class _TimeBudget:
    """Cooperative wall-clock budget shared by repeated solver calls."""

    def __init__(self, timeout=None):
        if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
            raise ValueError('timeout must be a positive finite number of seconds')
        self.deadline = None if timeout is None else perf_counter() + timeout

    def remaining(self):
        if self.deadline is None:
            return None
        seconds = self.deadline - perf_counter()
        if seconds <= 0:
            raise TimeoutError('Time limit reached; domain computation is incomplete')
        return seconds

    def check(self, solver):
        remaining = self.remaining()
        if remaining is not None:
            solver.set(timeout=min(4294967295, max(1, math.ceil(remaining * 1000))))
        result = solver.check()
        self.remaining()
        if (remaining is not None and result == z3.unknown
                and any(word in solver.reason_unknown().lower() for word in ('timeout', 'canceled', 'cancelled'))):
            raise TimeoutError('Solver time limit reached; domain computation is incomplete')
        return result


def _validate_variable(variable, ctx, *, target=False):
    """Reject expressions, unsupported sorts, and mixed Z3 contexts."""
    description = ('Interval target must be a numeric variable (Int, Real, or BitVec)'
                   if target else 'Variable lists must contain only Int, Real, BitVec, or Bool variables')
    if (not z3.is_expr(variable) or not z3.is_const(variable)
            or variable.decl().kind() != z3.Z3_OP_UNINTERPRETED):
        raise ValueError(description)
    supported = z3.is_int(variable) or z3.is_real(variable) or z3.is_bv(variable)
    if not target:
        supported = supported or z3.is_bool(variable)
    if not supported:
        raise ValueError(description)
    if variable.ctx != ctx:
        raise ValueError('Variables and formula must use the same Z3 context')
