from pydantic import BaseModel


class RaisonRequest(BaseModel):

    seek_analytical_solution: bool = False
    function_is_polynomial: bool = False
    seek_complex_root: bool = False
    derivative_is_available: bool = False
    good_initial_approximation: bool = False
    integer_valued_threshold_problem: bool = False
    opposite_signs_interval: bool = False
    continuous_extension_available: bool = False
    length_interval_large: bool = False
    steep_gradient_or_no_gradient_near_root: bool = False
    inflection_points_near_solution: bool = False
    extremum_points_near_solution: bool = False
    function_behaves_smoothly_near_root: bool = False
    known_k_multiplicity_of_root: bool = False
    function_is_monotonic: bool = False
    need_simplicity: bool = False
    need_robustness: bool = False
    need_speed: bool = False