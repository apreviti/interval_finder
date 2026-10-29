# Author: Alessandro Previti
import unittest
import z3
from interval_finder import VarIntervalFinder
from interval_finder.verify import verify_intervals


class BitVectorBoundTests(unittest.TestCase):
    def check_domain(self, bits, build, expected):
        for ctx in (z3.main_ctx(), z3.Context()):
            with self.subTest(bits=bits, expected=expected, custom_context=ctx != z3.main_ctx()):
                x = z3.BitVec('x', bits, ctx=ctx)
                formula = build(x)
                finder = VarIntervalFinder(formula)
                intervals = finder.get_intervals(x, lambda _: None)
                self.assertEqual([(iv.l_val.as_long(), iv.h_val.as_long()) for iv in intervals], expected)
                for iv in intervals:
                    self.assertEqual(iv.l_val.size(), bits)
                    self.assertEqual(iv.h_val.size(), bits)
                    self.assertFalse(iv.l_open)
                    self.assertFalse(iv.h_open)
                self.assertTrue(verify_intervals(formula, finder.variables, x, intervals)[0])
                # Independent oracle: fix each bit pattern and check satisfiability.
                solver = z3.Solver(ctx=ctx)
                solver.set(timeout=1000)
                solver.add(formula)
                actual_values = []
                for value in range(1 << bits):
                    solver.push()
                    solver.add(x == value)
                    result = solver.check()
                    solver.pop()
                    self.assertNotEqual(result, z3.unknown)
                    if result == z3.sat:
                        actual_values.append(value)
                expected_values = [v for lo, hi in expected for v in range(lo, hi + 1)]
                self.assertEqual(actual_values, expected_values)

    def test_unsigned_endpoints_and_bit_widths(self):
        for bits in (1, 4, 8):
            maximum = (1 << bits) - 1
            cases = [
                (lambda x: x == x, [(0, maximum)]),
                (lambda x: x == 0, [(0, 0)]),
                (lambda x, m=maximum: x == m, [(maximum, maximum)]),
                (lambda x: z3.UGT(x, 0), [(1, maximum)]),
                (lambda x, m=maximum: z3.ULT(x, m), [(0, maximum - 1)]),
                (lambda x: z3.ULT(x, 0), []),
                (lambda x, m=maximum: z3.UGT(x, m), []),
            ]
            for build, expected in cases:
                self.check_domain(bits, build, expected)

    def test_unsigned_sign_boundary_and_disjoint_extremes(self):
        self.check_domain(8, lambda x: z3.UGT(x, 127), [(128, 255)])
        self.check_domain(8, lambda x: z3.And(z3.UGE(x, 126), z3.ULE(x, 129)), [(126, 129)])
        self.check_domain(8, lambda x: z3.Or(z3.ULE(x, 2), z3.UGE(x, 253)), [(0, 2), (253, 255)])

    def test_signed_constraints_report_unsigned_intervals(self):
        self.check_domain(8, lambda x: x < 0, [(128, 255)])
        self.check_domain(8, lambda x: x >= 0, [(0, 127)])
        self.check_domain(8, lambda x: z3.And(x >= -2, x <= 2), [(0, 2), (254, 255)])
        self.check_domain(8, lambda x: x == -128, [(128, 128)])
        self.check_domain(8, lambda x: x == -1, [(255, 255)])

    def test_modular_arithmetic_wraparound(self):
        self.check_domain(8, lambda x: x + 1 == 0, [(255, 255)])
        self.check_domain(8, lambda x: x - 1 == 255, [(0, 0)])
        self.check_domain(8, lambda x: z3.ULT(x + 1, 2), [(0, 0), (255, 255)])


if __name__ == '__main__':
    unittest.main()
