const API_BASE_URL = "/api";

const equationInput = document.getElementById("equation");
const methodSelect = document.getElementById("method");
const solveButton = document.getElementById("solveButton");
const resultBox = document.getElementById("result");
const drawGraphButton = document.getElementById("drawGraphButton");
const resetZoomButton = document.getElementById("resetZoomButton");
const graphBox = document.getElementById("graphBox");

const criteriaBox = document.getElementById("criteriaBox");
const criteriaToggle = document.getElementById("criteriaToggle");
const criteriaDropdown = document.getElementById("criteriaDropdown");
const criteriaSummary = document.getElementById("criteriaSummary");
const criteriaMenu = document.getElementById("criteriaMenu");

const intervalInputs = document.getElementById("intervalInputs");
const initialInputs = document.getElementById("initialInputs");
const x0Input = document.getElementById("x0Input");
const x1Input = document.getElementById("x1Input");

const aValue = document.getElementById("aValue");
const bValue = document.getElementById("bValue");
const x0Value = document.getElementById("x0Value");
const x1Value = document.getElementById("x1Value");

const historyButton = document.getElementById("historyButton");
const historyBox = document.getElementById("historyBox");
const historyContent = document.getElementById("historyContent");
const closeHistoryButton = document.getElementById("closeHistoryButton");

let solveTimerInterval = null;
let slowLoadingTimer = null;
let solveStartedAt = null;
let lastSolveElapsedSeconds = 0;

let currentGraphEquation = "";
let currentGraphXMin = -10;
let currentGraphXMax = 10;

// ABESS_ADAPTIVE_GRAPH_V1
let initialGraphXMin = -10;
let initialGraphXMax = 10;
let graphIsUpdating = false;
let graphRelayoutTimer = null;

// ABESS_DOUBLE_CLICK_GRAPH_V1
let lastGraphCurveClick = null;

// ABESS_VIEWPORT_PERSISTENCE_V1
let graphViewportRevision = 0;
let nextIntervalPoint = "a";

if (criteriaBox) {
    criteriaBox.classList.add("hidden");
}

if (graphBox) {
    graphBox.classList.add("hidden");
}

if (historyBox) {
    historyBox.classList.add("hidden");
}

function getGuestId() {
    let guestId = localStorage.getItem("guest_id");

    if (!guestId) {
        if (window.crypto && crypto.randomUUID) {
            guestId = `guest_${crypto.randomUUID()}`;
        } else {
            guestId = `guest_${Date.now()}_${Math.random().toString(16).slice(2)}`;
        }

        localStorage.setItem("guest_id", guestId);
    }

    return guestId;
}

function getAccessToken() {
    return localStorage.getItem("access_token");
}

function getAuthHeaders() {
    const headers = {
        "Content-Type": "application/json"
    };

    const token = getAccessToken();

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    return headers;
}

