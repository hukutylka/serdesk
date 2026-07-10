const API = "";

const state = {
  token: localStorage.getItem("token") || null,
  user: JSON.parse(localStorage.getItem("user") || "null"),
  categories: [],
  statuses: [],
  specialists: [],
  filters: { status_id: "", category_id: "", specialist_id: "", urgency: "", search: "" },
  sort: { sort_by: "created_at", sort_desc: true },
  currentRequestId: null,
  refreshTimer: null,
};

const urgencyClass = { low: "low", medium: "medium", high: "high", critical: "critical" };
const statusBadgeClass = { "Новая": "new", "В работе": "progress", "Завершена": "done" };

// ---------- API helper ----------

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;

  const response = await fetch(`${API}${path}`, { ...options, headers });

  if (response.status === 401) {
    logout();
    throw new Error("Требуется повторный вход");
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Ошибка запроса");
  }
  return data;
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function showError(elId, message) {
  const box = document.getElementById(elId);
  box.textContent = message;
  box.hidden = false;
  setTimeout(() => { box.hidden = true; }, 5000);
}

// ---------- Auth ----------

function saveSession(token, user) {
  state.token = token;
  state.user = user;
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
}

function logout() {
  state.token = null;
  state.user = null;
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  if (state.refreshTimer) clearInterval(state.refreshTimer);
  document.getElementById("app-screen").classList.add("hidden");
  document.getElementById("login-screen").classList.remove("hidden");
}

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  try {
    const result = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ login: form.login.value.trim(), password: form.password.value }),
    });
    saveSession(result.access_token, result.user);
    await enterApp();
  } catch (error) {
    showError("login-alert", error.message);
  }
});

document.getElementById("logout-btn").addEventListener("click", logout);

// ---------- Navigation ----------

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const view = btn.dataset.view;
    document.getElementById("view-requests").classList.toggle("hidden", view !== "requests");
    document.getElementById("view-settings").classList.toggle("hidden", view !== "settings");
    if (view === "settings") loadSettings();
  });
});

// ---------- Bootstrap after login ----------

async function enterApp() {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app-screen").classList.remove("hidden");
  document.getElementById("current-user-name").textContent = state.user.full_name;
  document.getElementById("current-user-role").textContent =
    state.user.role === "admin" ? "Администратор" : "Специалист";
  document.getElementById("nav-settings").hidden = state.user.role !== "admin";

  await Promise.all([loadCategories(), loadStatuses(), loadSpecialists()]);
  buildStatusTabs();
  await Promise.all([loadRequests(), loadStats()]);

  if (state.refreshTimer) clearInterval(state.refreshTimer);
  state.refreshTimer = setInterval(() => {
    if (document.getElementById("request-modal").classList.contains("hidden")) {
      loadRequests();
      loadStats();
    }
  }, 20000);
}

async function loadCategories() {
  state.categories = await api("/api/categories");
  const select = document.getElementById("filter-category");
  select.innerHTML =
    `<option value="">Все категории</option>` +
    state.categories.map((c) => `<option value="${c.id}">${c.name}</option>`).join("");
}

async function loadStatuses() {
  state.statuses = await api("/api/statuses");
}

async function loadSpecialists() {
  state.specialists = await api("/api/specialists");
  const select = document.getElementById("filter-specialist");
  select.innerHTML =
    `<option value="">Все специалисты</option>` +
    state.specialists.map((s) => `<option value="${s.id}">${s.full_name}</option>`).join("");
}

function buildStatusTabs() {
  const wrap = document.getElementById("status-tabs");
  const extra = state.statuses
    .map((s) => `<button type="button" class="tab" data-status="${s.id}">${s.name}</button>`)
    .join("");
  wrap.innerHTML = `<button type="button" class="tab active" data-status="">Все</button>` + extra;

  wrap.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      wrap.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      state.filters.status_id = tab.dataset.status;
      loadRequests();
    });
  });
}

// ---------- Requests list ----------

let searchTimer;
document.getElementById("search-input").addEventListener("input", (event) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.filters.search = event.target.value.trim();
    loadRequests();
  }, 300);
});

