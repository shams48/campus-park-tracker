const POLL_INTERVAL_MS = 2000;
const HISTORY_MINUTES = 60;
const LOT_COLORS = ["#38bdf8", "#a78bfa", "#22c55e", "#f59e0b", "#ef4444"];

const lotsEl = document.getElementById("lots");
const lastUpdateEl = document.getElementById("last-update");
const chartCanvas = document.getElementById("history-chart");
let chart = null;

async function fetchLots() {
  const res = await fetch("/api/lots");
  if (!res.ok) throw new Error(`GET /api/lots failed: ${res.status}`);
  return res.json();
}

async function postEvent(lotId, type) {
  const res = await fetch("/api/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lot_id: lotId, type }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

function statusClass(status) {
  return `status-${status}`;
}

function renderLots(lots) {
  lotsEl.innerHTML = "";
  for (const lot of lots) {
    const pct = Math.min(100, (lot.occupancy / lot.capacity) * 100);
    const inDisabled = lot.occupancy >= lot.capacity ? "disabled" : "";
    const outDisabled = lot.occupancy <= 0 ? "disabled" : "";

    const card = document.createElement("div");
    card.className = `lot-card ${statusClass(lot.status)}`;
    card.innerHTML = `
      <h2>${lot.name}</h2>
      <div class="count">${lot.free}<small> / ${lot.capacity} free</small></div>
      <div class="bar ${statusClass(lot.status)}"><div style="width:${pct}%"></div></div>
      <div class="muted">${lot.occupancy} cars parked</div>
      <div class="actions">
        <button data-lot="${lot.id}" data-type="in"  ${inDisabled}>Car in</button>
        <button data-lot="${lot.id}" data-type="out" ${outDisabled}>Car out</button>
      </div>
    `;
    lotsEl.appendChild(card);
  }

  for (const btn of lotsEl.querySelectorAll("button")) {
    btn.addEventListener("click", onEventClick);
  }
}

async function onEventClick(e) {
  const btn = e.currentTarget;
  const lotId = Number(btn.dataset.lot);
  const type = btn.dataset.type;
  btn.disabled = true;
  try {
    await postEvent(lotId, type);
    await refresh();
  } catch (err) {
    showToast(err.message, true);
  } finally {
    btn.disabled = false;
  }
}

async function fetchHistory(lotId) {
  const res = await fetch(`/api/lots/${lotId}/history?minutes=${HISTORY_MINUTES}`);
  if (!res.ok) throw new Error(`history fetch failed: ${res.status}`);
  return res.json();
}

function ensureChart() {
  if (chart) return chart;
  chart = new Chart(chartCanvas.getContext("2d"), {
    type: "line",
    data: { datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      parsing: false,
      interaction: { mode: "nearest", intersect: false },
      scales: {
        x: {
          type: "time",
          time: { unit: "minute", displayFormats: { minute: "HH:mm" } },
          ticks: { color: "#94a3b8" },
          grid: { color: "rgba(148,163,184,0.1)" },
        },
        y: {
          beginAtZero: true,
          ticks: { color: "#94a3b8", precision: 0 },
          grid: { color: "rgba(148,163,184,0.1)" },
          title: { display: true, text: "Cars parked", color: "#94a3b8" },
        },
      },
      plugins: {
        legend: { labels: { color: "#e2e8f0" } },
        tooltip: { mode: "nearest", intersect: false },
      },
    },
  });
  return chart;
}

async function refreshChart(lots) {
  const histories = await Promise.all(lots.map((l) => fetchHistory(l.id)));
  const c = ensureChart();
  c.data.datasets = histories.map((h, i) => ({
    label: h.lot_name,
    data: h.points.map((p) => ({ x: new Date(p.t).valueOf(), y: p.occupancy })),
    borderColor: LOT_COLORS[i % LOT_COLORS.length],
    backgroundColor: LOT_COLORS[i % LOT_COLORS.length] + "33",
    stepped: true,
    tension: 0,
    pointRadius: 0,
    fill: false,
  }));
  c.update();
}

async function refresh() {
  try {
    const lots = await fetchLots();
    renderLots(lots);
    await refreshChart(lots);
    lastUpdateEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    lastUpdateEl.textContent = `Connection error: ${err.message}`;
  }
}

let toastTimer = null;
function showToast(message, isError = false) {
  let el = document.querySelector(".toast");
  if (!el) {
    el = document.createElement("div");
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2500);
}

refresh();
setInterval(refresh, POLL_INTERVAL_MS);
