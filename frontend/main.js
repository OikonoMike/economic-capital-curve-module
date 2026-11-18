const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : `http://${window.location.hostname}:8000`;

const SCENARIO_NAMES = {
    0: "Базовый",
    1: "Сдвиг вверх",
    2: "Сдвиг вниз",
    3: "Увеличение наклона",
    4: "Уменьшение наклона",
    5: "Рост коротких",
    6: "Снижение коротких"
};

const dateInput = document.getElementById("dateInput");
const loadBtn = document.getElementById("loadBtn");
const messageEl = document.getElementById("message");
const resultsBody = document.querySelector("#resultsTable tbody");
const historyBody = document.querySelector("#historyTable tbody");
const downloadCsvBtn = document.getElementById("downloadCsv");
const downloadExcelBtn = document.getElementById("downloadExcel");
const scenarioSelect = document.getElementById("scenarioSelect");

let allRows = [];
let chartInstance = null;

function showMessage(text, type = "info") {
    messageEl.textContent = text;
    messageEl.className = "message " + type;
}

function clearMessage() {
    messageEl.className = "message";
    messageEl.textContent = "";
}

function renderTable(rows) {
    resultsBody.innerHTML = "";
    if (rows.length === 0) return;

    rows.forEach(row => {
        const tr = document.createElement("tr");
        const scenName = SCENARIO_NAMES[row.scenario_id] || row.scenario_code;
        tr.innerHTML = `
            <td><strong>${row.scenario_code}</strong><br><small>${scenName}</small></td>
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

function fillScenarioSelect(rows) {
    if (!scenarioSelect) return;
    scenarioSelect.innerHTML = '<option value="all">Все сценарии</option>';
    
    const seen = new Set();
    rows.forEach(r => {
        if (!seen.has(r.scenario_id)) {
            seen.add(r.scenario_id);
            const option = document.createElement("option");
            option.value = r.scenario_id;
            const name = SCENARIO_NAMES[r.scenario_id] || r.scenario_code;
            option.textContent = `${r.scenario_code} — ${name}`;
            scenarioSelect.appendChild(option);
        }
    });
}

function applyScenarioFilter() {
    if (!scenarioSelect) return;
    const val = scenarioSelect.value;
    const filtered = val === "all"
        ? allRows
        : allRows.filter(r => String(r.scenario_id) === val);
    renderTable(filtered);
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
            const name = SCENARIO_NAMES[r.scenario_id] || r.scenario_code;
            scenarios[r.scenario_id] = {
                label: `${r.scenario_code} (${name})`,
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
            allRows = [];
            renderTable([]);
            renderChart([]);
            if (scenarioSelect) scenarioSelect.innerHTML = '<option value="all">Все сценарии</option>';
            return;
        }

        if (!response.ok) {
            throw new Error(`Ошибка сервера: ${response.status}`);
        }

        const data = await response.json();
        allRows = data;
        
        fillScenarioSelect(data);
        applyScenarioFilter();
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

downloadCsvBtn.addEventListener("click", () => {
    if (allRows.length === 0) {
        showMessage("Нет данных для экспорта.", "error");
        return;
    }
    const headers = Object.keys(allRows[0]);
    const rows = allRows.map(r => headers.map(h => r[h]));
    const csv = [headers, ...rows].map(e => e.join(";")).join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `curves_${dateInput.value}.csv`;
    link.click();
});

downloadExcelBtn.addEventListener("click", () => {
    if (allRows.length === 0) {
        showMessage("Нет данных для экспорта.", "error");
        return;
    }
    const worksheet = XLSX.utils.json_to_sheet(allRows);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Curves");
    XLSX.writeFile(workbook, `curves_${dateInput.value}.xlsx`);
});

loadBtn.addEventListener("click", loadCurves);
if (scenarioSelect) {
    scenarioSelect.addEventListener("change", applyScenarioFilter);
}

loadRuns();
