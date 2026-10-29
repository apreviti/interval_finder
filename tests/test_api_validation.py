# Author: Alessandro Previti
import unittest
from unittest.mock import patch

import z3
from interval_finder import VarIntervalFinder


class ApiValidationTests(unittest.TestCase):
    def test_expression_and_nonvariable_targets_rejected_before_solver(self):
        x = z3.Int('x')
        finder = VarIntervalFinder(z3.Or(x == 0, x == 2), show_progress=False)
        a = z3.Array('a', z3.IntSort(), z3.IntSort())
        f = z3.Function('f', z3.IntSort(), z3.IntSort())
        invalid = [x + 1, z3.IntVal(1), z3.Bool('b'), a, f(x), 1, None]
        for target in invalid:
            with self.subTest(target=str(target)), patch('interval_finder.core.z3.Solver') as solver:
                with self.assertRaisesRegex(ValueError, 'Interval target must be'):
                    finder.get_intervals(target)
                solver.assert_not_called()
        self.assertEqual([str(iv) for iv in finder.get_intervals(x, lambda _: None)],
                         ['[0, 0]', '[2, 2]'])

    def test_unsupported_or_expression_list_entries_rejected(self):
        x = z3.Int('x')
        a = z3.Array('a', z3.IntSort(), z3.IntSort())
        for entry in (a, x + 1, z3.IntVal(0), None):
            with self.subTest(entry=str(entry)), self.assertRaisesRegex(ValueError, 'Variable lists'):
                VarIntervalFinder(x == 0, [x, entry])
        with self.assertRaisesRegex(ValueError, 'Variable lists'):
            VarIntervalFinder(z3.Select(a, 0) == 1, show_progress=False)

    def test_supported_targets_and_boolean_variables(self):
        for ctx in (z3.main_ctx(), z3.Context()):
            for sort in (z3.IntSort(ctx), z3.RealSort(ctx), z3.BitVecSort(4, ctx)):
                x = z3.Const('x', sort)
                b = z3.Bool('b', ctx=ctx)
                finder = VarIntervalFinder(z3.And(x == 2, b), [x, b])
                self.assertEqual([str(iv) for iv in finder.get_intervals(x, lambda _: None)], ['[2, 2]'])

    def test_mixed_contexts_rejected(self):
        x = z3.Int('x')
        other = z3.Int('x', ctx=z3.Context())
        with self.assertRaisesRegex(ValueError, 'same Z3 context'):
            VarIntervalFinder(x == 0, [other])
        finder = VarIntervalFinder(x == 0, [x])
        with self.assertRaisesRegex(ValueError, 'same Z3 context'):
            finder.get_intervals(other)

    def test_unconstrained_numeric_target_is_still_allowed(self):
        x = z3.Int('x')
        finder = VarIntervalFinder(z3.BoolVal(True), show_progress=False)
        self.assertEqual([str(iv) for iv in finder.get_intervals(x, lambda _: None)], ['(-∞, +∞)'])


if __name__ == '__main__':
    unittest.main()
