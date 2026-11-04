// ADMIN_FRONTEND_VERSION = "2026-11-03-v5-admin-summary-layout"

const ADMIN_API_BASE_URL = "/api";

const adminLoading = document.getElementById("adminLoading");
const adminContent = document.getElementById("adminContent");
const adminMessage = document.getElementById("adminMessage");
const adminUserEmail = document.getElementById("adminUserEmail");

const backToSolverButton = document.getElementById("backToSolverButton");
const adminHelpButton = document.getElementById("adminHelpButton");
const adminLogoutButton = document.getElementById("adminLogoutButton");
const refreshAdminButton = document.getElementById("refreshAdminButton");

const statTotalUsers =
    document.getElementById("statTotalUsers");

const statTotalAttempts =
    document.getElementById("statTotalAttempts");

const statSuccessfulAttempts =
    document.getElementById("statSuccessfulAttempts");

const statFailedAttempts =
    document.getElementById("statFailedAttempts");

const statManualAttempts =
    document.getElementById("statManualAttempts");

const statRaisonAttempts =
    document.getElementById("statRaisonAttempts");

const statWebRequests =
    document.getElementById("statWebRequests");

const statApiRequests =
    document.getElementById("statApiRequests");

const statGuestRecords =
    document.getElementById("statGuestRecords");

const statGuestAttempts =
    document.getElementById("statGuestAttempts");

const statVerifiedUsers =
    document.getElementById("statVerifiedUsers");


const usersCount = document.getElementById("usersCount");
const historyCount = document.getElementById("historyCount");
const guestsCount = document.getElementById("guestsCount");

const usersTableBody = document.getElementById("usersTableBody");
const historyTableBody = document.getElementById("historyTableBody");
const guestsTableBody = document.getElementById("guestsTableBody");

const methodUsageTableBody =
    document.getElementById("methodUsageTableBody");

const methodUsageSummary =
    document.getElementById("methodUsageSummary");

const raisonMethodSelectionTableBody =
    document.getElementById("raisonMethodSelectionTableBody");

const raisonSelectionSummary =
    document.getElementById("raisonSelectionSummary");

const ADMIN_SUPPORTED_METHODS = new Set([
    "bisection",
    "newton",
    "secant",
    "fzero",
    "itp",
    "muller",
    "solve",
    "roots",
    "integer_exhaustive_scan"
]);


const adminTabs = document.querySelectorAll(".admin-tab");
const tabPanels = document.querySelectorAll(".tab-panel");


const ADMIN_TECHNICAL_ERROR_PATTERNS = [
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
    "database",
    "sqlite",
    "python",
    "stack trace"
];


function sanitizeAdminMessage(
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
        ADMIN_TECHNICAL_ERROR_PATTERNS.some(
            (pattern) => lowerMessage.includes(pattern)
        );

    if (containsTechnicalDetails) {
        return fallback;
    }

    return cleanMessage;
}


function getAccessToken() {
    return localStorage.getItem("access_token");
}


function clearAuthState() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("access_mode");
    localStorage.removeItem("user_email");
}


function redirectToSolver() {
    window.location.href = "./index.html";
}


function redirectToAdminHelp() {
    window.location.href = "./admin-help.html";
}


function showAdminMessage(
    message,
    type = "error"
) {
    if (!adminMessage) return;

    adminMessage.textContent =
        sanitizeAdminMessage(
            message,
            type === "success"
                ? "The operation was completed successfully."
                : "The request could not be completed. Please try again later."
        );

    adminMessage.className =
        `admin-message ${type}`;
}


function hideAdminMessage() {
    if (!adminMessage) return;

    adminMessage.textContent = "";
    adminMessage.className =
        "admin-message hidden";
}


function setLoading(isLoading) {
    if (adminLoading) {
        adminLoading.classList.toggle(
            "hidden",
            !isLoading
        );
    }

    if (adminContent) {
        adminContent.classList.toggle(
            "hidden",
            isLoading
        );
    }

    if (refreshAdminButton) {
        refreshAdminButton.disabled =
            isLoading;
    }
}


