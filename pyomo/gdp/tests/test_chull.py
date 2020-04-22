#  ___________________________________________________________________________
#
#  Pyomo: Python Optimization Modeling Objects
#  Copyright 2017 National Technology and Engineering Solutions of Sandia, LLC
#  Under the terms of Contract DE-NA0003525 with National Technology and
#  Engineering Solutions of Sandia, LLC, the U.S. Government retains certain
#  rights in this software.
#  This software is distributed under the 3-clause BSD License.
#  ___________________________________________________________________________

import pyutilib.th as unittest

from pyomo.environ import *
from pyomo.core.base import constraint
from pyomo.repn import generate_standard_repn

from pyomo.gdp import *
import pyomo.gdp.tests.models as models
import common_tests as ct

import pyomo.opt
linear_solvers = pyomo.opt.check_available_solvers(
    'glpk','cbc','gurobi','cplex')

import random
from six import iteritems, iterkeys

# DEBUG
from nose.tools import set_trace


EPS = TransformationFactory('gdp.chull').CONFIG.EPS

class CommonTests:
    def setUp(self):
        # set seed so we can test name collisions predictably
        random.seed(666)

    def diff_apply_to_and_create_using(self, model):
        ct.diff_apply_to_and_create_using(self, model, 'gdp.chull')

