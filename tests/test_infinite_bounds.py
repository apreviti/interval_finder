# Author: Alessandro Previti
import unittest

import z3

from interval_finder import VarIntervalFinder
from interval_finder.verify import verify_intervals


class InfiniteBoundTests(unittest.TestCase):
    def test_unbounded_domains_and_tails(self):
        for constructor in (z3.Int, z3.Real):
            x = constructor('x')
            y = constructor('y')
            cases = [
                (x == y, [(None, None)]),
                (x <= 5, [(None, 5)]),
                (x >= 5, [(5, None)]),
                (z3.Or(x <= 0, x >= 10), [(None, 0), (10, None)]),
            ]
            for formula, expected in cases:
                with self.subTest(sort=str(x.sort()), formula=str(formula)):
                    finder = VarIntervalFinder(formula)
                    intervals = finder.get_intervals(x, lambda _: None)
                    self.assertEqual(len(intervals), len(expected))
                    for interval, (lower, upper) in zip(intervals, expected):
                        for actual, bound in ((interval.l_val, lower), (interval.h_val, upper)):
                            if bound is None:
                                self.assertIsNone(actual)
                            else:
                                self.assertTrue(z3.is_true(z3.simplify(actual == bound)))
                    self.assertTrue(verify_intervals(formula, finder.variables, x, intervals)[0])


if __name__ == '__main__':
    unittest.main()
