const APP_BASE_PATH = window.location.pathname.startsWith("/albums") ? "/albums" : "";
const PAGE_SIZE = 200;

const state = {
  statuses: [],
  studios: [],
  primaryModels: [],
  rows: [],
  total: 0,
  offset: 0,
  limit: PAGE_SIZE,
};

const ui = {
  studioSelect: document.getElementById("studioSelect"),
  modelSelect: document.getElementById("modelSelect"),
  statusSelect: document.getElementById("statusSelect"),
  importStatusSelect: document.getElementById("importStatusSelect"),
  keywordInput: document.getElementById("keywordInput"),
  searchBtn: document.getElementById("searchBtn"),
  resetBtn: document.getElementById("resetBtn"),
  albumsBody: document.getElementById("albumsBody"),
  statusText: document.getElementById("statusText"),
  rowCount: document.getElementById("rowCount"),
  totalCount: document.getElementById("totalCount"),
  pageText: document.getElementById("pageText"),
  prevPageBtn: document.getElementById("prevPageBtn"),
  nextPageBtn: document.getElementById("nextPageBtn"),
  popup: document.getElementById("popup"),
};

function apiUrl(path) {
  return `${APP_BASE_PATH}${path}`;
}

function setStatus(message) {
  ui.statusText.textContent = message;
}

function showPopup(message, ok = true) {
  ui.popup.textContent = message;
  ui.popup.className = `popup ${ok ? "ok" : "error"}`;
  ui.popup.classList.remove("hidden");
  setTimeout(() => ui.popup.classList.add("hidden"), 3200);
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function badge(label, className = "") {
  const cls = className ? `badge ${className}` : "badge";
  return `<span class="${cls}">${escapeHtml(label)}</span>`;
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    throw new Error(data.error || "request failed");
  }
  return data;
}

function fillSelect(selectEl, values, formatter) {
  const existing = selectEl.value;
  selectEl.innerHTML = "";
  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "全部";
  selectEl.appendChild(allOption);

  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = formatter ? formatter(value).value : value;
    option.textContent = formatter ? formatter(value).label : value;
    selectEl.appendChild(option);
  });

  if (Array.from(selectEl.options).some((opt) => opt.value === existing)) {
    selectEl.value = existing;
  }
}

async function loadOptions() {
  const data = await fetchJson(apiUrl("/api/albums/options"));
  state.statuses = data.statuses || [];
  state.studios = data.studios || [];
  state.primaryModels = data.primary_models || [];

  fillSelect(ui.studioSelect, state.studios);
  fillSelect(ui.modelSelect, state.primaryModels);
  fillSelect(ui.statusSelect, state.statuses, (item) => ({
    value: String(item.id),
    label: `${item.id} - ${item.name}`,
  }));
}

function currentFilters() {
  const rawStatus = ui.statusSelect.value;
  return {
    studio_name: ui.studioSelect.value.trim(),
    primary_model: ui.modelSelect.value.trim(),
    status_id: rawStatus === "" ? null : Number(rawStatus),
    import_status: ui.importStatusSelect.value,
    keyword: ui.keywordInput.value.trim(),
    offset: state.offset,
    limit: state.limit,
  };
}

function renderRows() {
  if (state.rows.length === 0) {
    ui.albumsBody.innerHTML = '<tr><td colspan="8">未找到符合条件的数据。</td></tr>';
    return;
  }

  ui.albumsBody.innerHTML = state.rows
    .map((row) => {
      const statusText = row.status_name ? `${row.status_id} - ${row.status_name}` : String(row.status_id || "");
      const importBadge =
        row.import_status === "imported" ? badge("已导入", "badge-ok") : badge("未导入", "badge-warn");
      return `
        <tr>
          <td>${row.id}</td>
          <td class="path-cell">${escapeHtml(row.current_path)}</td>
          <td>${escapeHtml(row.primary_model)}</td>
          <td>${escapeHtml(row.studio_name)}</td>
          <td>${escapeHtml(row.album_name)}</td>
          <td>${escapeHtml(row.additional_models)}</td>
          <td title="${escapeHtml(row.status_description || "")}">${escapeHtml(statusText)}</td>
          <td>${importBadge}</td>
        </tr>
      `;
    })
    .join("");
}

function updateSummary() {
  ui.rowCount.textContent = String(state.rows.length);
  ui.totalCount.textContent = String(state.total);
  const page = Math.floor(state.offset / state.limit) + 1;
  const totalPages = Math.max(1, Math.ceil(state.total / state.limit));
  ui.pageText.textContent = `${page} / ${totalPages}`;
  ui.prevPageBtn.disabled = state.offset <= 0;
  ui.nextPageBtn.disabled = state.offset + state.limit >= state.total;
}

async function searchAlbums() {
  setStatus("正在查询...");
  const data = await fetchJson(apiUrl("/api/albums/search"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentFilters()),
  });

  state.rows = data.rows || [];
  state.total = Number(data.total || 0);
  renderRows();
  updateSummary();
  setStatus(`查询完成：共 ${state.total} 条，当前 ${state.rows.length} 条`);
}

function resetFilters() {
  ui.studioSelect.value = "";
  ui.modelSelect.value = "";
  ui.statusSelect.value = "";
  ui.importStatusSelect.value = "all";
  ui.keywordInput.value = "";
  state.offset = 0;
}

function bindEvents() {
  ui.searchBtn.addEventListener("click", async () => {
    try {
      state.offset = 0;
      await searchAlbums();
    } catch (error) {
      setStatus("查询失败");
      showPopup(error.message || "查询失败", false);
    }
  });

  ui.resetBtn.addEventListener("click", async () => {
    try {
      resetFilters();
      await searchAlbums();
    } catch (error) {
      setStatus("查询失败");
      showPopup(error.message || "查询失败", false);
    }
  });

  ui.keywordInput.addEventListener("keydown", async (event) => {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    try {
      state.offset = 0;
      await searchAlbums();
    } catch (error) {
      setStatus("查询失败");
      showPopup(error.message || "查询失败", false);
    }
  });

  ui.prevPageBtn.addEventListener("click", async () => {
    if (state.offset <= 0) {
      return;
    }
    state.offset = Math.max(0, state.offset - state.limit);
    try {
      await searchAlbums();
    } catch (error) {
      setStatus("翻页失败");
      showPopup(error.message || "翻页失败", false);
    }
  });

  ui.nextPageBtn.addEventListener("click", async () => {
    if (state.offset + state.limit >= state.total) {
      return;
    }
    state.offset += state.limit;
    try {
      await searchAlbums();
    } catch (error) {
      setStatus("翻页失败");
      showPopup(error.message || "翻页失败", false);
    }
  });
}

async function init() {
  try {
    setStatus("正在加载筛选项...");
    await loadOptions();
    bindEvents();
    await searchAlbums();
  } catch (error) {
    setStatus("初始化失败");
    showPopup(error.message || "初始化失败", false);
  }
}

init();
