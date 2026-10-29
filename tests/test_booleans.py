# Author: Alessandro Previti
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import z3

from interval_finder import get_vars, VarIntervalFinder
from interval_finder.cli import main
from interval_finder.verify import verify_intervals


class BooleanTests(unittest.TestCase):
    def test_cli_reports_full_domains_without_backbone_filtering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'full.smt2'
            path.write_text('(declare-const x Int)\n(declare-const y Int)\n(assert (= x y))\n')
            output = io.StringIO()
            with patch('sys.argv', ['interval-finder', '--verify', str(path)]):
                with patch.object(VarIntervalFinder, 'is_bb_var',
                                  side_effect=AssertionError('unexpected backbone check')):
                    with contextlib.redirect_stdout(output):
                        main()
            for name in ('x', 'y'):
                self.assertIn(f'Var {name} (Int) intervals: (-∞, +∞)', output.getvalue())
            self.assertEqual(output.getvalue().count('Intervals are correct'), 2)

    def test_boolean_assignments_are_quantified(self):
        x = z3.Int('x')
        b = z3.Bool('b')
        cases = [
            (z3.And(x >= 0, x <= 2, b), ['[0, 2]']),
            (z3.And(x >= 0, x <= 2, z3.Not(b)), ['[0, 2]']),
            (z3.Or(z3.And(b, x == 0), z3.And(z3.Not(b), x == 2)),
             ['[0, 0]', '[2, 2]']),
        ]
        for formula, expected in cases:
            with self.subTest(formula=str(formula)):
                finder = VarIntervalFinder(formula)
                self.assertEqual(finder.interval_variables, [x])
                self.assertTrue(finder.is_bb_var(x))
                intervals = finder.get_intervals(x, lambda _: None)
                self.assertEqual(list(map(str, intervals)), expected)
                self.assertTrue(verify_intervals(formula, finder.variables, x, intervals)[0])
        with self.assertRaisesRegex(ValueError, 'numeric'):
            finder.get_intervals(b)

    def test_cli_includes_booleans_by_default_and_honors_target_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'boolean.smt2'
            path.write_text('(declare-const x Int)\n(declare-fun b () Bool)\n'
                            '(declare-const y Int)\n'
                            '(assert (and (>= x 0) (<= x 2) b (= y x)))\n')
            variables = get_vars(path)
            self.assertEqual([str(var.sort()) for var in variables], ['Int', 'Bool', 'Int'])
            for flags in (['--var', 'x'], ['--vars', 'x']):
                with self.subTest(flags=flags):
                    output = io.StringIO()
                    with patch('sys.argv', ['interval-finder', str(path), '--verify', *flags]):
                        with contextlib.redirect_stdout(output):
                            main()
                    self.assertIn('Var x (Int) intervals: [0, 2]', output.getvalue())
                    self.assertIn('Intervals are correct', output.getvalue())
                    self.assertNotIn('Var b (Bool)', output.getvalue())
                    self.assertNotIn('Var y (Int)', output.getvalue())
            output = io.StringIO()
            with patch('sys.argv', ['interval-finder', '--verify', str(path)]):
                with contextlib.redirect_stdout(output):
                    main()
            self.assertIn('Var x (Int) intervals: [0, 2]', output.getvalue())
            self.assertIn('Var y (Int) intervals: [0, 2]', output.getvalue())
            self.assertIn('Var b (Bool) domain: {true}', output.getvalue())
            self.assertIn('Boolean domain is correct', output.getvalue())
            self.assertEqual(output.getvalue().count('Intervals are correct'), 2)
            for flags in (['--var', 'missing'],):
                with self.subTest(invalid_flags=flags):
                    with patch('sys.argv', ['interval-finder', *flags, str(path)]):
                        with contextlib.redirect_stderr(io.StringIO()):
                            with self.assertRaises(SystemExit) as error:
                                main()
                    self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