async function adminFetch(path) {
    const token = getAccessToken();

    if (!token) {
        throw new Error("NO_TOKEN");
    }

    let response;

    try {
        response = await fetch(
            `${ADMIN_API_BASE_URL}${path}`,
            {
                method: "GET",
                headers: {
                    "Authorization":
                        `Bearer ${token}`,
                    "Accept":
                        "application/json"
                }
            }
        );
    } catch (error) {
        console.error(
            "Admin API connection failed.",
            error
        );

        throw new Error("NETWORK_ERROR");
    }

    let data = null;

    try {
        data = await response.json();
    } catch {
        data = null;
    }

    if (response.status === 401) {
        throw new Error("UNAUTHORIZED");
    }

    if (response.status === 403) {
        throw new Error("FORBIDDEN");
    }

    if (!response.ok) {
        console.error(
            "Admin API request failed.",
            {
                path: path,
                status: response.status
            }
        );

        throw new Error("REQUEST_FAILED");
    }

    return data;
}


function formatDate(value) {
    if (!value) {
        return "-";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "-";
    }

    return date.toLocaleString(
        "en-GB",
        {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit"
        }
    );
}


function formatBoolean(value) {
    return value ? "Yes" : "No";
}


function formatSelectionSource(source) {
    if (source === "manual") {
        return "Manual";
    }

    if (source === "raison") {
        return "rAIson";
    }

    if (source === "automatic_fallback") {
        return "Automatic fallback";
    }

    return "Unknown";
}


function formatRequestSource(source) {

    const normalized =
        String(source || "")
            .trim()
            .toUpperCase();

    if (normalized === "WEB") {
        return "WEB";
    }

    if (normalized === "API") {
        return "API";
    }

    return "Unknown";
}


function createCell(
    value,
    className = null
) {
    const cell =
        document.createElement("td");

    cell.textContent =
        value ?? "-";

    if (className) {
        cell.classList.add(className);
    }

    return cell;
}


function createStatusCell(
    text,
    statusClass
) {
    const cell =
        document.createElement("td");

    const badge =
        document.createElement("span");

    badge.className =
        `status-badge ${statusClass}`;

    badge.textContent = text;

    cell.appendChild(badge);

    return cell;
}


function renderStats(stats) {

    const values = stats || {};

    if (statTotalUsers) {
        statTotalUsers.textContent =
            values.total_users ?? 0;
    }

    if (statTotalAttempts) {
        statTotalAttempts.textContent =
            values.total_attempts ?? 0;
    }

    if (statSuccessfulAttempts) {
        statSuccessfulAttempts.textContent =
            values.successful_attempts ?? 0;
    }

    if (statFailedAttempts) {
        statFailedAttempts.textContent =
            values.failed_attempts ?? 0;
    }

    if (statManualAttempts) {
        statManualAttempts.textContent =
            values.manual_attempts ?? 0;
    }

    if (statRaisonAttempts) {
        statRaisonAttempts.textContent =
            values.raison_attempts ?? 0;
    }

    if (statWebRequests) {
        statWebRequests.textContent =
            values.web_requests ?? 0;
    }

    if (statApiRequests) {
        statApiRequests.textContent =
            values.api_requests ?? 0;
    }

    if (statGuestRecords) {
        statGuestRecords.textContent =
            values.total_guest_records ?? 0;
    }

    if (statGuestAttempts) {
        statGuestAttempts.textContent =
            values.total_guest_solves ?? 0;
    }

    if (statVerifiedUsers) {
        statVerifiedUsers.textContent =
            values.verified_users ?? 0;
    }
}


function renderStatisticsSummary(container, summary, available, notes, explanation, unavailable) {
    container.replaceChildren();
    if (available) {
        const metrics = document.createElement("dl");
        metrics.className = "admin-summary-metrics";
        [
            ["Attempts", "attempts", ""],
            ["Successful", "successful", " admin-summary-metric--success"],
            ["Failed", "failed", " admin-summary-metric--failed"]
        ].forEach(([label, key, modifier]) => {
            const metric = document.createElement("div");
            metric.className = "admin-summary-metric" + modifier;
            const name = document.createElement("dt");
            name.textContent = label;
            const value = document.createElement("dd");
            value.textContent = summary[key].toLocaleString("en-US");
            metric.appendChild(name);
            metric.appendChild(value);
            metrics.appendChild(metric);
        });
        container.appendChild(metrics);
    }
    if (notes || !available) {
        const caption = document.createElement("p");
        caption.className = "admin-summary-caption";
        caption.textContent = available ? notes : unavailable;
        container.appendChild(caption);
    }
    const details = document.createElement("details");
    details.className = "admin-summary-details";
    const toggle = document.createElement("summary");
    toggle.textContent = "About these counts";
    const text = document.createElement("p");
    text.textContent = explanation;
    details.appendChild(toggle);
    details.appendChild(text);
    container.appendChild(details);
}