class TwoTermDisj(unittest.TestCase, CommonTests):
    def setUp(self):
        # set seed to test unique namer
        random.seed(666)

    def test_transformation_block(self):
        m = models.makeTwoTermDisj_Nonlinear()
        TransformationFactory('gdp.chull').apply_to(m)

        transBlock = m._pyomo_gdp_chull_relaxation
        self.assertIsInstance(transBlock, Block)
        lbub = transBlock.lbub
        self.assertIsInstance(lbub, Set)
        self.assertEqual(lbub, ['lb', 'ub', 'eq'])

        disjBlock = transBlock.relaxedDisjuncts
        self.assertIsInstance(disjBlock, Block)
        self.assertEqual(len(disjBlock), 2)

    def test_transformation_block_name_collision(self):
        ct.check_transformation_block_name_collision(self, 'chull')

    def test_disaggregated_vars(self):
        m = models.makeTwoTermDisj_Nonlinear()
        TransformationFactory('gdp.chull').apply_to(m)

        disjBlock = m._pyomo_gdp_chull_relaxation.relaxedDisjuncts
        # same on both disjuncts
        for i in [0,1]:
            relaxationBlock = disjBlock[i]
            w = relaxationBlock.w
            x = relaxationBlock.x
            y = relaxationBlock.y
            # variables created
            self.assertIsInstance(w, Var)
            self.assertIsInstance(x, Var)
            self.assertIsInstance(y, Var)
            # the are in reals
            self.assertIsInstance(w.domain, RealSet)
            self.assertIsInstance(x.domain, RealSet)
            self.assertIsInstance(y.domain, RealSet)
            # they don't have bounds
            self.assertEqual(w.lb, 0)
            self.assertEqual(w.ub, 7)
            self.assertEqual(x.lb, 0)
            self.assertEqual(x.ub, 8)
            self.assertEqual(y.lb, -10)
            self.assertEqual(y.ub, 0)

    def check_furman_et_al_denominator(self, expr, ind_var):
        self.assertEqual(expr._const, EPS)
        self.assertEqual(len(expr._args), 1)
        self.assertEqual(len(expr._coef), 1)
        self.assertEqual(expr._coef[0], 1 - EPS)
        self.assertIs(expr._args[0], ind_var)

    def test_transformed_constraint_nonlinear(self):
        m = models.makeTwoTermDisj_Nonlinear()
        TransformationFactory('gdp.chull').apply_to(m)

        disjBlock = m._pyomo_gdp_chull_relaxation.relaxedDisjuncts

        # the only constraint on the first block is the non-linear one
        disj1c = disjBlock[0].component("d[0].c")
        self.assertIsInstance(disj1c, Constraint)
        # we only have an upper bound
        self.assertEqual(len(disj1c), 1)
        cons = disj1c['ub']
        self.assertIsNone(cons.lower)
        self.assertEqual(cons.upper, 0)
        repn = generate_standard_repn(cons.body)
        self.assertFalse(repn.is_linear())
        self.assertEqual(len(repn.linear_vars), 1)
        # This is a weak test, but as good as any to ensure that the
        # substitution was done correctly
        EPS_1 = 1-EPS
        self.assertEqual(
            str(cons.body),
            "(%s*d[0].indicator_var + %s)*("
            "_pyomo_gdp_chull_relaxation.relaxedDisjuncts[0].x"
            "/(%s*d[0].indicator_var + %s) + "
            "(_pyomo_gdp_chull_relaxation.relaxedDisjuncts[0].y/"
            "(%s*d[0].indicator_var + %s))**2) - "
            "%s*(0.0 + 0.0**2)*(1 - d[0].indicator_var) "
            "- 14.0*d[0].indicator_var"
            % (EPS_1, EPS, EPS_1, EPS, EPS_1, EPS, EPS))

    def test_transformed_constraints_linear(self):
        m = models.makeTwoTermDisj_Nonlinear()
        TransformationFactory('gdp.chull').apply_to(m)

        disjBlock = m._pyomo_gdp_chull_relaxation.relaxedDisjuncts

        # the only constraint on the first block is the non-linear one
        c1 = disjBlock[1].component("d[1].c1")
        # has only lb
        self.assertEqual(len(c1), 1)
        cons = c1['lb']
        self.assertIsNone(cons.lower)
        self.assertEqual(cons.upper, 0)
        repn = generate_standard_repn(cons.body)
        self.assertTrue(repn.is_linear())
        self.assertEqual(len(repn.linear_vars), 2)
        ct.check_linear_coef(self, repn, disjBlock[1].x, -1)
        ct.check_linear_coef(self, repn, m.d[1].indicator_var, 2)
        self.assertEqual(repn.constant, 0)
        self.assertEqual(disjBlock[1].x.lb, 0)
        self.assertEqual(disjBlock[1].x.ub, 8)

        c2 = disjBlock[1].component("d[1].c2")
        # 'eq' is preserved
        self.assertEqual(len(c2), 1)
        cons = c2['eq']
        self.assertEqual(cons.lower, 0)
        self.assertEqual(cons.upper, 0)
        repn = generate_standard_repn(cons.body)
        self.assertTrue(repn.is_linear())
        self.assertEqual(len(repn.linear_vars), 2)
        ct.check_linear_coef(self, repn, disjBlock[1].w, 1)
        ct.check_linear_coef(self, repn, m.d[1].indicator_var, -3)
        self.assertEqual(repn.constant, 0)
        self.assertEqual(disjBlock[1].w.lb, 0)
        self.assertEqual(disjBlock[1].w.ub, 7)

        c3 = disjBlock[1].component("d[1].c3")
        # bounded inequality is split
        self.assertEqual(len(c3), 2)
        cons = c3['lb']
        self.assertIsNone(cons.lower)
        self.assertEqual(cons.upper, 0)
        repn = generate_standard_repn(cons.body)
        self.assertTrue(repn.is_linear())
        self.assertEqual(len(repn.linear_vars), 2)
        ct.check_linear_coef(self, repn, disjBlock[1].x, -1)
        ct.check_linear_coef(self, repn, m.d[1].indicator_var, 1)
        self.assertEqual(repn.constant, 0)

        cons = c3['ub']
        self.assertIsNone(cons.lower)
        self.assertEqual(cons.upper, 0)
        repn = generate_standard_repn(cons.body)
        self.assertTrue(repn.is_linear())
        self.assertEqual(len(repn.linear_vars), 2)
        ct.check_linear_coef(self, repn, disjBlock[1].x, 1)
        ct.check_linear_coef(self, repn, m.d[1].indicator_var, -3)
        self.assertEqual(repn.constant, 0)

    def check_bound_constraints(self, cons, disvar, indvar, lb, ub):
        self.assertIsInstance(cons, Constraint)
        # both lb and ub
        self.assertEqual(len(cons), 2)
        varlb = cons['lb']
        self.assertIsNone(varlb.lower)
        self.assertEqual(varlb.upper, 0)
        repn = generate_standard_repn(varlb.body)
        self.assertTrue(repn.is_linear())
        self.assertEqual(repn.constant, 0)
        self.assertEqual(len(repn.linear_vars), 2)
        ct.check_linear_coef(self, repn, indvar, lb)
        ct.check_linear_coef(self, repn, disvar, -1)

        varub = cons['ub']
        self.assertIsNone(varub.lower)
        self.assertEqual(varub.upper, 0)
        repn = generate_standard_repn(varub.body)
        self.assertTrue(repn.is_linear())
        self.assertEqual(repn.constant, 0)
        self.assertEqual(len(repn.linear_vars), 2)
        ct.check_linear_coef(self, repn, indvar, -ub)
        ct.check_linear_coef(self, repn, disvar, 1)

    def test_disaggregatedVar_bounds(self):
        m = models.makeTwoTermDisj_Nonlinear()
        TransformationFactory('gdp.chull').apply_to(m)

        disjBlock = m._pyomo_gdp_chull_relaxation.relaxedDisjuncts
        for i in [0,1]:
            # check bounds constraints for each variable on each of the two
            # disjuncts.
            self.check_bound_constraints(disjBlock[i].w_bounds, disjBlock[i].w,
                                         m.d[i].indicator_var, 2, 7)
            self.check_bound_constraints(disjBlock[i].x_bounds, disjBlock[i].x,
                                         m.d[i].indicator_var, 1, 8)
            self.check_bound_constraints(disjBlock[i].y_bounds, disjBlock[i].y,
                                         m.d[i].indicator_var, -10, -3)

    def test_error_for_or(self):
        m = models.makeTwoTermDisj_Nonlinear()
        m.disjunction.xor = False

        self.assertRaisesRegexp(
            GDP_Error,
            "Cannot do convex hull transformation for disjunction disjunction "
            "with OR constraint. Must be an XOR!*",
            TransformationFactory('gdp.chull').apply_to,
            m)

    def check_disaggregation_constraint(self, cons, var, disvar1, disvar2):
        repn = generate_standard_repn(cons.body)
        self.assertEqual(cons.lower, 0)
        self.assertEqual(cons.upper, 0)
        self.assertEqual(len(repn.linear_vars), 3)
        ct.check_linear_coef(self, repn, var, 1)
        ct.check_linear_coef(self, repn, disvar1, -1)
        ct.check_linear_coef(self, repn, disvar2, -1)

    def test_disaggregation_constraint(self):
        m = models.makeTwoTermDisj_Nonlinear()
        chull = TransformationFactory('gdp.chull')
        chull.apply_to(m)
        disjBlock = m._pyomo_gdp_chull_relaxation.relaxedDisjuncts

        self.check_disaggregation_constraint(
            chull.get_disaggregation_constraint(m.w, m.disjunction), m.w,
            disjBlock[0].w, disjBlock[1].w)
        self.check_disaggregation_constraint(
            chull.get_disaggregation_constraint(m.x, m.disjunction), m.x,
            disjBlock[0].x, disjBlock[1].x)
        self.check_disaggregation_constraint(
            chull.get_disaggregation_constraint(m.y, m.disjunction), m.y,
            disjBlock[0].y, disjBlock[1].y)

    def test_xor_constraint_mapping(self):
        ct.check_xor_constraint_mapping(self, 'chull')

    def test_xor_constraint_mapping_two_disjunctions(self):
        ct.check_xor_constraint_mapping_two_disjunctions(self, 'chull')

    def test_transformed_disjunct_mappings(self):
        ct.check_disjunct_mapping(self, 'chull')

    def test_transformed_constraint_mappings(self):
        m = models.makeTwoTermDisj_Nonlinear()
        chull = TransformationFactory('gdp.chull')
        chull.apply_to(m)

        disjBlock = m._pyomo_gdp_chull_relaxation.relaxedDisjuncts

        # first disjunct
        orig1 = m.d[0].c
        trans1 = disjBlock[0].component("d[0].c")
        self.assertIs(chull.get_src_constraint(trans1), orig1)
        self.assertIs(chull.get_transformed_constraint(orig1), trans1)

        # second disjunct
        
        # first constraint
        orig1 = m.d[1].c1
        trans1 = disjBlock[1].component("d[1].c1")
        self.assertIs(chull.get_src_constraint(trans1), orig1)
        self.assertIs(chull.get_transformed_constraint(orig1), trans1)
        
        # second constraint
        orig2 = m.d[1].c2
        trans2 = disjBlock[1].component("d[1].c2")
        self.assertIs(chull.get_src_constraint(trans2), orig2)
        self.assertIs(chull.get_transformed_constraint(orig2), trans2)
        
        # third constraint
        orig3 = m.d[1].c3
        trans3 = disjBlock[1].component("d[1].c3")
        self.assertIs(chull.get_src_constraint(trans3), orig3)
        self.assertIs(chull.get_transformed_constraint(orig3), trans3)

    def test_disaggregatedVar_mappings(self):
        m = models.makeTwoTermDisj_Nonlinear()
        chull = TransformationFactory('gdp.chull')
        chull.apply_to(m)

        disjBlock = m._pyomo_gdp_chull_relaxation.relaxedDisjuncts

        for i in [0,1]:
            mappings = ComponentMap()
            mappings[m.w] = disjBlock[i].w
            mappings[m.y] = disjBlock[i].y
            mappings[m.x] = disjBlock[i].x

            for orig, disagg in iteritems(mappings):
                self.assertIs(chull.get_src_var(disagg), orig)
                self.assertIs(chull.get_disaggregated_var(orig, m.d[i]), disagg)

    def test_bigMConstraint_mappings(self):
        m = models.makeTwoTermDisj_Nonlinear()
        chull = TransformationFactory('gdp.chull')
        chull.apply_to(m)

        disjBlock = m._pyomo_gdp_chull_relaxation.relaxedDisjuncts

        for i in [0,1]:
            mappings = ComponentMap()
            # [ESJ 11/05/2019] I think this test was useless before... I think
            # this *map* was useless before. It should be disaggregated variable
            # to the constraints, not the original variable? Why did this even
            # work??
            mappings[disjBlock[i].w] = disjBlock[i].w_bounds
            mappings[disjBlock[i].y] = disjBlock[i].y_bounds
            mappings[disjBlock[i].x] = disjBlock[i].x_bounds
            for var, cons in iteritems(mappings):
                self.assertIs(chull.get_var_bounds_constraint(var), cons)

    def test_create_using_nonlinear(self):
        m = models.makeTwoTermDisj_Nonlinear()
        self.diff_apply_to_and_create_using(m)

    # [ESJ 02/14/2020] In order to match bigm and the (unfortunate) expectation
    # we have established, we never decide something is local based on where it
    # is declared. We treat variables declared on Disjuncts as if they are
    # declared globally. We need to use the bounds as if they are global and
    # also disaggregate the variable
    def test_locally_declared_var_bounds_used_globally(self):
        m = models.localVar()
        chull = TransformationFactory('gdp.chull')
        chull.apply_to(m)

        # check that we used the bounds on the local variable as if they are
        # global. Which means checking the bounds constraints...
        y_disagg = m.disj2.transformation_block().y
        cons = chull.get_var_bounds_constraint(y_disagg)
        lb = cons['lb']
        self.assertIsNone(lb.lower)
        self.assertEqual(value(lb.upper), 0)
        repn = generate_standard_repn(lb.body)
        self.assertTrue(repn.is_linear())
        ct.check_linear_coef(self, repn, m.disj2.indicator_var, 1)
        ct.check_linear_coef(self, repn, y_disagg, -1)

        ub = cons['ub']
        self.assertIsNone(ub.lower)
        self.assertEqual(value(ub.upper), 0)
        repn = generate_standard_repn(ub.body)
        self.assertTrue(repn.is_linear())
        ct.check_linear_coef(self, repn, y_disagg, 1)
        ct.check_linear_coef(self, repn, m.disj2.indicator_var, -3)

    def test_locally_declared_variables_disaggregated(self):
        m = models.localVar()

        chull = TransformationFactory('gdp.chull')
        chull.apply_to(m)

        # two birds one stone: test the mappings too
        disj1y = chull.get_disaggregated_var(m.disj2.y, m.disj1)
        disj2y = chull.get_disaggregated_var(m.disj2.y, m.disj2)
        self.assertIs(disj1y, m.disj1._transformation_block().y)
        self.assertIs(disj2y, m.disj2._transformation_block().y)
        self.assertIs(chull.get_src_var(disj1y), m.disj2.y)
        self.assertIs(chull.get_src_var(disj2y), m.disj2.y)

    def test_global_vars_local_to_a_disjunction_disaggregated(self):
        # The point of this is that where a variable is declared has absolutely
        # nothing to do with whether or not it should be disaggregated. With the
        # only exception being that we can tell disaggregated variables and we
        # know they are really and truly local to only one disjunct (EVER, in the
        # whole model) because we declared them.

        # So here, for some perverse reason, we declare the variables on disj1,
        # but we use them in disj2. Both of them need to be disaggregated in
        # both disjunctions though: Neither is local. (And, unless we want to do
        # a search of the whole model (or disallow this kind of insanity) we
        # can't be smarter because what if you transformed this one disjunction
        # at a time? You can never assume a variable isn't used elsewhere in the
        # model, and if it is, you must disaggregate it.)
        m = ConcreteModel()
        m.disj1 = Disjunct()
        m.disj1.x = Var(bounds=(1, 10))
        m.disj1.y = Var(bounds=(2, 11))
        m.disj1.cons1 = Constraint(expr=m.disj1.x + m.disj1.y <= 5)
        m.disj2 = Disjunct()
        m.disj2.cons = Constraint(expr=m.disj1.y >= 8)
        m.disjunction1 = Disjunction(expr=[m.disj1, m.disj2])

        m.disj3 = Disjunct()
        m.disj3.cons = Constraint(expr=m.disj1.x >= 7)
        m.disj4 = Disjunct()
        m.disj4.cons = Constraint(expr=m.disj1.y == 3)
        m.disjunction2 = Disjunction(expr=[m.disj3, m.disj4])

        chull = TransformationFactory('gdp.chull')
        chull.apply_to(m)
        # check that all the variables are disaggregated
        for disj in [m.disj1, m.disj2, m.disj3, m.disj4]:
            transBlock = disj.transformation_block()
            self.assertEqual(len([v for v in
                                  transBlock.component_data_objects(Var)]), 2)
            x = transBlock.component("x")
            y = transBlock.component("y")
            self.assertIsInstance(x, Var)
            self.assertIsInstance(y, Var)
            self.assertIs(chull.get_disaggregated_var(m.disj1.x, disj), x)
            self.assertIs(chull.get_src_var(x), m.disj1.x)
            self.assertIs(chull.get_disaggregated_var(m.disj1.y, disj), y)
            self.assertIs(chull.get_src_var(y), m.disj1.y)

    def check_name_collision_disaggregated_vars(self, m, disj, name):
        chull = TransformationFactory('gdp.chull')
        transBlock = disj.transformation_block()
        self.assertEqual(len([v for v in
                              transBlock.component_data_objects(Var)]), 2)
        x = transBlock.component("x")
        x2 = transBlock.component(name)
        self.assertIsInstance(x, Var)
        self.assertIsInstance(x2, Var)
        self.assertIs(chull.get_disaggregated_var(m.disj1.x, disj), x)
        self.assertIs(chull.get_src_var(x), m.disj1.x)
        self.assertIs(chull.get_disaggregated_var(m.x, disj), x2)
        self.assertIs(chull.get_src_var(x2), m.x)

    def test_disaggregated_var_name_collision(self):
        # same model as the test above, but now I am putting what was disj1.y
        # as m.x, just to invite disaster.
        m = ConcreteModel()
        m.x = Var(bounds=(2, 11))
        m.disj1 = Disjunct()
        m.disj1.x = Var(bounds=(1, 10))
        m.disj1.cons1 = Constraint(expr=m.disj1.x + m.x <= 5)
        m.disj2 = Disjunct()
        m.disj2.cons = Constraint(expr=m.x >= 8)
        m.disjunction1 = Disjunction(expr=[m.disj1, m.disj2])

        m.disj3 = Disjunct()
        m.disj3.cons = Constraint(expr=m.disj1.x >= 7)
        m.disj4 = Disjunct()
        m.disj4.cons = Constraint(expr=m.x == 3)
        m.disjunction2 = Disjunction(expr=[m.disj3, m.disj4])

        chull = TransformationFactory('gdp.chull')
        chull.apply_to(m)
        for disj, nm in ((m.disj1, "x_4"), (m.disj2, "x_9"),
                         (m.disj3, "x_5"), (m.disj4, "x_8")):
            self.check_name_collision_disaggregated_vars(m, disj, nm)

    def test_target_not_a_component_err(self):
        decoy = ConcreteModel()
        decoy.block = Block()
        m = models.makeTwoSimpleDisjunctions()
        self.assertRaisesRegexp(
            GDP_Error,
            "Target block is not a component on instance unknown!",
            TransformationFactory('gdp.chull').apply_to,
            m,
            targets=[decoy.block])

    def test_do_not_transform_user_deactivated_disjuncts(self):
        ct.check_user_deactivated_disjuncts(self, 'chull')

    def test_do_not_transform_userDeactivated_IndexedDisjunction(self):
        ct.check_do_not_transform_userDeactivated_indexedDisjunction(self,
                                                                     'chull')

    def test_disjunction_deactivated(self):
        ct.check_disjunction_deactivated(self, 'chull')

    def test_disjunctDatas_deactivated(self):
        ct.check_disjunctDatas_deactivated(self, 'chull')

    def test_deactivated_constraints(self):
        ct.check_deactivated_constraints(self, 'chull')

    def check_no_double_transformation(self):
        ct.check_do_not_transform_twice_if_disjunction_reactivated(self,
                                                                   'chull')

    def test_indicator_vars(self):
        ct.check_indicator_vars(self, 'chull')

    def test_xor_constraints(self):
        ct.check_xor_constraint(self, 'chull')

    def test_unbounded_var_error(self):
        m = models.makeTwoTermDisj_Nonlinear()
        # no bounds
        m.w.setlb(None)
        m.w.setub(None)
        self.assertRaisesRegexp(
            GDP_Error,
            "Variables that appear in disjuncts must be "
            "bounded in order to use the chull "
            "transformation! Missing bound for w.*",
            TransformationFactory('gdp.chull').apply_to,
            m)

    def test_indexed_constraints_in_disjunct(self):
        m = models.makeThreeTermDisj_IndexedConstraints()

        TransformationFactory('gdp.chull').apply_to(m)
        transBlock = m._pyomo_gdp_chull_relaxation

        # 2 blocks: the original Disjunct and the transformation block
        self.assertEqual(
            len(list(m.component_objects(Block, descend_into=False))), 2)
        self.assertEqual(
            len(list(m.component_objects(Disjunct))), 0)

        # Each relaxed disjunct should have 3 vars, but i "d[i].c"
        # Constraints
        for i in [1,2,3]:
            relaxed = transBlock.relaxedDisjuncts[i-1]
            self.assertEqual(len(list(relaxed.component_objects(Var))), 3)
            self.assertEqual(len(list(relaxed.component_data_objects(Var))), 3)
            self.assertEqual(
                len(list(relaxed.component_objects(Constraint))), 4)
            # Note: m.x LB == 0, so only 3 bounds constriants (not 6)
            self.assertEqual(
                len(list(relaxed.component_data_objects(Constraint))), 3+i)
            self.assertEqual(len(relaxed.component('d[%s].c'%i)), i)

    def test_virtual_indexed_constraints_in_disjunct(self):
        m = ConcreteModel()
        m.I = [1,2,3]
        m.x = Var(m.I, bounds=(-1,10))
        def d_rule(d,j):
            m = d.model()
            d.c = Constraint(Any)
            for k in range(j):
                d.c[k+1] = m.x[k+1] >= k+1
        m.d = Disjunct(m.I, rule=d_rule)
        m.disjunction = Disjunction(expr=[m.d[i] for i in m.I])

        TransformationFactory('gdp.chull').apply_to(m)
        transBlock = m._pyomo_gdp_chull_relaxation

        # 2 blocks: the original Disjunct and the transformation block
        self.assertEqual(
            len(list(m.component_objects(Block, descend_into=False))), 2)
        self.assertEqual(
            len(list(m.component_objects(Disjunct))), 0)

        # Each relaxed disjunct should have 3 vars, but i "d[i].c"
        # Constraints
        for i in [1,2,3]:
            relaxed = transBlock.relaxedDisjuncts[i-1]
            self.assertEqual(len(list(relaxed.component_objects(Var))), 3)
            self.assertEqual(len(list(relaxed.component_data_objects(Var))), 3)
            self.assertEqual(
                len(list(relaxed.component_objects(Constraint))), 4)
            self.assertEqual(
                len(list(relaxed.component_data_objects(Constraint))), 3*2+i)
            self.assertEqual(len(relaxed.component('d[%s].c'%i)), i)

    def test_do_not_transform_deactivated_constraintDatas(self):
        m = models.makeTwoTermDisj_IndexedConstraints()
        m.a[1].setlb(0)
        m.a[1].setub(100)
        m.a[2].setlb(0)
        m.a[2].setub(100)
        m.b.simpledisj1.c[1].deactivate()
        chull = TransformationFactory('gdp.chull')
        chull.apply_to(m)
        indexedCons = chull.get_transformed_constraint(m.b.simpledisj1.c)
        # This is actually 0 because c[1] is deactivated and c[0] fixes a[2] to
        # 0, which is done by fixing the diaggregated variable instead
        self.assertEqual(len(indexedCons), 0)
        disaggregated_a2 = chull.get_disaggregated_var(m.a[2], m.b.simpledisj1)
        self.assertIsInstance(disaggregated_a2, Var)
        self.assertTrue(disaggregated_a2.is_fixed())
        self.assertEqual(value(disaggregated_a2), 0)
        
        # ESJ: TODO: This is my insane idea to map to the disaggregated var that
        # is fixed if that is in fact what the "constraint" is. Also I guess it
        # should be a list of length 1... Ick.
        self.assertIs(chull.get_transformed_constraint(m.b.simpledisj1.c[2]),
                      disaggregated_a2)

        self.assertRaisesRegexp(
            GDP_Error,
            "Constraint b.simpledisj1.c\[1\] has not been transformed.",
            chull.get_transformed_constraint,
            m.b.simpledisj1.c[1])


