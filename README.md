# Interval Finder

Compute each variable's feasible domain in an SMT formula using Z3: disjoint
intervals for numeric variables and feasible-value sets for Booleans.

## Supported theories

- **QF_LIA** — Linear Integer Arithmetic
- **QF_LRA** — Linear Real Arithmetic
- **QF_BV** — Bit-Vectors; domains are reported as unsigned intervals, while
  signed and unsigned comparisons in the input formula retain their semantics.

## Installation

Requires Python 3.10 or newer. From this directory, using your chosen Python environment:

```bash
python -m pip install .
```

## Command-line usage

```bash
interval-finder formula.smt2
interval-finder formula.smt2 --var x
interval-finder formula.smt2 --vars x y b --verify --timeout 10
```

The equivalent module command is `python -m interval_finder`.

| Option | Meaning |
|---|---|
| `--var NAME` | Select one variable; may appear only once. |
| `--vars NAME ...` | Select several space-separated names; put the filename first. |
| `--verify` | Verify reported numeric and Boolean domains. |
| `--timeout SECONDS` | Overall computation and verification budget; default unlimited. |

With neither selection option, all declared variables are processed, including
Booleans. `--var` and `--vars` are mutually exclusive. Boolean domains are
`{false}`, `{true}`, `{false, true}`, or `{}` for an unsatisfiable formula.

Parsing and variable collection display elapsed times. The CLI reads declarations
directly for fast variable collection. It supports Int, Real, Bool, and positive-width
BitVec constants in a single declaration scope; nonconstant functions, duplicate
names, unsupported sorts, and sort aliases are rejected. Z3 validates the formula.

Numeric intervals print as they are found. Domains requiring infinitely many
intervals, such as the nonnegative even integers, can keep producing output
without terminating. See the [even integers](instances/examples/even_integers.smt2)
and [nonnegative even integers](instances/examples/nonnegative_even_integers.smt2)
examples; use `--timeout` to limit their runtime.

The timeout starts after parsing and variable collection and spans all selected
targets and verification. Z3 cancellation is cooperative. On timeout, output is
marked `INCOMPLETE`, previously printed intervals may be partial, and the exit
status is **124**. A verification failure returns **1**; normal completion returns
**0**. An UNKNOWN result raises an error and never certifies correctness.

## Python API

```python
import z3
from interval_finder import VarIntervalFinder, verify_intervals

x = z3.Int("x")
formula = z3.Or(z3.And(x >= 0, x <= 2), x == 5)
finder = VarIntervalFinder(formula)
intervals = finder.get_intervals(x, timeout=10)
# Prints: [0, 2]; [5, 5];
correct, message = verify_intervals(formula, None, x, intervals, timeout=10)
```

Targets must be individual variables, not expressions such as `x + 1`. For a
Boolean variable `b`, use `finder.get_boolean_domain(b, timeout=10)`; it returns
a Python set of feasible Boolean values. `verify_boolean_domain()` checks that set.

Queries raise `TimeoutError` on timeout and `RuntimeError` on UNKNOWN; no partial
domain is returned as complete. Numeric queries print completed intervals by
default; pass `on_interval_found=lambda interval: None` to silence them.

Automatic variable discovery reports progress and timing. Set
`show_progress=False` in the constructor to silence this feedback. A spinner is
shown in interactive terminals; other output streams receive plain status text.

A runnable version is available in [scripts/example_api.py](scripts/example_api.py).
After installation, run it from the repository root:

```bash
python scripts/example_api.py
```

### Optional performance optimization

For a quick test, omit the variable list and use automatic Z3 discovery. On large
formulas, reading declarations directly can avoid expensive expression-graph traversal:

```python
from interval_finder import get_vars

variables = get_vars("formula.smt2", ctx=formula.ctx)
finder = VarIntervalFinder(formula, variables)
```

> [!WARNING]
> A manually supplied list must contain **every free variable in the formula**,
> including Booleans and non-target variables. An incomplete list can produce
> incorrect intervals or verification results. Completeness is trusted, not checked.

This applies to both the finder and numeric verification. Pass `None` to the
verifier's variable-list argument to request automatic discovery. All variables
must use the same Z3 context as the formula.

## Tests

Run all regression tests and verify the bundled CLI example from the repository root:

```bash
python scripts/test_all.py
```

The checks use the current source tree and do not require downloaded benchmark collections.

## Author and license

Author: **Alessandro Previti**. Copyright (c) 2026 Alessandro Previti.

The source code is distributed under the [MIT License](LICENSE). Dependencies
retain their own copyright and license terms. The bundled SMT-LIB benchmarks
have separate [source, attribution, and licensing information](instances/benchmarks/README.md).

## Citation

The algorithm implemented here was presented in **On Computing Generalized Backbones** by Alessandro Previti, Alexey Ignatiev, Matti Järvisalo, and Joao Marques-Silva (ICTAI 2017, pp. 1050–1056). If you use this tool in your research, please cite this paper: [DOI](https://doi.org/10.1109/ICTAI.2017.00161) · [Open-access manuscript](https://hdl.handle.net/10138/309049).

```bibtex
@inproceedings{previti2017generalizedbackbones,
  author    = {Alessandro Previti and Alexey Ignatiev and
               Matti J{\"a}rvisalo and Joao Marques-Silva},
  title     = {On Computing Generalized Backbones},
  booktitle = {Proceedings - 2017 International Conference on Tools with Artificial Intelligence, ICTAI 2017},
  year      = {2017},
  pages     = {1050--1056},
  publisher = {IEEE Computer Society},
  doi       = {10.1109/ICTAI.2017.00161},
  url       = {https://doi.org/10.1109/ICTAI.2017.00161}
}
```
