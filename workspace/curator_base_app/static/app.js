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
  selectedPkValues: new Set(),
  selectionAnchorRowIndex: null,
};

const COLUMN_VISIBILITY_STORAGE_KEY = "normalize_app_workspace_album_column_visibility";
const LAST_STATUS_ID_KEY = "normalize_app_workspace_album_last_status_id";
const LAST_STUDIO_NAME_KEY = "normalize_app_workspace_album_last_studio_name";
const APP_BASE_PATH = window.location.pathname.startsWith("/normalize") ? "/normalize" : "";

const ui = {
  appShell: document.querySelector(".app-shell"),
  tableCard: document.querySelector(".table-card"),
  statusSelect: document.getElementById("statusSelect"),
  studioSelect: document.getElementById("studioSelect"),
  reloadBtn: document.getElementById("reloadBtn"),
  toggleColumnsBtn: document.getElementById("toggleColumnsBtn"),
  bulkStatusInput: document.getElementById("bulkStatusInput"),
  bulkApplyStatusBtn: document.getElementById("bulkApplyStatusBtn"),
  bulkAlbumFindInput: document.getElementById("bulkAlbumFindInput"),
  bulkAlbumReplaceInput: document.getElementById("bulkAlbumReplaceInput"),
  bulkApplyAlbumReplaceBtn: document.getElementById("bulkApplyAlbumReplaceBtn"),
  saveBtn: document.getElementById("saveBtn"),
  focusIdInput: document.getElementById("focusIdInput"),
  focusIdBtn: document.getElementById("focusIdBtn"),
  backupReasonInput: document.getElementById("backupReasonInput"),
  backupTagInput: document.getElementById("backupTagInput"),
  backupNowBtn: document.getElementById("backupNowBtn"),
  cleanupBackupsBtn: document.getElementById("cleanupBackupsBtn"),
  rollbackModeSelect: document.getElementById("rollbackModeSelect"),
  rollbackTimestampInput: document.getElementById("rollbackTimestampInput"),
  rollbackTagInput: document.getElementById("rollbackTagInput"),
  rollbackNowBtn: document.getElementById("rollbackNowBtn"),
  columnPanel: document.getElementById("columnPanel"),
  statusText: document.getElementById("statusText"),
  rowCount: document.getElementById("rowCount"),
  selectedCount: document.getElementById("selectedCount"),
  dirtyCount: document.getElementById("dirtyCount"),
  tableWrap: document.getElementById("tableWrap"),
  tableColgroup: document.getElementById("tableColgroup"),
  tableHead: document.getElementById("tableHead"),
  tableBody: document.getElementById("tableBody"),
  popup: document.getElementById("popup"),
};

let layoutRafId = null;
const TABLE_MAX_VISIBLE_ROWS = 15;
const STATUS_SAFE_GAP_PX = 24;

function getPx(cssValue) {
  const n = parseFloat(cssValue);
  return Number.isFinite(n) ? n : 0;
}

function updateTableWrapHeight() {
  if (!ui.appShell || !ui.tableCard || !ui.tableWrap) {
    return;
  }

  const shellStyle = window.getComputedStyle(ui.appShell);
  const shellPaddingTop = getPx(shellStyle.paddingTop);
  const shellPaddingBottom = getPx(shellStyle.paddingBottom);
  const shellGap = getPx(shellStyle.rowGap || shellStyle.gap);

  const visibleSections = Array.from(ui.appShell.children).filter(
    (el) => el instanceof HTMLElement && !el.classList.contains("hidden"),
  );

  const nonTableHeight = visibleSections
    .filter((el) => el !== ui.tableCard)
    .reduce((sum, el) => sum + el.offsetHeight, 0);

  const totalGap = shellGap * Math.max(visibleSections.length - 1, 0);

  const cardStyle = window.getComputedStyle(ui.tableCard);
  const cardChrome =
    getPx(cardStyle.borderTopWidth) +
    getPx(cardStyle.borderBottomWidth) +
    getPx(cardStyle.paddingTop) +
    getPx(cardStyle.paddingBottom);

  const shellInnerHeight = ui.appShell.clientHeight - shellPaddingTop - shellPaddingBottom;
  const available = shellInnerHeight - nonTableHeight - totalGap - cardChrome - STATUS_SAFE_GAP_PX;

  const tableHeadRow = ui.tableHead.querySelector("tr");
  const firstBodyRow = ui.tableBody.querySelector("tr");
  const headerHeight = tableHeadRow ? tableHeadRow.getBoundingClientRect().height : 36;
  const rowHeight = firstBodyRow ? firstBodyRow.getBoundingClientRect().height : 34;
  const maxRowsHeight = Math.ceil(headerHeight + rowHeight * TABLE_MAX_VISIBLE_ROWS + 2);

  // Allow table area to shrink aggressively so the bottom status bar remains visible.
  const nextHeight = Math.max(60, Math.floor(Math.min(available, maxRowsHeight)));
  ui.tableWrap.style.height = `${nextHeight}px`;
}