function renderMethodUsage(methodUsage, summary) {

    if (methodUsageSummary) {
        const summaryAvailable = summary
            && ["attempts", "successful", "failed", "not_attempted", "not_displayed", "unclassified"]
                .every((key) => Number.isInteger(summary[key]) && summary[key] >= 0);
        const explanation = "Request validation and failed method selections are excluded. "
            + "Solver setup attempts are included.";

        const notes = summaryAvailable ? [
            summary.not_attempted > 0 ? `${summary.not_attempted.toLocaleString("en-US")} requests stopped before solving` : "",
            summary.unclassified > 0 ? `${summary.unclassified.toLocaleString("en-US")} historical records pending classification` : ""
        ].filter(Boolean).join(" · ") : "";
        renderStatisticsSummary(methodUsageSummary, summary, summaryAvailable, notes,
            explanation, "Method usage summary is unavailable.");
    }

    const items =
        Array.isArray(methodUsage)
            ? methodUsage.filter((item) =>
                item && ADMIN_SUPPORTED_METHODS.has(item.method)
            )
            : [];

    if (!methodUsageTableBody) {
        return;
    }

    methodUsageTableBody.replaceChildren();

    if (items.length === 0) {

        const row =
            document.createElement("tr");

        const cell =
            createCell(
                "No method statistics available."
            );

        cell.colSpan = 4;

        row.appendChild(cell);
        methodUsageTableBody.appendChild(row);

        return;
    }

    items.forEach((item) => {

        const row =
            document.createElement("tr");

        row.appendChild(
            createCell(
                item.label
                || item.method
            )
        );

        row.appendChild(
            createCell(
                item.attempts ?? 0
            )
        );

        row.appendChild(
            createCell(
                item.successful ?? 0
            )
        );

        row.appendChild(
            createCell(
                item.failed ?? 0
            )
        );

        methodUsageTableBody.appendChild(row);
    });
}


function renderRaisonMethodSelection(methodSelection, summary) {
    const available = Array.isArray(methodSelection);
    const items = available
        ? methodSelection.filter((item) =>
            item && (
                ADMIN_SUPPORTED_METHODS.has(item.method)
                || item.method === "no_method_selected"
            )
        )
        : [];

    if (raisonSelectionSummary) {
        const summaryAvailable = available && summary
            && ["attempts", "successful", "failed", "not_attempted", "unclassified"]
                .every((key) => Number.isInteger(summary[key]) && summary[key] >= 0);

        const notes = summaryAvailable ? [
            summary.not_attempted > 0 ? `${summary.not_attempted.toLocaleString("en-US")} requests rejected before selection` : "",
            summary.unclassified > 0 ? `${summary.unclassified.toLocaleString("en-US")} historical requests pending classification` : ""
        ].filter(Boolean).join(" · ") : "";
        renderStatisticsSummary(raisonSelectionSummary, summary, summaryAvailable, notes,
            "Selection attempts count once per equation-solving request, including any internal retry; "
                + "standalone rAIson previews are excluded. Selection failures are not solver failures.",
            "rAIson selection statistics are unavailable.");
    }

    if (!raisonMethodSelectionTableBody) {
        return;
    }

    raisonMethodSelectionTableBody.replaceChildren();

    if (items.length === 0) {
        const row = document.createElement("tr");
        const cell = createCell(available
            ? "No rAIson selection statistics available."
            : "rAIson selection statistics are unavailable.");
        cell.colSpan = 4;
        row.appendChild(cell);
        raisonMethodSelectionTableBody.appendChild(row);
        return;
    }

    items.forEach((item) => {
        const row = document.createElement("tr");
        row.appendChild(createCell(item.method === "no_method_selected"
            ? "No supported method selected"
            : item.label || item.method));
        row.appendChild(createCell(item.attempts ?? 0));
        row.appendChild(createCell(item.successful ?? 0));
        row.appendChild(createCell(item.failed ?? 0));
        raisonMethodSelectionTableBody.appendChild(row);
    });
}