function escapeHtml(value) {
    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatMethod(method) {
    if (!method) {
        return "-";
    }

    const methodText = String(method).toLowerCase().trim();

    if (methodText === "bisection") return "Bisection Method";
    if (methodText === "newton") return "Newton-Raphson Method";
    if (methodText === "secant") return "Secant Method";
    if (methodText === "fzero") return "fzero";
    if (methodText === "itp") return "ITP Method";
    if (methodText === "muller") return "Muller Method";
    if (methodText === "solve") return "Symbolic Solve";
    if (methodText === "roots") return "Polynomial Roots";
    if (methodText === "integer_exhaustive_scan") {
        return "Integer Exhaustive Scan";
    }

    return String(method);
}

function formatComplexObject(value, digits = 10) {
    if (
        !value
        || typeof value !== "object"
        || Array.isArray(value)
        || value.real === undefined
        || value.imag === undefined
    ) {
        return null;
    }

    const real = Number(value.real);
    const imag = Number(value.imag);

    if (!Number.isFinite(real) || !Number.isFinite(imag)) {
        return null;
    }

    const clean = number => {
        return Number(number)
            .toFixed(digits)
            .replace(/\.?0+$/, "");
    };

    if (Math.abs(imag) < 1e-12) {
        return clean(real);
    }

    if (Math.abs(real) < 1e-12) {
        if (Math.abs(imag - 1) < 1e-12) return "i";
        if (Math.abs(imag + 1) < 1e-12) return "-i";
        return `${clean(imag)}i`;
    }

    const sign = imag >= 0 ? "+" : "-";
    const absImag = Math.abs(imag);

    const imagText =
        Math.abs(absImag - 1) < 1e-12
            ? "i"
            : `${clean(absImag)}i`;

    return `${clean(real)} ${sign} ${imagText}`;
}

function formatRoot(root) {
    if (
        root === null
        || root === undefined
        || root === ""
    ) {
        return "-";
    }

    if (Array.isArray(root)) {
        return root
            .map(item => formatRoot(item))
            .join(", ");
    }

    const complexText =
        formatComplexObject(root);

    if (complexText !== null) {
        return complexText;
    }

    if (typeof root === "object") {
        return JSON.stringify(root);
    }

    const numericRoot =
        Number(root);

    if (!Number.isFinite(numericRoot)) {
        return String(root);
    }

    return numericRoot
        .toFixed(10)
        .replace(/\.?0+$/, "");
}

function formatApproximation(value) {
    if (
        value === null
        || value === undefined
        || value === ""
    ) {
        return null;
    }

    const complexText =
        formatComplexObject(
            value,
            10
        );

    if (complexText !== null) {
        return complexText;
    }

    const numericValue =
        Number(value);

    if (!Number.isFinite(numericValue)) {
        return String(value);
    }

    return numericValue
        .toFixed(10)
        .replace(/\.?0+$/, "");
}

function formatElapsedSeconds(seconds) {
    const safeSeconds =
        Math.max(
            0,
            Math.floor(
                Number(seconds) || 0
            )
        );

    return `${String(safeSeconds).padStart(2, "0")} s`;
}

function formatDate(value) {
    if (!value) {
        return "-";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    return date.toLocaleString("en-GB");
}

function hideNumericalInputs() {
    if (intervalInputs) {
        intervalInputs.classList.add(
            "hidden"
        );
    }

    if (initialInputs) {
        initialInputs.classList.add(
            "hidden"
        );
    }

    if (x0Input) {
        x0Input.classList.add(
            "hidden"
        );
    }

    if (x1Input) {
        x1Input.classList.add(
            "hidden"
        );
    }

    document.getElementById("x2Input")?.classList.add("hidden");
}

function updateMethodUI() {
    if (!methodSelect) {
        return;
    }

    const method =
        methodSelect.value;

    hideNumericalInputs();

    const hints = {
        bisection: "Leave both a and b empty to automatically search for a suitable interval.",
        fzero: "Leave both a and b empty to automatically search for a suitable interval.",
        itp: "Leave both a and b empty to automatically search for a suitable interval.",
        newton: "Leave x0 empty to automatically estimate an initial value.",
        secant: "Leave both x0 and x1 empty to automatically estimate starting values.",
        muller: "Leave x0, x1 and x2 empty to automatically estimate three starting values.",
        integer_exhaustive_scan: "Interval limits are optional. Without them, the default integer range is used.",
        automatic: "Initial values are optional. The solver can estimate missing values for the method selected by rAIson."
    };

    const hint = document.getElementById("autoParametersHint");
    if (hint) {
        hint.textContent = hints[method] || "";
        hint.style.display = hints[method] ? "block" : "none";
    }

    if (criteriaBox) {
        criteriaBox.classList.add(
            "hidden"
        );
    }

    if (
        [
            "bisection",
            "fzero",
            "itp",
            "integer_exhaustive_scan"
        ].includes(method)
    ) {
        if (intervalInputs) {
            intervalInputs.classList.remove(
                "hidden"
            );
        }
    }

    if (method === "newton") {
        if (initialInputs) {
            initialInputs.classList.remove(
                "hidden"
            );
        }

        if (x0Input) {
            x0Input.classList.remove(
                "hidden"
            );
        }
    }

    if (method === "secant") {
        if (initialInputs) {
            initialInputs.classList.remove(
                "hidden"
            );
        }

        if (x0Input) {
            x0Input.classList.remove(
                "hidden"
            );
        }

        if (x1Input) {
            x1Input.classList.remove(
                "hidden"
            );
        }
    }

    if (method === "muller") {
        initialInputs?.classList.remove("hidden");
        x0Input?.classList.remove("hidden");
        x1Input?.classList.remove("hidden");
        document.getElementById("x2Input")?.classList.remove("hidden");
    }

    if (method === "automatic") {
        if (criteriaBox) {
            criteriaBox.classList.remove(
                "hidden"
            );
        }

        if (intervalInputs) {
            intervalInputs.classList.remove(
                "hidden"
            );
        }

        if (initialInputs) {
            initialInputs.classList.remove(
                "hidden"
            );
        }

        if (x0Input) {
            x0Input.classList.remove(
                "hidden"
            );
        }

        if (x1Input) {
            x1Input.classList.remove(
                "hidden"
            );
        }

        document.getElementById("x2Input")?.classList.remove("hidden");
    } else {
        setCriteriaDropdownOpen(
            false
        );
    }
}

if (methodSelect) {
    methodSelect.addEventListener(
        "change",
        updateMethodUI
    );
}

const HIDDEN_RAISON_CRITERIA =
    new Set([
        "no_context",
        "no context",
        "opt450268"
    ]);

function normalizeCriterionValue(
    value
) {
    return String(value ?? "")
        .trim()
        .toLowerCase();
}

function getSelectedCriteria() {
    if (!criteriaMenu) {
        return [];
    }

    const checkedBoxes =
        criteriaMenu.querySelectorAll(
            'input[type="checkbox"]:checked'
        );

    return Array
        .from(checkedBoxes)
        .map(
            checkbox =>
                checkbox.value
        )
        .filter(
            criterion => {
                return (
                    !HIDDEN_RAISON_CRITERIA.has(
                        normalizeCriterionValue(
                            criterion
                        )
                    )
                );
            }
        );
}

function updateCriteriaSummary() {
    if (!criteriaSummary) {
        return;
    }

    const selectedCount =
        getSelectedCriteria().length;

    if (selectedCount === 0) {
        criteriaSummary.textContent =
            "No criteria selected";

        return;
    }

    if (selectedCount === 1) {
        criteriaSummary.textContent =
            "1 criterion selected";

        return;
    }

    criteriaSummary.textContent =
        `${selectedCount} criteria selected`;
}

function setCriteriaDropdownOpen(
    isOpen
) {
    if (
        !criteriaBox
        || !criteriaToggle
        || !criteriaDropdown
    ) {
        return;
    }

    const shouldOpen =
        Boolean(isOpen);

    criteriaDropdown.classList.toggle(
        "hidden",
        !shouldOpen
    );

    criteriaBox.classList.toggle(
        "open",
        shouldOpen
    );

    criteriaToggle.setAttribute(
        "aria-expanded",
        shouldOpen
            ? "true"
            : "false"
    );
}

function toggleCriteriaDropdown() {
    if (!criteriaDropdown) {
        return;
    }

    setCriteriaDropdownOpen(
        criteriaDropdown.classList.contains(
            "hidden"
        )
    );
}

if (criteriaToggle) {
    criteriaToggle.addEventListener(
        "click",
        function (event) {
            event.preventDefault();
            event.stopPropagation();

            toggleCriteriaDropdown();
        }
    );
}

if (criteriaDropdown) {
    criteriaDropdown.addEventListener(
        "click",
        function (event) {
            event.stopPropagation();
        }
    );
}

if (criteriaMenu) {
    criteriaMenu.addEventListener(
        "change",
        updateCriteriaSummary
    );
}

document.addEventListener(
    "click",
    function (event) {
        if (
            criteriaBox
            && !criteriaBox.contains(
                event.target
            )
        ) {
            setCriteriaDropdownOpen(
                false
            );
        }
    }
);

document.addEventListener(
    "keydown",
    function (event) {
        if (event.key === "Escape") {
            setCriteriaDropdownOpen(
                false
            );
        }
    }
);

function setSolvingState(isSolving) {
    if (!solveButton) {
        return;
    }

    solveButton.disabled =
        isSolving;

    solveButton.textContent =
        isSolving
            ? "Solving..."
            : "Solve";
}

function updateSolveTimerDisplay() {
    if (solveStartedAt === null) {
        return;
    }

    const elapsedSeconds =
        Math.floor(
            (
                performance.now()
                - solveStartedAt
            )
            / 1000
        );

    lastSolveElapsedSeconds =
        elapsedSeconds;

    const timerValue =
        document.getElementById(
            "solveTimerValue"
        );

    if (timerValue) {
        timerValue.textContent =
            formatElapsedSeconds(
                elapsedSeconds
            );
    }
}

function startSolveTimer(
    methodValue
) {
    stopSolveTimer();

    solveStartedAt =
        performance.now();

    lastSolveElapsedSeconds = 0;

    const isAutomatic =
        methodValue === "automatic";

    const loadingMessage =
        isAutomatic
            ? (
                "The application is evaluating "
                + "the method through rAIson..."
            )
            : (
                `Solving with ${
                    formatMethod(methodValue)
                }...`
            );

    resultBox.innerHTML = `
        <div class="result-loading">
            <strong id="solveLoadingMessage">
                ${escapeHtml(
                    loadingMessage
                )}
            </strong>

            <div
                class="solve-timer"
                aria-live="polite"
            >
                <span
                    class="loading-spinner"
                    aria-hidden="true"
                ></span>

                <span id="solveTimerValue">
                    00 s
                </span>
            </div>
        </div>
    `;

    solveTimerInterval =
        setInterval(
            updateSolveTimerDisplay,
            250
        );

    slowLoadingTimer =
        setTimeout(
            () => {
                const loadingMessageElement =
                    document.getElementById(
                        "solveLoadingMessage"
                    );

                if (
                    loadingMessageElement
                ) {
                    loadingMessageElement.textContent =
                        "This is taking a little longer than usual...";
                }
            },
            8000
        );
}

function stopSolveTimer() {
    if (solveTimerInterval) {
        clearInterval(
            solveTimerInterval
        );

        solveTimerInterval = null;
    }

    if (slowLoadingTimer) {
        clearTimeout(
            slowLoadingTimer
        );

        slowLoadingTimer = null;
    }

    if (solveStartedAt === null) {
        return (
            lastSolveElapsedSeconds
        );
    }

    const elapsedMilliseconds =
        performance.now()
        - solveStartedAt;

    const elapsedSeconds =
        Math.max(
            1,
            Math.ceil(
                elapsedMilliseconds
                / 1000
            )
        );

    solveStartedAt = null;

    lastSolveElapsedSeconds =
        elapsedSeconds;

    return elapsedSeconds;
}

function showInfo(
    message,
    suggestion = null
) {
    resultBox.innerHTML = `
        <div class="result-error">
            <strong>
                Notice:
            </strong>

            ${escapeHtml(message)}

            ${
                suggestion
                    ? `
                        <p>
                            ${escapeHtml(
                                suggestion
                            )}
                        </p>
                    `
                    : ""
            }
        </div>
    `;
}

function showError(
    title,
    message,
    suggestion = null,
    methodContext = null
) {
    resultBox.innerHTML = `
        <div class="result-error">

            <strong>
                ${escapeHtml(
                    title
                    || "Unable to solve the equation."
                )}
            </strong>

            ${
                methodContext
                    ? `
                        <p>
                            <strong>
                                ${escapeHtml(
                                    methodContext.label
                                )}
                            </strong>

                            ${escapeHtml(
                                methodContext.value
                            )}
                        </p>
                    `
                    : ""
            }

            ${
                message
                    ? `
                        <p>
                            ${escapeHtml(
                                message
                            )}
                        </p>
                    `
                    : ""
            }

            ${
                suggestion
                    ? `
                        <p>
                            <strong>
                                Suggestion:
                            </strong>

                            ${escapeHtml(
                                suggestion
                            )}
                        </p>
                    `
                    : ""
            }

        </div>
    `;
}

const TECHNICAL_ERROR_PATTERNS = [
    "traceback",
    "exception",
    "sqlalchemy",
    "uvicorn",
    "fastapi",
    ".env",
    "127.0.0.1",
    "localhost",
    "errno",
    "/app/",
    "docker",
    "smtp",
    "operationalerror",
    "integrityerror"
];

function sanitizeUserMessage(
    message,
    fallback =
        "The request could not be completed."
) {
    if (
        typeof message !== "string"
    ) {
        return fallback;
    }

    const cleanMessage =
        message.trim();

    if (!cleanMessage) {
        return fallback;
    }

    const lowerMessage =
        cleanMessage.toLowerCase();

    const containsTechnicalDetails =
        TECHNICAL_ERROR_PATTERNS
            .some(
                pattern =>
                    lowerMessage.includes(
                        pattern
                    )
            );

    return containsTechnicalDetails
        ? fallback
        : cleanMessage;
}

function getErrorTitle(data) {
    if (!data) {
        return (
            "Unable to complete the request."
        );
    }

    if (
        data.detail
        && typeof data.detail === "object"
    ) {
        if (
            data.detail.error
            === "GUEST_LIMIT_REACHED"
        ) {
            return (
                "Guest solve limit reached."
            );
        }

        if (
            data.detail.error
            === "GUEST_ID_REQUIRED"
        ) {
            return (
                "Guest session could not be identified."
            );
        }

        if (data.detail.title) {
            return sanitizeUserMessage(
                data.detail.title,
                "Unable to complete the request."
            );
        }
    }

    if (data.title) {
        return sanitizeUserMessage(
            data.title,
            "Unable to solve the equation."
        );
    }

    return (
        "Unable to solve the equation."
    );
}

function getErrorMethodContext(
    data,
    methodValue
) {
    if (!data) {
        return null;
    }

    const source =
        data.selection_source;

    const usedRaison =
        data.used_raison === true
        || source === "raison";

    const raisonMethod =
        data.raison_method_full_name
        || data.raison_label
        || data.raison_method;

    if (
        usedRaison
        && raisonMethod
    ) {
        return {
            label:
                "rAIson selected:",

            value:
                raisonMethod
        };
    }

    if (
        methodValue
        && methodValue !== "automatic"
    ) {
        const method =
            data.python_method_full_name
            || data.final_method
            || data.method
            || methodValue;

        return {
            label:
                "Selected method:",

            value:
                formatMethod(
                    method
                )
        };
    }

    return null;
}

function showErrorResponse(
    data,
    methodValue
) {
    showError(
        getErrorTitle(
            data
        ),

        getErrorMessage(
            data
        ),

        getErrorSuggestion(
            data
        ),

        getErrorMethodContext(
            data,
            methodValue
        )
    );
}

function getErrorMessage(data) {
    if (!data) {
        return (
            "The server returned an error."
        );
    }

    if (
        typeof data.detail
        === "string"
    ) {
        return sanitizeUserMessage(
            data.detail,
            "The request could not be completed."
        );
    }

    if (
        data.detail
        && typeof data.detail === "object"
    ) {
        return sanitizeUserMessage(
            data.detail.message,
            "The server returned an error."
        );
    }

    return sanitizeUserMessage(
        data.message
        || data.error,

        "The server returned an error."
    );
}

function getErrorSuggestion(data) {
    if (!data) {
        return null;
    }

    if (
        data.detail
        && typeof data.detail === "object"
    ) {
        if (
            data.detail.error
            === "GUEST_LIMIT_REACHED"
        ) {
            return (
                "Log in or create an account "
                + "to continue."
            );
        }

        return data.detail.suggestion
            ? sanitizeUserMessage(
                data.detail.suggestion,
                null
            )
            : null;
    }

    return data.suggestion
        ? sanitizeUserMessage(
            data.suggestion,
            null
        )
        : null;
}

function isGuestLimitReached(data) {
    return (
        data
        && data.detail
        && typeof data.detail === "object"
        && data.detail.error
            === "GUEST_LIMIT_REACHED"
    );
}

function redirectGuestToAuth() {
    localStorage.removeItem(
        "access_mode"
    );

    setTimeout(
        () => {
            if (
                typeof showAuthScreen
                === "function"
            ) {
                showAuthScreen(
                    "You have reached the limit of 3 free solves. Log in to continue."
                );

                window.scrollTo(
                    0,
                    0
                );
            }
        },
        1200
    );
}

function showGuestUsage(data) {
    if (
        data.user_type !== "guest"
    ) {
        return "";
    }

    const used =
        data.guest_solves_used;

    const remaining =
        data.guest_solves_remaining;

    if (
        used === undefined
        || remaining === undefined
    ) {
        return "";
    }

    return `
        <div class="result-note">
            Guest usage:
            ${escapeHtml(used)}/3 solves used.
            ${escapeHtml(remaining)} remaining.
        </div>
    `;
}

function buildAnalyticalSolutionHtml(
    data
) {
    if (
        !Array.isArray(
            data.analytical_solutions
        )
        || data.analytical_solutions.length
            === 0
    ) {
        return "";
    }

    const variable =
        data.solution_variable
        || "x";

    const exactSolutions =
        data.analytical_solutions
            .map(
                solution => {
                    return `
                        <div
                            class="analytical-solution-line"
                        >
                            ${escapeHtml(
                                variable
                            )}
                            =
                            ${escapeHtml(
                                solution
                            )}
                        </div>
                    `;
                }
            )
            .join("");

    let approximationHtml = "";

    if (
        Array.isArray(
            data.numeric_solutions
        )
    ) {
        const approximations =
            data.numeric_solutions
                .map(
                    (
                        approximation,
                        index
                    ) => {
                        if (
                            approximation === null
                            || approximation === undefined
                        ) {
                            return "";
                        }

                        const approximationText =
                            formatApproximation(
                                approximation
                            );

                        if (
                            approximationText
                            === null
                        ) {
                            return "";
                        }

                        const exactValue =
                            data.analytical_solutions[
                                index
                            ];

                        if (
                            exactValue !== undefined
                            && String(
                                exactValue
                            ) === String(
                                approximationText
                            )
                        ) {
                            return "";
                        }

                        return `
                            <div
                                class="analytical-solution-line"
                            >
                                ${escapeHtml(
                                    variable
                                )}
                                ≈
                                ${escapeHtml(
                                    approximationText
                                )}
                            </div>
                        `;
                    }
                )
                .filter(Boolean)
                .join("");

        if (approximations) {
            approximationHtml = `
                <div
                    class="analytical-solution-section"
                    style="margin-top: 14px;"
                >
                    <strong>
                        Decimal Approximations:
                    </strong>

                    <div style="margin-top: 8px;">
                        ${approximations}
                    </div>
                </div>
            `;
        }
    }

    return `
        <div
            class="analytical-solution-box"
            style="
                margin-top: 14px;
                padding: 14px;
                border: 1px solid #dbe3ef;
                border-radius: 12px;
                background: #f8fafc;
            "
        >
            <div
                class="analytical-solution-section"
            >
                <strong>
                    Analytical Solution:
                </strong>

                <div style="margin-top: 8px;">
                    ${exactSolutions}
                </div>
            </div>

            ${approximationHtml}
        </div>
    `;
}

function showSuccess(
    data,
    elapsedSeconds
) {
    const pythonMethod =
        data.python_method_full_name
        || formatMethod(
            data.final_method
            || data.method
        );

    const raisonMethod =
        data.raison_suggestion
        || data.raison_method_full_name
        || data.raison_label
        || data.raison_method;

    const hasAnalyticalSolution =
        Array.isArray(
            data.analytical_solutions
        )
        && data.analytical_solutions.length
            > 0;

    const root =
        formatRoot(
            data.root
        );

    const usageHtml =
        showGuestUsage(
            data
        );

    const analyticalSolutionHtml =
        buildAnalyticalSolutionHtml(
            data
        );

    resultBox.innerHTML = `
        <div class="result-success">

            <h3>
                Result
            </h3>

            ${
                data.used_raison
                && raisonMethod
                    ? `
                        <p>
                            <strong>
                                rAIson suggested:
                            </strong>

                            ${escapeHtml(
                                data.raison_suggestion
                                ? data.raison_suggestion.replace(
                                    "rAIson suggested: ",
                                    ""
                                )
                                : raisonMethod
                            )}
                        </p>
                    `
                    : ""
            }

            <p>
                <strong>
                    Python solved with:
                </strong>

                ${escapeHtml(
                    pythonMethod
                )}
            </p>

            ${
                hasAnalyticalSolution
                    ? analyticalSolutionHtml
                    : `
                        <p>
                            <strong>
                                Root:
                            </strong>

                            ${escapeHtml(
                                root
                            )}
                        </p>
                    `
            }

            <p>
                <strong>
                    Execution time:
                </strong>

                ${escapeHtml(
                    formatElapsedSeconds(
                        elapsedSeconds
                    )
                )}
            </p>

            ${usageHtml}

        </div>
    `;
}

function validateInputs(equation, methodValue) {
    if (!equation) {
        return {
            message: "Enter an equation first.",
            suggestion: "Example: x^3 + 2*x - 5 = 0"
        };
    }

    const filled = element =>
        String(element?.value ?? "").trim() !== "";

    if (["bisection", "fzero", "itp"].includes(methodValue)) {
        if (filled(aValue) !== filled(bValue)) {
            return {
                message: "Enter both a and b, or leave both empty.",
                suggestion: "Empty fields allow automatic interval search."
            };
        }
    }

    if (methodValue === "secant") {
        if (filled(x0Value) !== filled(x1Value)) {
            return {
                message: "Enter both x0 and x1, or leave both empty.",
                suggestion: "Empty fields allow automatic starting values."
            };
        }
    }

    if (methodValue === "muller") {
        const values = [
            filled(x0Value),
            filled(x1Value),
            filled(document.getElementById("x2Value"))
        ];

        if (values.some(Boolean) && !values.every(Boolean)) {
            return {
                message: "Enter all three values x0, x1 and x2, or leave all empty.",
                suggestion: "Empty fields allow automatic starting values."
            };
        }
    }

    return null;
}

function toNumberOrNull(value) {
    if (
        value === ""
        || value === null
        || value === undefined
    ) {
        return null;
    }

    const numberValue =
        Number(value);

    if (
        !Number.isFinite(
            numberValue
        )
    ) {
        return null;
    }

    return numberValue;
}

function formatGraphInputNumber(
    value
) {
    const numberValue =
        Number(value);

    if (
        !Number.isFinite(
            numberValue
        )
    ) {
        return "";
    }

    return Number(
        numberValue.toFixed(6)
    );
}

function reorderIntervalValues() {
    const aNumber =
        toNumberOrNull(
            aValue.value
        );

    const bNumber =
        toNumberOrNull(
            bValue.value
        );

    if (
        aNumber === null
        || bNumber === null
    ) {
        return;
    }

    if (aNumber > bNumber) {
        aValue.value =
            formatGraphInputNumber(
                bNumber
            );

        bValue.value =
            formatGraphInputNumber(
                aNumber
            );
    }
}

function buildIntervalShapes() {
    const shapes = [];

    const aNumber =
        toNumberOrNull(
            aValue.value
        );

    const bNumber =
        toNumberOrNull(
            bValue.value
        );

    if (
        aNumber !== null
        && bNumber !== null
    ) {
        const left =
            Math.min(
                aNumber,
                bNumber
            );

        const right =
            Math.max(
                aNumber,
                bNumber
            );

        shapes.push({
            type: "rect",
            xref: "x",
            yref: "paper",
            x0: left,
            x1: right,
            y0: 0,
            y1: 1,

            fillcolor:
                "rgba(0, 120, 255, 0.10)",

            line: {
                width: 0
            },

            layer: "below"
        });
    }

    if (
        aNumber !== null
    ) {
        shapes.push({
            type: "line",
            xref: "x",
            yref: "paper",
            x0: aNumber,
            x1: aNumber,
            y0: 0,
            y1: 1,

            line: {
                color:
                    "rgba(0, 90, 255, 0.95)",

                width: 2,
                dash: "dash"
            }
        });
    }

    if (
        bNumber !== null
    ) {
        shapes.push({
            type: "line",
            xref: "x",
            yref: "paper",
            x0: bNumber,
            x1: bNumber,
            y0: 0,
            y1: 1,

            line: {
                color:
                    "rgba(255, 80, 80, 0.95)",

                width: 2,
                dash: "dash"
            }
        });
    }

    return shapes;
}

async function updateIntervalMarkers() {
    const graphDiv =
        document.getElementById(
            "functionChart"
        );

    if (
        !graphDiv
        || typeof Plotly === "undefined"
        || !graphDiv.data
    ) {
        return;
    }

    try {
        graphIsUpdating = true;

        await Plotly.relayout(
            graphDiv,
            {
                shapes:
                    buildIntervalShapes()
            }
        );

        setTimeout(
            () => {
                graphIsUpdating =
                    false;
            },
            100
        );

    } catch (error) {
        graphIsUpdating =
            false;

        console.error(
            "Interval marker update error:",
            error
        );
    }
}

function handleGraphClick(data) {
    if (
        !data
        || !data.points
        || data.points.length === 0
    ) {
        return;
    }

    const clickedX =
        Number(
            data.points[0].x
        );

    if (
        !Number.isFinite(
            clickedX
        )
    ) {
        return;
    }

    // Require two nearby clicks within 450 ms.
    // A single click never changes a or b.
    const now = Date.now();

    const originalEvent =
        data.event || {};

    const touchPoint =
        originalEvent.changedTouches
        && originalEvent.changedTouches[0];

    const pointerX =
        typeof originalEvent.clientX === "number"
            ? originalEvent.clientX
            : touchPoint
                ? touchPoint.clientX
                : null;

    const pointerY =
        typeof originalEvent.clientY === "number"
            ? originalEvent.clientY
            : touchPoint
                ? touchPoint.clientY
                : null;

    const previous =
        lastGraphCurveClick;

    const closeInTime =
        previous !== null
        && now - previous.time <= 450;

    const graphDiv =
        document.getElementById("functionChart");

    const visibleRange =
        readGraphAxisRange(graphDiv, "xaxis");

    const xTolerance =
        visibleRange
            ? (visibleRange[1] - visibleRange[0]) * 0.025
            : Math.max(1, Math.abs(clickedX)) * 0.001;

    const closeInX =
        previous !== null
        && Math.abs(clickedX - previous.x) <= xTolerance;

    const hasPointerCoordinates =
        previous !== null
        && previous.pointerX !== null
        && previous.pointerY !== null
        && pointerX !== null
        && pointerY !== null;

    const closeOnScreen =
        !hasPointerCoordinates
        || (
            Math.abs(pointerX - previous.pointerX) <= 24
            && Math.abs(pointerY - previous.pointerY) <= 24
        );

    const isDoubleClick =
        closeInTime
        && closeInX
        && closeOnScreen;

    lastGraphCurveClick = {
        time: now,
        x: clickedX,
        pointerX: pointerX,
        pointerY: pointerY
    };

    if (!isDoubleClick) {
        return;
    }

    lastGraphCurveClick = null;

    const selectedX =
        formatGraphInputNumber(
            clickedX
        );

    if (
        nextIntervalPoint === "a"
    ) {
        aValue.value =
            selectedX;

        bValue.value =
            "";

        nextIntervalPoint =
            "b";

    } else {
        bValue.value =
            selectedX;

        reorderIntervalValues();

        nextIntervalPoint =
            "a";
    }

    updateIntervalMarkers();
}

function handleManualIntervalChange() {
    const aNumber =
        toNumberOrNull(
            aValue.value
        );

    const bNumber =
        toNumberOrNull(
            bValue.value
        );

    if (
        aNumber !== null
        && bNumber === null
    ) {
        nextIntervalPoint =
            "b";

    } else if (
        aNumber !== null
        && bNumber !== null
    ) {
        nextIntervalPoint =
            "a";
    }

    updateIntervalMarkers();
}

if (aValue) {
    aValue.addEventListener(
        "input",
        handleManualIntervalChange
    );
}

if (bValue) {
    bValue.addEventListener(
        "input",
        handleManualIntervalChange
    );
}

async function fetchGraphPoints(
    equation,
    xMin,
    xMax,
    points = 900
) {
    const response =
        await fetch(
            `${API_BASE_URL}/equation/graph`,
            {
                method:
                    "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify({
                        equation:
                            equation,

                        x_min:
                            xMin,

                        x_max:
                            xMax,

                        points:
                            points
                    })
            }
        );

    const data =
        await response.json();

    if (
        !response.ok
        || !data.success
    ) {
        throw data;
    }

    return (
        data.points || []
    );
}

