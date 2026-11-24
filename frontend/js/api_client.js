// Same-origin by default (nginx proxies /api in Docker). When the page is
// opened directly from disk, talk to the local backend.
const API_BASE_URL =
    window.DASHBOARD_API_BASE_URL ||
    (window.location.protocol === "file:"
        ? "http://localhost:8000/api"
        : "/api");

const TOKEN_KEY = "dm_access_token";

const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: 90000,
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401) {
            localStorage.removeItem(TOKEN_KEY);
            window.dispatchEvent(new CustomEvent("dm:unauthorized"));
        }
        return Promise.reject(error);
    }
);

function apiErrorMessage(error, fallback) {
    const detail = error && error.response && error.response.data
        ? error.response.data.detail
        : null;
    if (!detail) return fallback;
    return typeof detail === "string" ? detail : fallback;
}

async function login(username, password) {
    const { data } = await api.post("/auth/login", { username, password });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    return data;
}

async function logout() {
    try {
        await api.post("/auth/logout");
    } finally {
        localStorage.removeItem(TOKEN_KEY);
    }
}

async function fetchMe() {
    const { data } = await api.get("/auth/me");
    return data;
}

async function fetchMetrics() {
    const { data } = await api.get("/dashboard/metrics");
    return data;
}

async function fetchHistory(period = "30d", range = null, group = "day") {
    const params = { period, group };
    if (range && range.start && range.end) {
        params.period = "custom";
        params.start = range.start;
        params.end = range.end;
    }
    const { data } = await api.get("/dashboard/history", { params });
    return data;
}

async function refreshData() {
    const { data } = await api.post("/dashboard/refresh");
    return data;
}
