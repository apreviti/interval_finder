(declare-const a Real)
(declare-const b Int)
(declare-const c Int)
;(declare-fun x () (_ BitVec 8))

;(assert (>= (+ (* 1 a)  (* 1 b)) 10))
(assert 
    (or 
        (and (>= a 3) (<= a 5)) 
        (and (>= a 9) (<= a 12))
        ;(>= a 9)
    )
)
(assert 
    (or
        (and (<= b 9) (> b 4))
        (< b 1)
    )
)
;(assert (bvugt x (_ bv5 8))) ; x > 5 (unsigned)
(check-sat)
