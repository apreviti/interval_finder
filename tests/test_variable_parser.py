# Author: Alessandro Previti
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import z3

from interval_finder import VarIntervalFinder
from interval_finder.utils import get_vars
from interval_finder.verify import verify_intervals


class VariableParserTests(unittest.TestCase):
    def test_public_parser_export_matches_utility(self):
        from interval_finder import get_vars as public_get_vars
        self.assertIs(public_get_vars, get_vars)

    def parse(self, text, ctx=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.smt2'
            path.write_text(text)
            return get_vars(path, ctx=ctx)

    def test_declarations_match_z3_with_comments_quotes_and_multiline_sorts(self):
        text = '''
        ; (declare-const ignored Int)
        (set-info :source "fake (declare-const ignored Int); ""quoted""")
        (declare-const |x (with spaces);| Int) (declare-fun b () Bool)
        (declare-fun r
            ( ; empty argument list
            ) Real)
        (declare-const v (_ ; bit width follows
            BitVec 7))
        (assert (and (= |x (with spaces);| 1) b (= r 1.5) (= v #b0000001)))
        '''
        for ctx in (z3.main_ctx(), z3.Context()):
            with self.subTest(custom_context=ctx != z3.main_ctx()):
                variables = self.parse(text, ctx)
                formula = z3.parse_smt2_string(text, ctx=ctx)
                self.assertEqual(set(variables), set(z3.z3util.get_vars(z3.And(formula))))
                self.assertEqual(variables[-1].size(), 7)
                self.assertTrue(all(var.ctx == ctx for var in variables))

    def test_unused_declarations_are_retained(self):
        self.assertEqual([str(var) for var in self.parse('(declare-const unused Bool)')],
                         ['unused'])

    def test_invalid_or_unsupported_declarations_raise(self):
        for text in (
            '(declare-fun f (Int) Int)',
            '(declare-const a (Array Int Int))',
            '(declare-const x (_ BitVec 0))',
            '(declare-const x Int) (declare-const x Real)',
            '(declare-const x Int',
            '(declare-const |unfinished Int)',
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.parse(text)

    def test_supplied_variables_avoid_formula_traversal(self):
        x = z3.Int('x')
        b = z3.Bool('b')
        formula = z3.And(x >= 0, x <= 2, b)
        with patch('interval_finder.core.z3.z3util.get_vars', side_effect=AssertionError('unexpected traversal')):
            finder = VarIntervalFinder(formula, [x, b])
            intervals = finder.get_intervals(x, lambda _: None)
            self.assertTrue(verify_intervals(formula, finder.variables, x, intervals)[0])
        self.assertEqual(list(map(str, intervals)), ['[0, 2]'])


if __name__ == '__main__':
    unittest.main()