class IndexedDisjunction(unittest.TestCase, CommonTests):
    def setUp(self):
        # set seed so we can test name collisions predictably
        random.seed(666)

    def test_disaggregation_constraints(self):
        m = models.makeTwoTermIndexedDisjunction()
        chull = TransformationFactory('gdp.chull')
        chull.apply_to(m)
        relaxedDisjuncts = m._pyomo_gdp_chull_relaxation.relaxedDisjuncts

        disaggregatedVars = {
            1: [relaxedDisjuncts[0].component('x[1]'),
                relaxedDisjuncts[1].component('x[1]')],
            2: [relaxedDisjuncts[2].component('x[2]'),
                relaxedDisjuncts[3].component('x[2]')],
            3: [relaxedDisjuncts[4].component('x[3]'),
                relaxedDisjuncts[5].component('x[3]')],
        }

        for i, disVars in iteritems(disaggregatedVars):
            cons = chull.get_disaggregation_constraint(m.x[i],
                                                       m.disjunction[i])
            self.assertEqual(cons.lower, 0)
            self.assertEqual(cons.upper, 0)
            repn = generate_standard_repn(cons.body)
            self.assertTrue(repn.is_linear())
            self.assertEqual(repn.constant, 0)
            self.assertEqual(len(repn.linear_vars), 3)
            ct.check_linear_coef(self, repn, m.x[i], 1)
            ct.check_linear_coef(self, repn, disVars[0], -1)
            ct.check_linear_coef(self, repn, disVars[1], -1)

    def test_disaggregation_constraints_tuple_indices(self):
        m = models.makeTwoTermMultiIndexedDisjunction()
        chull = TransformationFactory('gdp.chull')
        chull.apply_to(m)
        relaxedDisjuncts = m._pyomo_gdp_chull_relaxation.relaxedDisjuncts

        disaggregatedVars = {
            (1,'A'): [relaxedDisjuncts[0].component('a[1,A]'),
                      relaxedDisjuncts[1].component('a[1,A]')],
            (1,'B'): [relaxedDisjuncts[2].component('a[1,B]'),
                      relaxedDisjuncts[3].component('a[1,B]')],
            (2,'A'): [relaxedDisjuncts[4].component('a[2,A]'),
                      relaxedDisjuncts[5].component('a[2,A]')],
            (2,'B'): [relaxedDisjuncts[6].component('a[2,B]'),
                      relaxedDisjuncts[7].component('a[2,B]')],
        }

        for i, disVars in iteritems(disaggregatedVars):
            cons = chull.get_disaggregation_constraint(m.a[i],
                                                       m.disjunction[i])
            self.assertEqual(cons.lower, 0)
            self.assertEqual(cons.upper, 0)
            # NOTE: fixed variables are evaluated here.
            repn = generate_standard_repn(cons.body)
            self.assertTrue(repn.is_linear())
            self.assertEqual(repn.constant, 0)
            # The flag=1 disjunct disaggregated variable is fixed to 0, so the
            # below is actually correct:
            self.assertEqual(len(repn.linear_vars), 2)
            ct.check_linear_coef(self, repn, m.a[i], 1)
            ct.check_linear_coef(self, repn, disVars[0], -1)
            self.assertTrue(disVars[1].is_fixed())
            self.assertEqual(value(disVars[1]), 0)

    def test_xor_constraints(self):
        ct.check_indexed_xor_constraints(self, 'chull')

    def test_create_using(self):
        m = models.makeTwoTermMultiIndexedDisjunction()
        ct.diff_apply_to_and_create_using(self, m, 'gdp.chull')

    def test_deactivated_constraints(self):
        ct.check_constraints_deactivated_indexedDisjunction(self, 'chull')

    def test_disjunction_data_target(self):
        ct.check_disjunction_data_target(self, 'chull')

    def test_disjunction_data_target_any_index(self):
        ct.check_disjunction_data_target_any_index(self, 'chull')
    
    def check_trans_block_disjunctions_of_disjunct_datas(self, m):
        transBlock1 = m.component("_pyomo_gdp_chull_relaxation")
        self.assertIsInstance(transBlock1, Block)
        self.assertIsInstance(transBlock1.component("relaxedDisjuncts"), Block)
        # We end up with a transformation block for every SimpleDisjunction or
        # IndexedDisjunction.
        self.assertEqual(len(transBlock1.relaxedDisjuncts), 2)
        self.assertIsInstance(transBlock1.relaxedDisjuncts[0].component("x"),
                              Var)
        self.assertTrue(transBlock1.relaxedDisjuncts[0].x.is_fixed())
        self.assertEqual(value(transBlock1.relaxedDisjuncts[0].x), 0)
        self.assertIsInstance(transBlock1.relaxedDisjuncts[0].component(
            "firstTerm[1].cons"), Constraint)
        # No constraint becuase disaggregated variable fixed to 0
        self.assertEqual(len(transBlock1.relaxedDisjuncts[0].component(
            "firstTerm[1].cons")), 0)
        self.assertIsInstance(transBlock1.relaxedDisjuncts[0].component(
            "x_bounds"), Constraint)
        self.assertEqual(len(transBlock1.relaxedDisjuncts[0].component(
            "x_bounds")), 2)

        self.assertIsInstance(transBlock1.relaxedDisjuncts[1].component("x"),
                              Var)
        self.assertIsInstance(transBlock1.relaxedDisjuncts[1].component(
            "secondTerm[1].cons"), Constraint)
        self.assertEqual(len(transBlock1.relaxedDisjuncts[1].component(
            "secondTerm[1].cons")), 1)
        self.assertIsInstance(transBlock1.relaxedDisjuncts[1].component(
            "x_bounds"), Constraint)
        self.assertEqual(len(transBlock1.relaxedDisjuncts[1].component(
            "x_bounds")), 2)

        transBlock2 = m.component("_pyomo_gdp_chull_relaxation_4")
        self.assertIsInstance(transBlock2, Block)
        self.assertIsInstance(transBlock2.component("relaxedDisjuncts"), Block)
        self.assertEqual(len(transBlock2.relaxedDisjuncts), 2)
        self.assertIsInstance(transBlock2.relaxedDisjuncts[0].component("x"),
                              Var)
        self.assertIsInstance(transBlock2.relaxedDisjuncts[0].component(
            "firstTerm[2].cons"), Constraint)
        # we have an equality constraint
        self.assertEqual(len(transBlock2.relaxedDisjuncts[0].component(
            "firstTerm[2].cons")), 1)
        self.assertIsInstance(transBlock2.relaxedDisjuncts[0].component(
            "x_bounds"), Constraint)
        self.assertEqual(len(transBlock2.relaxedDisjuncts[0].component(
            "x_bounds")), 2)

        self.assertIsInstance(transBlock2.relaxedDisjuncts[1].component("x"),
                              Var)
        self.assertIsInstance(transBlock2.relaxedDisjuncts[1].component(
            "secondTerm[2].cons"), Constraint)
        self.assertEqual(len(transBlock2.relaxedDisjuncts[1].component(
            "secondTerm[2].cons")), 1)
        self.assertIsInstance(transBlock2.relaxedDisjuncts[1].component(
            "x_bounds"), Constraint)
        self.assertEqual(len(transBlock2.relaxedDisjuncts[1].component(
            "x_bounds")), 2)
                        
    def test_simple_disjunction_of_disjunct_datas(self):
        ct.check_simple_disjunction_of_disjunct_datas(self, 'chull')

    def test_any_indexed_disjunction_of_disjunct_datas(self):
        m = models.makeAnyIndexedDisjunctionOfDisjunctDatas()
        TransformationFactory('gdp.chull').apply_to(m)

        transBlock = m.component("_pyomo_gdp_chull_relaxation")
        self.assertIsInstance(transBlock, Block)
        self.assertIsInstance(transBlock.component("relaxedDisjuncts"), Block)
        self.assertEqual(len(transBlock.relaxedDisjuncts), 4)
        self.assertIsInstance(transBlock.relaxedDisjuncts[0].component("x"),
                              Var)
        self.assertTrue(transBlock.relaxedDisjuncts[0].x.is_fixed())
        self.assertEqual(value(transBlock.relaxedDisjuncts[0].x), 0)
        self.assertIsInstance(transBlock.relaxedDisjuncts[0].component(
            "firstTerm[1].cons"), Constraint)
        # No constraint becuase disaggregated variable fixed to 0
        self.assertEqual(len(transBlock.relaxedDisjuncts[0].component(
            "firstTerm[1].cons")), 0)
        self.assertIsInstance(transBlock.relaxedDisjuncts[0].component(
            "x_bounds"), Constraint)
        self.assertEqual(len(transBlock.relaxedDisjuncts[0].component(
            "x_bounds")), 2)

        self.assertIsInstance(transBlock.relaxedDisjuncts[1].component("x"),
                              Var)
        self.assertIsInstance(transBlock.relaxedDisjuncts[1].component(
            "secondTerm[1].cons"), Constraint)
        self.assertEqual(len(transBlock.relaxedDisjuncts[1].component(
            "secondTerm[1].cons")), 1)
        self.assertIsInstance(transBlock.relaxedDisjuncts[1].component(
            "x_bounds"), Constraint)
        self.assertEqual(len(transBlock.relaxedDisjuncts[1].component(
            "x_bounds")), 2)

        self.assertIsInstance(transBlock.relaxedDisjuncts[2].component("x"),
                              Var)
        self.assertIsInstance(transBlock.relaxedDisjuncts[2].component(
            "firstTerm[2].cons"), Constraint)
        # we have an equality constraint
        self.assertEqual(len(transBlock.relaxedDisjuncts[2].component(
            "firstTerm[2].cons")), 1)
        self.assertIsInstance(transBlock.relaxedDisjuncts[2].component(
            "x_bounds"), Constraint)
        self.assertEqual(len(transBlock.relaxedDisjuncts[2].component(
            "x_bounds")), 2)

        self.assertIsInstance(transBlock.relaxedDisjuncts[3].component("x"),
                              Var)
        self.assertIsInstance(transBlock.relaxedDisjuncts[3].component(
            "secondTerm[2].cons"), Constraint)
        self.assertEqual(len(transBlock.relaxedDisjuncts[3].component(
            "secondTerm[2].cons")), 1)
        self.assertIsInstance(transBlock.relaxedDisjuncts[3].component(
            "x_bounds"), Constraint)
        self.assertEqual(len(transBlock.relaxedDisjuncts[3].component(
            "x_bounds")), 2)

        self.assertIsInstance(transBlock.component("disjunction_xor"),
                              Constraint)
        self.assertEqual(len(transBlock.component("disjunction_xor")), 2)

    def check_first_iteration(self, model):
        transBlock = model.component("_pyomo_gdp_chull_relaxation")
        self.assertIsInstance(transBlock, Block)
        self.assertIsInstance(
            transBlock.component("disjunctionList_xor"), Constraint)
        self.assertEqual(len(transBlock.disjunctionList_xor), 1)
        self.assertFalse(model.disjunctionList[0].active)

        self.assertIsInstance(transBlock.relaxedDisjuncts, Block)
        self.assertEqual(len(transBlock.relaxedDisjuncts), 2)

        self.assertIsInstance(transBlock.relaxedDisjuncts[0].x, Var)
        self.assertTrue(transBlock.relaxedDisjuncts[0].x.is_fixed())
        self.assertEqual(value(transBlock.relaxedDisjuncts[0].x), 0)
        self.assertIsInstance(transBlock.relaxedDisjuncts[0].component(
            "firstTerm[0].cons"), Constraint)
        self.assertEqual(len(transBlock.relaxedDisjuncts[0].component(
            "firstTerm[0].cons")), 0)
        self.assertIsInstance(transBlock.relaxedDisjuncts[0].x_bounds,
                              Constraint)
        self.assertEqual(len(transBlock.relaxedDisjuncts[0].x_bounds), 2)

        self.assertIsInstance(transBlock.relaxedDisjuncts[1].x, Var)
        self.assertFalse(transBlock.relaxedDisjuncts[1].x.is_fixed())
        self.assertIsInstance(transBlock.relaxedDisjuncts[1].component(
            "secondTerm[0].cons"), Constraint)
        self.assertEqual(len(transBlock.relaxedDisjuncts[1].component(
            "secondTerm[0].cons")), 1)
        self.assertIsInstance(transBlock.relaxedDisjuncts[1].x_bounds,
                              Constraint)
        self.assertEqual(len(transBlock.relaxedDisjuncts[1].x_bounds), 2)

    def check_second_iteration(self, model):
        transBlock = model.component("_pyomo_gdp_chull_relaxation")
        self.assertIsInstance(transBlock, Block)
        self.assertIsInstance(transBlock.component("relaxedDisjuncts"), Block)
        self.assertEqual(len(transBlock.relaxedDisjuncts), 4)
        self.assertIsInstance(transBlock.relaxedDisjuncts[2].component(
            "firstTerm[1].cons"), Constraint)
        self.assertEqual(len(transBlock.relaxedDisjuncts[2].component(
            "firstTerm[1].cons")), 1)
        self.assertIsInstance(transBlock.relaxedDisjuncts[3].component(
            "secondTerm[1].cons"), Constraint)
        self.assertEqual(len(transBlock.relaxedDisjuncts[3].component(
            "secondTerm[1].cons")), 1)
        self.assertEqual(
            len(transBlock.disjunctionList_xor), 2)
        self.assertFalse(model.disjunctionList[1].active)
        self.assertFalse(model.disjunctionList[0].active)

    def test_disjunction_and_disjuncts_indexed_by_any(self):
        model = ConcreteModel()
        model.x = Var(bounds=(-100, 100))

        model.firstTerm = Disjunct(Any)
        model.secondTerm = Disjunct(Any)
        model.disjunctionList = Disjunction(Any)

        model.obj = Objective(expr=model.x)
        
        for i in range(2):
            model.firstTerm[i].cons = Constraint(expr=model.x == 2*i)
            model.secondTerm[i].cons = Constraint(expr=model.x >= i + 2)
            model.disjunctionList[i] = [model.firstTerm[i], model.secondTerm[i]]

            TransformationFactory('gdp.chull').apply_to(model)

            if i == 0:
                self.check_first_iteration(model)

            if i == 1:
                self.check_second_iteration(model)

    def test_iteratively_adding_disjunctions_transform_container(self):
        ct.check_iteratively_adding_disjunctions_transform_container(self,
                                                                     'chull')

    def test_iteratively_adding_disjunctions_transform_model(self):
        # Same as above, but transforming whole model in every iteration
        model = ConcreteModel()
        model.x = Var(bounds=(-100, 100))
        model.disjunctionList = Disjunction(Any)
        model.obj = Objective(expr=model.x)
        for i in range(2):
            firstTermName = "firstTerm[%s]" % i
            model.add_component(firstTermName, Disjunct())
            model.component(firstTermName).cons = Constraint(
                expr=model.x == 2*i)
            secondTermName = "secondTerm[%s]" % i
            model.add_component(secondTermName, Disjunct())
            model.component(secondTermName).cons = Constraint(
                expr=model.x >= i + 2)
            model.disjunctionList[i] = [model.component(firstTermName),
                                        model.component(secondTermName)]

            # we're lazy and we just transform the model (and in
            # theory we are transforming at every iteration because we are
            # solving at every iteration)
            TransformationFactory('gdp.chull').apply_to(model)
            if i == 0:
                self.check_first_iteration(model)

            if i == 1:
                self.check_second_iteration(model)

    def test_iteratively_adding_to_indexed_disjunction_on_block(self):
        ct.check_iteratively_adding_to_indexed_disjunction_on_block(self,
                                                                    'chull')

