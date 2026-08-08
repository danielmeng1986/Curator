const ImportPage = {
  _step: 1,
  _items: [],
  _previews: [],
  _results: [],
  _config: null,
  _importAction: 'COPY',
  _previewToken: '',
  _previewUuid: '',
  _previewExpiresAt: '',
  _operationUuid: '',
  _executionSummary: null,

  async render() {
    const el = document.getElementById('page-content');
    document.getElementById('pageActionBtn').classList.add('hidden');
    try {
      this._config = await api.get('/config');
    } catch (error) {
      ui.renderPageError(el, error, 'Import');
      return;
    }
    this._step = 1;
    this._items = [];
    this._previews = [];
    this._results = [];
    this._importAction = 'COPY';
    this._previewToken = '';
    this._operationUuid = '';
    this._executionSummary = null;
    this._renderStep(el);
  },

  _renderStep(el = document.getElementById('page-content')) {
    el.innerHTML = `
      <div class="page-header"><h1 class="page-title">Import Albums</h1></div>
      <div class="wizard-steps">
        ${['Compose', 'Review', 'Preview', 'Confirm', 'Results'].map((s, i) => `
          <div class="wizard-step ${this._step === i + 1 ? 'active' : this._step > i + 1 ? 'done' : ''}">${s}</div>
        `).join('')}
      </div>
      <div id="stepContent"></div>`;
    const sc = document.getElementById('stepContent');
    ({ 1: this._renderStep1, 2: this._renderStep2, 3: this._renderStep3,
       4: this._renderStep4, 5: this._renderStep5 }[this._step]).call(this, sc);
  },

  _actionDescription(action = this._importAction) {
    return {
      COPY: 'Copy source files to the archive and preserve the source folder.',
      MOVE: 'Move source files to the archive; the source folder is removed after a successful move.',
      DATABASE_ONLY: 'Create database records only; no files are copied, moved, or deleted.',
    }[action] || '';
  },

  _renderStep1(el) {
    const defaultStudio = this._config?.default_import_studio || 'MetArt';
    const sourceRoot = this._config?.import_source_root || '';
    el.innerHTML = `
      <div class="card" style="padding:20px">
        <div class="form-section-title">Import settings</div>
        <div class="form-grid" style="margin-bottom:16px">
          <div class="form-field form-field-full">
            <label for="iAction">Import Action (applies to this batch)</label>
            <select id="iAction" onchange="ImportPage._setAction(this.value)">
              ${['COPY', 'MOVE', 'DATABASE_ONLY'].map(value => `<option value="${value}" ${value === this._importAction ? 'selected' : ''}>${value}</option>`).join('')}
            </select>
            <small id="iActionHelp">${esc(this._actionDescription())}</small>
          </div>
        </div>
        <div class="form-section-title">Add Album to Import Batch</div>
        <p style="font-size:.85rem;color:var(--ink-soft)">
          Folder name format: <code>ModelName in AlbumName</code><br>
          Source root: <span class="path-mono">${esc(sourceRoot)}</span>
        </p>
        <div class="form-grid" style="margin-bottom:12px">
          <div class="form-field form-field-full">
            <label for="iSourcePath">Source Path (full path to folder)</label>
            <input id="iSourcePath" class="path-mono" placeholder="${esc(sourceRoot)}/ModelName in AlbumName">
          </div>
          <div class="form-field"><label for="iStudio">Studio Name</label><input id="iStudio" value="${esc(defaultStudio)}"></div>
          <div class="form-field"><label for="iModel">Model Name (override)</label><input id="iModel" placeholder="Leave blank to parse from folder name"></div>
          <div class="form-field"><label for="iAlbum">Album Name (override)</label><input id="iAlbum" placeholder="Leave blank to parse from folder name"></div>
        </div>
        <button class="btn btn-primary" onclick="ImportPage._addItem()">+ Add to Batch</button>
      </div>
      ${this._items.length ? `
      <div class="card" style="padding:16px;margin-top:16px">
        <div class="form-section-title">Batch (${this._items.length} items)</div>
        <div class="table-wrap"><table><thead><tr><th>#</th><th>Source Path</th><th>Studio</th><th>Model</th><th>Album</th><th></th></tr></thead>
          <tbody>${this._items.map((item, i) => `<tr><td>${i + 1}</td>
            <td class="path-mono" style="font-size:.75rem">${esc(item.source_path || '')}</td><td>${esc(item.studio_name)}</td>
            <td>${esc(item.model_name || '(from folder)')}</td><td>${esc(item.album_name || '(from folder)')}</td>
            <td><button class="btn btn-sm btn-danger" aria-label="Remove item ${i + 1}" onclick="ImportPage._removeItem(${i})">×</button></td></tr>`).join('')}</tbody>
        </table></div>
        <div style="margin-top:12px"><button class="btn btn-primary" onclick="ImportPage._requestPreview()">Preview →</button></div>
      </div>` : ''}`;
  },

  _setAction(value) {
    this._importAction = value;
    const help = document.getElementById('iActionHelp');
    if (help) help.textContent = this._actionDescription();
  },

  _addItem() {
    const source_path = document.getElementById('iSourcePath')?.value?.trim() || '';
    const model_name = document.getElementById('iModel')?.value?.trim() || null;
    const album_name = document.getElementById('iAlbum')?.value?.trim() || null;
    if (!source_path && (!model_name || !album_name)) {
      toast('Enter a source path or both model and album names', 'error'); return;
    }
    const folder_name = source_path ? source_path.replace(/[\\/]+$/, '').split(/[\\/]/).pop() : '';
    this._items.push({
      source_path, folder_name,
      studio_name: document.getElementById('iStudio')?.value?.trim() || this._config?.default_import_studio || 'MetArt',
      model_name, album_name,
    });
    this._renderStep();
  },

  _removeItem(i) { this._items.splice(i, 1); this._renderStep(); },

  async _requestPreview(items = this._items) {
    if (!items.length) { toast('Select at least one valid item', 'error'); return false; }
    this._step = 2;
    this._renderStep();
    const result = await ui.runAction('import-preview', () => api.post('/import/preview', {
      items, import_action: this._importAction,
    }), { context: 'preview the Import' });
    if (!result.ok) { this._step = 1; this._renderStep(); return false; }
    const preview = result.value.preview;
    this._items = items;
    this._previews = (preview.items || []).map((item, index) => ({ ...item, selected: Boolean(item.can_import), sourceIndex: index }));
    this._previewToken = preview.preview_token || '';
    this._previewUuid = preview.preview_uuid || '';
    this._previewExpiresAt = preview.expires_at || '';
    this._step = 3;
    this._renderStep();
    return true;
  },

  _renderStep2(el) { el.innerHTML = '<div class="loading">Generating zero-write preview…</div>'; },

  _warnings(item) {
    const warnings = [];
    if (item.can_import && !item.model_exists) warnings.push('New Model');
    if (item.can_import && !item.studio_exists) warnings.push('New Studio');
    if (item.source_at_canonical_destination) warnings.push('Already canonical; database-only will be used');
    return warnings;
  },

  _renderStep3(el) {
    const valid = this._previews.filter(x => x.can_import);
    const errors = this._previews.filter(x => !x.can_import);
    const selected = valid.filter(x => x.selected).length;
    const rows = this._previews.map((item, i) => {
      const itemErrors = (item.validation_errors || []).map(error => error.message || error.code).filter(Boolean);
      const warnings = this._warnings(item);
      return `<tr class="${item.can_import ? (warnings.length ? 'import-preview-row-warn' : 'import-preview-row-ok') : 'import-preview-row-error'}">
        <td>${item.can_import ? `<input type="checkbox" aria-label="Select ${esc(item.album_name || `item ${i + 1}`)}" ${item.selected ? 'checked' : ''} onchange="ImportPage._togglePreview(${i}, this.checked)">` : '—'}</td>
        <td>${esc(item.model_name || '')}</td><td>${esc(item.studio_name || '')}</td><td>${esc(item.album_name || '')}</td>
        <td class="path-mono" style="font-size:.72rem">${esc(item.expected_path || '')}</td>
        <td>${warnings.map(w => `<span class="chip chip-warn">${esc(w)}</span>`).join(' ') || '—'}</td>
        <td>${itemErrors.map(e => `<span class="chip chip-error">${esc(e)}</span>`).join(' ') || '—'}</td>
      </tr>`;
    }).join('');
    el.innerHTML = `
      <div class="card" style="padding:16px;margin-bottom:16px">
        <div class="form-section-title">Preview Summary — ${esc(this._importAction)}</div>
        <p>${esc(this._actionDescription())}</p>
        <div class="stats-grid" style="grid-template-columns:repeat(3,1fr)">
          <div class="stat-card"><div class="stat-number">${this._previews.length}</div><div class="stat-label">Total</div></div>
          <div class="stat-card"><div class="stat-number" style="color:var(--ok)">${valid.length}</div><div class="stat-label">Valid</div></div>
          <div class="stat-card"><div class="stat-number" style="color:var(--error)">${errors.length}</div><div class="stat-label">Errors</div></div>
        </div>
        <p style="font-size:.78rem;color:var(--ink-soft)">Preview ${esc(this._previewUuid)} expires ${esc(this._previewExpiresAt)}. Preview does not change the database or filesystem.</p>
      </div>
      <div class="card table-wrap" style="margin-bottom:16px"><table style="font-size:.82rem"><thead><tr>
        <th>Select</th><th>Model</th><th>Studio</th><th>Album</th><th>Canonical destination</th><th>Warnings</th><th>Errors</th>
      </tr></thead><tbody>${rows}</tbody></table></div>
      <div style="display:flex;gap:10px;align-items:center">
        <button class="btn btn-secondary" onclick="ImportPage._backToStep1()">← Back</button>
        ${selected ? `<button class="btn btn-primary" onclick="ImportPage._reviewSelection()">Confirm selected (${selected}) →</button>` : '<span style="color:var(--error);font-size:.88rem">Select at least one valid item</span>'}
      </div>`;
  },

  _togglePreview(index, selected) { this._previews[index].selected = selected; this._renderStep(); },
  _backToStep1() { this._step = 1; this._previewToken = ''; this._renderStep(); },

  async _reviewSelection() {
    const selectedIndexes = this._previews.filter(item => item.can_import && item.selected).map(item => item.sourceIndex);
    if (!selectedIndexes.length) { toast('Select at least one valid item', 'error'); return; }
    if (selectedIndexes.length !== this._items.length) {
      const selectedItems = selectedIndexes.map(index => this._items[index]);
      if (!await this._requestPreview(selectedItems)) return;
    }
    this._step = 4;
    this._renderStep();
  },

  _renderStep4(el) {
    el.innerHTML = `
      <div class="card" style="padding:20px;border:2px solid var(--error)">
        <div class="form-section-title" style="color:var(--error)">Confirm ${esc(this._importAction)} Import</div>
        <p>You are about to import <strong>${this._previews.filter(x => x.can_import).length}</strong> album(s) from reviewed preview <span class="path-mono">${esc(this._previewUuid)}</span>.</p>
        <ul style="font-size:.88rem;margin:0 0 16px;padding-left:20px">
          <li>${esc(this._actionDescription())}</li><li>Create any missing Model, Studio, and Album records.</li>
          <li>Create an Operation record and report durable per-item outcomes.</li>
        </ul>
        <p style="color:var(--error);font-size:.88rem"><strong>The Backend will reject this execution if the source, configuration, database state, or preview identity has changed.</strong></p>
        <div style="display:flex;gap:10px;margin-top:16px">
          <button class="btn btn-secondary" onclick="ImportPage._goStep3()">← Back</button>
          <button id="executeImportBtn" class="btn btn-danger" onclick="ImportPage._executeImport(this)">Execute reviewed ${esc(this._importAction)} (${this._items.length} items)</button>
        </div>
      </div>`;
  },

  _goStep3() { this._step = 3; this._renderStep(); },

  async _executeImport(trigger) {
    const result = await ui.runAction('import-execute', () => api.post('/import/execute', {
      preview_token: this._previewToken,
    }), { trigger, context: 'execute the Import' });
    if (!result.ok) return;
    this._results = result.value.results || [];
    this._executionSummary = result.value.summary || {};
    this._operationUuid = result.value.operation_uuid || '';
    this._previewToken = '';
    this._step = 5;
    this._renderStep();
  },

  _renderStep5(el) {
    const summary = this._executionSummary || {};
    const rows = this._results.map((r, i) => {
      const state = r.needs_repair ? 'NeedsRepair' : r.skipped ? 'Skipped' : r.ok ? 'Succeeded' : 'Failed';
      const stateClass = r.ok ? 'chip-ok' : r.needs_repair ? 'chip-warn' : 'chip-error';
      return `<tr class="${r.ok ? 'import-preview-row-ok' : r.needs_repair ? 'import-preview-row-warn' : 'import-preview-row-error'}">
        <td>${i + 1}</td><td>${esc(r.model_name || '')}</td><td>${esc(r.studio_name || '')}</td><td>${esc(r.album_name || '')}</td>
        <td>${r.album_id ? `<a href="#/albums/${r.album_id}">Album #${r.album_id}</a>` : '—'}</td><td>${esc(r.effective_action || '—')}</td>
        <td><span class="chip ${stateClass}">${esc(state)}</span>${r.error ? ` ${esc(r.error)}` : ''}</td></tr>`;
    }).join('');
    el.innerHTML = `
      <div class="card" style="padding:16px;margin-bottom:16px"><div class="form-section-title">Import Results</div>
        <div class="stats-grid" style="grid-template-columns:repeat(4,1fr)">
          <div class="stat-card"><div class="stat-number">${summary.total ?? this._results.length}</div><div class="stat-label">Total</div></div>
          <div class="stat-card"><div class="stat-number" style="color:var(--ok)">${summary.created ?? 0}</div><div class="stat-label">Created</div></div>
          <div class="stat-card"><div class="stat-number">${summary.skipped ?? 0}</div><div class="stat-label">Skipped</div></div>
          <div class="stat-card"><div class="stat-number" style="color:var(--error)">${(summary.errors ?? 0) + (summary.needs_repair ?? 0)}</div><div class="stat-label">Attention</div></div>
        </div></div>
      <div class="card table-wrap" style="margin-bottom:16px"><table style="font-size:.85rem"><thead><tr>
        <th>#</th><th>Model</th><th>Studio</th><th>Album</th><th>Record</th><th>Action</th><th>Durable outcome</th>
      </tr></thead><tbody>${rows}</tbody></table></div>
      ${summary.needs_repair ? '<p class="alert alert-warning">One or more records were created but their filesystem work needs repair. Review the Operation; this UI has not attempted a repair.</p>' : ''}
      <div style="display:flex;gap:10px"><button class="btn btn-secondary" onclick="ImportPage.render()">Start New Import</button>
        ${this._operationUuid ? `<a href="#/operations/${esc(this._operationUuid)}" class="btn btn-primary">View Operation</a>` : '<a href="#/albums" class="btn btn-primary">View Albums</a>'}
      </div>`;
  },
};
