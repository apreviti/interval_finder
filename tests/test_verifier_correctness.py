# Author: Alessandro Previti
import random
import unittest
import z3
from interval_finder import ValInterval
from interval_finder.verify import verify_intervals


class VerifierCorrectnessTests(unittest.TestCase):
    def test_real_endpoints_and_missing_components(self):
        for ctx in (z3.main_ctx(), z3.Context()):
            x = z3.Real('x', ctx=ctx)
            val = lambda n: z3.RealVal(n, ctx=ctx)
            f = z3.And(x > 0, x < 1)
            cases = [
                ([ValInterval(val(0), val(1), True, True)], True),
                ([ValInterval(val(0), val(1), False, True)], False),
                ([ValInterval(val(0), val(1), True, False)], False),
                ([ValInterval(val('1/4'), val('3/4'))], False),
                ([], False),
                ([ValInterval(None, None)], False),
            ]
            for intervals, expected in cases:
                with self.subTest(intervals=list(map(str, intervals))):
                    self.assertEqual(verify_intervals(f, [x], x, intervals)[0], expected)
            f = z3.Or(x == 0, x == 2)
            self.assertFalse(verify_intervals(f, [x], x, [ValInterval(val(0), val(0))])[0])
            self.assertFalse(verify_intervals(f, [x], x, [ValInterval(val(0), val(2))])[0])

    def test_dont_care_unsat_and_empty_assertions(self):
        for ctx in (z3.main_ctx(), z3.Context()):
            x = z3.Int('x', ctx=ctx)
            b = z3.Bool('b', ctx=ctx)
            zero = z3.IntVal(0, ctx=ctx)
            full = [ValInterval(None, None)]
            partial = [ValInterval(zero, zero)]
            for variables in (None, [x, b]):
                self.assertTrue(verify_intervals(b, variables, x, full)[0])
                self.assertFalse(verify_intervals(b, variables, x, partial)[0])
                self.assertFalse(verify_intervals(b, variables, x, [])[0])
                self.assertTrue(verify_intervals(z3.And(b, z3.Not(b)), variables, x, [])[0])
                self.assertFalse(verify_intervals(z3.And(b, z3.Not(b)), variables, x, full)[0])
            empty = z3.parse_smt2_string('', ctx=ctx)
            self.assertTrue(verify_intervals(empty, None, x, full)[0])
            self.assertFalse(verify_intervals(empty, None, x, partial)[0])

    def test_exhaustive_oracle_for_boolean_dependent_bitvectors(self):
        rng = random.Random(20261028)
        for ctx in (z3.main_ctx(), z3.Context()):
            x = z3.BitVec('x', 3, ctx=ctx)
            y = z3.BitVec('y', 2, ctx=ctx)
            b = z3.Bool('b', ctx=ctx)
            for case in range(40):
                # Arbitrary feasible triples; no interval-finder code is called.
                triples = [(a, c, flag) for a in range(8) for c in range(4)
                           for flag in (False, True) if rng.random() < .06]
                terms = [z3.And(x == a, y == c, b == flag) for a, c, flag in triples]
                formula = z3.Or(terms) if terms else z3.BoolVal(False, ctx=ctx)
                feasible = set()
                solver = z3.Solver(ctx=ctx)
                solver.set(timeout=1000)
                solver.add(formula)
                for value in range(8):
                    solver.push(); solver.add(x == value)
                    result = solver.check(); solver.pop()
                    self.assertNotEqual(result, z3.unknown)
                    if result == z3.sat:
                        feasible.add(value)
                candidates = [feasible, set(), set(range(8)), feasible ^ {rng.randrange(8)}]
                for candidate in candidates:
                    intervals = [ValInterval(z3.BitVecVal(v, 3, ctx), z3.BitVecVal(v, 3, ctx))
                                 for v in sorted(candidate)]
                    for variables in (None, [x, y, b]):
                        with self.subTest(case=case, candidate=sorted(candidate)):
                            self.assertEqual(verify_intervals(formula, variables, x, intervals)[0],
                                             candidate == feasible)


if __name__ == '__main__':
    unittest.main()
