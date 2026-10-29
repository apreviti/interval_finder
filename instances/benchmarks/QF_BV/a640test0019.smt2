(set-info :smt-lib-version 2.6)
(set-logic QF_BV)
(set-info :source |
Bit-vector benchmarks from Dawson Engler's tool contributed by Vijay Ganesh
(vganesh@stanford.edu).  Translated into SMT-LIB format by Clark Barrett using
CVC3.

|)
(set-info :category "industrial")
(set-info :status sat)
(declare-fun buffer_0 () (_ BitVec 8))
(declare-fun buffer_1 () (_ BitVec 8))
(declare-fun buffer_2 () (_ BitVec 8))
(assert (not (= ((_ sign_extend 24) buffer_0) (_ bv0 32))))
(assert (not (= ((_ sign_extend 24) buffer_0) (_ bv43 32))))
(assert (not (= ((_ sign_extend 24) buffer_0) (_ bv37 32))))
(assert (not (not (= ((_ sign_extend 24) buffer_1) (_ bv0 32)))))
(check-sat)
(exit)