function buildGraphTrace(
    equation,
    points
) {
    const xValues =
        points.map(
            point =>
                point.x
        );

    const yValues =
        points.map(
            point =>
                point.y
        );

    return {
        x:
            xValues,

        y:
            yValues,

        type:
            "scatter",

        mode:
            "lines",

        connectgaps:
            false,

        name:
            `f(x) = ${equation}`,

        line: {
            width: 3
        },

        hovertemplate:
            "x = %{x:.4f}<br>y = %{y:.4f}<extra></extra>"
    };
}

function buildGraphLayout(
    equation,
    xRange = null
) {
    const xAxis = {
        title: {
            text: "x"
        },

        showgrid:
            true,

        zeroline:
            true,

        fixedrange:
            false
    };

    if (xRange) {
        xAxis.range =
            xRange;
    }

    return {
        title: {
            text: ""
        },

        autosize:
            true,

        dragmode:
            "pan",

        margin: {
            l: 60,
            r: 30,
            t: 60,
            b: 60
        },

        xaxis:
            xAxis,

        yaxis: {
            title: {
                text: "f(x)"
            },

            showgrid:
                true,

            zeroline:
                true,

            fixedrange:
                false,

            autorange:
                true
        },

        shapes:
            buildIntervalShapes(),

        hovermode:
            "closest"
    };
}

