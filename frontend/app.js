const API_BASE =
  window.API_BASE ||
  (window.location.hostname === "localhost" && window.location.port === "5500"
    ? "http://localhost:8000/api"
    : "/api");

const state = {
  congressmen: [],
  congressmanByName: new Map(),
  leyes: [],
  currentBills: [],
  currentLeyId: null,
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
  billRoleFilter: document.getElementById("bill-role-filter"),
  billStatusFilter: document.getElementById("bill-status-filter"),
  billSearchId: document.getElementById("bill-search-id"),
  billSearchTitle: document.getElementById("bill-search-title"),
  billSuggestId: document.getElementById("bill-suggest-id"),
  billSuggestTitle: document.getElementById("bill-suggest-title"),
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

function formatDate(value, fallback) {
  if (!value) return fallback;
  const text = String(value);
  const datePart = text.split("T")[0].split(" ")[0];
  return datePart ? datePart.replace(/-/g, "/") : fallback;
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
          <td>${formatDate(bill.presentation_date, "—")}</td>
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

function populateBillFilters(bills) {
  if (!els.billRoleFilter || !els.billStatusFilter) {
    return;
  }

  const roles = Array.from(new Set(bills.map((b) => b.role_type).filter(Boolean))).sort();
  const statuses = Array.from(new Set(bills.map((b) => b.status).filter(Boolean))).sort();

  els.billRoleFilter.innerHTML = [
    '<option value="">All</option>',
    ...roles.map((role) => `<option value="${role}">${role}</option>`),
  ].join("");

  els.billStatusFilter.innerHTML = [
    '<option value="">All</option>',
    ...statuses.map((status) => `<option value="${status}">${status}</option>`),
  ].join("");
}

function applyBillFilters() {
  const role = els.billRoleFilter?.value || "";
  const status = els.billStatusFilter?.value || "";
  const filtered = state.currentBills.filter((bill) => {
    if (role && bill.role_type !== role) return false;
    if (status && bill.status !== status) return false;
    return true;
  });
  renderBills(filtered);
}

function renderBillSteps(steps) {
  if (!steps || steps.length === 0) {
    els.billSteps.innerHTML = '<div class="empty-state">No steps found for this law.</div>';
    return;
  }

  const showVoteButton = state.currentLeyId === "31751";
  els.billSteps.innerHTML = steps
    .map(
      (step, index) => `
        <div class="timeline-item">
          <div class="timeline-head">
            <div class="timeline-title">${step.step_type || "Step"}</div>
            ${
              showVoteButton && step.step_type === "VOTE"
                ? `<button type="button" class="timeline-action" data-action="view-vote" data-step-index="${index}">ver votacion</button>`
                : ""
            }
          </div>
          <div class="timeline-meta">${formatDate(step.step_date, "Date not available")}</div>
          <div>${step.step_detail || ""}</div>
        </div>
      `
    )
    .join("");
}

function closeBillSuggest() {
  if (els.billSuggestId) {
    els.billSuggestId.classList.remove("open");
    els.billSuggestId.innerHTML = "";
  }
  if (els.billSuggestTitle) {
    els.billSuggestTitle.classList.remove("open");
    els.billSuggestTitle.innerHTML = "";
  }
}

function renderBillSuggestions(query, type) {
  const target = type === "id" ? els.billSuggestId : els.billSuggestTitle;
  if (!target) {
    return;
  }
  const q = query.trim().toLowerCase();
  if (!q) {
    closeBillSuggest();
    return;
  }
  const matches = (state.leyes || [])
    .filter((item) => {
      if (type === "id") {
        return item.id.toLowerCase().includes(q);
      }
      return item.title.toLowerCase().includes(q);
    })
    .slice(0, 8);

  if (matches.length === 0) {
    closeBillSuggest();
    return;
  }

  target.innerHTML = matches
    .map(
      (item, idx) =>
        `<div class="suggestion-item${idx === 0 ? " active" : ""}" data-bill="${item.bill_id}">${item.id} — ${item.title}</div>`
    )
    .join("");
  target.classList.add("open");
}

function selectBillSuggestion(el) {
  const billId = el.dataset.bill;
  const label = el.textContent || "";
  if (els.billSearchId) {
    const split = label.split(" — ");
    els.billSearchId.value = split[0] || label;
  }
  if (els.billSearchTitle) {
    const split = label.split(" — ");
    els.billSearchTitle.value = split.slice(1).join(" — ") || label;
  }
  closeBillSuggest();
  loadBillSteps(billId);
}

function resolveBillFromInputs() {
  const idValue = (els.billSearchId?.value || "").trim().toLowerCase();
  const titleValue = (els.billSearchTitle?.value || "").trim().toLowerCase();
  if (!idValue && !titleValue) {
    return null;
  }
  const match = (state.leyes || []).find((item) => {
    if (idValue && item.id.toLowerCase() === idValue) {
      return true;
    }
    if (titleValue && item.title.toLowerCase() === titleValue) {
      return true;
    }
    return false;
  });
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
    state.currentBills = bills || [];
    populateBillFilters(state.currentBills);
    applyBillFilters();
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

  const selectedLey = (state.leyes || []).find((item) => item.bill_id === billId);
  state.currentLeyId = selectedLey?.id || null;

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

  if (els.billSearchId) {
    els.billSearchId.addEventListener("input", (e) => {
      renderBillSuggestions(e.target.value, "id");
    });
    els.billSearchId.addEventListener("focus", (e) => {
      renderBillSuggestions(e.target.value, "id");
    });
  }

  if (els.billSearchTitle) {
    els.billSearchTitle.addEventListener("input", (e) => {
      renderBillSuggestions(e.target.value, "title");
    });
    els.billSearchTitle.addEventListener("focus", (e) => {
      renderBillSuggestions(e.target.value, "title");
    });
  }

  if (els.billSuggestId) {
    els.billSuggestId.addEventListener("click", (e) => {
      const item = e.target.closest(".suggestion-item");
      if (item) {
        selectBillSuggestion(item);
      }
    });
  }

  if (els.billSuggestTitle) {
    els.billSuggestTitle.addEventListener("click", (e) => {
      const item = e.target.closest(".suggestion-item");
      if (item) {
        selectBillSuggestion(item);
      }
    });
  }

  if (els.billButton) {
    els.billButton.addEventListener("click", () => {
      const billId = resolveBillFromInputs();
      if (billId) {
        loadBillSteps(billId);
      }
    });
  }

  document.addEventListener("click", (e) => {
    const isSearch = e.target === els.billSearchId || e.target === els.billSearchTitle;
    const inSuggest =
      (els.billSuggestId && els.billSuggestId.contains(e.target)) ||
      (els.billSuggestTitle && els.billSuggestTitle.contains(e.target));
    if (!isSearch && !inSuggest) {
      closeBillSuggest();
    }
  });

  if (els.billRoleFilter) {
    els.billRoleFilter.addEventListener("change", () => {
      applyBillFilters();
    });
  }

  if (els.billStatusFilter) {
    els.billStatusFilter.addEventListener("change", () => {
      applyBillFilters();
    });
  }

  if (els.billSteps) {
    els.billSteps.addEventListener("click", (e) => {
      const button = e.target.closest('[data-action="view-vote"]');
      if (!button) {
        return;
      }

      const params = new URLSearchParams();
      if (state.currentLeyId) {
        params.set("ley", state.currentLeyId);
      }
      if (button.dataset.stepIndex) {
        params.set("step", button.dataset.stepIndex);
      }

      window.location.href = `./graphic.html?${params.toString()}`;
    });
  }
}

function init() {
  els.apiBase.textContent = API_BASE;
  bindEvents();
  loadCongressmanList();
  loadLeyesList();
}

init();