class TestTargets_SingleDisjunction(unittest.TestCase, CommonTests):
    def test_only_targets_inactive(self):
        ct.check_only_targets_inactive(self, 'chull')

    def test_only_targets_transformed(self):
        ct.check_only_targets_get_transformed(self, 'chull')

    def test_target_not_a_component_err(self):
        ct.check_target_not_a_component_error(self, 'chull')

class TestTargets_IndexedDisjunction(unittest.TestCase, CommonTests):
    # There are a couple tests for targets above, but since I had the patience
    # to make all these for bigm also, I may as well reap the benefits here too.
    def test_indexedDisj_targets_inactive(self):
        ct.check_indexedDisj_targets_inactive(self, 'chull')

    def test_indexedDisj_only_targets_transformed(self):
        ct.check_indexedDisj_only_targets_transformed(self, 'chull')
        
    def test_warn_for_untransformed(self):
        ct.check_warn_for_untransformed(self, 'chull')

    def test_disjData_targets_inactive(self):
        ct.check_disjData_targets_inactive(self, 'chull')
        m = models.makeDisjunctionsOnIndexedBlock()        

    def test_disjData_only_targets_transformed(self):
        ct.check_disjData_only_targets_transformed(self, 'chull')

    def test_indexedBlock_targets_inactive(self):
        ct.check_indexedDisj_targets_inactive(self, 'chull')

    def test_indexedBlock_only_targets_transformed(self):
        ct.check_indexedBlock_only_targets_transformed(self, 'chull')

    def test_blockData_targets_inactive(self):
        ct.check_blockData_targets_inactive(self, 'chull')

    def test_blockData_only_targets_transformed(self):
        ct.check_blockData_only_targets_transformed(self, 'chull')

    def test_do_not_transform_deactivated_targets(self):
        ct.check_do_not_transform_deactivated_targets(self, 'chull')

    def test_create_using(self):
        m = models.makeDisjunctionsOnIndexedBlock()
        ct.diff_apply_to_and_create_using(self, m, 'gdp.chull')

