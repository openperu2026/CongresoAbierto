const API_BASE =
  window.API_BASE ||
  (window.location.hostname === "localhost" && window.location.port === "5500"
    ? "http://localhost:8000/api"
    : "/api");

const state = {
  congressmen: [],
  congressmanByName: new Map(),
  leyes: [],
};

const els = {
  tabs: Array.from(document.querySelectorAll(".tab")),
  panels: Array.from(document.querySelectorAll(".tab-panel")),
  tabJumps: Array.from(document.querySelectorAll("[data-tab-jump]")),
  searchSelect: document.getElementById("congressman-select"),
  searchButton: document.getElementById("congressman-go"),
  details: document.getElementById("congressman-details"),
  photoImg: document.getElementById("photo-img"),
  photoFallback: document.querySelector(".photo-fallback"),
  billsTable: document.getElementById("bills-table"),
  billSearch: document.getElementById("bill-search"),
  billSuggest: document.getElementById("bill-suggest"),
  billButton: document.getElementById("bill-go"),
  billStatus: document.getElementById("bill-status"),
  billSummary: document.getElementById("bill-summary"),
  billSteps: document.getElementById("bill-steps"),
  apiBase: document.getElementById("api-base"),
  apiStatus: document.getElementById("api-status"),
};

function setActiveTab(tabName) {
  els.tabs.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
  els.panels.forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${tabName}`);
  });
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json();
}

function renderDetails(data) {
  if (!data) {
    els.details.innerHTML = '<div class="empty-state">Select a congressman to see details.</div>';
    return;
  }

  const lines = [
    { label: "Party", value: data.party_name || "—" },
    { label: "Bancada", value: data.current_bancada || "—" },
    { label: "Distrito electoral", value: data.dist_electoral || "—" },
    { label: "Votes in election", value: data.votes_in_election ?? "—" },
  ];

  els.details.innerHTML = lines
    .map(
      (item) => `
        <div class="detail-line">
          <div class="detail-label">${item.label}</div>
          <div>${item.value}</div>
        </div>
      `
    )
    .join("");
}

function renderPhoto(url, name) {
  if (!url) {
    els.photoImg.classList.remove("visible");
    els.photoImg.removeAttribute("src");
    els.photoImg.alt = "";
    els.photoFallback.style.display = "block";
    return;
  }

  els.photoImg.alt = `Photo of ${name}`;
  els.photoImg.src = url;
  els.photoImg.onload = () => {
    els.photoImg.classList.add("visible");
    els.photoFallback.style.display = "none";
  };
  els.photoImg.onerror = () => {
    els.photoImg.classList.remove("visible");
    els.photoFallback.style.display = "block";
  };
}

function renderBills(bills) {
  if (!bills || bills.length === 0) {
    els.billsTable.innerHTML = '<div class="empty-state">No bills found for this congressman.</div>';
    return;
  }

  const rows = bills
    .map(
      (bill) => `
        <tr>
          <td>${bill.title || bill.bill_id}</td>
          <td>${bill.role_type}</td>
          <td>${bill.presentation_date || "—"}</td>
          <td>${bill.status || "—"}</td>
        </tr>
      `
    )
    .join("");

  els.billsTable.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Bill</th>
          <th>Role</th>
          <th>Presented</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        ${rows}
      </tbody>
    </table>
  `;
}

function renderBillSteps(steps) {
  if (!steps || steps.length === 0) {
    els.billSteps.innerHTML = '<div class="empty-state">No steps found for this law.</div>';
    return;
  }

  els.billSteps.innerHTML = steps
    .map(
      (step) => `
        <div class="timeline-item">
          <div class="timeline-title">${step.step_type || "Step"}</div>
          <div class="timeline-meta">${step.step_date || "Date not available"}</div>
          <div>${step.step_detail || ""}</div>
        </div>
      `
    )
    .join("");
}

function closeBillSuggest() {
  if (els.billSuggest) {
    els.billSuggest.classList.remove("open");
    els.billSuggest.innerHTML = "";
  }
}

function renderBillSuggestions(query) {
  if (!els.billSuggest) {
    return;
  }
  const q = query.trim().toLowerCase();
  if (!q) {
    closeBillSuggest();
    return;
  }
  const matches = (state.leyes || [])
    .filter(
      (item) =>
        item.id.toLowerCase().includes(q) ||
        item.title.toLowerCase().includes(q)
    )
    .slice(0, 8);

  if (matches.length === 0) {
    closeBillSuggest();
    return;
  }

  els.billSuggest.innerHTML = matches
    .map(
      (item, idx) =>
        `<div class="suggestion-item${idx === 0 ? " active" : ""}" data-bill="${item.bill_id}">${item.id} — ${item.title}</div>`
    )
    .join("");
  els.billSuggest.classList.add("open");
}

