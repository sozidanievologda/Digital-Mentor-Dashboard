let historyChart;

document.addEventListener("DOMContentLoaded", async () => {
    async function updateMetrics() {
        try {
            document.getElementById("pensioners-count").textContent = "Загрузка...";
            document.getElementById("volunteers-count").textContent = "Загрузка...";
            document.getElementById("connection-status").textContent = "Проверка...";

            const metrics = await fetchMetrics();
            document.getElementById("pensioners-count").textContent = metrics.pensioners_count;
            document.getElementById("volunteers-count").textContent = metrics.volunteers_count;
            document.getElementById("last-updated").textContent = new Date(metrics.last_updated).toLocaleString();
            document.getElementById("connection-status").textContent = metrics.status === "active" ? "Активно" : metrics.status;
        } catch (error) {
            console.error("Error updating metrics:", error);
            document.getElementById("pensioners-count").textContent = "Ошибка загрузки";
            document.getElementById("volunteers-count").textContent = "Ошибка загрузки";
            document.getElementById("connection-status").textContent = "Ошибка сервера";
        }
    }

    async function updateHistoryChart(period = "30d") {
        let loadingElement = document.querySelector('.loading');
        if (!loadingElement) {
            loadingElement = document.createElement('div');
            loadingElement.className = 'loading';
            document.getElementById("history-chart").before(loadingElement);
        }

        try {
            loadingElement.textContent = 'Загрузка данных...';
            const history = await fetchHistory(period);
            loadingElement.remove();
            renderHistoryChart(history);
        } catch (error) {
            console.error("Error updating history chart:", error);
            if (loadingElement.parentNode) {
                loadingElement.remove();
            }
            const errorElement = document.createElement('div');
            errorElement.className = 'loading';
            errorElement.textContent = "Ошибка загрузки данных";
            document.getElementById("history-chart").before(errorElement);
        }
    }

    function renderHistoryChart(history) {
        const canvas = document.getElementById("history-chart");
        const ctx = canvas.getContext("2d");

        if (historyChart) {
            historyChart.destroy();
            historyChart = null;
        }

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const sortedPensioners = [...history.pensioners].sort((a, b) => a.date.localeCompare(b.date));
        const sortedVolunteers = [...history.volunteers].sort((a, b) => a.date.localeCompare(b.date));
        const dates = Array.from(new Set([
            ...sortedPensioners.map(item => item.date),
            ...sortedVolunteers.map(item => item.date)
        ])).sort((a, b) => a.localeCompare(b));

        const pensionersMap = Object.fromEntries(sortedPensioners.map(item => [item.date, item.count]));
        const volunteersMap = Object.fromEntries(sortedVolunteers.map(item => [item.date, item.count]));

        const labels = dates;
        const pensionersData = labels.map(date => pensionersMap[date] ?? null);
        const volunteersData = labels.map(date => volunteersMap[date] ?? null);

        console.log("Creating chart with data:", {
            labels: labels.slice(0, 5),
            pensioners: pensionersData.slice(0, 5),
            volunteers: volunteersData.slice(0, 5)
        });

        historyChart = new Chart(ctx, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Пенсионеры",
                        data: pensionersData,
                        borderColor: "rgb(75, 192, 192)",
                        tension: 0.1,
                        fill: false
                    },
                    {
                        label: "Волонтеры",
                        data: volunteersData,
                        borderColor: "rgb(192, 75, 192)",
                        tension: 0.1,
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    tooltip: {
                        mode: "index",
                        intersect: false,
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Дата'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Количество'
                        }
                    }
                }
            }
        });
    }

    document.getElementById("refresh-btn").addEventListener("click", updateMetrics);

    document.querySelectorAll(".period-selector button").forEach(button => {
        button.addEventListener("click", () => {
            updateHistoryChart(button.dataset.period);
        });
    });

    await Promise.allSettled([updateMetrics(), updateHistoryChart()]);
});