class DisaggregatedVarNamingConflict(unittest.TestCase):
    @staticmethod
    def makeModel():
        m = ConcreteModel()
        m.b = Block()
        m.b.x = Var(bounds=(0, 10))
        m.add_component("b.x", Var(bounds=(-9, 9)))
        def disjunct_rule(d, i):
            m = d.model()
            if i:
                d.cons_block = Constraint(expr=m.b.x >= 5)
                d.cons_model = Constraint(expr=m.component("b.x")==0)
            else:
                d.cons_model = Constraint(expr=m.component("b.x") <= -5)
        m.disjunct = Disjunct([0,1], rule=disjunct_rule)
        m.disjunction = Disjunction(expr=[m.disjunct[0], m.disjunct[1]])

        return m

    def test_disaggregation_constraints(self):
        m = self.makeModel()
        chull = TransformationFactory('gdp.chull')
        chull.apply_to(m)

        disaggregationConstraints = m._pyomo_gdp_chull_relaxation.\
                                    disaggregationConstraints

        consmap = [
            (m.component("b.x"), disaggregationConstraints[0]),
            (m.b.x, disaggregationConstraints[1]) 
        ]

        for v, cons in consmap:
            disCons = chull.get_disaggregation_constraint(v, m.disjunction)
            self.assertIs(disCons, cons)
    

