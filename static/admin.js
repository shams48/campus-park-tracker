const POLL_INTERVAL_MS = 3000;

const summaryEl = document.getElementById("summary");
const tbodyEl = document.querySelector("#events-table tbody");
const lastUpdateEl = document.getElementById("last-update");

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok && res.status !== 204) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

function fmtTime(iso) {
  const d = new Date(iso);
  return d.toLocaleString();
}

function renderSummary(lots) {
  summaryEl.innerHTML = "";
  for (const lot of lots) {
    const card = document.createElement("div");
    card.className = `summary-card status-${lot.status}`;
    card.innerHTML = `
      <div class="summary-name">${lot.name}</div>
      <div class="summary-count">${lot.occupancy}<small> / ${lot.capacity}</small></div>
      <div class="muted small">${lot.free} free</div>
    `;
    summaryEl.appendChild(card);
  }
}

function renderEvents(events) {
  tbodyEl.innerHTML = "";
  if (events.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="5" class="muted center">No events yet</td>`;
    tbodyEl.appendChild(tr);
    return;
  }
  for (const e of events) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="muted">#${e.id}</td>
      <td>${e.lot_name}</td>
      <td><span class="pill pill-${e.type}">${e.type === "in" ? "Car in" : "Car out"}</span></td>
      <td class="muted">${fmtTime(e.created_at)}</td>
      <td><button class="danger" data-id="${e.id}">Delete</button></td>
    `;
    tbodyEl.appendChild(tr);
  }
  for (const btn of tbodyEl.querySelectorAll("button.danger")) {
    btn.addEventListener("click", onDelete);
  }
}

async function onDelete(e) {
  const btn = e.currentTarget;
  const id = btn.dataset.id;
  if (!confirm(`Delete event #${id}? This will recompute occupancy.`)) return;
  btn.disabled = true;
  try {
    await fetchJson(`/api/events/${id}`, { method: "DELETE" });
    await refresh();
  } catch (err) {
    alert(err.message);
    btn.disabled = false;
  }
}

async function refresh() {
  try {
    const [lots, events] = await Promise.all([
      fetchJson("/api/lots"),
      fetchJson("/api/events?limit=100"),
    ]);
    renderSummary(lots);
    renderEvents(events);
    lastUpdateEl.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    lastUpdateEl.textContent = `Connection error: ${err.message}`;
  }
}

refresh();
setInterval(refresh, POLL_INTERVAL_MS);
