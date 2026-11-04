// AUTH_FRONTEND_VERSION = "2026-10-01-v7-api-key-my-information"
const AUTH_API_BASE_URL = "/api";
const authScreen = document.getElementById("authScreen");
const solverScreen = document.getElementById("solverScreen");
const authEmail = document.getElementById("authEmail");
const authPassword = document.getElementById("authPassword");
const loginButton = document.getElementById("loginButton");
const registerButton = document.getElementById("registerButton");
const guestButton = document.getElementById("guestButton");
const logoutButton = document.getElementById("logoutButton");
const authMessage = document.getElementById("authMessage");
const userStatus = document.getElementById("userStatus");
const authHistoryButton = document.getElementById("historyButton");
const authHistoryBox = document.getElementById("historyBox");
const adminDashboardButton =
    document.getElementById("adminDashboardButton");
const adminManualButton =
    document.getElementById("adminManualButton");
let myInformationButton = null;
let myInformationModal = null;
let myInformationEmail = null;
let myInformationRole = null;
let myInformationApiKeyInput = null;
let myInformationToggleButton = null;
let myInformationCopyButton = null;
let myInformationRegenerateButton = null;
let myInformationCloseButton = null;
let myInformationMessage = null;
let currentApiKey = "";
const TECHNICAL_AUTH_ERROR_PATTERNS = [
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
    "integrityerror",
    "connectionrefused",
    "database error"
];
function sanitizeAuthMessage(
    message,
    fallback = "The request could not be completed. Please try again later."
) {
    if (typeof message !== "string") {
        return fallback;
    }
    const cleanMessage = message.trim();
    if (!cleanMessage) {
        return fallback;
    }
    if (cleanMessage.length > 300) {
        return fallback;
    }
    const lowerMessage = cleanMessage.toLowerCase();
    const containsTechnicalDetails =
        TECHNICAL_AUTH_ERROR_PATTERNS.some(
            (pattern) => lowerMessage.includes(pattern)
        );
    if (containsTechnicalDetails) {
        return fallback;
    }
    return cleanMessage;
}
function getApiErrorMessage(data, fallback) {
    if (!data || typeof data !== "object") {
        return fallback;
    }
    if (typeof data.detail === "string") {
        return sanitizeAuthMessage(
            data.detail,
            fallback
        );
    }
    return fallback;
}
function setAuthMessage(message, type = "error") {
    if (!authMessage) return;
    authMessage.textContent = sanitizeAuthMessage(
        message,
        type === "success"
            ? "The operation was completed successfully."
            : "The request could not be completed. Please try again later."
    );
    authMessage.className = `auth-message ${type}`;
}
function clearAuthMessage() {
    if (!authMessage) return;
    authMessage.textContent = "";
    authMessage.className = "auth-message";
}
function clearSolverForm() {
    const equationInput = document.getElementById("equation");
    const methodSelect = document.getElementById("method");
    const aValue = document.getElementById("aValue");
    const bValue = document.getElementById("bValue");
    const x0Value = document.getElementById("x0Value");
    const x1Value = document.getElementById("x1Value");
    const resultBox = document.getElementById("result");
    const graphBox = document.getElementById("graphBox");
    const historyBox = document.getElementById("historyBox");
    const historyContent = document.getElementById("historyContent");
    const criteriaMenu = document.getElementById("criteriaMenu");
    if (equationInput) {
        equationInput.value = "";
    }
    if (methodSelect) {
        methodSelect.value = "bisection";
    }
    if (aValue) {
        aValue.value = "";
    }
    if (bValue) {
        bValue.value = "";
    }
    if (x0Value) {
        x0Value.value = "";
    }
    if (x1Value) {
        x1Value.value = "";
    }
    if (resultBox) {
        resultBox.innerHTML = `
            <div class="result-placeholder">
                <strong>No result yet</strong>
                <p>
                    Click Solve to solve the equation or Draw Graph
                    to display the graph.
                </p>
            </div>
        `;
    }
    if (graphBox) {
        graphBox.classList.add("hidden");
    }
    if (historyBox) {
        historyBox.classList.add("hidden");
    }
    if (historyContent) {
        historyContent.innerHTML = "";
    }
    if (criteriaMenu) {
        const checkedBoxes = criteriaMenu.querySelectorAll(
            'input[type="checkbox"]:checked'
        );
        checkedBoxes.forEach((checkbox) => {
            checkbox.checked = false;
        });
    }
    if (typeof updateMethodUI === "function") {
        updateMethodUI();
    }
}
function hideAdminDashboardButton() {
    if (adminDashboardButton) {
        adminDashboardButton.classList.add("hidden");
    }

    if (adminManualButton) {
        adminManualButton.classList.add("hidden");
    }
}
async function updateAdminDashboardButton() {
    hideAdminDashboardButton();
    if (!adminDashboardButton) return;
    const accessMode = localStorage.getItem("access_mode");
    const token = localStorage.getItem("access_token");
    if (
        accessMode !== "registered" ||
        !token
    ) {
        return;
    }
    try {
        const response = await fetch(
            `${AUTH_API_BASE_URL}/admin/me`,
            {
                method: "GET",
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );
        if (!response.ok) {
            return;
        }
        const data = await response.json();
        if (
            data.success &&
            data.is_admin
        ) {
            adminDashboardButton.classList.remove("hidden");

            if (adminManualButton) {
                adminManualButton.classList.remove("hidden");
            }
        }
    } catch (error) {
        console.error(
            "Admin access check failed.",
            error
        );
    }
}
function ensureMyInformationStyles() {
    if (document.getElementById("myInformationStyles")) {
        return;
    }
    const style = document.createElement("style");
    style.id = "myInformationStyles";
    style.textContent = `
        #myInformationButton.hidden,
        #myInformationModal.hidden {
            display: none !important;
        }
        #myInformationModal {
            position: fixed;
            inset: 0;
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            background: rgba(0, 0, 0, 0.55);
        }
        #myInformationModal .my-information-card {
            width: min(560px, 100%);
            max-height: 90vh;
            overflow-y: auto;
            box-sizing: border-box;
            padding: 24px;
            border-radius: 14px;
            background: #ffffff;
            color: #111827;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.28);
        }
        #myInformationModal .my-information-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 20px;
        }
        #myInformationModal .my-information-title {
            margin: 0;
            font-size: 1.35rem;
        }
        #myInformationModal .my-information-close {
            border: 0;
            background: transparent;
            font-size: 1.7rem;
            line-height: 1;
            cursor: pointer;
            color: inherit;
        }
        #myInformationModal .my-information-row {
            margin-bottom: 16px;
        }
        #myInformationModal .my-information-label {
            display: block;
            margin-bottom: 6px;
            font-weight: 700;
        }
        #myInformationModal .my-information-value {
            margin: 0;
            word-break: break-word;
        }
        #myInformationModal .my-information-key-wrap {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        #myInformationModal .my-information-key-input {
            flex: 1 1 300px;
            min-width: 0;
            box-sizing: border-box;
            padding: 10px 12px;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            background: #f8fafc;
            color: #111827;
            font-family: monospace;
        }
        #myInformationModal .my-information-actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 16px;
        }
        #myInformationModal .my-information-button {
            padding: 9px 14px;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            background: #ffffff;
            color: #111827;
            cursor: pointer;
            font: inherit;
        }
        #myInformationModal .my-information-button:hover {
            background: #f1f5f9;
        }
        #myInformationModal .my-information-danger {
            border-color: #dc2626;
            color: #b91c1c;
        }
        #myInformationModal .my-information-message {
            min-height: 1.2em;
            margin: 14px 0 0;
            font-size: 0.95rem;
        }
        #myInformationModal .my-information-message.error {
            color: #b91c1c;
        }
        #myInformationModal .my-information-message.success {
            color: #166534;
        }
        @media (prefers-color-scheme: dark) {
            #myInformationModal .my-information-card {
                background: #111827;
                color: #f8fafc;
            }
            #myInformationModal .my-information-key-input {
                border-color: #475569;
                background: #0f172a;
                color: #f8fafc;
            }
            #myInformationModal .my-information-button {
                border-color: #475569;
                background: #1e293b;
                color: #f8fafc;
            }
            #myInformationModal .my-information-button:hover {
                background: #334155;
            }
        }
    `;
    document.head.appendChild(style);
}
function setMyInformationMessage(
    message = "",
    type = ""
) {
    if (!myInformationMessage) {
        return;
    }
    myInformationMessage.textContent = message;
    myInformationMessage.className =
        "my-information-message";
    if (
        type === "error" ||
        type === "success"
    ) {
        myInformationMessage.classList.add(type);
    }
}
function resetMyInformationSensitiveState() {
    currentApiKey = "";
    if (myInformationApiKeyInput) {
        myInformationApiKeyInput.value = "";
        myInformationApiKeyInput.type = "password";
    }
    if (myInformationToggleButton) {
        myInformationToggleButton.textContent = "Show";
    }
    setMyInformationMessage();
}
function closeMyInformation() {
    if (myInformationModal) {
        myInformationModal.classList.add("hidden");
        myInformationModal.setAttribute(
            "aria-hidden",
            "true"
        );
    }
    resetMyInformationSensitiveState();
    if (
        myInformationButton &&
        !myInformationButton.classList.contains("hidden")
    ) {
        myInformationButton.focus();
    }
}
function hideMyInformationButton() {
    if (!myInformationButton) {
        return;
    }
    myInformationButton.classList.add("hidden");
    if (
        myInformationModal &&
        !myInformationModal.classList.contains("hidden")
    ) {
        closeMyInformation();
    }
}
function showMyInformationButton() {
    if (!myInformationButton) {
        return;
    }
    myInformationButton.classList.remove("hidden");
}
function createMyInformationUi() {
    if (
        document.getElementById("myInformationButton") ||
        document.getElementById("myInformationModal")
    ) {
        myInformationButton =
            document.getElementById(
                "myInformationButton"
            );
        myInformationModal =
            document.getElementById(
                "myInformationModal"
            );
        return;
    }
    ensureMyInformationStyles();
    myInformationButton =
        document.createElement("button");
    myInformationButton.id = "myInformationButton";
    myInformationButton.type = "button";
    myInformationButton.textContent = "My Information";
    myInformationButton.classList.add("hidden");
    if (logoutButton) {
        if (logoutButton.className) {
            myInformationButton.className =
                logoutButton.className;
            myInformationButton.classList.add("hidden");
        }
        logoutButton.parentNode.insertBefore(
            myInformationButton,
            logoutButton
        );
    } else if (solverScreen) {
        solverScreen.prepend(
            myInformationButton
        );
    } else {
        document.body.appendChild(
            myInformationButton
        );
    }
    myInformationModal =
        document.createElement("div");
    myInformationModal.id =
        "myInformationModal";
    myInformationModal.className = "hidden";
    myInformationModal.setAttribute(
        "role",
        "dialog"
    );
    myInformationModal.setAttribute(
        "aria-modal",
        "true"
    );
    myInformationModal.setAttribute(
        "aria-labelledby",
        "myInformationTitle"
    );
    myInformationModal.setAttribute(
        "aria-hidden",
        "true"
    );
    const card =
        document.createElement("div");
    card.className =
        "my-information-card";
    const header =
        document.createElement("div");
    header.className =
        "my-information-header";
    const title =
        document.createElement("h2");
    title.id = "myInformationTitle";
    title.className =
        "my-information-title";
    title.textContent =
        "My Information";
    myInformationCloseButton =
        document.createElement("button");
    myInformationCloseButton.type =
        "button";
    myInformationCloseButton.className =
        "my-information-close";
    myInformationCloseButton.setAttribute(
        "aria-label",
        "Close My Information"
    );
    myInformationCloseButton.textContent =
        "×";
    header.appendChild(title);
    header.appendChild(
        myInformationCloseButton
    );
    const emailRow =
        document.createElement("div");
    emailRow.className =
        "my-information-row";
    const emailLabel =
        document.createElement("span");
    emailLabel.className =
        "my-information-label";
    emailLabel.textContent = "Email";
    myInformationEmail =
        document.createElement("p");
    myInformationEmail.className =
        "my-information-value";
    emailRow.appendChild(emailLabel);
    emailRow.appendChild(
        myInformationEmail
    );
    const roleRow =
        document.createElement("div");
    roleRow.className =
        "my-information-row";
    const roleLabel =
        document.createElement("span");
    roleLabel.className =
        "my-information-label";
    roleLabel.textContent = "Role";
    myInformationRole =
        document.createElement("p");
    myInformationRole.className =
        "my-information-value";
    roleRow.appendChild(roleLabel);
    roleRow.appendChild(
        myInformationRole
    );
    const apiKeyRow =
        document.createElement("div");
    apiKeyRow.className =
        "my-information-row";
    const apiKeyLabel =
        document.createElement("label");
    apiKeyLabel.className =
        "my-information-label";
    apiKeyLabel.htmlFor =
        "myInformationApiKey";
    apiKeyLabel.textContent =
        "API Key";
    const apiKeyWrap =
        document.createElement("div");
    apiKeyWrap.className =
        "my-information-key-wrap";
    myInformationApiKeyInput =
        document.createElement("input");
    myInformationApiKeyInput.id =
        "myInformationApiKey";
    myInformationApiKeyInput.className =
        "my-information-key-input";
    myInformationApiKeyInput.type =
        "password";
    myInformationApiKeyInput.readOnly =
        true;
    myInformationApiKeyInput.autocomplete =
        "off";
    myInformationApiKeyInput.spellcheck =
        false;
    myInformationToggleButton =
        document.createElement("button");
    myInformationToggleButton.type =
        "button";
    myInformationToggleButton.className =
        "my-information-button";
    myInformationToggleButton.textContent =
        "Show";
    myInformationCopyButton =
        document.createElement("button");
    myInformationCopyButton.type =
        "button";
    myInformationCopyButton.className =
        "my-information-button";
    myInformationCopyButton.textContent =
        "Copy";
    apiKeyWrap.appendChild(
        myInformationApiKeyInput
    );
    apiKeyWrap.appendChild(
        myInformationToggleButton
    );
    apiKeyWrap.appendChild(
        myInformationCopyButton
    );
    apiKeyRow.appendChild(apiKeyLabel);
    apiKeyRow.appendChild(apiKeyWrap);
    const actions =
        document.createElement("div");
    actions.className =
        "my-information-actions";
    myInformationRegenerateButton =
        document.createElement("button");
    myInformationRegenerateButton.type =
        "button";
    myInformationRegenerateButton.className =
        "my-information-button my-information-danger";
    myInformationRegenerateButton.textContent =
        "Regenerate API Key";
    actions.appendChild(
        myInformationRegenerateButton
    );
    myInformationMessage =
        document.createElement("p");
    myInformationMessage.className =
        "my-information-message";
    card.appendChild(header);
    card.appendChild(emailRow);
    card.appendChild(roleRow);
    card.appendChild(apiKeyRow);
    card.appendChild(actions);
    card.appendChild(
        myInformationMessage
    );
    myInformationModal.appendChild(card);
    document.body.appendChild(
        myInformationModal
    );
    myInformationButton.addEventListener(
        "click",
        openMyInformation
    );
    myInformationCloseButton.addEventListener(
        "click",
        closeMyInformation
    );
    myInformationToggleButton.addEventListener(
        "click",
        toggleApiKeyVisibility
    );
    myInformationCopyButton.addEventListener(
        "click",
        copyApiKey
    );
    myInformationRegenerateButton.addEventListener(
        "click",
        regenerateApiKey
    );
    myInformationModal.addEventListener(
        "click",
        (event) => {
            if (
                event.target ===
                myInformationModal
            ) {
                closeMyInformation();
            }
        }
    );
    document.addEventListener(
        "keydown",
        (event) => {
            if (
                event.key === "Escape" &&
                myInformationModal &&
                !myInformationModal.classList.contains(
                    "hidden"
                )
            ) {
                closeMyInformation();
            }
        }
    );
}
async function openMyInformation() {
    const accessMode =
        localStorage.getItem(
            "access_mode"
        );
    const token =
        localStorage.getItem(
            "access_token"
        );
    if (
        accessMode !== "registered" ||
        !token
    ) {
        hideMyInformationButton();
        return;
    }
    resetMyInformationSensitiveState();
    if (myInformationEmail) {
        myInformationEmail.textContent =
            "Loading...";
    }
    if (myInformationRole) {
        myInformationRole.textContent =
            "Loading...";
    }
    if (myInformationModal) {
        myInformationModal.classList.remove(
            "hidden"
        );
        myInformationModal.setAttribute(
            "aria-hidden",
            "false"
        );
    }
    setMyInformationMessage(
        "Loading account information..."
    );
    try {
        const response = await fetch(
            `${AUTH_API_BASE_URL}/auth/my-information`,
            {
                method: "GET",
                headers: {
                    "Authorization":
                        `Bearer ${token}`,
                    "Cache-Control":
                        "no-store"
                },
                cache: "no-store"
            }
        );
        let data = {};
        try {
            data = await response.json();
        } catch {
            data = {};
        }
        if (
            response.status === 401 ||
            response.status === 403
        ) {
            closeMyInformation();
            clearAuthState();
            clearSolverForm();
            hideAdminDashboardButton();
            showAuthScreen(
                "Your session has expired. Please log in again.",
                "error"
            );
            return;
        }
        if (!response.ok) {
            throw new Error(
                getApiErrorMessage(
                    data,
                    "Unable to load your information."
                )
            );
        }
        if (
            typeof data.api_key !== "string" ||
            !data.api_key
        ) {
            throw new Error(
                "Your API key could not be loaded."
            );
        }
        currentApiKey = data.api_key;
        if (myInformationEmail) {
            myInformationEmail.textContent =
                data.email || "";
        }
        if (myInformationRole) {
            myInformationRole.textContent =
                data.role || "";
        }
        if (myInformationApiKeyInput) {
            myInformationApiKeyInput.value =
                currentApiKey;
            myInformationApiKeyInput.type =
                "password";
        }
        if (myInformationToggleButton) {
            myInformationToggleButton.textContent =
                "Show";
        }
        setMyInformationMessage();
        if (myInformationCloseButton) {
            myInformationCloseButton.focus();
        }
    } catch (error) {
        currentApiKey = "";
        if (myInformationApiKeyInput) {
            myInformationApiKeyInput.value =
                "";
        }
        setMyInformationMessage(
            error instanceof Error
                ? sanitizeAuthMessage(
                    error.message,
                    "Unable to load your information."
                )
                : "Unable to load your information.",
            "error"
        );
    }
}
function toggleApiKeyVisibility() {
    if (
        !myInformationApiKeyInput ||
        !currentApiKey
    ) {
        return;
    }
    const shouldShow =
        myInformationApiKeyInput.type ===
        "password";
    myInformationApiKeyInput.type =
        shouldShow
            ? "text"
            : "password";
    if (myInformationToggleButton) {
        myInformationToggleButton.textContent =
            shouldShow
                ? "Hide"
                : "Show";
    }
}
async function copyApiKey() {
    if (!currentApiKey) {
        setMyInformationMessage(
            "The API key is not available.",
            "error"
        );
        return;
    }
    try {
        if (
            navigator.clipboard &&
            window.isSecureContext
        ) {
            await navigator.clipboard.writeText(
                currentApiKey
            );
        } else {
            const temporaryInput =
                document.createElement(
                    "textarea"
                );
            temporaryInput.value =
                currentApiKey;
            temporaryInput.setAttribute(
                "readonly",
                ""
            );
            temporaryInput.style.position =
                "fixed";
            temporaryInput.style.opacity =
                "0";
            document.body.appendChild(
                temporaryInput
            );
            temporaryInput.select();
            const copied =
                document.execCommand(
                    "copy"
                );
            temporaryInput.remove();
            if (!copied) {
                throw new Error(
                    "Copy operation failed."
                );
            }
        }
        setMyInformationMessage(
            "API key copied to clipboard.",
            "success"
        );
    } catch {
        setMyInformationMessage(
            "The API key could not be copied automatically. Use Show and copy it manually.",
            "error"
        );
    }
}
async function regenerateApiKey() {
    const token =
        localStorage.getItem(
            "access_token"
        );
    if (!token) {
        closeMyInformation();
        clearAuthState();
        showAuthScreen(
            "Please log in again.",
            "error"
        );
        return;
    }
    const confirmed =
        window.confirm(
            "Regenerate your API key? The previous key will stop working immediately."
        );
    if (!confirmed) {
        return;
    }
    if (myInformationRegenerateButton) {
        myInformationRegenerateButton.disabled =
            true;
    }
    if (myInformationCopyButton) {
        myInformationCopyButton.disabled =
            true;
    }
    if (myInformationToggleButton) {
        myInformationToggleButton.disabled =
            true;
    }
    setMyInformationMessage(
        "Generating a new API key..."
    );
    try {
        const response = await fetch(
            `${AUTH_API_BASE_URL}/auth/regenerate-api-key`,
            {
                method: "POST",
                headers: {
                    "Authorization":
                        `Bearer ${token}`,
                    "Content-Type":
                        "application/json",
                    "Cache-Control":
                        "no-store"
                },
                cache: "no-store"
            }
        );
        let data = {};
        try {
            data = await response.json();
        } catch {
            data = {};
        }
        if (
            response.status === 401 ||
            response.status === 403
        ) {
            closeMyInformation();
            clearAuthState();
            clearSolverForm();
            hideAdminDashboardButton();
            showAuthScreen(
                "Your session has expired. Please log in again.",
                "error"
            );
            return;
        }
        if (!response.ok) {
            throw new Error(
                getApiErrorMessage(
                    data,
                    "The API key could not be regenerated."
                )
            );
        }
        if (
            typeof data.api_key !== "string" ||
            !data.api_key
        ) {
            throw new Error(
                "The new API key could not be loaded."
            );
        }
        currentApiKey = data.api_key;
        if (myInformationApiKeyInput) {
            myInformationApiKeyInput.value =
                currentApiKey;
            myInformationApiKeyInput.type =
                "text";
        }
        if (myInformationToggleButton) {
            myInformationToggleButton.textContent =
                "Hide";
        }
        setMyInformationMessage(
            "A new API key was created. The previous key is no longer valid.",
            "success"
        );
    } catch (error) {
        setMyInformationMessage(
            error instanceof Error
                ? sanitizeAuthMessage(
                    error.message,
                    "The API key could not be regenerated."
                )
                : "The API key could not be regenerated.",
            "error"
        );
    } finally {
        if (myInformationRegenerateButton) {
            myInformationRegenerateButton.disabled =
                false;
        }
        if (myInformationCopyButton) {
            myInformationCopyButton.disabled =
                false;
        }
        if (myInformationToggleButton) {
            myInformationToggleButton.disabled =
                false;
        }
    }
}
function showAuthScreen(
    message = null,
    type = "error"
) {
    authScreen.classList.remove("hidden");
    solverScreen.classList.add("hidden");
    hideAdminDashboardButton();
    hideMyInformationButton();
    if (message) {
        setAuthMessage(
            message,
            type
        );
    } else {
        clearAuthMessage();
    }
}
function showSolverScreen(
    shouldClearSolver = false
) {
    authScreen.classList.add("hidden");
    solverScreen.classList.remove("hidden");
    clearAuthMessage();
    if (shouldClearSolver) {
        clearSolverForm();
    }
    updateUserStatus();
}
function updateUserStatus() {
    const accessMode =
        localStorage.getItem("access_mode");
    const userEmail =
        localStorage.getItem("user_email");
    if (!userStatus) return;
    if (
        accessMode === "registered" &&
        userEmail
    ) {
        userStatus.textContent =
            `Logged in as ${userEmail}`;
        if (authHistoryButton) {
            authHistoryButton.classList.remove(
                "hidden"
            );
        }
        updateAdminDashboardButton();
        showMyInformationButton();
        return;
    }
    userStatus.textContent = "Guest mode";
    if (authHistoryButton) {
        authHistoryButton.classList.add(
            "hidden"
        );
    }
    if (authHistoryBox) {
        authHistoryBox.classList.add(
            "hidden"
        );
    }
    hideAdminDashboardButton();
    hideMyInformationButton();
}
function getAuthInputs() {
    return {
        email: authEmail
            ? authEmail.value.trim()
            : "",
        password: authPassword
            ? authPassword.value
            : ""
    };
}
function validateAuthInputs(
    email,
    password
) {
    if (
        !email ||
        !password
    ) {
        setAuthMessage(
            "Please enter your email address and password.",
            "error"
        );
        return false;
    }
    if (password.length < 6) {
        setAuthMessage(
            "Password must contain at least 6 characters.",
            "error"
        );
        return false;
    }
    return true;
}
function clearAuthState() {
    localStorage.removeItem(
        "access_token"
    );
    localStorage.removeItem(
        "access_mode"
    );
    localStorage.removeItem(
        "user_email"
    );
}
function clearRegisteredStateOnly() {
    localStorage.removeItem(
        "access_token"
    );
    localStorage.removeItem(
        "user_email"
    );
}
async function loginUser() {
    clearAuthMessage();
    const {
        email,
        password
    } = getAuthInputs();
    if (
        !validateAuthInputs(
            email,
            password
        )
    ) {
        return;
    }
    try {
        const response = await fetch(
            `${AUTH_API_BASE_URL}/auth/login`,
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body: JSON.stringify({
                    email: email,
                    password: password
                })
            }
        );
        let data = {};
        try {
            data = await response.json();
        } catch {
            data = {};
        }
        if (!response.ok) {
            const fallbackMessage =
                response.status >= 500
                    ? "Unable to connect to the server. Please try again later."
                    : "Unable to log in. Please check your email and password.";
            setAuthMessage(
                getApiErrorMessage(
                    data,
                    fallbackMessage
                ),
                "error"
            );
            return;
        }
        if (
            !data.access_token ||
            typeof data.access_token !== "string"
        ) {
            setAuthMessage(
                "Login could not be completed. Please try again later.",
                "error"
            );
            return;
        }
        localStorage.setItem(
            "access_token",
            data.access_token
        );
        localStorage.setItem(
            "access_mode",
            "registered"
        );
        localStorage.setItem(
            "user_email",
            email
        );
        showSolverScreen(true);
    } catch (error) {
        console.error(
            "Login request failed.",
            error
        );
        setAuthMessage(
            "Unable to connect to the server. Please try again later.",
            "error"
        );
    }
}
async function registerUser() {
    clearAuthMessage();
    const {
        email,
        password
    } = getAuthInputs();
    if (
        !validateAuthInputs(
            email,
            password
        )
    ) {
        return;
    }
    try {
        const response = await fetch(
            `${AUTH_API_BASE_URL}/auth/register`,
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body: JSON.stringify({
                    email: email,
                    password: password
                })
            }
        );
        let data = {};
        try {
            data = await response.json();
        } catch {
            data = {};
        }
        if (!response.ok) {
            const message =
                getApiErrorMessage(
                    data,
                    "Registration could not be completed. Please try again later."
                );
            const lowerMessage =
                message.toLowerCase();
            if (
                lowerMessage.includes(
                    "already registered"
                ) ||
                lowerMessage.includes(
                    "already in use"
                )
            ) {
                setAuthMessage(
                    "This email address is already registered. Please log in instead.",
                    "error"
                );
                return;
            }
            setAuthMessage(
                message,
                "error"
            );
            return;
        }
        clearRegisteredStateOnly();
        setAuthMessage(
            sanitizeAuthMessage(
                data.message,
                "Your account has been created. Check your email to verify your account."
            ),
            "success"
        );
        if (authPassword) {
            authPassword.value = "";
        }
    } catch (error) {
        console.error(
            "Registration request failed.",
            error
        );
        setAuthMessage(
            "Unable to connect to the server. Please try again later.",
            "error"
        );
    }
}
function continueAsGuest() {
    clearRegisteredStateOnly();
    localStorage.setItem(
        "access_mode",
        "guest"
    );
    hideAdminDashboardButton();
    hideMyInformationButton();
    clearAuthMessage();
    showSolverScreen(true);
}
function logoutUser() {
    closeMyInformation();
    clearAuthState();
    clearSolverForm();
    hideAdminDashboardButton();
    hideMyInformationButton();
    showAuthScreen();
}
function openAdminDashboard() {
    window.location.href =
        "./admin.html";
}
function initAuthState() {
    const accessMode =
        localStorage.getItem(
            "access_mode"
        );
    const token =
        localStorage.getItem(
            "access_token"
        );
    const userEmail =
        localStorage.getItem(
            "user_email"
        );
    if (
        accessMode === "registered" &&
        token &&
        userEmail
    ) {
        showSolverScreen(false);
        return;
    }
    if (accessMode === "guest") {
        showSolverScreen(false);
        return;
    }
    clearAuthState();
    clearSolverForm();
    showAuthScreen();
}
if (loginButton) {
    loginButton.addEventListener(
        "click",
        loginUser
    );
}
if (registerButton) {
    registerButton.addEventListener(
        "click",
        registerUser
    );
}
if (guestButton) {
    guestButton.addEventListener(
        "click",
        continueAsGuest
    );
}
if (logoutButton) {
    logoutButton.addEventListener(
        "click",
        logoutUser
    );
}
if (adminDashboardButton) {
    adminDashboardButton.addEventListener(
        "click",
        openAdminDashboard
    );
}

