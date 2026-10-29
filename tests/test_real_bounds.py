# Author: Alessandro Previti
import unittest
import z3
from interval_finder import VarIntervalFinder
from interval_finder.verify import verify_intervals


class RealBoundTests(unittest.TestCase):
    def check_domain(self, ctx, build, expected):
        x = z3.Real('x', ctx=ctx)
        formula = build(x)
        finder = VarIntervalFinder(formula)
        intervals = finder.get_intervals(x, lambda _: None)
        self.assertEqual(len(intervals), len(expected))
        for iv, (lo, hi, lo_open, hi_open) in zip(intervals, expected):
            for actual, value in ((iv.l_val, lo), (iv.h_val, hi)):
                if value is None:
                    self.assertIsNone(actual)
                else:
                    self.assertTrue(z3.is_true(z3.simplify(actual == z3.RealVal(value, ctx=ctx))))
            self.assertEqual(iv.l_open, lo_open)
            self.assertEqual(iv.h_open, hi_open)
        self.assertEqual(verify_intervals(formula, finder.variables, x, intervals),
                         (True, 'Intervals are correct'))

    def test_open_and_mixed_finite_bounds(self):
        cases = [
            (lambda x: z3.And(x > 0, x < 1), [(0, 1, True, True)]),
            (lambda x: z3.And(x >= 0, x < 1), [(0, 1, False, True)]),
            (lambda x: z3.And(x > 0, x <= 1), [(0, 1, True, False)]),
            (lambda x: z3.And(3*x > -2, 7*x < 5), [('-2/3', '5/7', True, True)]),
        ]
        for ctx in (z3.main_ctx(), z3.Context()):
            for build, expected in cases:
                with self.subTest(expected=expected, custom_context=ctx != z3.main_ctx()):
                    self.check_domain(ctx, build, expected)

    def test_open_unbounded_tails(self):
        cases = [
            (lambda x: x < 0, [(None, 0, False, True)]),
            (lambda x: x > 0, [(0, None, True, False)]),
            (lambda x: z3.Or(x < 0, x > 1), [(None, 0, False, True), (1, None, True, False)]),
        ]
        for ctx in (z3.main_ctx(), z3.Context()):
            for build, expected in cases:
                with self.subTest(expected=expected):
                    self.check_domain(ctx, build, expected)

    def test_disjoint_intervals_and_missing_point(self):
        cases = [
            (lambda x: z3.Or(z3.And(x > 0, x < 1), z3.And(x >= 2, x < 3)),
             [(0, 1, True, True), (2, 3, False, True)]),
            (lambda x: z3.And(x >= 0, x <= 2, x != 1),
             [(0, 1, False, True), (1, 2, True, False)]),
            (lambda x: z3.Or(z3.And(x > 0, x < 1), x == 2),
             [(0, 1, True, True), (2, 2, False, False)]),
        ]
        for ctx in (z3.main_ctx(), z3.Context()):
            for build, expected in cases:
                with self.subTest(expected=expected):
                    self.check_domain(ctx, build, expected)

    def test_boolean_dependent_open_bounds(self):
        for ctx in (z3.main_ctx(), z3.Context()):
            b = z3.Bool('b', ctx=ctx)
            self.check_domain(ctx,
                lambda x: z3.Or(z3.And(b, x > 0, x < 1),
                                z3.And(z3.Not(b), x > 2, x <= 3)),
                [(0, 1, True, True), (2, 3, True, False)])


if __name__ == '__main__':
    unittest.main()