function getGraphConfig() {
    return {
        responsive:
            true,

        scrollZoom:
            true,

        // Reset only through the Reset Zoom button.
        doubleClick:
            false,

        displayModeBar:
            true,

        displaylogo:
            false,

        modeBarButtonsToRemove: [
            "lasso2d",
            "select2d"
        ]
    };
}

function attachGraphEvents(
    graphDiv
) {
    if (
        !graphDiv
        || !graphDiv.on
    ) {
        return;
    }

    if (
        graphDiv.removeAllListeners
    ) {
        graphDiv.removeAllListeners(
            "plotly_click"
        );

        graphDiv.removeAllListeners(
            "plotly_relayout"
        );
    }

    graphDiv.on(
        "plotly_click",
        handleGraphClick
    );

    graphDiv.on(
        "plotly_relayout",
        handleGraphRelayout
    );
}


function readGraphAxisRange(graphDiv, axisName) {
    if (!graphDiv) {
        return null;
    }

    const layoutAxis =
        graphDiv.layout && graphDiv.layout[axisName];

    const fullAxis =
        graphDiv._fullLayout
            && graphDiv._fullLayout[axisName];

    const candidate =
        layoutAxis && Array.isArray(layoutAxis.range)
            ? layoutAxis.range
            : fullAxis && fullAxis.range;

    if (!Array.isArray(candidate) || candidate.length !== 2) {
        return null;
    }

    const minimum = Number(candidate[0]);
    const maximum = Number(candidate[1]);

    if (
        !Number.isFinite(minimum)
        || !Number.isFinite(maximum)
        || maximum <= minimum
    ) {
        return null;
    }

    return [minimum, maximum];
}

