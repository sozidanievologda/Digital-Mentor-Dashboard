let historyChart = null;
let currentHistory = null;
let currentPeriod = "30d";
let currentRange = null;
let currentMode = "cumulative";
let autoRefreshTimer = null;

const AUTO_REFRESH_MS = 5 * 60 * 1000;

document.addEventListener("DOMContentLoaded", () => {
    bindEvents();
    boot();
});

async function boot() {
    if (!localStorage.getItem(TOKEN_KEY)) {
        showLogin();
        return;
    }
    try {
        const me = await fetchMe();
        showDashboard(me.username);
        await loadAll();
    } catch (error) {
        showLogin();
    }
}

function bindEvents() {
    document.getElementById("login-form").addEventListener("submit", onLogin);
    document.getElementById("logout-btn").addEventListener("click", onLogout);
    document.getElementById("refresh-btn").addEventListener("click", onRefresh);
    document.getElementById("export-btn").addEventListener("click", exportCsv);
    document.getElementById("apply-range").addEventListener("click", onApplyRange);

    document.querySelectorAll(".period-selector button").forEach((button) => {
        button.addEventListener("click", () => {
            currentPeriod = button.dataset.period;
            currentRange = null;
            document.getElementById("range-start").value = "";
            document.getElementById("range-end").value = "";
            setActivePeriod(button);
            loadHistory();
        });
    });

    document.querySelectorAll(".mode-selector button").forEach((button) => {
        button.addEventListener("click", () => {
            currentMode = button.dataset.mode;
            document.querySelectorAll(".mode-selector button").forEach((item) => {
                item.classList.toggle("active", item === button);
            });

            // Short ranges produce a single bar; switch to a useful default.
            if (currentMode === "monthly" && !currentRange
                && (currentPeriod === "7d" || currentPeriod === "30d")) {
                currentPeriod = "12m";
                setActivePeriod(
                    document.querySelector('.period-selector button[data-period="12m"]')
                );
            }
            loadHistory();
        });
    });

    window.addEventListener("dm:unauthorized", () => {
        showLogin("Сессия истекла, войдите заново");
    });

    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible" && localStorage.getItem(TOKEN_KEY)) {
            loadAll();
        }
    });
}

function showLogin(message) {
    clearInterval(autoRefreshTimer);
    document.getElementById("dashboard-view").hidden = true;
    document.getElementById("login-view").hidden = false;
    document.getElementById("login-password").value = "";
    const errorBox = document.getElementById("login-error");
    if (message) {
        errorBox.textContent = message;
        errorBox.hidden = false;
    } else {
        errorBox.hidden = true;
    }
}

function showDashboard(username) {
    document.getElementById("login-view").hidden = true;
    document.getElementById("dashboard-view").hidden = false;
    document.getElementById("current-user").textContent = username;

    clearInterval(autoRefreshTimer);
    autoRefreshTimer = setInterval(() => {
        if (document.visibilityState === "visible") {
            loadAll();
        }
    }, AUTO_REFRESH_MS);
}

async function onLogin(event) {
    event.preventDefault();
    const button = document.getElementById("login-submit");
    const errorBox = document.getElementById("login-error");
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;

    errorBox.hidden = true;
    button.disabled = true;
    button.textContent = "Вход...";

    try {
        await login(username, password);
        const me = await fetchMe();
        showDashboard(me.username);
        await loadAll();
    } catch (error) {
        errorBox.textContent = apiErrorMessage(error, "Не удалось войти");
        errorBox.hidden = false;
    } finally {
        button.disabled = false;
        button.textContent = "Войти";
    }
}

async function onLogout() {
    try {
        await logout();
    } catch (error) {
        // Token is removed locally even if the request fails.
    }
    showLogin();
}

async function loadAll() {
    const [metricsResult, historyResult] = await Promise.allSettled([
        fetchMetrics(),
        fetchHistory(currentPeriod, currentRange, historyGroup()),
    ]);

    if (metricsResult.status === "fulfilled") {
        renderMetrics(metricsResult.value);
    } else {
        renderMetricsError(metricsResult.reason);
    }

    if (historyResult.status === "fulfilled") {
        renderHistory(historyResult.value);
    } else {
        renderHistoryError(historyResult.reason);
    }
}

function formatDateTime(value) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleString("ru-RU");
}

function formatNumber(value) {
    if (value === null || value === undefined) return "—";
    return Number(value).toLocaleString("ru-RU");
}

function renderMetrics(metrics) {
    document.getElementById("pensioners-count").textContent = formatNumber(metrics.pensioners_count);
    document.getElementById("total-users").textContent = formatNumber(metrics.total_users);
    document.getElementById("volunteers-count").textContent = formatNumber(metrics.volunteers_count);
    document.getElementById("last-updated").textContent = formatDateTime(
        metrics.last_success_at || metrics.last_updated
    );

    const state = metrics.data_status || (metrics.status === "active" ? "live" : "stale");
    setStatus(state, metrics.error);
}

function renderMetricsError(error) {
    document.getElementById("pensioners-count").textContent = "—";
    document.getElementById("total-users").textContent = "—";
    document.getElementById("volunteers-count").textContent = "—";
    const detail = apiErrorMessage(error, "Нет данных");
    setStatus("error", detail);
}