function scheduleTableWrapHeightUpdate() {
  if (layoutRafId !== null) {
    cancelAnimationFrame(layoutRafId);
  }
  layoutRafId = requestAnimationFrame(() => {
    layoutRafId = null;
    updateTableWrapHeight();
  });
}

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

function apiUrl(path) {
  return `${APP_BASE_PATH}${path}`;
}

function toIsoFromDateTimeLocal(value) {
  if (!value) {
    return "";
  }
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) {
    return "";
  }
  return dt.toISOString();
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

function updateSelectionCounter() {
  ui.selectedCount.textContent = String(state.selectedPkValues.size);
  ui.bulkApplyStatusBtn.disabled = state.selectedPkValues.size === 0;
  ui.bulkApplyAlbumReplaceBtn.disabled = state.selectedPkValues.size === 0;
}

function setRowSelected(tr, selected) {
  const pkValue = Number(tr.dataset.pkValue);
  if (!Number.isFinite(pkValue)) {
    return;
  }
  if (selected) {
    state.selectedPkValues.add(pkValue);
  } else {
    state.selectedPkValues.delete(pkValue);
  }
  tr.classList.toggle("row-selected", selected);
}

function clearRowSelection() {
  state.selectedPkValues.clear();
  state.selectionAnchorRowIndex = null;
  ui.tableBody.querySelectorAll("tr.row-selected").forEach((tr) => {
    tr.classList.remove("row-selected");
  });
  updateSelectionCounter();
}

function selectRowRange(startIndex, endIndex) {
  const rows = ui.tableBody.querySelectorAll("tr");
  const min = Math.min(startIndex, endIndex);
  const max = Math.max(startIndex, endIndex);
  clearRowSelection();
  for (let i = min; i <= max; i += 1) {
    const tr = rows[i];
    if (tr) {
      setRowSelected(tr, true);
    }
  }
  updateSelectionCounter();
}

function selectAllRows() {
  const rows = ui.tableBody.querySelectorAll("tr");
  if (rows.length === 0) {
    return;
  }

  clearRowSelection();
  rows.forEach((tr) => setRowSelected(tr, true));
  state.selectionAnchorRowIndex = 0;
  updateSelectionCounter();
}

function shouldHandleTableSelectAll(event) {
  if (event.key.toLowerCase() !== "a" || (!event.metaKey && !event.ctrlKey)) {
    return false;
  }

  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) {
    return false;
  }

  if (target.isContentEditable) {
    return ui.tableWrap.contains(target);
  }

  return ui.tableWrap.contains(target) || ui.tableWrap.contains(document.activeElement);
}

function onGlobalKeyDown(event) {
  if (!shouldHandleTableSelectAll(event)) {
    return;
  }

  event.preventDefault();
  selectAllRows();
}

function onRowClick(event) {
  const tr = event.currentTarget;
  const rowIndex = Number(tr.dataset.rowIndex);
  if (!Number.isFinite(rowIndex)) {
    return;
  }

  if (event.shiftKey && Number.isFinite(state.selectionAnchorRowIndex)) {
    selectRowRange(state.selectionAnchorRowIndex, rowIndex);
    return;
  }

  if (event.metaKey || event.ctrlKey) {
    setRowSelected(tr, !tr.classList.contains("row-selected"));
    state.selectionAnchorRowIndex = rowIndex;
    updateSelectionCounter();
    return;
  }

  clearRowSelection();
  setRowSelected(tr, true);
  state.selectionAnchorRowIndex = rowIndex;
  updateSelectionCounter();
}