function handleGraphRelayout(
    eventData
) {
    if (
        graphIsUpdating
        || !eventData
    ) {
        return;
    }

    lastGraphCurveClick = null;
    graphViewportRevision += 1;
    clearTimeout(graphRelayoutTimer);

    let newXMin =
        eventData[
            "xaxis.range[0]"
        ];

    let newXMax =
        eventData[
            "xaxis.range[1]"
        ];

    if (
        Array.isArray(
            eventData[
                "xaxis.range"
            ]
        )
    ) {
        newXMin =
            eventData[
                "xaxis.range"
            ][0];

        newXMax =
            eventData[
                "xaxis.range"
            ][1];
    }

    if (
        newXMin === undefined
        || newXMax === undefined
    ) {
        const graphDiv =
            document.getElementById("functionChart");

        const currentRange =
            readGraphAxisRange(graphDiv, "xaxis");

        if (!currentRange) {
            return;
        }

        newXMin = currentRange[0];
        newXMax = currentRange[1];
    }

    newXMin =
        Number(newXMin);

    newXMax =
        Number(newXMax);

    if (
        !Number.isFinite(
            newXMin
        )
        || !Number.isFinite(
            newXMax
        )
        || newXMax <= newXMin
    ) {
        return;
    }

    const loadedWidth =
        currentGraphXMax - currentGraphXMin;

    const visibleWidth =
        newXMax - newXMin;

    // Resample after substantial zoom-in,
    // or whenever the view leaves loaded bounds.
    const needsMorePoints =
        newXMin < currentGraphXMin
        || newXMax > currentGraphXMax
        || visibleWidth < loadedWidth * 0.60;

    if (!needsMorePoints) {
        return;
    }

    const requestedRevision =
        graphViewportRevision;

    graphRelayoutTimer =
        setTimeout(
            () => {
                if (
                    requestedRevision
                    !== graphViewportRevision
                ) {
                    return;
                }

                updateGraphForVisibleRange(
                    newXMin,
                    newXMax,
                    requestedRevision
                );
            },
            450
        );
}