function createPasswordResetUi() {
    if (
        !authScreen
        || document.getElementById(
            "forgotPasswordButton"
        )
    ) {
        return;
    }

    const guestButtonElement =
        document.getElementById(
            "guestButton"
        );

    const forgotButton =
        document.createElement(
            "button"
        );

    forgotButton.type =
        "button";

    forgotButton.id =
        "forgotPasswordButton";

    forgotButton.textContent =
        "Forgot password?";

    forgotButton.style.display =
        "block";

    forgotButton.style.margin =
        "12px auto";

    forgotButton.style.border =
        "none";

    forgotButton.style.background =
        "transparent";

    forgotButton.style.cursor =
        "pointer";

    forgotButton.style.textDecoration =
        "underline";

    if (authMessage) {
        authScreen.insertBefore(
            forgotButton,
            authMessage
        );
    } else {
        authScreen.appendChild(
            forgotButton
        );
    }

    forgotButton.addEventListener(
        "click",
        requestPasswordReset
    );
}


async function requestPasswordReset() {
    clearAuthMessage();

    const email =
        authEmail
            ? authEmail.value.trim()
            : "";

    if (!email) {
        setAuthMessage(
            "Please enter your email address first.",
            "error"
        );

        return;
    }

    try {
        const response =
            await fetch(
                `${AUTH_API_BASE_URL}/auth/forgot-password`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        email: email
                    })
                }
            );

        let data = {};

        try {
            data =
                await response.json();
        } catch {
            data = {};
        }

        if (!response.ok) {
            setAuthMessage(
                getApiErrorMessage(
                    data,
                    "The password reset request could not be completed."
                ),
                "error"
            );

            return;
        }

        setAuthMessage(
            data.message
            || "If an eligible account exists, a password reset email has been sent.",
            "success"
        );

    } catch (error) {
        console.error(
            "Password reset request failed.",
            error
        );

        setAuthMessage(
            "Unable to connect to the server. Please try again later.",
            "error"
        );
    }
}


