; Backbones: a >= 6 / b >= 0
(declare-const a Int)
(declare-const b Int)
(assert (>= (+ (* 2 a)  (* -3 b)) 11))
(assert (>= (+ (* -1 a) (* 3 b)) -6))
(assert (<= b 4))
;(assert (= a 6))
(check-sat)