async function updateGraphForVisibleRange(
    visibleXMin,
    visibleXMax,
    requestedRevision
) {
    const graphDiv =
        document.getElementById(
            "functionChart"
        );

    const equation =
        currentGraphEquation
        || equationInput.value.trim();

    if (
        !graphDiv
        || !equation
        || typeof Plotly
            === "undefined"
    ) {
        return;
    }

    const visibleWidth =
        visibleXMax
        - visibleXMin;

    const extraSpace =
        visibleWidth
        * 0.25;

    const fetchXMin =
        visibleXMin
        - extraSpace;

    const fetchXMax =
        visibleXMax
        + extraSpace;

    try {
        const points =
            await fetchGraphPoints(
                equation,
                fetchXMin,
                fetchXMax,
                900
            );

        // Ignore outdated responses.
        if (
            requestedRevision !== graphViewportRevision
            || equation !== currentGraphEquation
        ) {
            return;
        }

        // Capture the latest user-selected viewport.
        const activeXRange =
            readGraphAxisRange(graphDiv, "xaxis");

        const activeYRange =
            readGraphAxisRange(graphDiv, "yaxis");

        const trace =
            buildGraphTrace(
                equation,
                points
            );

        // Preserve the user-selected viewport.
        // Refresh only the calculated curve points.
        graphIsUpdating = true;

        const preservedAxes = {};

        if (activeXRange) {
            preservedAxes["xaxis.range"] =
                activeXRange;

            preservedAxes["xaxis.autorange"] =
                false;
        }

        if (activeYRange) {
            preservedAxes["yaxis.range"] =
                activeYRange;

            preservedAxes["yaxis.autorange"] =
                false;
        }

        if (Object.keys(preservedAxes).length > 0) {
            await Plotly.relayout(
                graphDiv,
                preservedAxes
            );
        }

        await Plotly.restyle(
            graphDiv,
            {
                x: [trace.x],
                y: [trace.y]
            },
            [0]
        );

        currentGraphXMin =
            fetchXMin;

        currentGraphXMax =
            fetchXMax;

        attachGraphEvents(
            graphDiv
        );

        setTimeout(
            () => {
                graphIsUpdating =
                    false;
            },
            150
        );

    } catch (error) {
        graphIsUpdating =
            false;

        console.error(
            "Graph zoom update error:",
            error
        );
    }
}

