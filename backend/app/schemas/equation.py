from pydantic import BaseModel
from typing import Optional


class EquationSolveRequest(BaseModel):
    equation: str
    method: Optional[str] = None
    guest_id: Optional[str] = None

    a: Optional[float] = None
    b: Optional[float] = None
    x0: Optional[float] = None
    x1: Optional[float] = None
    x2: Optional[float] = None

    # Κριτήρια RAISON που μπορεί να επιλέξει ο χρήστης.
    # Το κρυφό "no context" διαχειρίζεται αποκλειστικά το backend
    # και για αυτό δεν υπάρχει ως πεδίο στο request.
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

    # Επιτρέπονται μηδέν, ένα ή περισσότερα κριτήρια.
    criteria: Optional[list[str]] = None
    selected_elements: Optional[list[str]] = None