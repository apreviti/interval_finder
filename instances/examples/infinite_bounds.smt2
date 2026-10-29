; Expected integer intervals:
; unrestricted: (-∞, +∞)
; upper_only:   (-∞, 5]
; lower_only:   [5, +∞)
; two_tails:    (-∞, 0]; [10, +∞)

(set-logic QF_LIA)
(declare-const unrestricted Int)
(declare-const upper_only Int)
(declare-const lower_only Int)
(declare-const two_tails Int)

(assert (<= upper_only 5))
(assert (>= lower_only 5))
(assert (or (<= two_tails 0) (>= two_tails 10)))

(check-sat)