let adminHistoryItems = [];
let activeHistoryUserId = null;
let activeHistoryUserEmail = "";


function updateHistoryFilterUI() {

    const historyFilterStatus =
        document.getElementById(
            "historyFilterStatus"
        );

    const clearHistoryFilterButton =
        document.getElementById(
            "clearHistoryFilterButton"
        );

    if (
        !historyFilterStatus
        || !clearHistoryFilterButton
    ) {
        return;
    }


    if (activeHistoryUserId === null) {

        historyFilterStatus.textContent =
            "Showing all users";

        clearHistoryFilterButton.classList.add(
            "hidden"
        );

        return;
    }


    historyFilterStatus.textContent =
        `Showing history for ${
            activeHistoryUserEmail
            || `User ${activeHistoryUserId}`
        }`;

    clearHistoryFilterButton.classList.remove(
        "hidden"
    );
}


function renderHistoryForCurrentFilter() {

    let visibleHistory =
        adminHistoryItems;


    if (activeHistoryUserId !== null) {

        visibleHistory =
            adminHistoryItems.filter(
                (item) =>
                    String(item.user_id)
                    === String(activeHistoryUserId)
            );
    }


    renderHistory(
        visibleHistory
    );

    updateHistoryFilterUI();
}


function showUserHistory(user) {

    activeHistoryUserId =
        user.id;

    activeHistoryUserEmail =
        user.email
        || `User ${user.id}`;


    renderHistoryForCurrentFilter();

    activateTab(
        "history"
    );


    const historyTabElement =
        document.getElementById(
            "historyTab"
        );

    if (historyTabElement) {

        historyTabElement.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });
    }
}


function clearHistoryUserFilter() {

    activeHistoryUserId = null;
    activeHistoryUserEmail = "";

    renderHistoryForCurrentFilter();
}


function renderUsers(users) {
    const items =
        Array.isArray(users)
            ? users
            : [];

    if (usersCount) {
        usersCount.textContent =
            `${items.length} records`;
    }

    if (!usersTableBody) return;

    usersTableBody.replaceChildren();

    if (items.length === 0) {
        const row =
            document.createElement("tr");

        const cell =
            createCell(
                "No registered users found."
            );

        cell.colSpan = 7;

        row.appendChild(cell);
        usersTableBody.appendChild(row);

        return;
    }

    items.forEach((user) => {
        const row =
            document.createElement("tr");

        row.appendChild(
            createCell(user.id)
        );

        row.appendChild(
            createCell(user.email)
        );

        row.appendChild(
            createStatusCell(
                user.role || "user",
                user.role === "admin"
                    ? "status-admin"
                    : "status-user"
            )
        );

        row.appendChild(
            createStatusCell(
                formatBoolean(
                    user.is_verified
                ),
                user.is_verified
                    ? "status-success"
                    : "status-muted"
            )
        );

        row.appendChild(
            createStatusCell(
                formatBoolean(
                    user.is_active
                ),
                user.is_active
                    ? "status-success"
                    : "status-danger"
            )
        );

        row.appendChild(
            createCell(
                formatDate(
                    user.created_at
                )
            )
        );


        const historyActionCell =
            document.createElement("td");

        const viewHistoryButton =
            document.createElement("button");

        viewHistoryButton.type =
            "button";

        viewHistoryButton.className =
            "btn-secondary";

        viewHistoryButton.textContent =
            "View History";

        viewHistoryButton.addEventListener(
            "click",
            () => {
                showUserHistory(user);
            }
        );

        historyActionCell.appendChild(
            viewHistoryButton
        );

        row.appendChild(
            historyActionCell
        );


        usersTableBody.appendChild(row);
    });
}