function selectBillSuggestion(el) {
  const billId = el.dataset.bill;
  const label = el.textContent || "";
  if (els.billSearch) {
    els.billSearch.value = label;
  }
  closeBillSuggest();
  loadBillSteps(billId);
}

function resolveBillFromInput() {
  const value = (els.billSearch?.value || "").trim().toLowerCase();
  if (!value) {
    return null;
  }
  const match = (state.leyes || []).find(
    (item) =>
      `${item.id} — ${item.title}`.toLowerCase() === value ||
      item.id.toLowerCase() === value
  );
  return match ? match.bill_id : null;
}

async function loadCongressman(id, name) {
  try {
    const [details, bills] = await Promise.all([
      fetchJson(`${API_BASE}/congresistas/${id}`),
      fetchJson(`${API_BASE}/congresistas/${id}/bills`),
    ]);
    renderDetails(details);
    renderPhoto(details.photo_url, name || details.nombre || "");
    renderBills(bills);
  } catch (err) {
    console.error(err);
    els.details.innerHTML = '<div class="empty-state">Failed to load congressman details.</div>';
    els.billsTable.innerHTML = '<div class="empty-state">Failed to load bills.</div>';
  }
}

async function loadBillSteps(billId) {
  if (!billId) {
    return;
  }

  try {
    const steps = await fetchJson(`${API_BASE}/bills/${billId}/steps`);
    renderBillSteps(steps);
    if (els.billStatus) {
      els.billStatus.textContent = "";
    }
  } catch (err) {
    console.error(err);
    els.billSteps.innerHTML = '<div class="empty-state">Failed to load steps.</div>';
    if (els.billStatus) {
      els.billStatus.textContent = "API not reachable. Is backend running on port 8000?";
    }
  }
}

function resolveCongressmanId() {
  const value = els.searchSelect.value;
  if (!value) {
    return null;
  }
  return Number(value);
}

async function loadCongressmanList() {
  try {
    const data = await fetchJson(`${API_BASE}/congresistas`);
    state.congressmen = data;
    state.congressmanByName.clear();

    const options = [
      '<option value="">Select a congressman</option>',
      ...data.map((item) => {
        state.congressmanByName.set(String(item.id), item);
        return `<option value="${item.id}">${item.nombre}</option>`;
      }),
    ].join("");

    els.searchSelect.innerHTML = options;
    if (els.apiStatus) {
      els.apiStatus.textContent = "";
    }
  } catch (err) {
    console.error(err);
    els.searchSelect.innerHTML = '<option value="">Failed to load</option>';
    if (els.apiStatus) {
      els.apiStatus.textContent = "API not reachable. Is backend running on port 8000?";
    }
  }
}

async function loadLeyesList() {
  try {
    const data = await fetchJson(`${API_BASE}/leyes`);
    state.leyes = data;
    if (els.billStatus) {
      els.billStatus.textContent = "";
    }
  } catch (err) {
    console.error(err);
    if (els.billStatus) {
      els.billStatus.textContent = "API not reachable. Is backend running on port 8000?";
    }
    state.leyes = [];
  }
}

function bindEvents() {
  els.tabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      setActiveTab(btn.dataset.tab);
    });
  });

  els.tabJumps.forEach((btn) => {
    btn.addEventListener("click", () => setActiveTab(btn.dataset.tabJump));
  });

  els.searchButton.addEventListener("click", () => {
    const id = resolveCongressmanId();
    if (id) {
      const name = state.congressmanByName.get(String(id))?.nombre;
      loadCongressman(id, name);
    }
  });

  els.searchSelect.addEventListener("change", () => {
    const id = resolveCongressmanId();
    if (id) {
      const name = state.congressmanByName.get(String(id))?.nombre;
      loadCongressman(id, name);
    }
  });

  if (els.billSearch) {
    els.billSearch.addEventListener("input", (e) => {
      renderBillSuggestions(e.target.value);
    });
    els.billSearch.addEventListener("focus", (e) => {
      renderBillSuggestions(e.target.value);
    });
  }

  if (els.billSuggest) {
    els.billSuggest.addEventListener("click", (e) => {
      const item = e.target.closest(".suggestion-item");
      if (item) {
        selectBillSuggestion(item);
      }
    });
  }

  if (els.billButton) {
    els.billButton.addEventListener("click", () => {
      const billId = resolveBillFromInput();
      if (billId) {
        loadBillSteps(billId);
      }
    });
  }

  document.addEventListener("click", (e) => {
    if (els.billSuggest && !els.billSuggest.contains(e.target) && e.target !== els.billSearch) {
      closeBillSuggest();
    }
  });
}

function init() {
  els.apiBase.textContent = API_BASE;
  bindEvents();
  loadCongressmanList();
  loadLeyesList();
}

init();
