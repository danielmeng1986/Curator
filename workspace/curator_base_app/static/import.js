const APP_BASE_PATH = window.location.pathname.startsWith("/import") ? "/import" : "";

const state = {
  importSourceRoot: "",
  archiveRoot: "",
  defaultImportStudio: "MetArt",
  rows: [],
  showImportFailuresOnly: false,
};

const ui = {
  batchFolderPicker: document.getElementById("batchFolderPicker"),
  globalStudioInput: document.getElementById("globalStudioInput"),
  studioDatalist: document.getElementById("studioDatalist"),
  applyStudioBtn: document.getElementById("applyStudioBtn"),
  keepSourceCheckbox: document.getElementById("keepSourceCheckbox"),
  selectAllBtn: document.getElementById("selectAllBtn"),
  clearSelectionBtn: document.getElementById("clearSelectionBtn"),
  previewBatchBtn: document.getElementById("previewBatchBtn"),
  importBatchBtn: document.getElementById("importBatchBtn"),
  importRootText: document.getElementById("importRootText"),
  archiveRootText: document.getElementById("archiveRootText"),
  batchImportPreview: document.getElementById("batchImportPreview"),
  batchRowsBody: document.getElementById("batchRowsBody"),
  statusText: document.getElementById("statusText"),
  parsedCount: document.getElementById("parsedCount"),
  selectedCount: document.getElementById("selectedCount"),
  importableCount: document.getElementById("importableCount"),
  popup: document.getElementById("popup"),
};

function apiUrl(path) {
  return `${APP_BASE_PATH}${path}`;
}

function joinPosixPath(basePath, leafName) {
  const base = String(basePath || "").trim().replace(/\/+$/, "");
  const leaf = String(leafName || "").replace(/^\/+/, "");
  if (!base) {
    return leaf;
  }
  if (!leaf) {
    return base;
  }
  return `${base}/${leaf}`;
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

function setImportPreviewText(message, ok = true) {
  ui.batchImportPreview.textContent = message;
  ui.batchImportPreview.classList.toggle("import-preview-error", !ok);
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    throw new Error(data.error || "request failed");
  }
  return data;
}

function selectedRows() {
  return state.rows.filter((row) => row.selected);
}

function previewableRows() {
  return selectedRows().filter((row) => row.preview && row.preview.ok && row.preview.can_import);
}

function isImportFailureRow(row) {
  return Boolean(row.importResult && row.importResult.success === false);
}

function isImportSuccessRow(row) {
  return Boolean(row.importResult && row.importResult.success !== false);
}

function renderableRows() {
  if (!state.showImportFailuresOnly) {
    return state.rows.map((row, index) => ({ row, index }));
  }
  return state.rows
    .map((row, index) => ({ row, index }))
    .filter((item) => isImportFailureRow(item.row));
}

function updateSummary() {
  ui.parsedCount.textContent = String(state.rows.length);
  ui.selectedCount.textContent = String(selectedRows().length);
  ui.importableCount.textContent = String(previewableRows().length);
  ui.importBatchBtn.disabled = previewableRows().length === 0;
}

function badge(label, className = "") {
  const cls = className ? `badge ${className}` : "badge";
  return `<span class="${cls}">${label}</span>`;
}

function flagsHtml(row) {
  if (!row.preview || !row.preview.ok) {
    return row.preview && row.preview.error ? badge("解析失败", "badge-error") : "";
  }

  const flags = [];
  if (row.preview.will_create_model) {
    flags.push(badge("新建 Model", "badge-warn"));
  }
  if (row.preview.will_create_studio) {
    flags.push(badge("新建 Studio", "badge-warn"));
  }
  if (row.preview.destination_exists) {
    flags.push(badge("目标目录已存在", "badge-error"));
  }
  if (row.preview.workspace_album_exists) {
    flags.push(badge(`workspace_album#${row.preview.workspace_album_id}`, "badge-error"));
  }
  if (flags.length === 0) {
    flags.push(badge("可导入", "badge-ok"));
  }
  return flags.join(" ");
}

