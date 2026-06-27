const state = {
  schema: [],
  columns: [],
  rows: [],
  queryName: "",
  pkColumn: "id",
  columnState: new Map(),
  pendingChanges: new Map(),
  originalByPk: new Map(),
  lastEditedColumn: null,
};

const COLUMN_VISIBILITY_STORAGE_KEY = "normalize_app_workspace_album_column_visibility";

const ui = {
  querySelect: document.getElementById("querySelect"),
  loadQueryBtn: document.getElementById("loadQueryBtn"),
  reloadBtn: document.getElementById("reloadBtn"),
  toggleColumnsBtn: document.getElementById("toggleColumnsBtn"),
  saveBtn: document.getElementById("saveBtn"),
  columnPanel: document.getElementById("columnPanel"),
  statusText: document.getElementById("statusText"),
  rowCount: document.getElementById("rowCount"),
  dirtyCount: document.getElementById("dirtyCount"),
  tableWrap: document.getElementById("tableWrap"),
  tableColgroup: document.getElementById("tableColgroup"),
  tableHead: document.getElementById("tableHead"),
  tableBody: document.getElementById("tableBody"),
  popup: document.getElementById("popup"),
};

function setStatus(text) {
  ui.statusText.textContent = text;
}

function showPopup(message, ok = true) {
  ui.popup.textContent = message;
  ui.popup.className = `popup ${ok ? "ok" : "error"}`;
  ui.popup.classList.remove("hidden");
  setTimeout(() => ui.popup.classList.add("hidden"), 3200);
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    throw new Error(data.error || "request failed");
  }
  return data;
}

function getPkColumnFromSchema(schema) {
  const pk = schema.find((col) => col.pk);
  return pk ? pk.name : "id";
}

function normalizeCellValue(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}

function parseForCommit(raw, columnName) {
  const schemaItem = state.schema.find((col) => col.name === columnName);
  if (!schemaItem) {
    return raw;
  }
  const trimmed = raw.trim();

  if (trimmed === "") {
    return null;
  }

  const typeName = (schemaItem.type || "").toUpperCase();
  if (typeName.includes("INT")) {
    const n = Number(trimmed);
    if (Number.isNaN(n)) {
      throw new Error(`${columnName} 需要整数值`);
    }
    return Math.trunc(n);
  }

  return raw;
}

function updateDirtyCounter() {
  ui.dirtyCount.textContent = String(state.pendingChanges.size);
  ui.saveBtn.disabled = state.pendingChanges.size === 0;
}

function resetPendingChanges() {
  state.pendingChanges.clear();
  updateDirtyCounter();
}

function getColumnWidth(column) {
  const current = state.columnState.get(column);
  if (current && current.width) {
    return current.width;
  }
  if (column === state.pkColumn) {
    return 90;
  }
  return 180;
}

