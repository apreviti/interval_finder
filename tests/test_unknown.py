# Author: Alessandro Previti
import unittest
from unittest.mock import Mock, patch

import z3

from interval_finder import ValInterval, VarIntervalFinder, is_formula_sat
from interval_finder.verify import verify_intervals


class UnknownTests(unittest.TestCase):
    def setUp(self):
        self.x = z3.Int('x')
        self.formula = z3.And(self.x >= 0, self.x <= 2)
        self.finder = VarIntervalFinder(self.formula)
        self.intervals = [ValInterval(z3.IntVal(0), z3.IntVal(2))]

    def test_unknown_solver_checks_raise(self):
        operations = [
            lambda: is_formula_sat(self.formula),
            lambda: self.finder.is_bb_var(self.x),
            lambda: self.finder.has_falsifying_assignment(self.x, None, None),
        ]
        for operation in operations:
            with self.subTest(operation=operation):
                with patch('interval_finder.core.z3.Solver') as solver:
                    solver.return_value.check.return_value = z3.unknown
                    solver.return_value.reason_unknown.return_value = 'controlled unknown'
                    with self.assertRaisesRegex(RuntimeError, 'controlled unknown'):
                        operation()
                    solver.return_value.model.assert_not_called()
        self.assertIsNone(self.finder._falsifying_assignment)

    def test_non_sat_optimization_never_reads_bounds(self):
        for result in (z3.unknown, z3.unsat):
            for bound in (self.finder.get_lb, self.finder.get_ub):
                with self.subTest(result=str(result), bound=bound.__name__):
                    with patch('interval_finder.core.z3.Optimize') as optimize:
                        optimizer = optimize.return_value
                        optimizer.check.return_value = result
                        optimizer.reason_unknown.return_value = 'controlled unknown'
                        with self.assertRaises(RuntimeError if result == z3.unknown else ValueError):
                            bound(self.x)
                        optimizer.lower.assert_not_called()
                        optimizer.upper.assert_not_called()

    def test_unknown_gap_search_does_not_emit_interval(self):
        callback = Mock()
        with patch('interval_finder.core.z3.Solver') as solver:
            solver.return_value.check.side_effect = [z3.sat, z3.unknown]
            solver.return_value.reason_unknown.return_value = 'controlled unknown'
            with self.assertRaisesRegex(RuntimeError, 'Falsifying-assignment'):
                self.finder.get_intervals(self.x, callback)
        callback.assert_not_called()

    def test_either_unknown_verification_check_prevents_success(self):
        for results in ([z3.unknown], [z3.unsat, z3.unknown]):
            with self.subTest(results=list(map(str, results))):
                with patch('interval_finder.verify.z3.Solver') as solver:
                    solver.return_value.check.side_effect = results
                    solver.return_value.reason_unknown.return_value = 'controlled unknown'
                    with self.assertRaisesRegex(RuntimeError, 'verification returned unknown'):
                        verify_intervals(self.formula, [self.x], self.x, self.intervals)
                    solver.return_value.model.assert_not_called()

    def test_definite_results_still_work(self):
        self.assertTrue(is_formula_sat(self.formula))
        self.assertFalse(is_formula_sat(z3.And(self.x > 1, self.x < 0)))
        self.assertEqual(verify_intervals(self.formula, [self.x], self.x, self.intervals),
                         (True, 'Intervals are correct'))
        self.assertFalse(verify_intervals(self.formula, [self.x], self.x,
                                         [ValInterval(z3.IntVal(0), z3.IntVal(3))])[0])
        self.assertFalse(verify_intervals(self.formula, [self.x], self.x,
                                         [ValInterval(z3.IntVal(0), z3.IntVal(1))])[0])


if __name__ == '__main__':
    unittest.main()
