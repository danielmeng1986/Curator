const WorkspacePage = {
  _selected: new Set(),
  _listState: { q: '', status_id: '', studio_name: '', primary_model: '', linked: '', limit: 50, offset: 0 },
  _statuses: [],

  async renderList(params) {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading…</div>';

    const btn = document.getElementById('pageActionBtn');
    btn.classList.add('hidden');

    try {
      const statusesData = await api.get('/statuses');
      this._statuses = statusesData.statuses || [];
      this._selected.clear();
      await this._loadList(el);
    } catch (e) {
      el.innerHTML = `<div class="error-msg">Error: ${esc(e.message)}</div>`;
    }
  },

  async _loadList(el) {
    const s = this._listState;
    const qs = new URLSearchParams();
    if (s.q) qs.set('q', s.q);
    if (s.status_id) qs.set('status_id', s.status_id);
    if (s.studio_name) qs.set('studio_name', s.studio_name);
    if (s.primary_model) qs.set('primary_model', s.primary_model);
    if (s.linked) qs.set('linked', s.linked);
    qs.set('limit', s.limit);
    qs.set('offset', s.offset);

    const data = await api.get('/workspace/albums?' + qs);
    const albums = data.albums || [];
    const total = data.total || 0;

    const statusOpts = this._statuses.map(st =>
      `<option value="${st.id}" ${String(s.status_id) === String(st.id) ? 'selected' : ''}>${esc(st.name)}</option>`).join('');

    const rows = albums.map(a => `
      <tr>
        <td class="col-check"><input type="checkbox" ${this._selected.has(a.id) ? 'checked' : ''} onchange="WorkspacePage._toggleSelect(${a.id}, this.checked)"></td>
        <td onclick="navigate('#/workspace/albums/${a.id}')" style="cursor:pointer">${esc(a.primary_model || '')}</td>
        <td onclick="navigate('#/workspace/albums/${a.id}')" style="cursor:pointer">${esc(a.studio_name || '')}</td>
        <td onclick="navigate('#/workspace/albums/${a.id}')" style="cursor:pointer">${esc(a.album_name || '')}</td>
        <td><span class="chip">${esc(a.status_name || '')}</span></td>
        <td style="font-size:.8rem;color:var(--ink-soft)">${a.album_id ? '<span class="chip chip-ok">Linked</span>' : '<span class="chip">Unlinked</span>'}</td>
        <td class="path-mono" style="font-size:.75rem;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(a.current_path || '')}</td>
      </tr>`).join('');

    const page = Math.floor(s.offset / s.limit) + 1;
    const totalPages = Math.ceil(total / s.limit) || 1;
    const selectedCount = this._selected.size;

    el.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">Workspace Albums <span style="font-weight:400;font-size:1rem;color:var(--ink-soft)">(${total})</span></h1>
      </div>
      <div class="filter-bar">
        <input type="search" id="wsQ" value="${esc(s.q)}" placeholder="Search…" style="min-width:180px">
        <select id="wsStatus"><option value="">All Statuses</option>${statusOpts}</select>
        <input id="wsStudio" value="${esc(s.studio_name)}" placeholder="Studio name…" style="width:140px">
        <input id="wsModel" value="${esc(s.primary_model)}" placeholder="Primary model…" style="width:140px">
        <select id="wsLinked">
          <option value="" ${!s.linked?'selected':''}>All</option>
          <option value="yes" ${s.linked==='yes'?'selected':''}>Linked</option>
          <option value="no" ${s.linked==='no'?'selected':''}>Unlinked</option>
        </select>
        <button class="btn btn-secondary btn-sm" onclick="WorkspacePage._applyFilter()">Filter</button>
      </div>
      <div class="batch-toolbar ${selectedCount === 0 ? 'hidden' : ''}" id="batchToolbar">
        <strong>${selectedCount} selected</strong>
        <select id="batchStatus">
          <option value="">— Set status —</option>
          ${this._statuses.map(st => `<option value="${st.id}">${esc(st.name)}</option>`).join('')}
        </select>
        <button class="btn btn-sm btn-primary" onclick="WorkspacePage._batchUpdate()">Apply</button>
        <button class="btn btn-sm btn-secondary" onclick="WorkspacePage._clearSelection()">Clear</button>
      </div>
      <div class="card table-wrap">
        <table><thead><tr>
          <th class="col-check"><input type="checkbox" id="selectAll" onchange="WorkspacePage._selectAll(this.checked)"></th>
          <th>Model</th><th>Studio</th><th>Album</th><th>Status</th><th>Linked</th><th>Path</th>
        </tr></thead>
        <tbody>${rows || '<tr><td colspan="7" style="text-align:center;color:var(--ink-soft)">No workspace albums</td></tr>'}</tbody>
        </table>
      </div>
      <div class="pagination">
        <button class="btn btn-secondary btn-sm" ${s.offset===0?'disabled':''} onclick="WorkspacePage._prevPage()">← Prev</button>
        <span class="page-info">Page ${page} / ${totalPages} · ${total} total</span>
        <button class="btn btn-secondary btn-sm" ${s.offset+s.limit>=total?'disabled':''} onclick="WorkspacePage._nextPage()">Next →</button>
      </div>
    `;

    // Wire filters
    let debounce;
    document.getElementById('wsQ').addEventListener('input', e => {
      clearTimeout(debounce);
      debounce = setTimeout(() => { this._listState.q = e.target.value; this._listState.offset = 0; this._loadList(el); }, 350);
    });
    ['wsStatus','wsLinked'].forEach(id => {
      document.getElementById(id)?.addEventListener('change', e => {
        if (id === 'wsStatus') this._listState.status_id = e.target.value;
        if (id === 'wsLinked') this._listState.linked = e.target.value;
      });
    });

    this._currentAlbums = albums;
  },

  _toggleSelect(id, checked) {
    if (checked) this._selected.add(id); else this._selected.delete(id);
    const toolbar = document.getElementById('batchToolbar');
    if (toolbar) {
      const count = this._selected.size;
      toolbar.classList.toggle('hidden', count === 0);
      const strong = toolbar.querySelector('strong');
      if (strong) strong.textContent = `${count} selected`;
    }
  },

  _selectAll(checked) {
    (this._currentAlbums || []).forEach(a => {
      if (checked) this._selected.add(a.id); else this._selected.delete(a.id);
    });
    document.querySelectorAll('tbody input[type=checkbox]').forEach(cb => { cb.checked = checked; });
    const toolbar = document.getElementById('batchToolbar');
    if (toolbar) {
      toolbar.classList.toggle('hidden', !checked || this._selected.size === 0);
      const strong = toolbar.querySelector('strong');
      if (strong) strong.textContent = `${this._selected.size} selected`;
    }
  },

  _clearSelection() {
    this._selected.clear();
    document.querySelectorAll('input[type=checkbox]').forEach(cb => { cb.checked = false; });
    document.getElementById('batchToolbar')?.classList.add('hidden');
  },

  async _batchUpdate() {
    const ids = [...this._selected];
    if (!ids.length) return;
    const statusId = document.getElementById('batchStatus')?.value;
    if (!statusId) { toast('Select a status to apply', 'error'); return; }

    const ok = await confirmDialog(`Apply status update to ${ids.length} item(s)?`);
    if (!ok) return;
    try {
      const res = await api.post('/workspace/albums/batch', { ids, changes: { status_id: parseInt(statusId) } });
      toast(`Updated ${res.updated || 0} items`);
      this._clearSelection();
      await this._loadList(document.getElementById('page-content'));
    } catch (e) {
      toast('Batch update failed: ' + e.message, 'error');
    }
  },

  _applyFilter() {
    this._listState.studio_name = document.getElementById('wsStudio')?.value || '';
    this._listState.primary_model = document.getElementById('wsModel')?.value || '';
    this._listState.status_id = document.getElementById('wsStatus')?.value || '';
    this._listState.linked = document.getElementById('wsLinked')?.value || '';
    this._listState.offset = 0;
    this._loadList(document.getElementById('page-content'));
  },
  _prevPage() { this._listState.offset = Math.max(0, this._listState.offset - this._listState.limit); this._loadList(document.getElementById('page-content')); },
  _nextPage() { this._listState.offset += this._listState.limit; this._loadList(document.getElementById('page-content')); },

  async renderDetail({ id }) {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading…</div>';

    try {
      const [d, statusesData] = await Promise.all([
        api.get(`/workspace/albums/${id}`),
        api.get('/statuses'),
      ]);
      const wa = d.album;
      const statuses = statusesData.statuses || [];

      const statusOpts = statuses.map(s =>
        `<option value="${s.id}" ${String(wa.status_id) === String(s.id) ? 'selected' : ''}>${esc(s.name)}</option>`).join('');

      el.innerHTML = `
        <div class="page-header">
          <h1 class="page-title">${esc(wa.album_name || 'Workspace Album')}</h1>
          <a href="#/workspace/albums" class="btn btn-secondary btn-sm">← Back</a>
        </div>
        <div class="card" style="padding:20px">
          <div class="form-section">
            <div class="form-section-title">Source Info</div>
            <div class="form-grid">
              <div class="form-field"><label>Primary Model</label><input id="wPrimaryModel" value="${esc(wa.primary_model || '')}"></div>
              <div class="form-field"><label>Studio Name</label><input id="wStudioName" value="${esc(wa.studio_name || '')}"></div>
              <div class="form-field"><label>Album Name</label><input id="wAlbumName" value="${esc(wa.album_name || '')}"></div>
              <div class="form-field form-field-full"><label>Additional Models</label><input id="wAddModels" value="${esc(wa.additional_models || '')}"></div>
              <div class="form-field form-field-full"><label>Current Path</label><input id="wCurrentPath" class="path-mono" value="${esc(wa.current_path || '')}"></div>
              <div class="form-field form-field-full"><label>Expected Path</label><input id="wExpectedPath" class="path-mono" value="${esc(wa.expected_path || '')}"></div>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">Review</div>
            <div class="form-grid">
              <div class="form-field">
                <label>Status</label>
                <select id="wStatus"><option value="">— none —</option>${statusOpts}</select>
              </div>
              <div class="form-field form-field-full"><label>Remark</label><textarea id="wRemark">${esc(wa.remark || '')}</textarea></div>
              <div class="form-field form-field-full"><label>AI Result</label><textarea id="wAiResult">${esc(wa.ai_result || '')}</textarea></div>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">Links</div>
            <div class="form-grid">
              <div class="form-field">
                <label>Belongs To (workspace album ID)</label>
                <input id="wBelongsTo" type="number" value="${wa.belongs_to_album_id ?? ''}">
              </div>
              <div class="form-field">
                <label>Linked Album ID</label>
                <input id="wAlbumId" type="number" value="${wa.album_id ?? ''}">
              </div>
            </div>
            ${wa.album_id ? `<p style="margin-top:8px;font-size:.88rem"><a href="#/albums/${wa.album_id}">→ View linked album #${wa.album_id}</a></p>` : ''}
          </div>

          <div class="record-details" style="margin-bottom:16px">
            <span class="record-detail-label">ID</span><span>${wa.id}</span>
            <span class="record-detail-label">Status</span><span>${esc(wa.status_name || '')}</span>
          </div>

          <div class="detail-actions">
            <button class="btn btn-primary" onclick="WorkspacePage._save(${id})">Save</button>
          </div>
        </div>
      `;
    } catch (e) {
      el.innerHTML = `<div class="error-msg">Error: ${esc(e.message)}</div>`;
    }
  },

  async _save(id) {
    const body = {
      primary_model: document.getElementById('wPrimaryModel')?.value || null,
      studio_name: document.getElementById('wStudioName')?.value || null,
      album_name: document.getElementById('wAlbumName')?.value || null,
      additional_models: document.getElementById('wAddModels')?.value || null,
      current_path: document.getElementById('wCurrentPath')?.value || null,
      expected_path: document.getElementById('wExpectedPath')?.value || null,
      status_id: document.getElementById('wStatus')?.value ? parseInt(document.getElementById('wStatus').value) : null,
      remark: document.getElementById('wRemark')?.value || null,
      ai_result: document.getElementById('wAiResult')?.value || null,
      belongs_to_album_id: document.getElementById('wBelongsTo')?.value ? parseInt(document.getElementById('wBelongsTo').value) : null,
      album_id: document.getElementById('wAlbumId')?.value ? parseInt(document.getElementById('wAlbumId').value) : null,
    };
    try {
      await api.put(`/workspace/albums/${id}`, body);
      toast('Saved');
    } catch (e) {
      toast('Save failed: ' + e.message, 'error');
    }
  },
};