function loadColumnVisibilityPrefs() {
  try {
    const raw = localStorage.getItem(COLUMN_VISIBILITY_STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveColumnVisibilityPrefs() {
  const payload = {};
  state.columnState.forEach((config, column) => {
    if (config && typeof config.visible === "boolean") {
      payload[column] = config.visible;
    }
  });
  try {
    localStorage.setItem(COLUMN_VISIBILITY_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Ignore storage write failures (e.g. private mode quota restrictions).
  }
}

function ensureColumnState() {
  const savedVisibility = loadColumnVisibilityPrefs();
  state.columns.forEach((column) => {
    if (!state.columnState.has(column)) {
      const savedVisible = savedVisibility[column];
      state.columnState.set(column, {
        visible: typeof savedVisible === "boolean" ? savedVisible : true,
        width: getColumnWidth(column),
      });
      return;
    }
    const existing = state.columnState.get(column);
    if (!("width" in existing)) {
      existing.width = getColumnWidth(column);
    }
  });
}

function setColumnVisible(column, visible) {
  const config = state.columnState.get(column) || { width: 180 };
  config.visible = visible;
  state.columnState.set(column, config);

  const index = state.columns.indexOf(column);
  if (index < 0) {
    return;
  }

  const selector = `[data-col-index="${index}"]`;
  document.querySelectorAll(selector).forEach((el) => {
    el.classList.toggle("hidden-col", !visible);
  });

  const col = ui.tableColgroup.querySelector(`col[data-col-index="${index}"]`);
  if (col) {
    col.classList.toggle("hidden-col", !visible);
  }

  saveColumnVisibilityPrefs();
}

function buildColumnPanel() {
  ui.columnPanel.innerHTML = "";
  state.columns.forEach((column) => {
    const item = document.createElement("label");
    item.className = "column-item";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = state.columnState.get(column)?.visible !== false;
    input.addEventListener("change", () => {
      setColumnVisible(column, input.checked);
    });

    const text = document.createElement("span");
    text.textContent = column;

    item.appendChild(input);
    item.appendChild(text);
    ui.columnPanel.appendChild(item);
  });
}

function setupColumnResizer(handle, column, colElement) {
  let startX = 0;
  let startWidth = 0;

  handle.addEventListener("mousedown", (event) => {
    event.preventDefault();
    startX = event.clientX;
    startWidth = colElement.getBoundingClientRect().width;

    const onMove = (moveEvent) => {
      const nextWidth = Math.max(70, startWidth + moveEvent.clientX - startX);
      colElement.style.width = `${nextWidth}px`;
      const config = state.columnState.get(column) || { visible: true, width: 180 };
      config.width = nextWidth;
      state.columnState.set(column, config);
    };

    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

function isEditableColumn(column) {
  return column !== state.pkColumn;
}

function focusNextRowSameColumn(cell) {
  const row = cell.parentElement;
  if (!row) {
    return;
  }

  const nextRow = row.nextElementSibling;
  if (!nextRow) {
    return;
  }

  const column = cell.dataset.column;
  const nextCell = nextRow.querySelector(`td[data-column="${column}"]`);
  if (!nextCell || nextCell.contentEditable !== "true") {
    return;
  }

  nextCell.focus();
  const selection = window.getSelection();
  if (!selection) {
    return;
  }
  const range = document.createRange();
  const cellText = (nextCell.textContent || "").trim();
  if (cellText) {
    // Non-empty cell: select all text so typing replaces content directly.
    range.selectNodeContents(nextCell);
  } else {
    range.selectNodeContents(nextCell);
    range.collapse(false);
  }
  selection.removeAllRanges();
  selection.addRange(range);
}

function onCellKeyDown(event) {
  if (event.key !== "Enter") {
    return;
  }
  event.preventDefault();
  const cell = event.currentTarget;

  // Trigger blur to reuse existing dirty-tracking behavior.
  cell.blur();
  focusNextRowSameColumn(cell);
}

function moveCaretOrSelectCell(cell) {
  cell.focus();
  const selection = window.getSelection();
  if (!selection) {
    return;
  }
  const range = document.createRange();
  const cellText = (cell.textContent || "").trim();
  if (cellText) {
    range.selectNodeContents(cell);
  } else {
    range.selectNodeContents(cell);
    range.collapse(false);
  }
  selection.removeAllRanges();
  selection.addRange(range);
}

function focusFirstRowOfColumn(column) {
  if (!column) {
    return;
  }

  if (ui.tableWrap) {
    ui.tableWrap.scrollTop = 0;
  }

  const firstRow = ui.tableBody.querySelector("tr");
  if (!firstRow) {
    return;
  }

  const targetCell = firstRow.querySelector(`td[data-column="${column}"]`);
  if (!targetCell || targetCell.contentEditable !== "true") {
    return;
  }

  moveCaretOrSelectCell(targetCell);
}

function buildTable() {
  ui.tableColgroup.innerHTML = "";
  ui.tableHead.innerHTML = "";
  ui.tableBody.innerHTML = "";

  ensureColumnState();

  const headRow = document.createElement("tr");

  state.columns.forEach((column, index) => {
    const colElement = document.createElement("col");
    colElement.dataset.colIndex = String(index);
    colElement.style.width = `${state.columnState.get(column).width}px`;
    if (state.columnState.get(column).visible === false) {
      colElement.classList.add("hidden-col");
    }
    ui.tableColgroup.appendChild(colElement);

    const th = document.createElement("th");
    th.dataset.colIndex = String(index);
    th.textContent = column;
    if (column === state.pkColumn) {
      th.classList.add("pk-col");
    }
    if (state.columnState.get(column).visible === false) {
      th.classList.add("hidden-col");
    }

    const resizer = document.createElement("div");
    resizer.className = "resizer";
    th.appendChild(resizer);
    setupColumnResizer(resizer, column, colElement);

    headRow.appendChild(th);
  });

  ui.tableHead.appendChild(headRow);

  state.rows.forEach((row) => {
    const tr = document.createElement("tr");
    const pkValue = row[state.pkColumn];

    state.columns.forEach((column, index) => {
      const td = document.createElement("td");
      td.dataset.colIndex = String(index);
      td.dataset.pkValue = String(pkValue);
      td.dataset.column = column;
      td.textContent = normalizeCellValue(row[column]);

      if (column === state.pkColumn) {
        td.classList.add("pk-col");
      }
      if (state.columnState.get(column).visible === false) {
        td.classList.add("hidden-col");
      }

      if (isEditableColumn(column)) {
        td.contentEditable = "true";
        td.spellcheck = false;
        td.addEventListener("blur", onCellBlur);
        td.addEventListener("keydown", onCellKeyDown);
      }

      tr.appendChild(td);
    });

    ui.tableBody.appendChild(tr);
  });

  ui.rowCount.textContent = String(state.rows.length);
}

function onCellBlur(event) {
  const cell = event.currentTarget;
  const pkValue = Number(cell.dataset.pkValue);
  const column = cell.dataset.column;
  state.lastEditedColumn = column;
  const raw = cell.textContent ?? "";
  const originalRow = state.originalByPk.get(pkValue) || {};
  const originalValue = normalizeCellValue(originalRow[column]);

  if (raw === originalValue) {
    const existing = state.pendingChanges.get(pkValue);
    if (existing && column in existing) {
      delete existing[column];
      if (Object.keys(existing).length === 0) {
        state.pendingChanges.delete(pkValue);
      } else {
        state.pendingChanges.set(pkValue, existing);
      }
    }
    cell.classList.remove("dirty-cell");
    updateDirtyCounter();
    return;
  }

  const rowChanges = state.pendingChanges.get(pkValue) || {};
  rowChanges[column] = raw;
  state.pendingChanges.set(pkValue, rowChanges);
  cell.classList.add("dirty-cell");
  updateDirtyCounter();
}

async function loadSchema() {
  const data = await fetchJson("/api/schema?table=workspace_album");
  state.schema = data.schema;
  state.pkColumn = getPkColumnFromSchema(state.schema);
}

async function loadQueries() {
  const data = await fetchJson("/api/queries");
  ui.querySelect.innerHTML = "";
  data.queries.forEach((query) => {
    const option = document.createElement("option");
    option.value = query.name;
    option.textContent = query.name;
    ui.querySelect.appendChild(option);
  });

  if (data.queries.length === 0) {
    throw new Error("database 目录中未找到可用 Query 文件");
  }

  const defaultOption = data.queries.find((q) => q.name === "need_confirm_album_wowgirls");
  if (defaultOption) {
    ui.querySelect.value = defaultOption.name;
  }
}

function hydrateOriginalRows(rows) {
  state.originalByPk.clear();
  rows.forEach((row) => {
    const pkValue = row[state.pkColumn];
    state.originalByPk.set(pkValue, { ...row });
  });
}

async function loadQueryData() {
  const queryName = ui.querySelect.value;
  setStatus(`正在加载 ${queryName} ...`);
  const data = await fetchJson("/api/run-query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query_name: queryName }),
  });

  state.queryName = data.query_name;
  state.columns = data.columns;
  state.rows = data.rows;

  if (!state.columns.includes(state.pkColumn)) {
    throw new Error(`查询结果缺少主键列 ${state.pkColumn}，无法提交修改`);
  }

  hydrateOriginalRows(state.rows);
  resetPendingChanges();
  buildColumnPanel();
  buildTable();
  setStatus(`已加载 ${state.queryName}，共 ${data.row_count} 行`);
}

async function submitChanges() {
  if (state.pendingChanges.size === 0) {
    showPopup("没有可提交的修改", false);
    return;
  }

  let targetColumn = state.lastEditedColumn;
  const active = document.activeElement;
  if (active && active.matches && active.matches("td[contenteditable='true']")) {
    targetColumn = active.dataset.column || targetColumn;
  }

  const updates = [];
  for (const [pkValue, changes] of state.pendingChanges.entries()) {
    const parsedChanges = {};
    for (const [column, raw] of Object.entries(changes)) {
      parsedChanges[column] = parseForCommit(raw, column);
    }
    updates.push({ pk_value: pkValue, changes: parsedChanges });
  }

  setStatus("正在提交修改...");
  const data = await fetchJson("/api/batch-update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      table: "workspace_album",
      pk_column: state.pkColumn,
      updates,
    }),
  });

  showPopup(`提交成功，已更新 ${data.applied_updates} 行`, true);
  await loadQueryData();

  if (!targetColumn) {
    targetColumn = state.columns.find((col) => col !== state.pkColumn) || null;
  }
  focusFirstRowOfColumn(targetColumn);
}

function bindEvents() {
  ui.loadQueryBtn.addEventListener("click", async () => {
    try {
      await loadQueryData();
    } catch (err) {
      setStatus(`加载失败: ${err.message}`);
      showPopup(`加载失败: ${err.message}`, false);
    }
  });

  ui.reloadBtn.addEventListener("click", async () => {
    try {
      await loadQueryData();
    } catch (err) {
      setStatus(`刷新失败: ${err.message}`);
      showPopup(`刷新失败: ${err.message}`, false);
    }
  });

  ui.toggleColumnsBtn.addEventListener("click", () => {
    ui.columnPanel.classList.toggle("hidden");
  });

  ui.saveBtn.addEventListener("click", async () => {
    try {
      await submitChanges();
    } catch (err) {
      setStatus(`提交失败: ${err.message}`);
      showPopup(`提交失败: ${err.message}`, false);
    }
  });
}

async function init() {
  bindEvents();
  try {
    await loadSchema();
    await loadQueries();
    await loadQueryData();
  } catch (err) {
    setStatus(`初始化失败: ${err.message}`);
    showPopup(`初始化失败: ${err.message}`, false);
  }
}

init();