function setStatus(state, detail) {
    const dot = document.getElementById("status-dot");
    const label = document.getElementById("connection-status");
    dot.className = `dot dot-${state}`;

    if (state === "live") {
        label.textContent = "Соединение с CRM активно";
    } else if (state === "stale") {
        label.textContent = "Данные устарели: нет свежей синхронизации с CRM";
    } else {
        label.textContent = "Нет связи с CRM";
    }
    label.title = detail || "";
}

function setActivePeriod(activeButton) {
    document.querySelectorAll(".period-selector button").forEach((button) => {
        button.classList.toggle("active", button === activeButton);
    });
}

async function loadHistory() {
    try {
        const history = await fetchHistory(currentPeriod, currentRange, historyGroup());
        renderHistory(history);
    } catch (error) {
        renderHistoryError(error);
    }
}

function historyGroup() {
    return currentMode === "monthly" ? "month" : "day";
}

function formatMonthLabel(value) {
    const [year, month] = value.split("-").map(Number);
    if (!year || !month) return value;
    return new Date(year, month - 1, 1).toLocaleDateString("ru-RU", {
        month: "short",
        year: "numeric",
    });
}

function renderHistory(history) {
    currentHistory = history;
    const errorBox = document.getElementById("chart-error");
    errorBox.hidden = true;

    const isMonthly = history.group === "month";
    const note = document.getElementById("chart-note");
    if (history.approximate) {
        note.textContent = isMonthly
            ? "Столбцы показывают новых участников за месяц. История до первого сбора данных рассчитана по датам создания карточек в CRM и является оценкой."
            : "Часть истории до первого сбора данных рассчитана по датам создания карточек в CRM и является оценкой.";
        note.hidden = false;
    } else {
        note.hidden = true;
    }

    const points = history.pensioners || [];
    const labels = isMonthly
        ? points.map((point) => formatMonthLabel(point.date))
        : points.map((point) => point.date);
    const values = points.map((point) => point.count);

    const canvas = document.getElementById("history-chart");
    const context = canvas.getContext("2d");

    if (historyChart) {
        historyChart.destroy();
        historyChart = null;
    }

    const dataset = isMonthly
        ? {
            label: "Пришло за месяц",
            data: values,
            backgroundColor: "rgba(75, 132, 192, 0.65)",
            borderColor: "rgb(75, 132, 192)",
            borderWidth: 1,
            borderRadius: 4,
            maxBarThickness: 56,
        }
        : {
            label: "Пенсионеры",
            data: values,
            borderColor: "rgb(75, 132, 192)",
            backgroundColor: "rgba(75, 132, 192, 0.15)",
            fill: true,
            tension: 0.2,
            pointRadius: 2,
            spanGaps: true,
        };

    historyChart = new Chart(context, {
        type: isMonthly ? "bar" : "line",
        data: {
            labels,
            datasets: [dataset],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (item) => `${isMonthly ? "Пришло" : "Пенсионеры"}: ${formatNumber(item.parsed.y)}`,
                    },
                },
            },
            scales: {
                x: {
                    title: { display: true, text: isMonthly ? "Месяц" : "Дата" },
                    ticks: { maxTicksLimit: 12, maxRotation: 0, autoSkip: true },
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: isMonthly ? "Человек за месяц" : "Количество" },
                    ticks: {
                        callback: (value) => Number(value).toLocaleString("ru-RU"),
                    },
                },
            },
        },
    });
}

function renderHistoryError(error) {
    const errorBox = document.getElementById("chart-error");
    errorBox.textContent = apiErrorMessage(error, "Не удалось загрузить историю");
    errorBox.hidden = false;
}

async function onRefresh() {
    const button = document.getElementById("refresh-btn");
    button.disabled = true;
    button.textContent = "Обновление...";

    try {
        const metrics = await refreshData();
        renderMetrics(metrics);
        await loadHistory();
    } catch (error) {
        const errorBox = document.getElementById("chart-error");
        errorBox.textContent = apiErrorMessage(error, "Не удалось обновить данные");
        errorBox.hidden = false;
    } finally {
        button.disabled = false;
        button.textContent = "Обновить";
    }
}

function onApplyRange() {
    const start = document.getElementById("range-start").value;
    const end = document.getElementById("range-end").value;
    const errorBox = document.getElementById("chart-error");

    if (!start || !end) {
        errorBox.textContent = "Выберите обе даты интервала";
        errorBox.hidden = false;
        return;
    }
    if (start > end) {
        errorBox.textContent = "Дата начала не может быть позже даты окончания";
        errorBox.hidden = false;
        return;
    }

    currentRange = { start, end };
    currentPeriod = "custom";
    setActivePeriod(null);
    loadHistory();
}

function exportCsv() {
    const errorBox = document.getElementById("chart-error");
    if (!currentHistory || !currentHistory.pensioners || !currentHistory.pensioners.length) {
        errorBox.textContent = "Нет данных для экспорта";
        errorBox.hidden = false;
        return;
    }

    const volunteers = currentHistory.volunteers || [];
    const isMonthly = currentHistory.group === "month";
    const rows = [
        isMonthly
            ? ["month", "new_participants", "volunteers"]
            : ["date", "pensioners", "volunteers"],
    ];
    currentHistory.pensioners.forEach((point, index) => {
        rows.push([
            point.date,
            point.count === null ? "" : point.count,
            volunteers[index] && volunteers[index].count !== null ? volunteers[index].count : "",
        ]);
    });

    const csv = "\uFEFF" + rows.map((row) => row.join(";")).join("\r\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `digital-mentor-${isMonthly ? "monthly-" : ""}${currentHistory.start}_${currentHistory.end}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}