function resultText(row) {
  if (row.importResult) {
    if (row.importResult.success === false) {
      return `失败原因: ${row.importResult.error || "导入失败"}`;
    }
    if (row.importResult.workspace_album_id) {
      return `已导入 id=${row.importResult.workspace_album_id}`;
    }
  }
  if (row.preview && row.preview.ok) {
    return row.preview.can_import ? "预览完成" : "存在冲突";
  }
  if (row.preview && row.preview.error) {
    return row.preview.error;
  }
  return "待预览";
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderRows() {
  if (state.rows.length === 0) {
    ui.batchRowsBody.innerHTML = '<tr><td colspan="9">尚未选择任何影集。</td></tr>';
    updateSummary();
    return;
  }

  const rows = renderableRows();
  if (rows.length === 0 && state.showImportFailuresOnly) {
    const hiddenSuccessCount = state.rows.filter((row) => isImportSuccessRow(row)).length;
    ui.batchRowsBody.innerHTML = `<tr><td colspan="9">导入结果中没有失败条目。已默认隐藏成功条目（${hiddenSuccessCount} 条）。</td></tr>`;
    updateSummary();
    return;
  }

  ui.batchRowsBody.innerHTML = rows
    .map(({ row, index }) => {
      const preview = row.preview && row.preview.ok ? row.preview : null;
      return `
        <tr data-row-index="${index}">
          <td><input type="checkbox" data-role="select-row" ${row.selected ? "checked" : ""} /></td>
          <td>${escapeHtml(row.folderName)}</td>
          <td class="path-cell">${escapeHtml(row.sourcePath)}</td>
          <td>
            <input
              type="text"
              class="table-text-input"
              data-role="studio-input"
              value="${escapeHtml(row.studioName)}"
              list="studioDatalist"
            />
          </td>
          <td>${escapeHtml(preview ? preview.model_name : "")}</td>
          <td>${escapeHtml(preview ? preview.album_name : "")}</td>
          <td class="path-cell">${escapeHtml(preview ? preview.expected_path : "")}</td>
          <td>${flagsHtml(row)}</td>
          <td>${escapeHtml(resultText(row))}</td>
        </tr>
      `;
    })
    .join("");

  ui.batchRowsBody.querySelectorAll('input[data-role="select-row"]').forEach((input) => {
    input.addEventListener("change", (event) => {
      const tr = event.target.closest("tr");
      const rowIndex = Number(tr?.dataset.rowIndex);
      if (!Number.isFinite(rowIndex)) {
        return;
      }
      state.rows[rowIndex].selected = Boolean(event.target.checked);
      updateSummary();
    });
  });

  ui.batchRowsBody.querySelectorAll('input[data-role="studio-input"]').forEach((input) => {
    input.addEventListener("input", (event) => {
      const tr = event.target.closest("tr");
      const rowIndex = Number(tr?.dataset.rowIndex);
      if (!Number.isFinite(rowIndex)) {
        return;
      }
      state.rows[rowIndex].studioName = String(event.target.value || "").trim() || state.defaultImportStudio;
      state.rows[rowIndex].preview = null;
      state.rows[rowIndex].importResult = null;
      updateSummary();
    });
  });

  updateSummary();
}

function extractFolderNames(files) {
  const folderNames = new Set();
  files.forEach((file) => {
    const rel = String(file.webkitRelativePath || file.name || "");
    const first = rel.split("/")[0] || "";
    if (first.length > 0) {
      folderNames.add(first);
    }
  });
  return Array.from(folderNames).filter((name) => name.length > 0).sort((a, b) => a.localeCompare(b));
}

function refreshRowsFromPicker() {
  state.showImportFailuresOnly = false;
  const files = Array.from(ui.batchFolderPicker.files || []);
  const folderNames = extractFolderNames(files);
  const previousByFolder = new Map(state.rows.map((row) => [row.folderName, row]));

  state.rows = folderNames.map((folderName) => {
    const existing = previousByFolder.get(folderName);
    return {
      folderName,
      selected: existing ? existing.selected : true,
      sourcePath: joinPosixPath(state.importSourceRoot, folderName),
      studioName: existing ? existing.studioName : (ui.globalStudioInput.value.trim() || state.defaultImportStudio),
      preview: existing ? existing.preview : null,
      importResult: existing ? existing.importResult : null,
    };
  });

  renderRows();
  setImportPreviewText(`已识别 ${state.rows.length} 个顶层影集文件夹。`);
  setStatus(`已读取 ${state.rows.length} 个待导入影集`);
}

async function loadOptions() {
  const data = await fetchJson(apiUrl("/api/options"));
  state.importSourceRoot = String(data.import_source_root || "").trim();
  state.archiveRoot = String(data.archive_root || "").trim();
  state.defaultImportStudio = String(data.default_import_studio || "MetArt").trim() || "MetArt";

  ui.globalStudioInput.value = state.defaultImportStudio;
  ui.importRootText.textContent = state.importSourceRoot || "(未配置)";
  ui.archiveRootText.textContent = state.archiveRoot || "(未配置)";

  ui.studioDatalist.innerHTML = "";
  (data.studios || []).forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    ui.studioDatalist.appendChild(option);
  });
}