function applyCellChange(pkValue, column, rawValue, cell = null) {
  state.lastEditedColumn = column;
  const originalRow = state.originalByPk.get(pkValue) || {};
  const originalValue = normalizeCellValue(originalRow[column]);

  if (rawValue === originalValue) {
    const existing = state.pendingChanges.get(pkValue);
    if (existing && column in existing) {
      delete existing[column];
      if (Object.keys(existing).length === 0) {
        state.pendingChanges.delete(pkValue);
      } else {
        state.pendingChanges.set(pkValue, existing);
      }
    }
    if (cell) {
      cell.classList.remove("dirty-cell");
    }
    updateDirtyCounter();
    return;
  }

  const rowChanges = state.pendingChanges.get(pkValue) || {};
  rowChanges[column] = rawValue;
  state.pendingChanges.set(pkValue, rowChanges);
  if (cell) {
    cell.classList.add("dirty-cell");
  }
  updateDirtyCounter();
}

function applyBulkStatusUpdate() {
  if (state.selectedPkValues.size === 0) {
    showPopup("请先选择至少一行", false);
    return;
  }

  if (!state.columns.includes("status_id")) {
    showPopup("当前结果不包含 status_id 列", false);
    return;
  }

  const rawInput = (ui.bulkStatusInput.value || "").trim();
  if (!rawInput) {
    showPopup("请输入要批量设置的 status_id", false);
    return;
  }

  let parsed;
  try {
    parsed = parseForCommit(rawInput, "status_id");
  } catch (err) {
    showPopup(err.message, false);
    return;
  }

  const normalized = normalizeCellValue(parsed);
  let applied = 0;
  state.selectedPkValues.forEach((pkValue) => {
    const cell = ui.tableBody.querySelector(`td[data-pk-value="${pkValue}"][data-column="status_id"]`);
    if (!cell) {
      return;
    }
    cell.textContent = normalized;
    applyCellChange(pkValue, "status_id", normalized, cell);
    applied += 1;
  });

  showPopup(`已将 ${applied} 行的 status_id 设为 ${normalized}`);
}

