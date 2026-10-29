# Author: Alessandro Previti
import unittest

import z3

from interval_finder import ValInterval, VarIntervalFinder
from interval_finder.verify import verify_intervals


class VerifyContextTests(unittest.TestCase):
    def test_computed_intervals_in_custom_context(self):
        ctx = z3.Context()
        for sort in (z3.IntSort(ctx), z3.RealSort(ctx), z3.BitVecSort(4, ctx)):
            x = z3.Const('x', sort)
            b = z3.Bool('b', ctx=ctx)
            formula = z3.And(x >= 0, x <= 2, b)
            with self.subTest(sort=str(sort)):
                intervals = VarIntervalFinder(formula).get_intervals(x, lambda _: None)
                self.assertEqual(verify_intervals(formula, [x, b], x, intervals),
                                 (True, 'Intervals are correct'))

    def test_empty_and_unbounded_intervals_in_custom_context(self):
        ctx = z3.Context()
        x = z3.Int('x', ctx=ctx)
        zero = z3.IntVal(0, ctx=ctx)
        cases = [
            (z3.And(x > 1, x < 0), [], True),
            (x >= 0, [], False),
            (x == x, [ValInterval(None, None)], True),
            (x >= 0, [ValInterval(None, None)], False),
            (x >= 0, [ValInterval(zero, None)], True),
        ]
        for formula, intervals, expected in cases:
            with self.subTest(formula=str(formula), intervals=list(map(str, intervals))):
                self.assertEqual(verify_intervals(formula, [x], x, intervals)[0], expected)

    def test_parsed_assertions_in_custom_context(self):
        ctx = z3.Context()
        x = z3.Int('x', ctx=ctx)
        for text, intervals in (
            ('(declare-const x Int) (assert (and (>= x 0) (<= x 2)))',
             [ValInterval(z3.IntVal(0, ctx), z3.IntVal(2, ctx))]),
            ('', [ValInterval(None, None)]),
        ):
            with self.subTest(text=text):
                formula = z3.parse_smt2_string(text, ctx=ctx)
                self.assertTrue(verify_intervals(formula, [x], x, intervals)[0])


if __name__ == '__main__':
    unittest.main()
