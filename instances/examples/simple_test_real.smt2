(declare-const a Real)
(declare-const b Real)
(assert
    (or 
        (and (>= a 3.0) (<= a 5.0)) 
        (and (>= a 9.0) (<= a 12.0))
    )
)
(assert 
    (or
        (and (<= b 9.0) (> b 4.0))
        (<= b 1.0)
    )
)
(check-sat)
