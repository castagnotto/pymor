# This file is part of the pyMOR project (http://www.pymor.org).
# Copyright 2013-2017 pyMOR developers and contributors. All rights reserved.
# License: BSD 2-Clause License (http://opensource.org/licenses/BSD-2-Clause)

from functools import partial

from pymor.algorithms.timestepping import ExplicitEulerTimeStepper, ImplicitEulerTimeStepper
from pymor.algorithms.preassemble import preassemble as preassemble_
from pymor.analyticalproblems.elliptic import StationaryProblem
from pymor.analyticalproblems.instationary import InstationaryProblem
from pymor.discretizations.basic import StationaryDiscretization, InstationaryDiscretization
from pymor.domaindiscretizers.default import discretize_domain_default
from pymor.functions.basic import ConstantFunction, LincombFunction
from pymor.grids.boundaryinfos import EmptyBoundaryInfo
from pymor.grids.referenceelements import line, triangle, square
from pymor.gui.visualizers import PatchVisualizer, OnedVisualizer
from pymor.operators.cg import (DiffusionOperatorP1, DiffusionOperatorQ1,
                                AdvectionOperatorP1, AdvectionOperatorQ1,
                                L2ProductP1, L2ProductQ1,
                                L2ProductFunctionalP1, L2ProductFunctionalQ1,
                                RobinBoundaryOperator, InterpolationOperator)
from pymor.operators.constructions import LincombOperator


def discretize_stationary_cg(analytical_problem, diameter=None, domain_discretizer=None,
                             grid_type=None, grid=None, boundary_info=None,
                             preassemble=True):
    """Discretizes an |StationaryProblem| using finite elements.

    Parameters
    ----------
    analytical_problem
        The |StationaryProblem| to discretize.
    diameter
        If not `None`, `diameter` is passed as an argument to the `domain_discretizer`.
    domain_discretizer
        Discretizer to be used for discretizing the analytical domain. This has
        to be a function `domain_discretizer(domain_description, diameter, ...)`.
        If `None`, |discretize_domain_default| is used.
    grid_type
        If not `None`, this parameter is forwarded to `domain_discretizer` to specify
        the type of the generated |Grid|.
    grid
        Instead of using a domain discretizer, the |Grid| can also be passed directly
        using this parameter.
    boundary_info
        A |BoundaryInfo| specifying the boundary types of the grid boundary entities.
        Must be provided if `grid` is specified.
    preassemble
        If `True`, preassemble all operators in the resulting |Discretization|.

    Returns
    -------
    discretization
        The |Discretization| that has been generated.
    data
        Dictionary with the following entries:

            :grid:           The generated |Grid|.
            :boundary_info:  The generated |BoundaryInfo|.
    """

    assert isinstance(analytical_problem, StationaryProblem)
    assert grid is None or boundary_info is not None
    assert boundary_info is None or grid is not None
    assert grid is None or domain_discretizer is None
    assert grid_type is None or grid is None

    p = analytical_problem

    if not (p.nonlinear_advection == p.nonlinear_advection_derivative ==
            p.nonlinear_reaction == p.nonlinear_reaction_derivative == None):
        raise NotImplementedError

    if grid is None:
        domain_discretizer = domain_discretizer or discretize_domain_default
        if grid_type:
            domain_discretizer = partial(domain_discretizer, grid_type=grid_type)
        if diameter is None:
            grid, boundary_info = domain_discretizer(p.domain)
        else:
            grid, boundary_info = domain_discretizer(p.domain, diameter=diameter)

    assert grid.reference_element in (line, triangle, square)

    if grid.reference_element is square:
        DiffusionOperator = DiffusionOperatorQ1
        AdvectionOperator = AdvectionOperatorQ1
        ReactionOperator  = L2ProductQ1
        Functional = L2ProductFunctionalQ1
    else:
        DiffusionOperator = DiffusionOperatorP1
        AdvectionOperator = AdvectionOperatorP1
        ReactionOperator  = L2ProductP1
        Functional = L2ProductFunctionalP1

    Li = [DiffusionOperator(grid, boundary_info, diffusion_constant=0, name='boundary_part')]
    coefficients = [1.]

    # diffusion part
    if isinstance(p.diffusion, LincombFunction):
        Li += [DiffusionOperator(grid, boundary_info, diffusion_function=df, dirichlet_clear_diag=True,
                                 name='diffusion_{}'.format(i))
               for i, df in enumerate(p.diffusion.functions)]
        coefficients += list(p.diffusion.coefficients)
    elif p.diffusion is not None:
        Li += [DiffusionOperator(grid, boundary_info, diffusion_function=p.diffusion,
                                 dirichlet_clear_diag=True, name='diffusion')]
        coefficients.append(1.)

    # advection part
    if isinstance(p.advection, LincombFunction):
        Li += [AdvectionOperator(grid, boundary_info, advection_function=af, dirichlet_clear_diag=True,
                                 name='advection_{}'.format(i))
               for i, af in enumerate(p.advection.functions)]
        coefficients += list(p.advection.coefficients)
    elif p.advection is not None:
        Li += [AdvectionOperator(grid, boundary_info, advection_function=p.advection,
                                 dirichlet_clear_diag=True, name='advection')]
        coefficients.append(1.)

    # reaction part
    if isinstance(p.reaction, LincombFunction):
        Li += [ReactionOperator(grid, boundary_info, coefficient_function=rf, dirichlet_clear_diag=True,
                                name='reaction_{}'.format(i))
               for i, rf in enumerate(p.reaction.functions)]
        coefficients += list(p.reaction.coefficients)
    elif p.reaction is not None:
        Li += [ReactionOperator(grid, boundary_info, coefficient_function=p.reaction,
                                dirichlet_clear_diag=True, name='reaction')]
        coefficients.append(1.)

    # robin boundaries
    if p.robin_data is not None:
        if grid.reference_element is square:
            raise NotImplementedError
        Li += [RobinBoundaryOperator(grid, boundary_info, robin_data=p.robin_data, order=2, name='robin')]
        coefficients.append(1.)

    L = LincombOperator(operators=Li, coefficients=coefficients, name='ellipticOperator')

    rhs = p.rhs or ConstantFunction(0., dim_domain=p.domain.dim)
    F = Functional(grid, rhs, boundary_info, dirichlet_data=p.dirichlet_data, neumann_data=p.neumann_data)

    if grid.reference_element in (triangle, square):
        visualizer = PatchVisualizer(grid=grid, bounding_box=grid.bounding_box(), codim=2)
    elif grid.reference_element is line:
        visualizer = OnedVisualizer(grid=grid, codim=1)
    else:
        visualizer = None

    Prod = L2ProductQ1 if grid.reference_element is square else L2ProductP1
    empty_bi = EmptyBoundaryInfo(grid)
    l2_product = Prod(grid, empty_bi, name='l2')
    l2_0_product = Prod(grid, boundary_info, dirichlet_clear_columns=True, name='l2_0')
    h1_semi_product = DiffusionOperator(grid, empty_bi, name='h1_semi')
    h1_0_semi_product = DiffusionOperator(grid, boundary_info, dirichlet_clear_columns=True, name='h1_0_semi')
    products = {'h1': l2_product + h1_semi_product,
                'h1_semi': h1_semi_product,
                'l2': l2_product,
                'h1_0': l2_0_product + h1_0_semi_product,
                'h1_0_semi': h1_0_semi_product,
                'l2_0': l2_0_product}

    parameter_space = p.parameter_space if hasattr(p, 'parameter_space') else None

    discretization = StationaryDiscretization(L, F, products=products, visualizer=visualizer,
                                              parameter_space=parameter_space, name='{}_CG'.format(p.name))

    data = {'grid': grid, 'boundary_info': boundary_info}

    if preassemble:
        data['unassembled_discretization'] = discretization
        discretization = preassemble_(discretization)

    return discretization, data


