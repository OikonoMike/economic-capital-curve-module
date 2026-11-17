const API_BASE = "http://localhost:8000";

const dateInput = document.getElementById("dateInput");
const loadBtn = document.getElementById("loadBtn");
const messageEl = document.getElementById("message");
const resultsBody = document.querySelector("#resultsTable tbody");
const historyBody = document.querySelector("#historyTable tbody");
const downloadCsvBtn = document.getElementById("downloadCsv");
const downloadExcelBtn = document.getElementById("downloadExcel");

let currentData = [];
let chartInstance = null;

function showMessage(text, type = "info") {
    messageEl.textContent = text;
    messageEl.className = "message " + type;
}

function clearMessage() {
    messageEl.className = "message";
    messageEl.textContent = "";
}

async function loadCurves() {
    clearMessage();
    const date = dateInput.value;
    if (!date) {
        showMessage("Пожалуйста, выберите дату.", "error");
        return;
    }

    showMessage("Загрузка данных...", "info");

    try {
        const response = await fetch(`${API_BASE}/curves?date=${date}`);

        if (response.status === 404) {
            showMessage(`Кривые за ${date} не найдены.`, "error");
            currentData = [];
            renderTable([]);
            renderChart([]);
            return;
        }

        if (!response.ok) {
            throw new Error(`Ошибка сервера: ${response.status}`);
        }

        const data = await response.json();
        currentData = data;
        renderTable(data);
        renderChart(data);
        showMessage(`Загружено ${data.length} строк за ${date}.`, "info");
    } catch (err) {
        console.error(err);
        showMessage(
            "Сервис недоступен. Проверьте, запущен ли бэкенд и настроен ли CORS.",
            "error"
        );
    }
}

function renderTable(rows) {
    resultsBody.innerHTML = "";
    if (rows.length === 0) return;

    const baseRows = rows.filter(r => r.scenario_id === 0);

    baseRows.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${row.scenario_code}</td>
            <td>${row.tenor_label}</td>
            <td>${row.tenor_years}</td>
            <td>${row.rate_pct}</td>
            <td>${row.discount_factor}</td>
            <td>${row.method}</td>
            <td>${row.is_interpolated ? "да" : "—"}</td>
            <td>${row.is_extrapolated ? "да" : "—"}</td>
            <td>${row.calculated_at}</td>
            <td>${row.run_type}</td>
        `;
        resultsBody.appendChild(tr);
    });
}

async function loadRuns() {
    try {
        const response = await fetch(`${API_BASE}/runs`);
        if (!response.ok) throw new Error();
        const data = await response.json();
        historyBody.innerHTML = "";
        data.forEach(row => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${row.report_date}</td>
                <td>${row.run_type}</td>
                <td>${row.status}</td>
                <td>${row.started_at}</td>
                <td>${row.error_message || "—"}</td>
            `;
            historyBody.appendChild(tr);
        });
    } catch (err) {
        console.warn("Не удалось загрузить историю запусков", err);
    }
}

function renderChart(rows) {
    const ctx = document.getElementById("curveChart").getContext("2d");
    if (chartInstance) chartInstance.destroy();
    if (rows.length === 0) return;

    const labels = [];
    const seen = new Set();
    rows.forEach(r => {
        if (!seen.has(r.tenor_label)) {
            seen.add(r.tenor_label);
            labels.push(r.tenor_label);
        }
    });

    const scenarios = {};
    rows.forEach(r => {
        if (!scenarios[r.scenario_id]) {
            scenarios[r.scenario_id] = {
                label: r.scenario_code,
                data: [],
                borderColor: r.scenario_id === 0 ? "blue" : `hsl(${r.scenario_id * 50}, 70%, 50%)`,
                fill: false,
            };
        }
        scenarios[r.scenario_id].data.push(r.rate_pct);
    });

    chartInstance = new Chart(ctx, {
        type: "line",
        data: { labels, datasets: Object.values(scenarios) },
        options: {
            responsive: false,
            plugins: { legend: { position: "top" } },
            scales: {
                y: { title: { display: true, text: "Ставка, %" } },
                x: { title: { display: true, text: "Тенор" } },
            },
        },
    });
}

downloadCsvBtn.addEventListener("click", () => {
    if (currentData.length === 0) {
        showMessage("Нет данных для экспорта.", "error");
        return;
    }
    const headers = Object.keys(currentData[0]);
    const rows = currentData.map(r => headers.map(h => r[h]));
    const csv = [headers, ...rows].map(e => e.join(";")).join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `curves_${dateInput.value}.csv`;
    link.click();
});

downloadExcelBtn.addEventListener("click", () => {
    if (currentData.length === 0) {
        showMessage("Нет данных для экспорта.", "error");
        return;
    }
    const worksheet = XLSX.utils.json_to_sheet(currentData);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Curves");
    XLSX.writeFile(workbook, `curves_${dateInput.value}.xlsx`);
});

loadBtn.addEventListener("click", loadCurves);

loadRuns();
