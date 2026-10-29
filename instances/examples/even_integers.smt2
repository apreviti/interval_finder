; The feasible values of x are all even integers, in both directions.
; Each feasible x is an isolated singleton interval [2*k, 2*k].
; Thus the exact domain requires infinitely many disjoint intervals.
; Try the interval finder with --var x; it may not terminate.
(set-logic QF_LIA)
(declare-const x Int)
(declare-const y Int)
(assert (= x (* 2 y)))
(check-sat)
