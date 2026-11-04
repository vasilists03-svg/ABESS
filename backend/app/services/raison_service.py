import logging
import os
import re
import time

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

RAISON_APP_ID = os.getenv("RAISON_APP_ID")
RAISON_VERSION = os.getenv("RAISON_VERSION", "latest")
RAISON_API_KEY = os.getenv("RAISON_API_KEY")

RAISON_TIMEOUT_SECONDS = int(os.getenv("RAISON_TIMEOUT_SECONDS", "20"))
RAISON_METADATA_CACHE_SECONDS = int(
    os.getenv("RAISON_METADATA_CACHE_SECONDS", "300")
)

if RAISON_APP_ID:
    RAISON_URL = (
        f"https://api.ai-raison.com/executions/"
        f"{RAISON_APP_ID}/{RAISON_VERSION}"
    )
else:
    RAISON_URL = None


SUPPORTED_METHODS = {
    "bisection",
    "newton",
    "secant",
    "fzero",
    "itp",
    "muller",
    "solve",
    "roots",
    "integer_exhaustive_scan",
}


_METADATA_CACHE = {
    "data": None,
    "loaded_at": 0.0,
}


class RaisonServiceError(RuntimeError):
    """Controlled error raised by the rAIson integration layer."""



def normalize_text_key(text: str):
    if text is None:
        return ""

    text = str(text).lower().strip()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)

    for char in [
        " ",
        "-",
        "_",
        "[",
        "]",
        ",",
        "*",
        ">",
        "<",
        "=",
        "(",
        ")",
        "/",
        ".",
    ]:
        text = text.replace(char, "")

    return text


def normalize_raison_method(method: str):
    """
    Converts the method name returned by rAIson into a method
    supported by the application.

    Returns None when the method is not supported.
    """
    if method is None:
        return None

    normalized = str(method).lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)

    method_map = {
        "binary search": "bisection",
        "bisection": "bisection",
        "bisection method": "bisection",

        "newton": "newton",
        "newton method": "newton",
        "newton-raphson": "newton",
        "newton raphson": "newton",
        "newton-raphson method": "newton",
        "newton raphson method": "newton",

        "secant": "secant",
        "secant method": "secant",

        # The rAIson toolbox exposes this solver as fzero.
        # The numerical layer may use a Brent-family implementation
        # internally, but the public method name remains fzero.
        "fzero": "fzero",
        "fzero method": "fzero",
        "brent-dekker/fzero": "fzero",
        "brent dekker/fzero": "fzero",

        "itp": "itp",
        "itp method": "itp",
        "interpolate truncate project": "itp",
        "interpolate-truncate-project": "itp",

        "muller": "muller",
        "muller method": "muller",
        "müller": "muller",
        "müller method": "muller",

        "solve": "solve",
        "symbolic solve": "solve",
        "analytical solve": "solve",
        "analytical solution": "solve",

        "roots": "roots",
        "polynomial roots": "roots",
        "poly roots": "roots",

        # Keep both spellings because the live policy has returned
        # the misspelled label "integer exhastive scan" in prior tests.
        "integer exhaustive scan": "integer_exhaustive_scan",
        "integer exhastive scan": "integer_exhaustive_scan",
        "integer exhaustive search": "integer_exhaustive_scan",
        "integer_exhaustive_scan": "integer_exhaustive_scan",
    }

    return method_map.get(normalized)


