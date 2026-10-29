# Author: Alessandro Previti
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import z3
from interval_finder import VarIntervalFinder
from interval_finder.utils import _TimeBudget
from interval_finder.verify import verify_intervals
from interval_finder.cli import main


class TimeoutTests(unittest.TestCase):
    def test_budget_is_shared_across_solver_calls(self):
        clock = [0.0]
        solver = Mock()
        def check():
            clock[0] += .4
            return z3.sat
        solver.check.side_effect = check
        with patch('interval_finder.utils.perf_counter', side_effect=lambda: clock[0]):
            budget = _TimeBudget(1)
            budget.check(solver)
            budget.check(solver)
            with self.assertRaises(TimeoutError):
                budget.check(solver)
        limits = [call.kwargs['timeout'] for call in solver.set.call_args_list]
        self.assertEqual(limits[0], 1000)
        self.assertTrue(limits[0] > limits[1] > limits[2])

    def test_solver_timeout_and_other_unknown_remain_distinct(self):
        solver = Mock()
        solver.check.return_value = z3.unknown
        solver.reason_unknown.return_value = 'timeout'
        with self.assertRaises(TimeoutError):
            _TimeBudget(10).check(solver)
        solver.reason_unknown.return_value = 'incomplete theory'
        self.assertEqual(_TimeBudget(10).check(solver), z3.unknown)

    def test_api_success_invalid_budget_and_restoration(self):
        x = z3.Int('x')
        finder = VarIntervalFinder(x == 2, show_progress=False)
        for invalid in (0, -1, float('nan'), float('inf')):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                finder.get_intervals(x, lambda _: None, timeout=invalid)
        with patch.object(finder, '_get_intervals', side_effect=TimeoutError('controlled')):
            with self.assertRaises(TimeoutError):
                finder.get_intervals(x, timeout=.1)
        self.assertIsNone(finder._budget.deadline)
        intervals = finder.get_intervals(x, lambda _: None, timeout=5)
        self.assertEqual([str(iv) for iv in intervals], ['[2, 2]'])
        self.assertTrue(verify_intervals(finder.formula, None, x, intervals, timeout=5)[0])

    def test_verifier_timeout_cannot_certify(self):
        x = z3.Int('x')
        with patch('interval_finder.verify.z3.Solver') as factory:
            factory.return_value.check.return_value = z3.unknown
            factory.return_value.reason_unknown.return_value = 'timeout'
            with self.assertRaises(TimeoutError):
                verify_intervals(x == 0, [x], x, [], timeout=1)

    def test_cli_budget_spans_multiple_targets(self):
        clock = [0.0]
        seen = []
        def compute(var, **kwargs):
            seen.append(kwargs['timeout'])
            clock[0] += .6
            return []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'two.smt2'
            path.write_text('(declare-const x Int) (declare-const y Int)')
            output = io.StringIO()
            with patch('interval_finder.utils.perf_counter', side_effect=lambda: clock[0]), \
                 patch('sys.argv', ['interval-finder', '--timeout', '1', str(path)]), \
                 patch.object(VarIntervalFinder, 'get_intervals', side_effect=compute), \
                 contextlib.redirect_stdout(output):
                self.assertEqual(main(), 124)
            self.assertEqual(len(seen), 2)
            self.assertAlmostEqual(seen[0], 1)
            self.assertAlmostEqual(seen[1], .4)
            self.assertIn('INCOMPLETE', output.getvalue())
            self.assertNotIn('c END', output.getvalue())

    def test_infinite_domain_cli_stops_with_failure_status(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evens.smt2'
            path.write_text('(set-logic QF_LIA) (declare-const x Int) '
                            '(declare-const y Int) (assert (= x (* 2 y))) (assert (>= x 0))')
            result = subprocess.run(
                [sys.executable, '-m', 'interval_finder', '--timeout', '.05', '--var', 'x', str(path)],
                env=dict(os.environ, PYTHONPATH=str(root/'src'), PYTHONDONTWRITEBYTECODE='1'),
                capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 124, result.stderr)
            self.assertIn('INCOMPLETE', result.stdout)
            self.assertIn('partial', result.stdout)
            self.assertNotIn('Intervals are correct', result.stdout)


if __name__ == '__main__':
    unittest.main()
