(declare-const a Int)
(declare-const b Int)
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
(check-sat)
