# Author: Alessandro Previti
import unittest

import z3

from interval_finder import VarIntervalFinder


class BackboneTests(unittest.TestCase):
    def test_single_integer_backbone_and_intervals(self):
        x = z3.Int('x')
        finder = VarIntervalFinder(z3.Or(z3.And(x >= 0, x < 10), x > 20))

        self.assertTrue(finder.is_bb_var(x))
        intervals = finder.get_intervals(x, lambda _: None)
        self.assertEqual(len(intervals), 2)
        self.assertEqual(intervals[0].l_val.as_long(), 0)
        self.assertEqual(intervals[0].h_val.as_long(), 9)
        self.assertFalse(intervals[0].l_open)
        self.assertFalse(intervals[0].h_open)
        self.assertEqual(intervals[1].l_val.as_long(), 21)
        self.assertIsNone(intervals[1].h_val)
        self.assertFalse(intervals[1].l_open)

    def test_single_variable_backbone(self):
        for ctx in (z3.main_ctx(), z3.Context()):
            for sort in (z3.IntSort(ctx), z3.RealSort(ctx), z3.BitVecSort(4, ctx)):
                x = z3.Const('x', sort)
                cases = [
                    (z3.And(x >= 0, x <= 2), True),
                    (x == x, False),
                ]
                for formula, expected in cases:
                    with self.subTest(sort=str(sort), formula=str(formula)):
                        self.assertEqual(VarIntervalFinder(formula).is_bb_var(x), expected)

    def test_other_variables_remain_quantified(self):
        x, y = z3.Ints('x y')
        self.assertFalse(VarIntervalFinder(x == y).is_bb_var(x))
        self.assertTrue(VarIntervalFinder(z3.And(x == y, y >= 0)).is_bb_var(x))


if __name__ == '__main__':
    unittest.main()