function getGraphMessageElement() {
    if (!graphBox) {
        return null;
    }

    let graphMessage =
        document.getElementById(
            "graphMessage"
        );

    if (!graphMessage) {
        graphMessage =
            document.createElement(
                "div"
            );

        graphMessage.id =
            "graphMessage";

        graphMessage.className =
            "graph-message";

        const graphDiv =
            document.getElementById(
                "functionChart"
            );

        if (graphDiv) {
            graphBox.insertBefore(
                graphMessage,
                graphDiv
            );
        } else {
            graphBox.appendChild(
                graphMessage
            );
        }
    }

    return graphMessage;
}

function showGraphMessage(
    message,
    isError = false
) {
    const graphMessage =
        getGraphMessageElement();

    if (!graphMessage) {
        return;
    }

    graphMessage.textContent =
        message;

    graphMessage.classList.toggle(
        "graph-message-error",
        isError
    );

    graphMessage.classList.remove(
        "hidden"
    );
}

function clearGraphMessage() {
    const graphMessage =
        getGraphMessageElement();

    if (!graphMessage) {
        return;
    }

    graphMessage.textContent =
        "";

    graphMessage.classList.add(
        "hidden"
    );

    graphMessage.classList.remove(
        "graph-message-error"
    );
}

function setGraphDrawingState(
    isDrawing
) {
    if (!drawGraphButton) {
        return;
    }

    drawGraphButton.disabled =
        isDrawing;

    drawGraphButton.textContent =
        isDrawing
            ? "Drawing..."
            : "Draw Graph";
}


function getInitialGraphRange() {
    const aText = aValue
        ? String(aValue.value).trim()
        : "";

    const bText = bValue
        ? String(bValue.value).trim()
        : "";

    if (aText !== "" && bText !== "") {
        const left = Number(aText);
        const right = Number(bText);
        const width = right - left;

        if (
            Number.isFinite(left)
            && Number.isFinite(right)
            && Number.isFinite(width)
            && width > 0
        ) {
            return [left, right];
        }
    }

    return [-10, 10];
}

async function drawGraph(
    equation,
    xMin = -10,
    xMax = 10
) {
    const drawRevision =
        ++graphViewportRevision;

    clearTimeout(graphRelayoutTimer);

    const graphDiv =
        document.getElementById(
            "functionChart"
        );

    if (!graphDiv) {
        console.error(
            "Graph div with id functionChart not found."
        );

        return false;
    }

    if (
        typeof Plotly
        === "undefined"
    ) {
        console.error(
            "Plotly is not loaded. Check index.html script."
        );

        return false;
    }

    try {
        if (graphBox) {
            graphBox.classList.remove(
                "hidden"
            );
        }

        showGraphMessage(
            "Generating graph..."
        );

        const points =
            await fetchGraphPoints(
                equation,
                xMin,
                xMax,
                700
            );

        if (
            drawRevision !== graphViewportRevision
        ) {
            return false;
        }

        currentGraphEquation =
            equation;

        // ABESS_FULL_EQUATION_TITLE_V1
        const equationDisplay =
            document.getElementById(
                "graphEquationDisplay"
            );

        if (equationDisplay) {
            equationDisplay.textContent =
                "f(x) = " + equation;
        }

        currentGraphXMin =
            xMin;

        currentGraphXMax =
            xMax;

        initialGraphXMin =
            xMin;

        initialGraphXMax =
            xMax;

        nextIntervalPoint =
            "a";

        const trace =
            buildGraphTrace(
                equation,
                points
            );

        const layout =
            buildGraphLayout(
                equation,
                [xMin, xMax]
            );

        const config =
            getGraphConfig();

        graphIsUpdating =
            true;

        await Plotly.react(
            graphDiv,
            [trace],
            layout,
            config
        );

        attachGraphEvents(
            graphDiv
        );

        clearGraphMessage();

        setTimeout(
            () => {
                graphIsUpdating =
                    false;
            },
            150
        );

        return true;

    } catch (error) {
        graphIsUpdating =
            false;

        console.error(
            "Graph generation error:",
            error
        );

        const message =
            getErrorMessage(
                error
            );

        if (graphBox) {
            graphBox.classList.remove(
                "hidden"
            );
        }

        showGraphMessage(
            message
            || (
                "The graph could "
                + "not be generated."
            ),
            true
        );

        return false;
    }
}

function showHistoryMessage(
    message
) {
    if (
        !historyBox
        || !historyContent
    ) {
        return;
    }

    historyBox.classList.remove(
        "hidden"
    );

    historyContent.innerHTML = `
        <div class="history-message">
            ${escapeHtml(message)}
        </div>
    `;
}

function showHistoryItems(items) {
    if (
        !historyBox
        || !historyContent
    ) {
        return;
    }

    historyBox.classList.remove(
        "hidden"
    );

    if (
        !items
        || items.length === 0
    ) {
        historyContent.innerHTML = `
            <div class="history-message">
                No solve history is available yet.
            </div>
        `;

        return;
    }

    const historyHtml =
        items
            .map(
                item => {
                    const isSuccess = (
                        item.success !== false
                        && item.success !== 0
                    );

                    const statusHtml = isSuccess
                        ? `
                            <span>
                                <strong>
                                    Status:
                                </strong>
                                Success
                            </span>
                        `
                        : `
                            <span>
                                <strong>
                                    Status:
                                </strong>
                                Failed
                            </span>
                        `;

                    const outcomeHtml = isSuccess
                        ? `
                            <span>
                                <strong>
                                    Result:
                                </strong>

                                ${escapeHtml(
                                    formatRoot(
                                        item.result
                                    )
                                )}
                            </span>
                        `
                        : `
                            <span>
                                <strong>
                                    Error:
                                </strong>

                                ${escapeHtml(
                                    item.error_code
                                    || "SOLVE_FAILED"
                                )}
                            </span>

                            <span>
                                <strong>
                                    Message:
                                </strong>

                                ${escapeHtml(
                                    item.error_message
                                    || "The solve attempt failed."
                                )}
                            </span>
                        `;

                    return `
                        <div class="history-item">

                            <div class="history-item-top">

                                <strong>
                                    ${escapeHtml(
                                        item.equation
                                    )}
                                </strong>

                                <span>
                                    ${escapeHtml(
                                        formatDate(
                                            item.created_at
                                        )
                                    )}
                                </span>

                            </div>

                            <div class="history-item-details">

                                <span>
                                    <strong>
                                        Method:
                                    </strong>

                                    ${escapeHtml(
                                        formatMethod(
                                            item.method
                                        )
                                    )}
                                </span>

                                ${statusHtml}

                                ${outcomeHtml}

                            </div>

                        </div>
                    `;
                }
            )
            .join("");

    historyContent.innerHTML =
        historyHtml;
}