["filter-category", "filter-specialist", "filter-urgency"].forEach((id) => {
  document.getElementById(id).addEventListener("change", (event) => {
    const key = { "filter-category": "category_id", "filter-specialist": "specialist_id", "filter-urgency": "urgency" }[id];
    state.filters[key] = event.target.value;
    loadRequests();
  });
});

document.getElementById("filter-sort").addEventListener("change", (event) => {
  const [sortBy, sortDesc] = event.target.value.split(":");
  state.sort.sort_by = sortBy;
  state.sort.sort_desc = sortDesc === "true";
  loadRequests();
});

function buildQuery() {
  const params = new URLSearchParams();
  const { status_id, category_id, specialist_id, urgency, search } = state.filters;
  if (search) params.set("search", search);
  if (status_id) params.set("status_id", status_id);
  if (category_id) params.set("category_id", category_id);
  if (specialist_id) params.set("specialist_id", specialist_id);
  if (urgency) params.set("urgency", urgency);
  params.set("sort_by", state.sort.sort_by);
  params.set("sort_desc", state.sort.sort_desc);
  return params.toString();
}

async function loadRequests() {
  const tbody = document.getElementById("requests-tbody");
  try {
    const items = await api(`/api/requests?${buildQuery()}`);
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="8">Заявок не найдено</td></tr>`;
      return;
    }
    tbody.innerHTML = items
      .map((r) => {
        const statusCls = statusBadgeClass[r.status_name] || "";
        const urgCls = urgencyClass[r.urgency] || "";
        return `
          <tr data-id="${r.id}" style="cursor:pointer;">
            <td>#${r.id}</td>
            <td>${fmtDate(r.created_at)}</td>
            <td>${r.client_name}</td>
            <td>${r.cabinet}</td>
            <td>${r.category_name}</td>
            <td><span class="badge ${urgCls}">${r.urgency_label}</span></td>
            <td><span class="badge ${statusCls}">${r.status_name}</span></td>
            <td>${r.specialist ? r.specialist.full_name : "—"}</td>
          </tr>`;
      })
      .join("");
    tbody.querySelectorAll("tr").forEach((row) => {
      row.addEventListener("click", () => openRequestModal(Number(row.dataset.id)));
    });
  } catch (error) {
    showError("requests-alert", error.message);
  }
}

async function loadStats() {
  try {
    const stats = await api("/api/stats");
    document.getElementById("stat-new").textContent = stats.new_count;
    document.getElementById("stat-progress").textContent = stats.in_progress_count;
    document.getElementById("stat-done").textContent = stats.completed_count;
    document.getElementById("stat-avg").textContent =
      stats.avg_processing_hours != null ? stats.avg_processing_hours : "—";
  } catch {
    /* тихо игнорируем ошибку статистики, чтобы не мешать основному списку */
  }
}

// ---------- Request modal ----------

const modal = document.getElementById("request-modal");
document.getElementById("modal-close").addEventListener("click", closeModal);
modal.addEventListener("click", (event) => {
  if (event.target === modal) closeModal();
});

function closeModal() {
  modal.classList.add("hidden");
  state.currentRequestId = null;
}

async function openRequestModal(id) {
  state.currentRequestId = id;
  document.getElementById("modal-title").textContent = `Заявка №${id}`;
  document.getElementById("modal-body").innerHTML = "Загрузка…";
  modal.classList.remove("hidden");
  await renderRequestDetail(id);
}

async function renderRequestDetail(id) {
  const req = await api(`/api/requests/${id}`);
  const body = document.getElementById("modal-body");

  const statusOptions = state.statuses
    .map((s) => `<option value="${s.id}" ${s.id === req.status_id ? "selected" : ""}>${s.name}</option>`)
    .join("");
  const specialistOptions =
    `<option value="">Не назначен</option>` +
    state.specialists
      .map((s) => `<option value="${s.id}" ${req.specialist && s.id === req.specialist.id ? "selected" : ""}>${s.full_name}</option>`)
      .join("");

  body.innerHTML = `
    <div>
      <p><strong>Заявитель:</strong> ${req.client.full_name}</p>
      <p><strong>Кабинет:</strong> ${req.cabinet}</p>
      <p><strong>Отдел:</strong>
        <span id="department-view">${req.client.department || "не указан"}</span>
      </p>
      <div style="display:flex; gap:8px; margin-bottom:12px;">
        <input id="department-input" placeholder="Указать отдел" value="${req.client.department || ""}" style="flex:1;">
        <button type="button" class="secondary" id="save-department-btn">Сохранить</button>
      </div>
      <p><strong>Категория:</strong> ${req.category_name}</p>
      <p><strong>Срочность:</strong> <span class="badge ${urgencyClass[req.urgency]}">${req.urgency_label}</span></p>
      <p><strong>Описание:</strong><br>${req.description}</p>
      <p><strong>Удобное время визита:</strong> ${req.preferred_visit_time || "не указано"}</p>
      <p><strong>Создана:</strong> ${fmtDate(req.created_at)}</p>
      <p><strong>Принята в работу:</strong> ${fmtDate(req.accepted_at)}</p>
      <p><strong>Завершена:</strong> ${fmtDate(req.completed_at)}</p>

      <h4>История изменений</h4>
      <div class="history-list">
        ${
          req.history.length
            ? req.history
                .map(
                  (h) => `
                <div class="history-item">
                  <div>${fmtDate(h.changed_at)} — ${h.changed_by_name || "система"}</div>
                  <div>${h.old_status_name ? `${h.old_status_name} → ` : ""}${h.new_status_name}</div>
                  ${h.comment ? `<div style="color:var(--muted);">${h.comment}</div>` : ""}
                </div>`
                )
                .join("")
            : `<p style="color:var(--muted);">Изменений пока нет.</p>`
        }
      </div>
    </div>

    <div>
      ${req.status_name === "Новая" ? `<button type="button" id="accept-btn" style="width:100%; margin-bottom:12px;">Принять в работу</button>` : ""}

      <label for="status-select">Статус</label>
      <select id="status-select">${statusOptions}</select>

      <label for="specialist-select" style="margin-top:12px;">Специалист</label>
      <select id="specialist-select">${specialistOptions}</select>

      <label for="comment-input" style="margin-top:12px;">Комментарий специалиста</label>
      <textarea id="comment-input" placeholder="Что было сделано...">${req.specialist_comment || ""}</textarea>

      <button type="button" id="save-changes-btn" style="width:100%; margin-top:12px;">Сохранить изменения</button>
    </div>
  `;

  const acceptBtn = document.getElementById("accept-btn");
  if (acceptBtn) {
    acceptBtn.addEventListener("click", async () => {
      try {
        await api(`/api/requests/${id}/accept`, { method: "POST" });
        await renderRequestDetail(id);
        await loadRequests();
        await loadStats();
      } catch (error) {
        alert(error.message);
      }
    });
  }

  document.getElementById("save-department-btn").addEventListener("click", async () => {
    const value = document.getElementById("department-input").value.trim();
    try {
      await api(`/api/requests/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ client_department: value }),
      });
      await renderRequestDetail(id);
    } catch (error) {
      alert(error.message);
    }
  });

  document.getElementById("save-changes-btn").addEventListener("click", async () => {
    const payload = {
      status_id: Number(document.getElementById("status-select").value),
      specialist_id: document.getElementById("specialist-select").value
        ? Number(document.getElementById("specialist-select").value)
        : null,
      specialist_comment: document.getElementById("comment-input").value.trim(),
    };
    try {
      await api(`/api/requests/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      await renderRequestDetail(id);
      await loadRequests();
      await loadStats();
    } catch (error) {
      alert(error.message);
    }
  });
}

// ---------- Settings (admin only) ----------

async function loadSettings() {
  if (state.user.role !== "admin") return;
  await Promise.all([loadAdminCategories(), loadAdminStatuses(), loadAdminUsers()]);
}

async function loadAdminCategories() {
  const categories = await api("/api/admin/categories");
  const list = document.getElementById("categories-list");
  list.innerHTML = categories
    .map(
      (c) => `
      <div style="display:flex; justify-content:space-between; align-items:center; padding:8px; border:1px solid var(--border); border-radius:8px;">
        <span style="${c.is_active ? "" : "text-decoration:line-through;color:var(--muted);"}">${c.name}</span>
        <button type="button" class="secondary" data-id="${c.id}" data-active="${c.is_active}" data-kind="category">
          ${c.is_active ? "Скрыть" : "Включить"}
        </button>
      </div>`
    )
    .join("");
  list.querySelectorAll("button").forEach((btn) => btn.addEventListener("click", toggleActive));
}

async function loadAdminStatuses() {
  const statuses = await api("/api/admin/statuses");
  const list = document.getElementById("statuses-list");
  list.innerHTML = statuses
    .map(
      (s) => `
      <div style="display:flex; justify-content:space-between; align-items:center; padding:8px; border:1px solid var(--border); border-radius:8px;">
        <span style="${s.is_active ? "" : "text-decoration:line-through;color:var(--muted);"}">${s.name}</span>
        <button type="button" class="secondary" data-id="${s.id}" data-active="${s.is_active}" data-kind="status">
          ${s.is_active ? "Скрыть" : "Включить"}
        </button>
      </div>`
    )
    .join("");
  list.querySelectorAll("button").forEach((btn) => btn.addEventListener("click", toggleActive));
}

async function toggleActive(event) {
  const { id, active, kind } = event.target.dataset;
  const path = kind === "category" ? `/api/admin/categories/${id}` : `/api/admin/statuses/${id}`;
  try {
    await api(path, { method: "PATCH", body: JSON.stringify({ is_active: active !== "true" }) });
    if (kind === "category") await Promise.all([loadAdminCategories(), loadCategories()]);
    else await Promise.all([loadAdminStatuses(), loadStatuses().then(buildStatusTabs)]);
  } catch (error) {
    alert(error.message);
  }
}

document.getElementById("category-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.getElementById("new-category-name");
  try {
    await api("/api/admin/categories", { method: "POST", body: JSON.stringify({ name: input.value.trim() }) });
    input.value = "";
    await Promise.all([loadAdminCategories(), loadCategories()]);
  } catch (error) {
    alert(error.message);
  }
});

document.getElementById("status-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.getElementById("new-status-name");
  try {
    await api("/api/admin/statuses", { method: "POST", body: JSON.stringify({ name: input.value.trim() }) });
    input.value = "";
    await Promise.all([loadAdminStatuses(), loadStatuses().then(buildStatusTabs)]);
  } catch (error) {
    alert(error.message);
  }
});

async function loadAdminUsers() {
  const users = await api("/api/admin/users");
  const tbody = document.getElementById("users-tbody");
  tbody.innerHTML = users
    .map(
      (u) => `
      <tr>
        <td>${u.full_name}</td>
        <td>${u.login}</td>
        <td>${u.role === "admin" ? "Администратор" : "Специалист"}</td>
        <td>${u.account_status === "active" ? "Активна" : "Заблокирована"}</td>
        <td>
          <button type="button" class="secondary" data-id="${u.id}" data-status="${u.account_status}">
            ${u.account_status === "active" ? "Заблокировать" : "Разблокировать"}
          </button>
        </td>
      </tr>`
    )
    .join("");
  tbody.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const action = btn.dataset.status === "active" ? "block" : "unblock";
      try {
        await api(`/api/admin/users/${btn.dataset.id}/${action}`, { method: "PATCH" });
        await Promise.all([loadAdminUsers(), loadSpecialists()]);
      } catch (error) {
        alert(error.message);
      }
    });
  });
}

document.getElementById("user-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    login: document.getElementById("new-user-login").value.trim(),
    password: document.getElementById("new-user-password").value,
    full_name: document.getElementById("new-user-fullname").value.trim(),
    role: document.getElementById("new-user-role").value,
  };
  try {
    await api("/api/admin/users", { method: "POST", body: JSON.stringify(payload) });
    event.target.reset();
    await Promise.all([loadAdminUsers(), loadSpecialists()]);
  } catch (error) {
    alert(error.message);
  }
});

// ---------- Init ----------

document.addEventListener("DOMContentLoaded", async () => {
  if (state.token && state.user) {
    try {
      await api("/api/auth/me");
      await enterApp();
      return;
    } catch {
      logout();
    }
  }
});
