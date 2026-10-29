# Author: Alessandro Previti
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import z3
from interval_finder import VarIntervalFinder
from interval_finder.cli import main
from interval_finder.verify import verify_boolean_domain


class BooleanDomainTests(unittest.TestCase):
    def test_all_four_domains_and_custom_contexts(self):
        for ctx in (z3.main_ctx(), z3.Context()):
            b = z3.Bool('b', ctx=ctx)
            cases = [(b, {True}), (z3.Not(b), {False}),
                     (z3.BoolVal(True, ctx), {False, True}),
                     (z3.And(b, z3.Not(b)), set())]
            for formula, expected in cases:
                with self.subTest(expected=expected):
                    finder = VarIntervalFinder(formula, show_progress=False)
                    values = finder.get_boolean_domain(b, timeout=5)
                    self.assertEqual(values, expected)
                    self.assertTrue(verify_boolean_domain(formula, b, values, timeout=5)[0])
                    for wrong in (expected ^ {True}, expected ^ {False}):
                        self.assertFalse(verify_boolean_domain(formula, b, wrong)[0])

    def test_boolean_numeric_dependencies(self):
        b = z3.Bool('b')
        x = z3.Int('x')
        formula = z3.And(z3.If(b, x == 2, x == 4), x < 3)
        finder = VarIntervalFinder(formula, [x, b])
        self.assertEqual(finder.get_boolean_domain(b), {True})
        self.assertEqual([str(iv) for iv in finder.get_intervals(x, lambda _: None)], ['[2, 2]'])

    def test_invalid_targets_and_values(self):
        b = z3.Bool('b')
        finder = VarIntervalFinder(b, [b])
        for target in (z3.Int('x'), z3.Not(b), z3.BoolVal(True)):
            with self.assertRaises(ValueError):
                finder.get_boolean_domain(target)
        with self.assertRaises(ValueError):
            verify_boolean_domain(b, b, {1})
        with self.assertRaises(ValueError):
            finder.get_boolean_domain(z3.Bool('b', ctx=z3.Context()))

    def test_unknown_and_timeout_never_return_partial_sets(self):
        b = z3.Bool('b')
        finder = VarIntervalFinder(b, [b])
        for module, operation in [('interval_finder.core', lambda: finder.get_boolean_domain(b)),
                                  ('interval_finder.verify', lambda: verify_boolean_domain(b, b, {True}))]:
            with patch(module + '.z3.Solver') as factory:
                factory.return_value.check.side_effect = [z3.sat if module == 'interval_finder.core' else z3.unsat, z3.unknown]
                factory.return_value.reason_unknown.return_value = 'controlled unknown'
                with self.assertRaisesRegex(RuntimeError, 'controlled unknown'):
                    operation()
        with self.assertRaises(TimeoutError):
            finder.get_boolean_domain(b, timeout=1e-12)
        with self.assertRaises(TimeoutError):
            verify_boolean_domain(b, b, {True}, timeout=1e-12)

    def test_cli_boolean_only_and_mixed_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'mixed.smt2'
            path.write_text('(declare-const x Int) (declare-const b Bool) '
                            '(assert (= x 2)) (assert (not b))')
            for flags in ([], ['--var', 'b'], ['--vars', 'b', 'x']):
                output = io.StringIO()
                with patch('sys.argv', ['interval-finder', str(path), '--verify', *flags]), contextlib.redirect_stdout(output):
                    self.assertEqual(main(), 0)
                self.assertIn('Var b (Bool) domain: {false}', output.getvalue())
                self.assertIn('Boolean domain is correct', output.getvalue())
                if flags == ['--var', 'b']:
                    self.assertNotIn('Var x (Int)', output.getvalue())
                else:
                    self.assertIn('Var x (Int) intervals: [2, 2]', output.getvalue())
            with patch('sys.argv', ['interval-finder', '--verify', str(path)]), \
                 patch('interval_finder.cli.verify_boolean_domain', return_value=(False, 'controlled failure')), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 1)

    def test_cli_unrestricted_and_unsat_boolean_sets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bool.smt2'
            for assertion, expected in [('', '{false, true}'), ('(assert false)', '{}')]:
                path.write_text('(declare-const b Bool)' + assertion)
                output = io.StringIO()
                with patch('sys.argv', ['interval-finder', str(path)]), contextlib.redirect_stdout(output):
                    self.assertEqual(main(), 0)
                self.assertIn('Var b (Bool) domain: ' + expected, output.getvalue())


if __name__ == '__main__':
    unittest.main()