function applyGlobalStudioToSelected() {
  const studioName = ui.globalStudioInput.value.trim() || state.defaultImportStudio;
  selectedRows().forEach((row) => {
    row.studioName = studioName;
    row.preview = null;
    row.importResult = null;
  });
  renderRows();
  setStatus(`已将 Studio=${studioName} 应用到 ${selectedRows().length} 个选中项`);
}

async function previewSelectedRows() {
  state.showImportFailuresOnly = false;
  const rows = selectedRows();
  if (rows.length === 0) {
    throw new Error("请先选择至少一个影集");
  }

  setStatus(`正在预览 ${rows.length} 个影集...`);
  const payload = {
    items: rows.map((row) => ({
      source_path: row.sourcePath,
      folder_name: row.folderName,
      studio_name: row.studioName,
    })),
  };
  const data = await fetchJson(apiUrl("/api/import-albums/preview"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  data.preview.items.forEach((preview, index) => {
    rows[index].preview = preview;
    rows[index].importResult = null;
  });

  renderRows();
  const summary = data.preview.summary;
  setImportPreviewText(
    `预览完成：共 ${summary.total} 项，正常 ${summary.ok}，错误 ${summary.errors}，新建 Model ${summary.will_create_models}，新建 Studio ${summary.will_create_studios}`,
    summary.errors === 0,
  );
  setStatus(`预览完成：可导入 ${previewableRows().length} 项`);
}

async function importSelectedRows() {
  const rows = previewableRows();
  if (rows.length === 0) {
    throw new Error("没有可导入的已预览项目");
  }

  const action = ui.keepSourceCheckbox.checked ? "复制" : "移动";
  if (!window.confirm(`确认${action} ${rows.length} 个影集到 Archive，并写入 workspace_album？`)) {
    return;
  }

  setStatus(`正在导入 ${rows.length} 个影集...`);
  const payload = {
    items: rows.map((row) => ({
      source_path: row.sourcePath,
      folder_name: row.folderName,
      studio_name: row.studioName,
      keep_source: ui.keepSourceCheckbox.checked,
    })),
  };
  const data = await fetchJson(apiUrl("/api/import-albums"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  data.result.items.forEach((result, index) => {
    rows[index].importResult = result;
    if (result.success !== false) {
      rows[index].selected = false;
    }
  });

  state.showImportFailuresOnly = true;

  renderRows();
  const summary = data.result.summary;
  const ok = summary.failed === 0;
  setImportPreviewText(`导入完成：成功 ${summary.success}，失败 ${summary.failed}。结果列表默认仅显示失败条目。`, ok);
  setStatus(`导入完成：成功 ${summary.success}，失败 ${summary.failed}`);
  showPopup(`导入完成：成功 ${summary.success}，失败 ${summary.failed}`, ok);
}

function bindEvents() {
  ui.batchFolderPicker.addEventListener("change", () => {
    refreshRowsFromPicker();
  });

  ui.globalStudioInput.addEventListener("input", () => {
    state.rows.forEach((row) => {
      row.preview = null;
      row.importResult = null;
    });
    renderRows();
  });

  ui.applyStudioBtn.addEventListener("click", () => {
    applyGlobalStudioToSelected();
  });

  ui.selectAllBtn.addEventListener("click", () => {
    state.rows.forEach((row) => {
      row.selected = true;
    });
    renderRows();
  });

  ui.clearSelectionBtn.addEventListener("click", () => {
    state.rows.forEach((row) => {
      row.selected = false;
    });
    renderRows();
  });

  ui.previewBatchBtn.addEventListener("click", async () => {
    try {
      await previewSelectedRows();
    } catch (err) {
      setStatus(`批量预览失败: ${err.message}`);
      setImportPreviewText(`批量预览失败: ${err.message}`, false);
      showPopup(`批量预览失败: ${err.message}`, false);
    }
  });

  ui.importBatchBtn.addEventListener("click", async () => {
    try {
      await importSelectedRows();
    } catch (err) {
      setStatus(`批量导入失败: ${err.message}`);
      showPopup(`批量导入失败: ${err.message}`, false);
    }
  });
}

async function init() {
  bindEvents();
  try {
    await loadOptions();
    renderRows();
    setStatus("准备就绪");
  } catch (err) {
    setStatus(`初始化失败: ${err.message}`);
    showPopup(`初始化失败: ${err.message}`, false);
  }
}

init();