def discretize_instationary_cg(analytical_problem, diameter=None, domain_discretizer=None, grid_type=None,
                               grid=None, boundary_info=None, num_values=None, time_stepper=None, nt=None,
                               preassemble=True):
    """Discretizes an |InstationaryProblem| with an |StationaryProblem| as stationary part
    using finite elements.

    Parameters
    ----------
    analytical_problem
        The |InstationaryProblem| to discretize.
    diameter
        If not `None`, `diameter` is passed as an argument to the `domain_discretizer`.
    domain_discretizer
        Discretizer to be used for discretizing the analytical domain. This has
        to be a function `domain_discretizer(domain_description, diameter, ...)`.
        If `None`, |discretize_domain_default| is used.
    grid_type
        If not `None`, this parameter is forwarded to `domain_discretizer` to specify
        the type of the generated |Grid|.
    grid
        Instead of using a domain discretizer, the |Grid| can also be passed directly
        using this parameter.
    boundary_info
        A |BoundaryInfo| specifying the boundary types of the grid boundary entities.
        Must be provided if `grid` is specified.
    num_values
        The number of returned vectors of the solution trajectory. If `None`, each
        intermediate vector that is calculated is returned.
    time_stepper
        The :class:`time-stepper <pymor.algorithms.timestepping.TimeStepperInterface>`
        to be used by :class:`~pymor.discretizations.basic.InstationaryDiscretization.solve`.
    nt
        If `time_stepper` is not specified, the number of time steps for implicit
        Euler time stepping.
    preassemble
        If `True`, preassemble all operators in the resulting |Discretization|.

    Returns
    -------
    discretization
        The |Discretization| that has been generated.
    data
        Dictionary with the following entries:

            :grid:           The generated |Grid|.
            :boundary_info:  The generated |BoundaryInfo|.
    """

    assert isinstance(analytical_problem, InstationaryProblem)
    assert isinstance(analytical_problem.stationary_part, StationaryProblem)
    assert grid is None or boundary_info is not None
    assert boundary_info is None or grid is not None
    assert grid is None or domain_discretizer is None
    assert (time_stepper is None) != (nt is None)

    p = analytical_problem

    d, data = discretize_stationary_cg(p.stationary_part, diameter=diameter, domain_discretizer=domain_discretizer,
                                       grid_type=grid_type, grid=grid, boundary_info=boundary_info)

    if p.initial_data.parametric:
        I = InterpolationOperator(data['grid'], p.initial_data)
    else:
        I = p.initial_data.evaluate(data['grid'].centers(data['grid'].dim))
        I = d.solution_space.make_array(I)

    if time_stepper is None:
        if p.stationary_part.diffusion is None:
            time_stepper = ExplicitEulerTimeStepper(nt=nt)
        else:
            time_stepper = ImplicitEulerTimeStepper(nt=nt)

    mass = d.l2_0_product

    discretization = InstationaryDiscretization(operator=d.operator, rhs=d.rhs, mass=mass, initial_data=I, T=p.T,
                                                products=d.products, time_stepper=time_stepper,
                                                parameter_space=p.parameter_space, visualizer=d.visualizer,
                                                num_values=num_values, name='{}_CG'.format(p.name))

    if preassemble:
        data['unassembled_discretization'] = discretization
        discretization = preassemble_(discretization)

    return discretization, data