function applyBulkAlbumNameReplace() {
  if (state.selectedPkValues.size === 0) {
    showPopup("请先选择至少一行", false);
    return;
  }

  if (!state.columns.includes("album_name")) {
    showPopup("当前结果不包含 album_name 列", false);
    return;
  }

  const findText = ui.bulkAlbumFindInput.value || "";
  const replaceText = ui.bulkAlbumReplaceInput.value || "";
  if (!findText) {
    showPopup("请先输入要替换的文本", false);
    return;
  }

  let touched = 0;
  let replacedRows = 0;
  state.selectedPkValues.forEach((pkValue) => {
    const cell = ui.tableBody.querySelector(`td[data-pk-value="${pkValue}"][data-column="album_name"]`);
    if (!cell) {
      return;
    }

    const current = cell.textContent || "";
    const next = current.split(findText).join(replaceText);
    if (next === current) {
      return;
    }

    cell.textContent = next;
    applyCellChange(pkValue, "album_name", next, cell);
    touched += 1;
    replacedRows += 1;
  });

  if (touched === 0) {
    showPopup("选中行中没有匹配到可替换内容", false);
    return;
  }

  showPopup(`已替换 ${replacedRows} 行的 album_name`);
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

function loadLastStatusIdPreference() {
  try {
    const raw = localStorage.getItem(LAST_STATUS_ID_KEY);
    return raw ? parseInt(raw, 10) : null;
  } catch (err) {
    console.warn("localStorage unavailable while loading last status_id", err);
    return null;
  }
}

function loadLastStudioNamePreference() {
  try {
    const raw = localStorage.getItem(LAST_STUDIO_NAME_KEY);
    return raw !== null ? String(raw) : null;
  } catch (err) {
    console.warn("localStorage unavailable while loading last studio_name", err);
    return null;
  }
}

function saveLastParamPreferences(statusId, studioName) {
  try {
    localStorage.setItem(LAST_STATUS_ID_KEY, String(statusId));
    localStorage.setItem(LAST_STUDIO_NAME_KEY, studioName);
  } catch (err) {
    console.warn("localStorage unavailable while saving preferences", err);
    setStatus("浏览器禁止 localStorage，无法记住上次查询参数");
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

function focusRowByWorkspaceAlbumId() {
  const raw = (ui.focusIdInput.value || "").trim();
  if (!raw) {
    showPopup("请输入要定位的 id", false);
    return;
  }

  const targetId = Number(raw);
  if (!Number.isInteger(targetId) || targetId <= 0) {
    showPopup("id 必须是正整数", false);
    return;
  }

  const targetRow = ui.tableBody.querySelector(`tr[data-pk-value="${targetId}"]`);
  if (!targetRow) {
    showPopup("id 不存在，未跳转", false);
    return;
  }

  targetRow.scrollIntoView({ block: "center", inline: "nearest" });
  clearRowSelection();
  setRowSelected(targetRow, true);

  const rowIndex = Number(targetRow.dataset.rowIndex);
  state.selectionAnchorRowIndex = Number.isFinite(rowIndex) ? rowIndex : null;
  updateSelectionCounter();

  const editableColumn = state.lastEditedColumn && isEditableColumn(state.lastEditedColumn)
    ? state.lastEditedColumn
    : state.columns.find((col) => isEditableColumn(col));

  if (!editableColumn) {
    return;
  }

  const targetCell = targetRow.querySelector(`td[data-column="${editableColumn}"]`);
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
    tr.dataset.pkValue = String(pkValue);
    tr.dataset.rowIndex = String(ui.tableBody.children.length);
    tr.addEventListener("click", onRowClick);

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
  updateSelectionCounter();
  scheduleTableWrapHeightUpdate();
}

function onCellBlur(event) {
  const cell = event.currentTarget;
  const pkValue = Number(cell.dataset.pkValue);
  const column = cell.dataset.column;
  const raw = cell.textContent ?? "";
  applyCellChange(pkValue, column, raw, cell);
}

async function loadSchema() {
  const data = await fetchJson(apiUrl("/api/schema?table=workspace_album"));
  state.schema = data.schema;
  state.pkColumn = getPkColumnFromSchema(state.schema);
}

async function loadOptions() {
  const data = await fetchJson(apiUrl("/api/options"));

  ui.statusSelect.innerHTML = "";
  data.statuses.forEach((s) => {
    const option = document.createElement("option");
    option.value = s.id;
    option.textContent = `${s.id} – ${s.name}`;
    option.title = s.description;
    ui.statusSelect.appendChild(option);
  });

  ui.studioSelect.innerHTML = "";
  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "（全部 Studio）";
  ui.studioSelect.appendChild(allOption);
  data.studios.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    ui.studioSelect.appendChild(option);
  });

  if (data.statuses.length === 0) {
    throw new Error("数据库中未找到 status 记录");
  }

  const savedStatusId = loadLastStatusIdPreference();
  if (savedStatusId !== null && data.statuses.some((s) => s.id === savedStatusId)) {
    ui.statusSelect.value = String(savedStatusId);
  }

  const savedStudioName = loadLastStudioNamePreference();
  if (savedStudioName !== null) {
    const exists = savedStudioName === "" || data.studios.includes(savedStudioName);
    if (exists) {
      ui.studioSelect.value = savedStudioName;
    }
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
  const statusId = parseInt(ui.statusSelect.value, 10);
  const studioName = ui.studioSelect.value;
  const label = studioName ? `status=${statusId}, studio=${studioName}` : `status=${statusId}, 全部 Studio`;
  setStatus(`正在加载 ${label} ...`);
  const data = await fetchJson(apiUrl("/api/run-query"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status_id: statusId, studio_name: studioName }),
  });

  state.queryName = studioName ? `status_${statusId}_${studioName}` : `status_${statusId}`;
  state.columns = data.columns;
  state.rows = data.rows;

  if (!state.columns.includes(state.pkColumn)) {
    throw new Error(`查询结果缺少主键列 ${state.pkColumn}，无法提交修改`);
  }

  hydrateOriginalRows(state.rows);
  resetPendingChanges();
  clearRowSelection();
  buildColumnPanel();
  buildTable();
  saveLastParamPreferences(statusId, studioName);
  setStatus(`已加载 ${label}，共 ${data.row_count} 行`);
  scheduleTableWrapHeightUpdate();
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
  const data = await fetchJson(apiUrl("/api/batch-update"), {
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

function syncRollbackModeUI() {
  const mode = ui.rollbackModeSelect.value;
  ui.rollbackTimestampInput.disabled = mode !== "timestamp";
  ui.rollbackTagInput.disabled = mode !== "tag";
}

async function createManualBackup() {
  const reason = (ui.backupReasonInput.value || "").trim();
  const tag = (ui.backupTagInput.value || "").trim();
  setStatus("正在创建手动快照...");
  const data = await fetchJson(apiUrl("/api/backup-now"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason, tag }),
  });
  const tagText = data.tag ? `，Tag: ${data.tag}` : "";
  showPopup(`快照已创建${tagText}`);
  setStatus(`手动快照已创建: ${data.snapshot}`);
}

async function cleanupBackups() {
  setStatus("正在清理过期快照...");
  const data = await fetchJson(apiUrl("/api/backups/cleanup"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  showPopup(`清理完成，删除 ${data.deleted.length} 个过期快照`);
  setStatus(`快照清理完成，删除 ${data.deleted.length} 个`);
}

async function rollbackNow() {
  const mode = ui.rollbackModeSelect.value;
  const payload = { mode };

  if (mode === "timestamp") {
    const isoTs = toIsoFromDateTimeLocal(ui.rollbackTimestampInput.value);
    if (!isoTs) {
      throw new Error("请选择有效的时间点");
    }
    payload.timestamp = isoTs;
  }

  if (mode === "tag") {
    const tag = (ui.rollbackTagInput.value || "").trim();
    if (!tag) {
      throw new Error("请输入 Tag");
    }
    payload.tag = tag;
  }

  setStatus("正在执行回滚...");
  const data = await fetchJson(apiUrl("/api/rollback"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  showPopup(`回滚完成，使用快照: ${data.selected_snapshot.filename}`);
  await loadQueryData();
  setStatus(`回滚完成: ${data.selected_snapshot.snapshot}`);
}

function bindEvents() {
  document.addEventListener("keydown", onGlobalKeyDown);

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
    scheduleTableWrapHeightUpdate();
  });

  ui.saveBtn.addEventListener("click", async () => {
    try {
      await submitChanges();
    } catch (err) {
      setStatus(`提交失败: ${err.message}`);
      showPopup(`提交失败: ${err.message}`, false);
    }
  });

  ui.bulkApplyStatusBtn.addEventListener("click", () => {
    applyBulkStatusUpdate();
  });

  ui.bulkApplyAlbumReplaceBtn.addEventListener("click", () => {
    applyBulkAlbumNameReplace();
  });

  ui.focusIdBtn.addEventListener("click", () => {
    focusRowByWorkspaceAlbumId();
  });

  ui.focusIdInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    focusRowByWorkspaceAlbumId();
  });

  ui.backupNowBtn.addEventListener("click", async () => {
    try {
      await createManualBackup();
    } catch (err) {
      setStatus(`手动备份失败: ${err.message}`);
      showPopup(`手动备份失败: ${err.message}`, false);
    }
  });

  ui.cleanupBackupsBtn.addEventListener("click", async () => {
    try {
      await cleanupBackups();
    } catch (err) {
      setStatus(`清理失败: ${err.message}`);
      showPopup(`清理失败: ${err.message}`, false);
    }
  });

  ui.rollbackModeSelect.addEventListener("change", () => {
    syncRollbackModeUI();
  });

  ui.rollbackNowBtn.addEventListener("click", async () => {
    try {
      await rollbackNow();
    } catch (err) {
      setStatus(`回滚失败: ${err.message}`);
      showPopup(`回滚失败: ${err.message}`, false);
    }
  });

  window.addEventListener("resize", () => {
    scheduleTableWrapHeightUpdate();
  });
}

async function init() {
  bindEvents();
  try {
    syncRollbackModeUI();
    await loadSchema();
    await loadOptions();
    await loadQueryData();
    scheduleTableWrapHeightUpdate();
  } catch (err) {
    setStatus(`初始化失败: ${err.message}`);
    showPopup(`初始化失败: ${err.message}`, false);
  }
}

init();
