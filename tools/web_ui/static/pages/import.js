const ImportPage = {
  _step: 1,
  _items: [],        // draft items in step 2
  _previews: [],     // preview results from server
  _results: [],      // execute results
  _config: null,

  async render(params) {
    const el = document.getElementById('page-content');
    const btn = document.getElementById('pageActionBtn');
    btn.classList.add('hidden');

    try {
      const cfg = await api.get('/config');
      this._config = cfg;
    } catch { this._config = {}; }

    this._step = 1;
    this._items = [];
    this._previews = [];
    this._results = [];
    this._renderStep(el);
  },

  _renderStep(el) {
    if (!el) el = document.getElementById('page-content');
    el.innerHTML = `
      <div class="page-header"><h1 class="page-title">Import Albums</h1></div>
      <div class="wizard-steps">
        ${['Compose', 'Review', 'Preview', 'Confirm', 'Results'].map((s, i) => `
          <div class="wizard-step ${this._step === i+1 ? 'active' : this._step > i+1 ? 'done' : ''}">${s}</div>
        `).join('')}
      </div>
      <div id="stepContent"></div>
    `;
    const sc = document.getElementById('stepContent');
    switch (this._step) {
      case 1: this._renderStep1(sc); break;
      case 2: this._renderStep2(sc); break;
      case 3: this._renderStep3(sc); break;
      case 4: this._renderStep4(sc); break;
      case 5: this._renderStep5(sc); break;
    }
  },

  _renderStep1(el) {
    const defaultStudio = this._config?.default_import_studio || 'MetArt';
    const sourceRoot = this._config?.import_source_root || '';
    el.innerHTML = `
      <div class="card" style="padding:20px">
        <div class="form-section-title">Add Album to Import Batch</div>
        <p style="font-size:.85rem;color:var(--ink-soft)">
          Folder name format: <code>ModelName in AlbumName</code><br>
          Source root: <span class="path-mono">${esc(sourceRoot)}</span>
        </p>
        <div class="form-grid" style="margin-bottom:12px">
          <div class="form-field form-field-full">
            <label>Source Path (full path to folder)</label>
            <input id="iSourcePath" class="path-mono" placeholder="${esc(sourceRoot)}/ModelName in AlbumName">
          </div>
          <div class="form-field">
            <label>Studio Name</label>
            <input id="iStudio" value="${esc(defaultStudio)}">
          </div>
          <div class="form-field">
            <label>Model Name (override)</label>
            <input id="iModel" placeholder="Leave blank to parse from folder name">
          </div>
          <div class="form-field">
            <label>Album Name (override)</label>
            <input id="iAlbum" placeholder="Leave blank to parse from folder name">
          </div>
          <div class="form-field">
            <label>Keep source? (copy instead of move)</label>
            <select id="iKeep"><option value="0">No (move)</option><option value="1">Yes (copy)</option></select>
          </div>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn btn-primary" onclick="ImportPage._addItem()">+ Add to Batch</button>
        </div>
      </div>

      ${this._items.length > 0 ? `
      <div class="card" style="padding:16px;margin-top:16px">
        <div class="form-section-title">Batch (${this._items.length} items)</div>
        <div class="table-wrap">
          <table><thead><tr><th>#</th><th>Source Path</th><th>Studio</th><th>Model</th><th>Album</th><th></th></tr></thead>
          <tbody>${this._items.map((item, i) => `
            <tr>
              <td>${i+1}</td>
              <td class="path-mono" style="font-size:.75rem">${esc(item.source_path || item.folder_name || '')}</td>
              <td>${esc(item.studio_name || '')}</td>
              <td>${esc(item.model_name || '(from folder)')}</td>
              <td>${esc(item.album_name || '(from folder)')}</td>
              <td><button class="btn btn-sm btn-danger" onclick="ImportPage._removeItem(${i})">×</button></td>
            </tr>`).join('')}
          </tbody></table>
        </div>
        <div style="margin-top:12px">
          <button class="btn btn-primary" onclick="ImportPage._goStep2()">Preview →</button>
        </div>
      </div>` : ''}
    `;
  },

  _addItem() {
    const source_path = document.getElementById('iSourcePath')?.value?.trim();
    const studio_name = document.getElementById('iStudio')?.value?.trim() || this._config?.default_import_studio || 'MetArt';
    const model_name = document.getElementById('iModel')?.value?.trim() || null;
    const album_name = document.getElementById('iAlbum')?.value?.trim() || null;
    const keep_source = document.getElementById('iKeep')?.value === '1';

    if (!source_path && !model_name && !album_name) {
      toast('Enter a source path or model+album names', 'error'); return;
    }
    this._items.push({ source_path, studio_name, model_name, album_name, keep_source });
    this._renderStep(document.getElementById('page-content'));
  },

  _removeItem(i) {
    this._items.splice(i, 1);
    this._renderStep(document.getElementById('page-content'));
  },

  async _goStep2() {
    if (!this._items.length) { toast('Add at least one item', 'error'); return; }
    this._step = 2;
    this._renderStep();
    try {
      const res = await api.post('/import/preview', { items: this._items });
      this._previews = res.preview?.items || [];
      this._step = 3;
      this._renderStep();
    } catch (e) {
      toast('Preview failed: ' + e.message, 'error');
      this._step = 1;
      this._renderStep();
    }
  },

  _renderStep2(el) {
    el.innerHTML = '<div class="loading">Generating preview…</div>';
  },

  _renderStep3(el) {
    const items = this._previews;
    const errors = items.filter(x => !x.ok);
    const summary = {
      total: items.length,
      ok: items.filter(x => x.ok).length,
      errors: errors.length,
      new_models: items.filter(x => x.ok && x.will_create_model).length,
      new_studios: items.filter(x => x.ok && x.will_create_studio).length,
      new_albums: items.filter(x => x.ok && !x.album_exists).length,
    };

    const rows = items.map((item, i) => {
      const rowClass = !item.ok ? 'import-preview-row-error' :
        item.destination_exists ? 'import-preview-row-warn' : 'import-preview-row-ok';
      return `<tr class="${rowClass}">
        <td>${i+1}</td>
        <td>${esc(item.model_name || '')}</td>
        <td>${esc(item.studio_name || '')}</td>
        <td>${esc(item.album_name || '')}</td>
        <td>${item.ok ? (item.model_exists ? 'Existing' : '<span class="chip chip-warn">New</span>') : '—'}</td>
        <td>${item.ok ? (item.studio_exists ? 'Existing' : '<span class="chip chip-warn">New</span>') : '—'}</td>
        <td>${item.ok ? (item.album_exists ? '<span class="chip chip-warn">Exists</span>' : '<span class="chip chip-ok">New</span>') : '—'}</td>
        <td>${item.ok ? (item.destination_exists ? '<span class="chip chip-error">Exists!</span>' : '<span class="chip chip-ok">Clear</span>') : '—'}</td>
        <td>${item.ok ? '' : `<span class="chip chip-error">${esc(item.error || 'Error')}</span>`}</td>
      </tr>`;
    }).join('');

    el.innerHTML = `
      <div class="card" style="padding:16px;margin-bottom:16px">
        <div class="form-section-title">Preview Summary</div>
        <div class="stats-grid" style="grid-template-columns:repeat(auto-fill,minmax(130px,1fr))">
          <div class="stat-card"><div class="stat-number">${summary.total}</div><div class="stat-label">Total</div></div>
          <div class="stat-card"><div class="stat-number" style="color:var(--ok)">${summary.ok}</div><div class="stat-label">OK</div></div>
          <div class="stat-card"><div class="stat-number" style="color:var(--error)">${summary.errors}</div><div class="stat-label">Errors</div></div>
          <div class="stat-card"><div class="stat-number">${summary.new_models}</div><div class="stat-label">New Models</div></div>
          <div class="stat-card"><div class="stat-number">${summary.new_studios}</div><div class="stat-label">New Studios</div></div>
          <div class="stat-card"><div class="stat-number">${summary.new_albums}</div><div class="stat-label">New Albums</div></div>
        </div>
      </div>
      <div class="card table-wrap" style="margin-bottom:16px">
        <table style="font-size:.82rem"><thead><tr>
          <th>#</th><th>Model</th><th>Studio</th><th>Album</th><th>Model?</th><th>Studio?</th><th>Album?</th><th>Path?</th><th>Error</th>
        </tr></thead>
        <tbody>${rows}</tbody></table>
      </div>
      <div style="display:flex;gap:10px">
        <button class="btn btn-secondary" onclick="ImportPage._backToStep1()">← Back</button>
        ${summary.errors === 0 ?
          `<button class="btn btn-primary" onclick="ImportPage._goStep4()">Confirm Import →</button>` :
          `<span style="color:var(--error);font-size:.88rem">Fix errors before importing</span>`}
      </div>
    `;
  },

  _backToStep1() {
    this._step = 1;
    this._renderStep();
  },

  _goStep4() {
    this._step = 4;
    this._renderStep();
  },

  _renderStep4(el) {
    const items = this._previews.filter(x => x.ok);
    el.innerHTML = `
      <div class="card" style="padding:20px;border:2px solid var(--error)">
        <div class="form-section-title" style="color:var(--error)">⚠ Confirm Import</div>
        <p>You are about to import <strong>${items.length}</strong> album(s). This will:</p>
        <ul style="font-size:.88rem;margin:0 0 16px;padding-left:20px">
          <li>Create a database snapshot (safety backup)</li>
          <li>Create any new model/studio/album records</li>
          <li>Move (or copy) files to the archive directory</li>
        </ul>
        <p style="color:var(--error);font-size:.88rem"><strong>File moves cannot be automatically undone.</strong> A DB rollback is available if needed.</p>
        <div style="display:flex;gap:10px;margin-top:16px">
          <button class="btn btn-secondary" onclick="ImportPage._goStep3()">← Back</button>
          <button class="btn btn-danger" onclick="ImportPage._executeImport()">Execute Import (${items.length} items)</button>
        </div>
      </div>
    `;
  },

  _goStep3() {
    this._step = 3;
    this._renderStep();
  },

  async _executeImport() {
    const el = document.getElementById('stepContent');
    if (el) el.innerHTML = '<div class="loading">Importing… please wait…</div>';
    try {
      const res = await api.post('/import/execute', { items: this._items });
      this._results = res.results || [];
      this._step = 5;
      this._renderStep();
    } catch (e) {
      toast('Import failed: ' + e.message, 'error');
      this._step = 4;
      this._renderStep();
    }
  },

  _renderStep5(el) {
    const results = this._results;
    const success = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success).length;

    const rows = results.map((r, i) => `
      <tr class="${r.success ? 'import-preview-row-ok' : 'import-preview-row-error'}">
        <td>${i+1}</td>
        <td>${esc(r.model_name || '')}</td>
        <td>${esc(r.studio_name || '')}</td>
        <td>${r.album_id ? `<a href="#/albums/${r.album_id}">Album #${r.album_id}</a>` : '—'}</td>
        <td>${r.success ? '<span class="chip chip-ok">✓ OK</span>' : `<span class="chip chip-error">✗ ${esc(r.error || 'Failed')}</span>`}</td>
      </tr>`).join('');

    el.innerHTML = `
      <div class="card" style="padding:16px;margin-bottom:16px">
        <div class="form-section-title">Import Results</div>
        <div class="stats-grid" style="grid-template-columns:repeat(3,1fr)">
          <div class="stat-card"><div class="stat-number">${results.length}</div><div class="stat-label">Total</div></div>
          <div class="stat-card"><div class="stat-number" style="color:var(--ok)">${success}</div><div class="stat-label">Succeeded</div></div>
          <div class="stat-card"><div class="stat-number" style="color:var(--error)">${failed}</div><div class="stat-label">Failed</div></div>
        </div>
      </div>
      <div class="card table-wrap" style="margin-bottom:16px">
        <table style="font-size:.85rem"><thead><tr>
          <th>#</th><th>Model</th><th>Studio</th><th>Album</th><th>Result</th>
        </tr></thead>
        <tbody>${rows}</tbody></table>
      </div>
      <div style="display:flex;gap:10px">
        <button class="btn btn-secondary" onclick="ImportPage.render({})">Start New Import</button>
        <a href="#/albums" class="btn btn-primary">View Albums</a>
      </div>
    `;
  },
};