class NestedDisjunction(unittest.TestCase, CommonTests):
    def setUp(self):
        # set seed so we can test name collisions predictably
        random.seed(666)

    def test_deactivated_disjunct_leaves_nested_disjuncts_active(self):
        m = models.makeNestedDisjunctions_FlatDisjuncts()
        m.d1.deactivate()
        # Specifying 'targets' prevents the HACK_GDP_Disjunct_Reclassifier
        # transformation of Disjuncts to Blocks
        TransformationFactory('gdp.chull').apply_to(m, targets=[m])

        self.assertFalse(m.d1.active)
        self.assertTrue(m.d1.indicator_var.fixed)
        self.assertEqual(m.d1.indicator_var.value, 0)

        self.assertFalse(m.d2.active)
        self.assertFalse(m.d2.indicator_var.fixed)

        self.assertTrue(m.d3.active)
        self.assertFalse(m.d3.indicator_var.fixed)

        self.assertTrue(m.d4.active)
        self.assertFalse(m.d4.indicator_var.fixed)

        m = models.makeNestedDisjunctions_NestedDisjuncts()
        m.d1.deactivate()
        # Specifying 'targets' prevents the HACK_GDP_Disjunct_Reclassifier
        # transformation of Disjuncts to Blocks
        TransformationFactory('gdp.chull').apply_to(m, targets=[m])

        self.assertFalse(m.d1.active)
        self.assertTrue(m.d1.indicator_var.fixed)
        self.assertEqual(m.d1.indicator_var.value, 0)

        self.assertFalse(m.d2.active)
        self.assertFalse(m.d2.indicator_var.fixed)

        self.assertTrue(m.d1.d3.active)
        self.assertFalse(m.d1.d3.indicator_var.fixed)

        self.assertTrue(m.d1.d4.active)
        self.assertFalse(m.d1.d4.indicator_var.fixed)

    @unittest.skipIf(not linear_solvers, "No linear solver available")
    def test_relaxation_feasibility(self):
        m = models.makeNestedDisjunctions_FlatDisjuncts()
        TransformationFactory('gdp.chull').apply_to(m)

        solver = SolverFactory(linear_solvers[0])

        cases = [
            (1,1,1,1,None),
            (0,0,0,0,None),
            (1,0,0,0,None),
            (0,1,0,0,1.1),
            (0,0,1,0,None),
            (0,0,0,1,None),
            (1,1,0,0,None),
            (1,0,1,0,1.2),
            (1,0,0,1,1.3),
            (1,0,1,1,None),
            ]
        for case in cases:
            m.d1.indicator_var.fix(case[0])
            m.d2.indicator_var.fix(case[1])
            m.d3.indicator_var.fix(case[2])
            m.d4.indicator_var.fix(case[3])
            results = solver.solve(m)
            if case[4] is None:
                self.assertEqual(results.solver.termination_condition,
                                 pyomo.opt.TerminationCondition.infeasible)
            else:
                self.assertEqual(results.solver.termination_condition,
                                 pyomo.opt.TerminationCondition.optimal)
                self.assertEqual(value(m.obj), case[4])

    def test_create_using(self):
        m = models.makeNestedDisjunctions_FlatDisjuncts()
        self.diff_apply_to_and_create_using(m)