function getHistoryUserLabel(item) {
    if (
        item.user_type ===
        "registered"
    ) {
        return (
            item.user_email ||
            `User ${item.user_id ?? "-"}`
        );
    }

    if (item.guest_id) {
        return `Guest: ${item.guest_id}`;
    }

    return "Guest";
}


function renderHistory(history) {

    const items =
        Array.isArray(history)
            ? history
            : [];

    if (historyCount) {
        historyCount.textContent =
            `${items.length} records`;
    }

    if (!historyTableBody) {
        return;
    }

    historyTableBody.replaceChildren();

    if (items.length === 0) {

        const row =
            document.createElement("tr");

        const cell =
            createCell(
                "No solve history found."
            );

        cell.colSpan = 12;

        row.appendChild(cell);
        historyTableBody.appendChild(row);

        return;
    }

    items.forEach((item) => {

        const row =
            document.createElement("tr");

        const selectionText =
            formatSelectionSource(
                item.selection_source
            );

        const requestText =
            formatRequestSource(
                item.request_source
            );

        let statusText = "Unknown";
        let statusClass = "status-muted";

        if (item.success === true) {
            statusText = "Success";
            statusClass = "status-success";
        }

        if (item.success === false) {
            statusText = "Failed";
            statusClass = "status-danger";
        }


        let resultText = "-";

        if (item.success === true) {

            resultText =
                item.result || "-";

        } else if (item.success === false) {

            const errorCode =
                item.error_code
                    ? `[${item.error_code}]`
                    : "";

            const errorMessage =
                item.error_message || "";

            resultText =
                [errorCode, errorMessage]
                    .filter(Boolean)
                    .join(" ");

            if (!resultText) {
                resultText =
                    "The attempt failed.";
            }

        } else {

            resultText =
                item.result
                || item.error_message
                || item.error_code
                || "-";
        }


        const iterationsText =
            item.iterations !== null
            && item.iterations !== undefined
                ? item.iterations
                : "-";


        const raisonSuggestedText =
            item.raison_method
                ? item.raison_method
                : "-";


        const raisonExplanationText =
            item.raison_explanation
                ? item.raison_explanation
                : "-";


        row.appendChild(
            createCell(item.id)
        );

        row.appendChild(
            createCell(
                getHistoryUserLabel(item)
            )
        );

        row.appendChild(
            createCell(
                item.equation
            )
        );

        row.appendChild(
            createCell(
                item.method
            )
        );

        row.appendChild(
            createStatusCell(
                statusText,
                statusClass
            )
        );

        row.appendChild(
            createCell(
                resultText
            )
        );

        row.appendChild(
            createStatusCell(
                selectionText,
                item.selection_source === "raison"
                    ? "status-raison"
                    : item.selection_source === "manual"
                        ? "status-manual"
                        : item.selection_source === "automatic_fallback"
                            ? "status-fallback"
                            : "status-muted"
            )
        );

        row.appendChild(
            createCell(
                requestText
            )
        );

        row.appendChild(
            createCell(
                iterationsText
            )
        );

        row.appendChild(
            createCell(
                raisonSuggestedText
            )
        );

        row.appendChild(
            createCell(
                raisonExplanationText
            )
        );

        row.appendChild(
            createCell(
                formatDate(
                    item.created_at
                )
            )
        );

        historyTableBody.appendChild(row);
    });
}


function renderGuests(guests) {
    const items =
        Array.isArray(guests)
            ? guests
            : [];

    if (guestsCount) {
        guestsCount.textContent =
            `${items.length} records`;
    }

    if (!guestsTableBody) return;

    guestsTableBody.replaceChildren();

    if (items.length === 0) {
        const row =
            document.createElement("tr");

        const cell =
            createCell(
                "No guest usage found."
            );

        cell.colSpan = 5;

        row.appendChild(cell);
        guestsTableBody.appendChild(row);

        return;
    }

    items.forEach((guest) => {
        const row =
            document.createElement("tr");

        row.appendChild(
            createCell(guest.id)
        );

        row.appendChild(
            createCell(guest.guest_id)
        );

        row.appendChild(
            createCell(
                guest.solve_count ?? 0
            )
        );

        row.appendChild(
            createCell(
                formatDate(
                    guest.created_at
                )
            )
        );

        row.appendChild(
            createCell(
                formatDate(
                    guest.last_used_at
                )
            )
        );

        guestsTableBody.appendChild(row);
    });
}


