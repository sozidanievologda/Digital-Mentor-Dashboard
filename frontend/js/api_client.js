// Same-origin by default (nginx proxies /api in Docker). When the page is
// opened directly from disk for local development, talk to the local backend.
const API_BASE_URL =
    window.DASHBOARD_API_BASE_URL ||
    (window.location.protocol === "file:"
        ? "http://localhost:8000/api/dashboard"
        : "/api/dashboard");

async function fetchMetrics() {
    try {
        const response = await axios.get(`${API_BASE_URL}/metrics`);
        return response.data;
    } catch (error) {
        console.error("Error fetching metrics:", error);
        throw error;
    }
}

async function fetchHistory(period = "30d") {
    try {
        const response = await axios.get(`${API_BASE_URL}/history?period=${period}`);
        return response.data;
    } catch (error) {
        console.error("Error fetching history:", error);
        throw error;
    }
}