class TestSpecialCases(unittest.TestCase):
    def test_warn_for_untransformed(self):
        m = models.makeDisjunctionsOnIndexedBlock()
        def innerdisj_rule(d, flag):
            m = d.model()
            if flag:
                d.c = Constraint(expr=m.a[1] <= 2)
            else:
                d.c = Constraint(expr=m.a[1] >= 65)
        m.disjunct1[1,1].innerdisjunct = Disjunct([0,1], rule=innerdisj_rule)
        m.disjunct1[1,1].innerdisjunction = Disjunction([0],
            rule=lambda a,i: [m.disjunct1[1,1].innerdisjunct[0],
                              m.disjunct1[1,1].innerdisjunct[1]])
        # This test relies on the order that the component objects of
        # the disjunct get considered. In this case, the disjunct
        # causes the error, but in another world, it could be the
        # disjunction, which is also active.
        self.assertRaisesRegexp(
            GDP_Error,
            "Found active disjunct disjunct1\[1,1\].innerdisjunct\[0\] "
            "in disjunct disjunct1\[1,1\]!.*",
            TransformationFactory('gdp.chull').create_using,
            m,
            targets=[m.disjunction1[1]])
        #
        # we will make that disjunction come first now...
        #
        tmp = m.disjunct1[1,1].innerdisjunct
        m.disjunct1[1,1].del_component(tmp)
        m.disjunct1[1,1].add_component('innerdisjunct', tmp)
        self.assertRaisesRegexp(
            GDP_Error,
            "Found untransformed disjunction disjunct1\[1,1\]."
            "innerdisjunction\[0\] in disjunct disjunct1\[1,1\]!.*",
            TransformationFactory('gdp.chull').create_using,
            m,
            targets=[m.disjunction1[1]])
        # Deactivating the disjunction will allow us to get past it back
        # to the Disjunct (after we realize there are no active
        # DisjunctionData within the active Disjunction)
        m.disjunct1[1,1].innerdisjunction[0].deactivate()
        self.assertRaisesRegexp(
            GDP_Error,
            "Found active disjunct disjunct1\[1,1\].innerdisjunct\[0\] "
            "in disjunct disjunct1\[1,1\]!.*",
            TransformationFactory('gdp.chull').create_using,
            m,
            targets=[m.disjunction1[1]])

    def test_local_vars(self):
        m = ConcreteModel()
        m.x = Var(bounds=(5,100))
        m.y = Var(bounds=(0,100))
        m.d1 = Disjunct()
        m.d1.c = Constraint(expr=m.y >= m.x)
        m.d2 = Disjunct()
        m.d2.z = Var()
        m.d2.c = Constraint(expr=m.y >= m.d2.z)
        m.disj = Disjunction(expr=[m.d1, m.d2])

        self.assertRaisesRegexp(
            GDP_Error,
            ".*Missing bound for d2.z.*",
            TransformationFactory('gdp.chull').create_using,
            m)
        m.d2.z.setlb(7)
        self.assertRaisesRegexp(
            GDP_Error,
            ".*Missing bound for d2.z.*",
            TransformationFactory('gdp.chull').create_using,
            m)
        m.d2.z.setub(9)

        i = TransformationFactory('gdp.chull').create_using(m)
        rd = i._pyomo_gdp_chull_relaxation.relaxedDisjuncts[1]
        # z should be disaggregated becuase we can't be sure it's not somewhere
        # else on the model
        self.assertEqual(sorted(rd.component_map(Var)), ['x','y','z'])
        self.assertEqual(len(rd.component_map(Constraint)), 4)
        # bounds haven't changed on original
        self.assertEqual(i.d2.z.bounds, (7,9))
        # check disaggregated variable
        self.assertIsInstance(rd.component("z"), Var)
        self.assertEqual(rd.z.bounds, (0,9))
        self.assertEqual(len(rd.z_bounds), 2)
        self.assertEqual(rd.z_bounds['lb'].lower, None)
        self.assertEqual(rd.z_bounds['lb'].upper, 0)
        self.assertEqual(rd.z_bounds['ub'].lower, None)
        self.assertEqual(rd.z_bounds['ub'].upper, 0)
        i.d2.indicator_var = 1
        rd.z = 2
        self.assertEqual(rd.z_bounds['lb'].body(), 5)
        self.assertEqual(rd.z_bounds['ub'].body(), -7)

        m.d2.z.setlb(-9)
        m.d2.z.setub(-7)
        i = TransformationFactory('gdp.chull').create_using(m)
        rd = i._pyomo_gdp_chull_relaxation.relaxedDisjuncts[1]
        self.assertEqual(sorted(rd.component_map(Var)), ['x','y','z'])
        self.assertEqual(len(rd.component_map(Constraint)), 4)
        # original bounds unchanged
        self.assertEqual(i.d2.z.bounds, (-9,-7))
        # check disaggregated variable
        self.assertIsInstance(rd.component("z"), Var)
        self.assertEqual(rd.z.bounds, (-9,0))
        self.assertEqual(len(rd.z_bounds), 2)
        self.assertEqual(rd.z_bounds['lb'].lower, None)
        self.assertEqual(rd.z_bounds['lb'].upper, 0)
        self.assertEqual(rd.z_bounds['ub'].lower, None)
        self.assertEqual(rd.z_bounds['ub'].upper, 0)
        i.d2.indicator_var = 1
        rd.z = 2
        self.assertEqual(rd.z_bounds['lb'].body(), -11)
        self.assertEqual(rd.z_bounds['ub'].body(), 9)