function restoreNormalAuthUi() {
    const emailGroup =
        authEmail
            ? authEmail.closest(
                ".form-group"
            )
            : null;

    const passwordGroup =
        authPassword
            ? authPassword.closest(
                ".form-group"
            )
            : null;

    const authActions =
        authScreen
            ? authScreen.querySelector(
                ".auth-actions"
            )
            : null;

    const guestButtonElement =
        document.getElementById(
            "guestButton"
        );

    const forgotButton =
        document.getElementById(
            "forgotPasswordButton"
        );

    const resetPanel =
        document.getElementById(
            "passwordResetPanel"
        );

    if (emailGroup) {
        emailGroup.classList.remove(
            "hidden"
        );
    }

    if (passwordGroup) {
        passwordGroup.classList.remove(
            "hidden"
        );
    }

    if (authActions) {
        authActions.classList.remove(
            "hidden"
        );
    }

    if (guestButtonElement) {
        guestButtonElement.classList.remove(
            "hidden"
        );
    }

    if (forgotButton) {
        forgotButton.classList.remove(
            "hidden"
        );
    }

    if (resetPanel) {
        resetPanel.remove();
    }
}


function showPasswordResetForm(
    token
) {
    clearAuthState();

    authScreen.classList.remove(
        "hidden"
    );

    solverScreen.classList.add(
        "hidden"
    );

    const emailGroup =
        authEmail
            ? authEmail.closest(
                ".form-group"
            )
            : null;

    const passwordGroup =
        authPassword
            ? authPassword.closest(
                ".form-group"
            )
            : null;

    const authActions =
        authScreen.querySelector(
            ".auth-actions"
        );

    const guestButtonElement =
        document.getElementById(
            "guestButton"
        );

    const forgotButton =
        document.getElementById(
            "forgotPasswordButton"
        );

    [
        emailGroup,
        passwordGroup,
        authActions,
        guestButtonElement,
        forgotButton
    ].forEach(
        element => {
            if (element) {
                element.classList.add(
                    "hidden"
                );
            }
        }
    );

    const existingPanel =
        document.getElementById(
            "passwordResetPanel"
        );

    if (existingPanel) {
        existingPanel.remove();
    }

    const panel =
        document.createElement(
            "div"
        );

    panel.id =
        "passwordResetPanel";

    panel.innerHTML = `
        <div class="form-group">
            <label for="resetPassword">
                New password
            </label>

            <input
                type="password"
                id="resetPassword"
                placeholder="Enter new password"
                autocomplete="new-password"
            >
        </div>

        <div class="form-group">
            <label for="resetPasswordConfirm">
                Confirm new password
            </label>

            <input
                type="password"
                id="resetPasswordConfirm"
                placeholder="Confirm new password"
                autocomplete="new-password"
            >
        </div>

        <button
            type="button"
            id="resetPasswordButton"
            class="btn-primary"
        >
            Change Password
        </button>
    `;

    if (authMessage) {
        authScreen.insertBefore(
            panel,
            authMessage
        );
    } else {
        authScreen.appendChild(
            panel
        );
    }

    const resetButton =
        document.getElementById(
            "resetPasswordButton"
        );

    resetButton.addEventListener(
        "click",
        async function () {
            const password =
                document.getElementById(
                    "resetPassword"
                ).value;

            const confirmation =
                document.getElementById(
                    "resetPasswordConfirm"
                ).value;

            if (password.length < 6) {
                setAuthMessage(
                    "Password must contain at least 6 characters.",
                    "error"
                );

                return;
            }

            if (
                password
                !== confirmation
            ) {
                setAuthMessage(
                    "The passwords do not match.",
                    "error"
                );

                return;
            }

            try {
                const response =
                    await fetch(
                        `${AUTH_API_BASE_URL}/auth/reset-password`,
                        {
                            method: "POST",
                            headers: {
                                "Content-Type":
                                    "application/json"
                            },
                            body: JSON.stringify({
                                token: token,
                                new_password:
                                    password
                            })
                        }
                    );

                let data = {};

                try {
                    data =
                        await response.json();
                } catch {
                    data = {};
                }

                if (!response.ok) {
                    setAuthMessage(
                        getApiErrorMessage(
                            data,
                            "The password could not be changed."
                        ),
                        "error"
                    );

                    return;
                }

                window.history.replaceState(
                    {},
                    document.title,
                    window.location.pathname
                );

                restoreNormalAuthUi();

                if (authPassword) {
                    authPassword.value =
                        "";
                }

                setAuthMessage(
                    data.message
                    || "Your password has been changed successfully. You can now log in.",
                    "success"
                );

            } catch (error) {
                console.error(
                    "Password reset failed.",
                    error
                );

                setAuthMessage(
                    "Unable to connect to the server. Please try again later.",
                    "error"
                );
            }
        }
    );
}


function initPasswordResetFlow() {
    const params =
        new URLSearchParams(
            window.location.search
        );

    const token =
        params.get(
            "reset_token"
        );

    if (!token) {
        return false;
    }

    showPasswordResetForm(
        token
    );

    return true;
}


createMyInformationUi();
createPasswordResetUi();

if (!initPasswordResetFlow()) {
    if (adminManualButton) {
    adminManualButton.addEventListener(
        "click",
        () => {
            window.location.href =
                "./admin-help.html";
        }
    );
}

initAuthState();
}
