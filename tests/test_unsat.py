# Author: Alessandro Previti
import unittest
from unittest.mock import Mock, patch

import z3

from interval_finder import VarIntervalFinder


class UnsatTests(unittest.TestCase):
    def test_unsat_domains_are_empty_without_emitting_intervals(self):
        for ctx in (z3.main_ctx(), z3.Context()):
            for sort in (z3.IntSort(ctx), z3.RealSort(ctx), z3.BitVecSort(4, ctx)):
                with self.subTest(sort=str(sort), custom_context=ctx != z3.main_ctx()):
                    x = z3.Const('x', sort)
                    finder = VarIntervalFinder(z3.And(x > 1, x < 0), [x])
                    callback = Mock()
                    with patch('interval_finder.core.z3.Optimize') as optimize:
                        self.assertEqual(finder.get_intervals(x, callback), [])
                        optimize.assert_not_called()
                    callback.assert_not_called()

    def test_sat_domains_still_work(self):
        x = z3.Int('x')
        cases = [
            (z3.And(x >= 0, x <= 2), ['[0, 2]']),
            (z3.Or(x == 0, x == 2), ['[0, 0]', '[2, 2]']),
            (x >= 0, ['[0, +∞)']),
        ]
        for formula, expected in cases:
            with self.subTest(formula=str(formula)):
                intervals = VarIntervalFinder(formula, [x]).get_intervals(x, lambda _: None)
                self.assertEqual(list(map(str, intervals)), expected)

    def test_unknown_initial_check_does_not_start_optimization(self):
        x = z3.Int('x')
        finder = VarIntervalFinder(x >= 0, [x])
        with patch('interval_finder.core.z3.Solver') as solver, patch('interval_finder.core.z3.Optimize') as optimize:
            solver.return_value.check.return_value = z3.unknown
            solver.return_value.reason_unknown.return_value = 'controlled test result'
            with self.assertRaisesRegex(RuntimeError, 'unknown'):
                finder.get_intervals(x)
            optimize.assert_not_called()


if __name__ == '__main__':
    unittest.main()