class RangeSetOnDisjunct(unittest.TestCase):
    def test_RangeSet(self):
        m = models.makeDisjunctWithRangeSet()
        TransformationFactory('gdp.chull').apply_to(m)
        self.assertIsInstance(m.d1.s, RangeSet)

class TransformABlock(unittest.TestCase, CommonTests):
    def test_transformation_simple_block(self):
        ct.check_transformation_simple_block(self, 'chull')

    def test_transform_block_data(self):
        ct.check_transform_block_data(self, 'chull')

    def test_simple_block_target(self):
        ct.check_simple_block_target(self, 'chull')

    def test_block_data_target(self):
        ct.check_block_data_target(self, 'chull')

    def test_indexed_block_target(self):
        ct.check_indexed_block_target(self, 'chull')

    def test_block_targets_inactive(self):
        ct.check_block_targets_inactive(self, 'chull')

    def test_block_only_targets_transformed(self):
        ct.check_block_only_targets_transformed(self, 'chull')

    def test_create_using(self):
        m = models.makeTwoTermDisjOnBlock()
        ct.diff_apply_to_and_create_using(self, m, 'gdp.chull')

class TestErrors(unittest.TestCase):
    def setUp(self):
        # set seed so we can test name collisions predictably
        random.seed(666)

    def test_ask_for_transformed_constraint_from_untransformed_disjunct(self):
        ct.check_ask_for_transformed_constraint_from_untransformed_disjunct(
            self, 'chull')

    def test_silly_target(self):
        ct.check_silly_target(self, 'chull')

    def test_retrieving_nondisjunctive_components(self):
        ct.check_retrieving_nondisjunctive_components(self, 'chull')

    def test_transform_empty_disjunction(self):
        ct.check_transform_empty_disjunction(self, 'chull')

    def test_deactivated_disjunct_nonzero_indicator_var(self):
        ct.check_deactivated_disjunct_nonzero_indicator_var(self,
                                                            'chull')

    def test_deactivated_disjunct_unfixed_indicator_var(self):
        ct.check_deactivated_disjunct_unfixed_indicator_var(self, 'chull')

    def test_infeasible_xor_because_all_disjuncts_deactivated(self):
        m = ct.setup_infeasible_xor_because_all_disjuncts_deactivated(self,
                                                                      'chull')
        chull = TransformationFactory('gdp.chull')
        transBlock = m.component("_pyomo_gdp_chull_relaxation")
        self.assertIsInstance(transBlock, Block)
        self.assertEqual(len(transBlock.relaxedDisjuncts), 2)
        self.assertIsInstance(transBlock.component("disjunction_xor"),
                              Constraint)
        disjunct1 = transBlock.relaxedDisjuncts[0]
        # we disaggregated the (deactivated) indicator variables
        d3_ind = m.disjunction_disjuncts[0].nestedDisjunction_disjuncts[0].\
                 indicator_var
        d4_ind = m.disjunction_disjuncts[0].nestedDisjunction_disjuncts[1].\
                 indicator_var
        self.assertIs(chull.get_disaggregated_var(d3_ind,
                                                  m.disjunction_disjuncts[0]),
                      disjunct1.indicator_var)
        self.assertIs(chull.get_src_var(disjunct1.indicator_var), d3_ind)
        self.assertIs(chull.get_disaggregated_var(d4_ind,
                                                  m.disjunction_disjuncts[0]),
                      disjunct1.indicator_var_4)
        self.assertIs(chull.get_src_var(disjunct1.indicator_var_4), d4_ind)

        relaxed_xor = disjunct1.component(
            "disjunction_disjuncts[0]._pyomo_gdp_chull_relaxation."
            "disjunction_disjuncts[0].nestedDisjunction_xor")
        self.assertIsInstance(relaxed_xor, Constraint)
        self.assertEqual(len(relaxed_xor), 1)
        repn = generate_standard_repn(relaxed_xor['eq'].body)
        self.assertEqual(relaxed_xor['eq'].lower, 0)
        self.assertEqual(relaxed_xor['eq'].upper, 0)
        self.assertTrue(repn.is_linear())
        self.assertEqual(len(repn.linear_vars), 3)
        # constraint says that the disaggregated indicator variables of the
        # nested disjuncts sum to the indicator variable of the outer disjunct.
        ct.check_linear_coef( self, repn,
                              m.disjunction.disjuncts[0].indicator_var, -1)
        ct.check_linear_coef(self, repn, disjunct1.indicator_var, 1)
        ct.check_linear_coef(self, repn, disjunct1.indicator_var_4, 1)
        self.assertEqual(repn.constant, 0)

        # but the disaggregation constraints are going to force them to 0
        d3_ind_dis = transBlock.disaggregationConstraints[1]
        self.assertEqual(d3_ind_dis.lower, 0)
        self.assertEqual(d3_ind_dis.upper, 0)
        repn = generate_standard_repn(d3_ind_dis.body)
        self.assertTrue(repn.is_linear())
        self.assertEqual(len(repn.linear_vars), 2)
        self.assertEqual(repn.constant, 0)
        ct.check_linear_coef(self, repn, disjunct1.indicator_var, -1)
        ct.check_linear_coef(self, repn,
                             transBlock.relaxedDisjuncts[1].indicator_var, -1)
        d4_ind_dis = transBlock.disaggregationConstraints[2]
        self.assertEqual(d4_ind_dis.lower, 0)
        self.assertEqual(d4_ind_dis.upper, 0)
        repn = generate_standard_repn(d4_ind_dis.body)
        self.assertTrue(repn.is_linear())
        self.assertEqual(len(repn.linear_vars), 2)
        self.assertEqual(repn.constant, 0)
        ct.check_linear_coef(self, repn, disjunct1.indicator_var_4, -1)
        ct.check_linear_coef(self, repn,
                             transBlock.relaxedDisjuncts[1].indicator_var_9, -1)
