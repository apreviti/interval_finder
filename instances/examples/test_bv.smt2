(set-logic QF_BV)

(declare-fun x () (_ BitVec 8))
(declare-fun y () (_ BitVec 8))

(assert (or
    (and (bvugt x (_ bv5 8)) (bvult x (_ bv128 8)))
    (and (bvugt x (_ bv168 8)) (bvult x (_ bv202 8)))
))

(check-sat)
(get-model)