function activateTab(tabName) {
    adminTabs.forEach((button) => {
        const isActive =
            button.dataset.tab ===
            tabName;

        button.classList.toggle(
            "active",
            isActive
        );
    });

    tabPanels.forEach((panel) => {
        const isTarget =
            panel.id ===
            `${tabName}Tab`;

        panel.classList.toggle(
            "hidden",
            !isTarget
        );
    });
}


async function verifyAdminAccess() {
    const accessMode =
        localStorage.getItem(
            "access_mode"
        );

    const token =
        getAccessToken();

    if (
        accessMode !== "registered" ||
        !token
    ) {
        redirectToSolver();
        return null;
    }

    const data =
        await adminFetch(
            "/admin/me"
        );

    if (
        !data ||
        !data.success ||
        !data.is_admin
    ) {
        throw new Error(
            "FORBIDDEN"
        );
    }

    if (adminUserEmail) {
        adminUserEmail.textContent =
            data.email || "Admin";
    }

    return data;
}


async function loadAdminData() {
    hideAdminMessage();
    setLoading(true);

    try {
        await verifyAdminAccess();

        const [
            statsData,
            usersData,
            historyData,
            guestsData
        ] = await Promise.all([
            adminFetch("/admin/stats"),
            adminFetch("/admin/users"),
            adminFetch("/admin/history"),
            adminFetch("/admin/guests")
        ]);

        renderStats(
            statsData?.stats
        );

        renderMethodUsage(
            statsData?.stats?.method_usage,
            statsData?.stats?.method_usage_summary
        );

        renderRaisonMethodSelection(
            statsData?.stats?.raison_method_selection,
            statsData?.stats?.raison_selection_summary
        );

        renderUsers(
            usersData?.users
        );

        adminHistoryItems =
            Array.isArray(
                historyData?.history
            )
                ? historyData.history
                : [];

        renderHistoryForCurrentFilter();

        renderGuests(
            guestsData?.guests
        );

        setLoading(false);

    } catch (error) {
        console.error(
            "Admin dashboard request failed.",
            error
        );

        const errorCode =
            error instanceof Error
                ? error.message
                : "UNKNOWN_ERROR";

        if (
            errorCode === "NO_TOKEN" ||
            errorCode === "UNAUTHORIZED"
        ) {
            clearAuthState();
            redirectToSolver();
            return;
        }

        if (errorCode === "FORBIDDEN") {
            showAdminMessage(
                "You do not have permission to access the Admin Dashboard.",
                "error"
            );
        } else if (
            errorCode === "NETWORK_ERROR"
        ) {
            showAdminMessage(
                "Unable to connect to the server. Please try again later.",
                "error"
            );
        } else {
            showAdminMessage(
                "Unable to load the Admin Dashboard data. Please try again later.",
                "error"
            );
        }

        if (adminLoading) {
            adminLoading.classList.add(
                "hidden"
            );
        }

        if (adminContent) {
            adminContent.classList.add(
                "hidden"
            );
        }
    }
}


function logoutAdmin() {
    clearAuthState();
    redirectToSolver();
}


adminTabs.forEach((button) => {
    button.addEventListener(
        "click",
        () => {
            activateTab(
                button.dataset.tab
            );
        }
    );
});


const clearHistoryFilterButton =
    document.getElementById(
        "clearHistoryFilterButton"
    );

if (clearHistoryFilterButton) {

    clearHistoryFilterButton.addEventListener(
        "click",
        clearHistoryUserFilter
    );
}


if (backToSolverButton) {
    backToSolverButton.addEventListener(
        "click",
        redirectToSolver
    );
}


if (adminHelpButton) {
    adminHelpButton.addEventListener(
        "click",
        redirectToAdminHelp
    );
}


if (adminLogoutButton) {
    adminLogoutButton.addEventListener(
        "click",
        logoutAdmin
    );
}


if (refreshAdminButton) {
    refreshAdminButton.addEventListener(
        "click",
        loadAdminData
    );
}


activateTab("users");
loadAdminData();
