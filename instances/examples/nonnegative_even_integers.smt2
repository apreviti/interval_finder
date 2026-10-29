; The feasible values of x are 0, 2, 4, 6, ... .
; The exact domain requires infinitely many singleton intervals.
; Try with --var x to observe interval output; computation may not terminate.
(set-logic QF_LIA)
(declare-const x Int)
(declare-const y Int)
(assert (= x (* 2 y)))
(assert (>= x 0))
(check-sat)
