const API = "";

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Ошибка запроса");
  }
  return data;
}

const urgencyOptions = [
  { value: "low", label: "Низкая" },
  { value: "medium", label: "Средняя" },
  { value: "high", label: "Высокая" },
  { value: "critical", label: "Критическая" },
];

function showAlert(message, type = "success") {
  const box = document.getElementById("alert-box");
  box.className = `alert ${type}`;
  box.textContent = message;
  box.hidden = false;
}

function hideAlert() {
  document.getElementById("alert-box").hidden = true;
}

async function loadCategories() {
  const categories = await api("/api/categories");
  const select = document.getElementById("category_id");
  select.innerHTML = categories
    .map((c) => `<option value="${c.id}">${c.name}</option>`)
    .join("");
}

function setupAutocomplete() {
  const input = document.getElementById("full_name");
  const list = document.getElementById("autocomplete-list");
  let timer;

  input.addEventListener("input", () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) {
      list.innerHTML = "";
      list.hidden = true;
      return;
    }
    timer = setTimeout(async () => {
      try {
        const items = await api(`/api/clients/autocomplete?q=${encodeURIComponent(q)}`);
        if (!items.length) {
          list.hidden = true;
          return;
        }
        list.innerHTML = items
          .map(
            (item) =>
              `<div class="autocomplete-item" data-name="${item.full_name}">${item.full_name}${
                item.department ? ` — ${item.department}` : ""
              }</div>`
          )
          .join("");
        list.hidden = false;
      } catch {
        list.hidden = true;
      }
    }, 250);
  });

  list.addEventListener("click", (event) => {
    const item = event.target.closest(".autocomplete-item");
    if (!item) return;
    input.value = item.dataset.name;
    list.hidden = true;
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".autocomplete-wrap")) {
      list.hidden = true;
    }
  });
}

document.getElementById("request-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  hideAlert();
  const form = event.target;
  const payload = {
    full_name: form.full_name.value.trim(),
    cabinet: form.cabinet.value.trim(),
    category_id: Number(form.category_id.value),
    description: form.description.value.trim(),
    urgency: form.urgency.value,
    preferred_visit_time: form.preferred_visit_time.value.trim() || null,
  };

  try {
    const result = await api("/api/requests", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showAlert(`${result.message} Номер заявки: ${result.id}.`);
    form.reset();
  } catch (error) {
    showAlert(error.message, "error");
  }
});

document.addEventListener("DOMContentLoaded", async () => {
  const urgencySelect = document.getElementById("urgency");
  urgencySelect.innerHTML = urgencyOptions
    .map((o) => `<option value="${o.value}">${o.label}</option>`)
    .join("");
  urgencySelect.value = "medium";
  await loadCategories();
  setupAutocomplete();
});