async function loadMyHistory() {
    const token =
        getAccessToken();

    if (!token) {
        showHistoryMessage(
            "Log in to view your solve history."
        );

        return;
    }

    showHistoryMessage(
        "Loading history..."
    );

    try {
        const response =
            await fetch(
                `${API_BASE_URL}/equation/my-history`,
                {
                    method:
                        "GET",

                    headers:
                        getAuthHeaders()
                }
            );

        const data =
            await response.json();

        if (
            !response.ok
            || !data.success
        ) {
            showHistoryMessage(
                getErrorMessage(
                    data
                )
            );

            return;
        }

        showHistoryItems(
            data.history
        );

    } catch (error) {
        console.error(
            "History error:",
            error
        );

        showHistoryMessage(
            "The solve history could not be loaded."
        );
    }
}

if (historyButton) {
    historyButton.addEventListener(
        "click",
        loadMyHistory
    );
}

if (closeHistoryButton) {
    closeHistoryButton.addEventListener(
        "click",
        function () {
            historyBox.classList.add(
                "hidden"
            );
        }
    );
}

if (solveButton) {
    solveButton.addEventListener(
        "click",
        async function () {
            const equation =
                equationInput.value.trim();

            const methodValue =
                methodSelect.value;

            const validationError =
                validateInputs(
                    equation,
                    methodValue
                );

            if (validationError) {
                showInfo(
                    validationError.message,
                    validationError.suggestion
                );

                return;
            }

            const payload = {
                equation:
                    equation,

                method:
                    methodValue
                        === "automatic"
                        ? null
                        : methodValue,

                guest_id:
                    getGuestId(),

                a:
                    aValue.value
                        ? parseFloat(
                            aValue.value
                        )
                        : null,

                b:
                    bValue.value
                        ? parseFloat(
                            bValue.value
                        )
                        : null,

                x0:
                    x0Value.value
                        ? parseFloat(
                            x0Value.value
                        )
                        : null,

                x1:
                    x1Value.value
                        ? parseFloat(
                            x1Value.value
                        )
                        : null,

                x2:
                    document.getElementById("x2Value")?.value
                        ? parseFloat(
                            document.getElementById("x2Value").value
                          )
                        : null,

                selected_elements:
                    methodValue
                        === "automatic"
                        ? getSelectedCriteria()
                        : []
            };

            startSolveTimer(
                methodValue
            );

            setSolvingState(
                true
            );

            const controller =
                new AbortController();

            const timeoutId =
                setTimeout(
                    () =>
                        controller.abort(),
                    45000
                );

            let response;

            try {
                response =
                    await fetch(
                        `${API_BASE_URL}/equation/solve`,
                        {
                            method:
                                "POST",

                            headers:
                                getAuthHeaders(),

                            body:
                                JSON.stringify(
                                    payload
                                ),

                            signal:
                                controller.signal
                        }
                    );

            } catch (error) {
                clearTimeout(
                    timeoutId
                );

                stopSolveTimer();

                if (
                    error.name
                    === "AbortError"
                ) {
                    showError(
                        "The solve request timed out.",
                        "The operation took longer than expected.",
                        "Try again. If the equation is computationally demanding, review the selected method or criteria."
                    );

                } else {
                    showError(
                        "The server could not be reached.",
                        "No response was received from the server.",
                        "Check your network connection and try again."
                    );
                }

                console.error(
                    "Solve network request error:",
                    error
                );

                setSolvingState(
                    false
                );

                return;
            }

            clearTimeout(
                timeoutId
            );

            let responseText = "";
            let data = null;

            try {
                responseText =
                    await response.text();

                data = responseText
                    ? JSON.parse(
                        responseText
                    )
                    : {};

            } catch (error) {
                console.error(
                    "Solve response parsing error:",
                    error
                );
            }

            const elapsedSeconds =
                stopSolveTimer();

            try {
                if (!response.ok) {
                    if (data) {
                        const guestLimitReached =
                            isGuestLimitReached(
                                data
                            );

                        showErrorResponse(
                            data,
                            methodValue
                        );

                        if (
                            guestLimitReached
                        ) {
                            redirectGuestToAuth();
                        }

                    } else {
                        showError(
                            "An internal server error occurred.",
                            "The server returned an unexpected response while processing the equation.",
                            "Try again. If the problem continues, report the equation and selected method."
                        );
                    }

                    return;
                }

                if (!data) {
                    showError(
                        "An invalid server response was received.",
                        "The solve request reached the server, but the response could not be interpreted.",
                        "Try again. If the problem continues, report the equation and selected method."
                    );

                    return;
                }

                if (!data.success) {
                    showErrorResponse(
                        data,
                        methodValue
                    );

                    return;
                }

                showSuccess(
                    data,
                    elapsedSeconds
                );

            } catch (error) {
                console.error(
                    "Solve response handling error:",
                    error
                );

                showError(
                    "The result could not be displayed.",
                    "The server completed the request, but the browser could not display the returned result correctly.",
                    "Refresh the page and try again."
                );

            } finally {
                setSolvingState(
                    false
                );
            }
        }
    );
}

if (drawGraphButton) {
    drawGraphButton.addEventListener(
        "click",
        async function () {
            const equation =
                equationInput.value.trim();

            if (!equation) {
                showInfo(
                    "Enter an equation first.",
                    "Example: x^3 + 2*x - 5 = 0"
                );

                return;
            }

            setGraphDrawingState(
                true
            );

            try {
                const [xMin, xMax] =
                    getInitialGraphRange();

                await drawGraph(
                    equation,
                    xMin,
                    xMax
                );

            } finally {
                setGraphDrawingState(
                    false
                );
            }
        }
    );
}

if (resetZoomButton) {
    resetZoomButton.addEventListener(
        "click",
        async function () {
            const equation =
                currentGraphEquation
                || equationInput
                    .value
                    .trim();

            if (!equation) {
                return;
            }

            await drawGraph(
                equation,
                initialGraphXMin,
                initialGraphXMax
            );
        }
    );
}

if (equationInput) {
    equationInput.addEventListener(
        "input",
        function () {
            const currentEquation =
                equationInput
                    .value
                    .trim();

            if (
                graphBox
                && currentGraphEquation
                && currentEquation
                    !== currentGraphEquation
            ) {
                graphBox.classList.add(
                    "hidden"
                );
            }
        }
    );
}

updateCriteriaSummary();
updateMethodUI();