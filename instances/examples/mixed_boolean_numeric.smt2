; Expected domains:
; choose_low: {false, true}
; x (Int): [0, 2]; [5, 7]
; r (Real): (0, 1); [3, 4]
; The Boolean selects matching low or high ranges for both numeric variables.
(declare-const choose_low Bool)
(declare-const x Int)
(declare-const r Real)
(assert (ite choose_low
    (and (<= 0 x) (<= x 2) (< 0 r) (< r 1))
    (and (<= 5 x) (<= x 7) (<= 3 r) (<= r 4))))
(check-sat)