def get_headers():
    if not RAISON_API_KEY:
        raise RaisonServiceError("RAISON authentication is not configured.")

    return {
        "x-api-key": RAISON_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def check_env():
    if not RAISON_APP_ID:
        raise RaisonServiceError("RAISON application configuration is incomplete.")

    if not RAISON_API_KEY:
        raise RaisonServiceError("RAISON authentication is not configured.")

    if not RAISON_URL:
        raise RaisonServiceError("RAISON application configuration is incomplete.")


def clear_raison_metadata_cache():
    """
    Clears the cached rAIson metadata when an immediate refresh
    is required without restarting the backend.
    """
    _METADATA_CACHE["data"] = None
    _METADATA_CACHE["loaded_at"] = 0.0


def get_raison_metadata(force_refresh: bool = False):
    check_env()

    current_time = time.monotonic()
    cached_data = _METADATA_CACHE["data"]
    cached_at = _METADATA_CACHE["loaded_at"]

    cache_is_valid = (
        cached_data is not None
        and RAISON_METADATA_CACHE_SECONDS > 0
        and current_time - cached_at < RAISON_METADATA_CACHE_SECONDS
    )

    if cache_is_valid and not force_refresh:
        return cached_data

    headers = get_headers()

    logger.info(
        "Requesting rAIson metadata for configured application version."
    )

    try:
        response = requests.get(
            RAISON_URL,
            headers=headers,
            timeout=RAISON_TIMEOUT_SECONDS,
        )

        logger.info(
            "rAIson metadata request completed with status %s.",
            response.status_code,
        )

        if response.status_code != 200:
            raise RaisonServiceError(
                f"RAISON metadata request failed with HTTP "
                f"{response.status_code}."
            )

        try:
            metadata = response.json()
        except ValueError as error:
            raise RaisonServiceError(
                "RAISON metadata response was not valid JSON."
            ) from error

        if not isinstance(metadata, dict):
            raise RaisonServiceError(
                "RAISON metadata response had an unexpected format."
            )

        _METADATA_CACHE["data"] = metadata
        _METADATA_CACHE["loaded_at"] = current_time

        return metadata

    except requests.exceptions.Timeout as error:
        raise RaisonServiceError(
            "RAISON metadata request timed out."
        ) from error

    except requests.exceptions.RequestException as error:
        raise RaisonServiceError(
            "RAISON metadata request failed."
        ) from error


def extract_elements_and_options(metadata):
    elements_by_label = {}
    elements_by_id = {}
    normalized_elements = {}
    options = []

    raw_elements = metadata.get("elements", [])
    raw_options = metadata.get("options", [])

    if not isinstance(raw_elements, list):
        raise RaisonServiceError(
            "RAISON metadata elements had an unexpected format."
        )

    if not isinstance(raw_options, list):
        raise RaisonServiceError(
            "RAISON metadata options had an unexpected format."
        )

    for item in raw_elements:
        if not isinstance(item, dict):
            continue

        label = item.get("label")
        element_id = item.get("id")

        if label and element_id:
            label = str(label).strip()
            element_id = str(element_id).strip()

            elements_by_label[label] = element_id
            elements_by_id[element_id] = label
            normalized_elements[normalize_text_key(label)] = {
                "label": label,
                "id": element_id,
            }

    seen_option_ids = set()

    for item in raw_options:
        if not isinstance(item, dict):
            continue

        option_id = item.get("id")

        if not option_id:
            continue

        option_id = str(option_id).strip()

        if option_id and option_id not in seen_option_ids:
            options.append({"id": option_id})
            seen_option_ids.add(option_id)

    if not elements_by_label:
        raise RaisonServiceError(
            "No rAIson criteria were available in metadata."
        )

    if not options:
        raise RaisonServiceError(
            "No rAIson methods were available in metadata."
        )

    return (
        elements_by_label,
        elements_by_id,
        normalized_elements,
        options,
    )


def find_element_id(
    criterion,
    elements_by_label,
    elements_by_id,
    normalized_elements,
):
    if criterion is None:
        raise RaisonServiceError("An empty criterion was provided.")

    criterion_text = str(criterion).strip()

    if not criterion_text:
        raise RaisonServiceError("An empty criterion was provided.")

    # The backend already uses the real OPT IDs.
    if criterion_text.startswith("OPT"):
        return criterion_text

    if criterion_text in elements_by_id:
        return criterion_text

    if criterion_text in elements_by_label:
        return elements_by_label[criterion_text]

    normalized_criterion = normalize_text_key(criterion_text)

    if normalized_criterion in normalized_elements:
        return normalized_elements[normalized_criterion]["id"]

    raise RaisonServiceError(
        "A selected criterion was not recognized by rAIson."
    )


def extract_response_list(response_data):
    """
    Returns the list of results from rAIson.

    When rAIson responds successfully but returns no results,
    an empty list is returned so the router can activate the
    hidden no-context fallback.
    """
    if isinstance(response_data, list):
        return response_data

    if isinstance(response_data, dict):
        if "isSolution" in response_data:
            return [response_data]

        for key in [
            "results",
            "solutions",
            "data",
            "response",
            "answers",
        ]:
            value = response_data.get(key)

            if isinstance(value, list):
                return value

            if isinstance(value, dict):
                nested_list = extract_response_list(value)

                if nested_list:
                    return nested_list

        return []

    raise RaisonServiceError(
        "RAISON response had an unexpected format."
    )


def is_true_solution(value):
    if value is True:
        return True

    if isinstance(value, str):
        return value.strip().lower() == "true"

    if isinstance(value, int):
        return value == 1

    return False


def check_solutions(response_data):
    response_list = extract_response_list(response_data)
    true_options = []

    for item in response_list:
        if not isinstance(item, dict):
            continue

        if not is_true_solution(item.get("isSolution")):
            continue

        option_data = item.get("option", {})

        if not isinstance(option_data, dict):
            option_data = {}

        option_id = option_data.get("id")
        option_label = option_data.get("label")

        # Responses where option fields are placed directly
        # on the result object are also supported.
        if option_id is None:
            option_id = item.get("optionId") or item.get("id")

        if option_label is None:
            option_label = (
                item.get("optionLabel")
                or item.get("label")
                or item.get("name")
            )

        normalized_method = normalize_raison_method(option_label)

        true_options.append({
            "id": option_id,
            "label": option_label,
            "normalized_method": normalized_method,
            "supported": normalized_method in SUPPORTED_METHODS,
            "explanation": item.get("explanation", []),
        })

    return true_options


def get_final_method_from_solutions(solutions):
    if not solutions:
        return None

    for solution in solutions:
        if not isinstance(solution, dict):
            continue

        method = solution.get("normalized_method")

        if method in SUPPORTED_METHODS:
            return method

    return None


def call_raison(selected_criteria):
    check_env()

    if selected_criteria is None:
        selected_criteria = []

    if not isinstance(selected_criteria, (list, tuple, set)):
        raise RaisonServiceError(
            "Selected criteria must be provided as a collection."
        )

    metadata = get_raison_metadata()

    (
        elements_by_label,
        elements_by_id,
        normalized_elements,
        options,
    ) = extract_elements_and_options(metadata)

    selected_elements = []
    selected_element_ids = set()
    normalized_selected_criteria = []

    for criterion in selected_criteria:
        element_id = find_element_id(
            criterion,
            elements_by_label,
            elements_by_id,
            normalized_elements,
        )

        if element_id in selected_element_ids:
            continue

        selected_elements.append({
            "id": element_id,
            "parameters": [],
        })
        selected_element_ids.add(element_id)
        normalized_selected_criteria.append(str(criterion).strip())

    payload = {
        "elements": selected_elements,
        "options": options,
        "limit": len(options),
    }

    headers = get_headers()

    logger.info(
        "Sending rAIson query with %s selected criteria.",
        len(normalized_selected_criteria),
    )

    try:
        response = requests.post(
            RAISON_URL,
            headers=headers,
            json=payload,
            timeout=RAISON_TIMEOUT_SECONDS,
        )

        logger.info(
            "rAIson query completed with status %s.",
            response.status_code,
        )

        if response.status_code != 200:
            raise RaisonServiceError(
                f"RAISON query request failed with HTTP "
                f"{response.status_code}."
            )

        try:
            response_data = response.json()
        except ValueError as error:
            raise RaisonServiceError(
                "RAISON query response was not valid JSON."
            ) from error

        solutions = check_solutions(response_data)
        final_method = get_final_method_from_solutions(solutions)

        return {
            "success": True,
            "selected_criteria": normalized_selected_criteria,
            "selected_elements": selected_elements,
            "solutions": solutions,
            "final_method": final_method,
            "has_solution": bool(solutions),
            "has_supported_method": final_method is not None,
            # Internal compatibility field. The router removes this
            # before returning data to a client-facing endpoint.
            "raw_response": response_data,
        }

    except requests.exceptions.Timeout as error:
        raise RaisonServiceError(
            "RAISON query request timed out."
        ) from error

    except requests.exceptions.RequestException as error:
        raise RaisonServiceError(
            "RAISON query request failed."
        ) from error


def get_available_criteria():
    metadata = get_raison_metadata()

    (
        elements_by_label,
        elements_by_id,
        normalized_elements,
        options,
    ) = extract_elements_and_options(metadata)

    return {
        "criteria": [
            {
                "label": label,
                "id": element_id,
            }
            for label, element_id in elements_by_label.items()
        ],
        "options": options,
    }