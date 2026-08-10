const AlbumsPage = {
  _editModels: [],
  _editRelations: [],
  _listState: { q: '', studio_id: '', status_id: '', model_id: '', rating_min: '', rating_max: '', capture_date_from: '', capture_date_to: '', publish_date_from: '', publish_date_to: '', sort: 'updated_at', limit: 50, offset: 0 },
  _selectedIds: new Set(),

  async renderList(params) {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading…</div>';

    // Read hash params
    const hash = window.location.hash;
    const qm = hash.indexOf('?');
    if (qm !== -1) {
      const sp = new URLSearchParams(hash.slice(qm + 1));
      Object.keys(this._listState).forEach(key => {
        if (sp.has(key)) this._listState[key] = ['limit', 'offset'].includes(key) ? Number(sp.get(key)) : sp.get(key);
      });
    }

    const btn = document.getElementById('pageActionBtn');
    btn.textContent = '+ New Album';
    btn.classList.remove('hidden');
    btn.onclick = () => navigate('#/albums/new');

    try {
      const [statusesData, studiosData, modelsData] = await Promise.all([
        api.get('/statuses'),
        api.get('/studios?limit=500'),
        api.get('/models?limit=1000'),
      ]);
      const statuses = statusesData.statuses || [];
      const studios = studiosData.studios || [];
      this._statuses = statuses;
      this._studios = studios;
      this._allModels = modelsData.models || [];
      await this._loadList(el, statuses, studios, this._allModels);
    } catch (e) {
      ui.renderPageError(el, e, 'Albums');
    }
  },

  async _loadList(el, statuses, studios, models = []) {
    const s = this._listState;
    const qs = new URLSearchParams({
      q: s.q, studio_id: s.studio_id, status_id: s.status_id,
      rating_min: s.rating_min, rating_max: s.rating_max,
      capture_date_from: s.capture_date_from, capture_date_to: s.capture_date_to,
      publish_date_from: s.publish_date_from, publish_date_to: s.publish_date_to,
      sort: s.sort, limit: s.limit, offset: s.offset,
    });
    if (s.model_id) qs.set('model_id', s.model_id);
    const data = await api.get('/albums?' + qs);
    const albums = data.albums || [];
    const total = data.total || 0;

    const statusOpts = statuses.map(s2 => `<option value="${s2.id}" ${String(s.status_id) === String(s2.id) ? 'selected' : ''}>${esc(s2.name)}</option>`).join('');
    const studioOpts = studios.map(s2 => `<option value="${s2.id}" ${String(s.studio_id) === String(s2.id) ? 'selected' : ''}>${esc(s2.name)}</option>`).join('');
    const modelOpts = models.map(m => `<option value="${m.id}" ${String(s.model_id) === String(m.id) ? 'selected' : ''}>${esc(m.display_name || m.primary_name)}</option>`).join('');

    const rows = albums.map(a => `
      <tr onclick="navigate('#/albums/${a.id}')">
        <td onclick="event.stopPropagation()"><input type="checkbox" aria-label="Select ${esc(a.title || 'Album')}" ${this._selectedIds.has(a.id) ? 'checked' : ''} onchange="AlbumsPage._toggleSelected(${a.id}, this.checked)"></td>
        <td>${esc(a.title || '')}</td>
        <td>${esc(a.studio_name || '')}</td>
        <td><span class="chip">${esc(a.status_name || '')}</span></td>
        <td style="color:var(--ink-soft);font-size:.8rem">${esc(a.model_names || '')}</td>
        <td>${esc(a.capture_date || '')}</td>
        <td>${a.rating != null ? '★'.repeat(Math.min(5, a.rating)) : ''}</td>
        <td class="path-mono">${a.path ? '📁' : ''}</td>
      </tr>`).join('');

    const page = Math.floor(s.offset / s.limit) + 1;
    const totalPages = Math.ceil(total / s.limit) || 1;

    el.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">Albums <span style="font-weight:400;font-size:1rem;color:var(--ink-soft)">(${total})</span></h1>
      </div>
      <div class="filter-bar">
        <input type="search" id="albumQ" value="${esc(s.q)}" placeholder="Search…" style="min-width:200px">
        <select id="albumStudio"><option value="">All Studios</option>${studioOpts}</select>
        <select id="albumStatus"><option value="">All Statuses</option>${statusOpts}</select>
        <select id="albumModel"><option value="">All Models</option>${modelOpts}</select>
        <input id="albumRatingMin" type="number" min="0" value="${esc(s.rating_min)}" placeholder="Min rating">
        <input id="albumRatingMax" type="number" min="0" value="${esc(s.rating_max)}" placeholder="Max rating">
        <label>Captured from <input id="albumCaptureFrom" type="date" value="${esc(s.capture_date_from)}"></label>
        <label>to <input id="albumCaptureTo" type="date" value="${esc(s.capture_date_to)}"></label>
        <label>Published from <input id="albumPublishFrom" type="date" value="${esc(s.publish_date_from)}"></label>
        <label>to <input id="albumPublishTo" type="date" value="${esc(s.publish_date_to)}"></label>
        <select id="albumSort">
          <option value="updated_at" ${s.sort==='updated_at'?'selected':''}>Updated</option>
          <option value="publish_date" ${s.sort==='publish_date'?'selected':''}>Published</option>
          <option value="capture_date" ${s.sort==='capture_date'?'selected':''}>Captured</option>
          <option value="title" ${s.sort==='title'?'selected':''}>Title</option>
          <option value="rating" ${s.sort==='rating'?'selected':''}>Rating</option>
        </select>
        <button class="btn btn-secondary btn-sm" onclick="AlbumsPage._applyFilter()">Filter</button>
        <button class="btn btn-primary btn-sm" data-required-scope="write" onclick="AlbumsPage._openBatch()">Batch edit selected</button>
      </div>
      <div class="card table-wrap">
        <table><thead><tr>
          <th></th><th>Title</th><th>Studio</th><th>Status</th><th>Models</th><th>Capture Date</th><th>Rating</th><th>Path</th>
        </tr></thead>
        <tbody>${rows || '<tr><td colspan="8" style="text-align:center;color:var(--ink-soft)">No albums found</td></tr>'}</tbody>
        </table>
      </div>
      <div class="pagination">
        <button class="btn btn-secondary btn-sm" ${s.offset === 0 ? 'disabled' : ''} onclick="AlbumsPage._prevPage()">← Prev</button>
        <span class="page-info">Page ${page} / ${totalPages} · ${total} total</span>
        <button class="btn btn-secondary btn-sm" ${s.offset + s.limit >= total ? 'disabled' : ''} onclick="AlbumsPage._nextPage()">Next →</button>
      </div>
    `;

    // Debounced search
    let debounce;
    document.getElementById('albumQ').addEventListener('input', e => {
      clearTimeout(debounce);
      debounce = setTimeout(() => { this._listState.q = e.target.value; this._listState.offset = 0; this._loadList(el, this._statuses, this._studios); }, 350);
    });
    document.getElementById('albumStudio').addEventListener('change', e => { this._listState.studio_id = e.target.value; this._listState.offset = 0; });
    document.getElementById('albumStatus').addEventListener('change', e => { this._listState.status_id = e.target.value; this._listState.offset = 0; });
    document.getElementById('albumModel').addEventListener('change', e => { this._listState.model_id = e.target.value; this._listState.offset = 0; });
    document.getElementById('albumSort').addEventListener('change', e => { this._listState.sort = e.target.value; this._listState.offset = 0; });
  },

  _syncListHash() {
    const qs = new URLSearchParams();
    Object.entries(this._listState).forEach(([key, value]) => { if (value !== '' && value !== 0) qs.set(key, value); });
    history.replaceState(null, '', `#/albums${qs.size ? `?${qs}` : ''}`);
  },

  _applyFilter() {
    Object.assign(this._listState, {
      q: document.getElementById('albumQ').value.trim(),
      studio_id: document.getElementById('albumStudio').value,
      status_id: document.getElementById('albumStatus').value,
      model_id: document.getElementById('albumModel').value,
      sort: document.getElementById('albumSort').value,
      rating_min: document.getElementById('albumRatingMin').value,
      rating_max: document.getElementById('albumRatingMax').value,
      capture_date_from: document.getElementById('albumCaptureFrom').value,
      capture_date_to: document.getElementById('albumCaptureTo').value,
      publish_date_from: document.getElementById('albumPublishFrom').value,
      publish_date_to: document.getElementById('albumPublishTo').value,
    });
    this._listState.offset = 0;
    this._syncListHash();
    this._loadList(document.getElementById('page-content'), this._statuses || [], this._studios || [], this._allModels || []);
  },
  _prevPage() { this._listState.offset = Math.max(0, this._listState.offset - this._listState.limit); this._syncListHash(); this._loadList(document.getElementById('page-content'), this._statuses || [], this._studios || [], this._allModels || []); },
  _nextPage() { this._listState.offset += this._listState.limit; this._syncListHash(); this._loadList(document.getElementById('page-content'), this._statuses || [], this._studios || [], this._allModels || []); },

  _toggleSelected(id, checked) { checked ? this._selectedIds.add(id) : this._selectedIds.delete(id); },

  _openBatch() {
    if (!this._selectedIds.size) { toast('Select at least one Album', 'error'); return; }
    const statusOpts = (this._statuses || []).map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');
    const studioOpts = (this._studios || []).map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');
    showModal(`
      <h3 class="modal-title">Batch edit ${this._selectedIds.size} Albums</h3>
      <div class="form-field"><label>Field</label><select id="batchField">
        <option value="status_id">Status</option><option value="studio_id">Studio</option><option value="rating">Rating</option>
      </select></div>
      <div class="form-field"><label>Value</label><select id="batchValue">${statusOpts}</select></div>
      <label><input type="checkbox" id="batchOverwrite"> Explicitly replace existing non-empty values</label>
      <div id="batchPreview"></div>
      <div class="modal-footer"><button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button class="btn btn-primary" id="batchPreviewBtn" onclick="AlbumsPage._previewBatch()">Review changes</button></div>
    `);
    document.getElementById('batchField').onchange = event => {
      const field = event.target.value;
      const value = document.getElementById('batchValue');
      if (field === 'status_id') value.outerHTML = `<select id="batchValue">${statusOpts}</select>`;
      else if (field === 'studio_id') value.outerHTML = `<select id="batchValue">${studioOpts}</select>`;
      else value.outerHTML = '<input id="batchValue" type="number" min="0">';
    };
  },

  async _previewBatch() {
    const field = document.getElementById('batchField').value;
    const raw = document.getElementById('batchValue').value;
    if (raw === '') { toast('Choose a batch value', 'error'); return; }
    const value = ['status_id', 'studio_id', 'rating'].includes(field) ? Number(raw) : raw;
    const result = await ui.runAction('album-batch-preview', () => api.post('/albums/batch/preview', {
      ids: [...this._selectedIds], changes: { [field]: value },
      overwrite_non_empty: document.getElementById('batchOverwrite').checked,
    }), { trigger: document.getElementById('batchPreviewBtn'), context: 'preview the Album batch' });
    if (!result.ok) return;
    this._batchPreviewToken = result.value.preview.preview_token;
    const summary = result.value.preview.summary;
    document.getElementById('batchPreview').innerHTML = `<div class="feedback ${summary.blocked ? 'feedback-conflict' : 'feedback-warning'}"><strong>${summary.eligible} eligible</strong> · ${summary.blocked} blocked by non-empty values</div>`;
    document.querySelector('.modal-footer').insertAdjacentHTML('beforeend', `<button class="btn btn-danger" id="batchExecuteBtn" ${summary.blocked ? 'disabled' : ''} onclick="AlbumsPage._executeBatch()">Execute reviewed batch</button>`);
  },

  async _executeBatch() {
    const result = await ui.runAction('album-batch-execute', () => api.post('/albums/batch/execute', {
      preview_token: this._batchPreviewToken,
    }), { trigger: document.getElementById('batchExecuteBtn'), context: 'execute the Album batch' });
    if (!result.ok) return;
    closeModal();
    this._selectedIds.clear();
    toast(`Updated ${result.value.result.summary.succeeded} Albums`);
    await this._loadList(document.getElementById('page-content'), this._statuses, this._studios, this._allModels);
  },

  async renderDetail({ id }) {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading…</div>';
    const isNew = !id;

    try {
      const [statusesData, studiosData, modelsData, albumsData] = await Promise.all([
        api.get('/statuses'),
        api.get('/studios?limit=500'),
        api.get('/models?limit=1000'),
        api.get('/albums?limit=500&sort=title'),
      ]);
      const statuses = statusesData.statuses || [];
      const studios = studiosData.studios || [];
      const allModels = modelsData.models || [];

      let album = null, models = [], relations = [], photos = [];
      if (!isNew) {
        const d = await api.get(`/albums/${id}`);
        album = d.album;
        models = d.models || [];
        relations = d.relations || [];
        photos = d.photos || [];
      }
      this._editModels = [...models];
      this._editRelations = [...relations];
      this._currentId = id;
      this._allModels = allModels;
      this._allAlbums = (albumsData.albums || []).filter(item => String(item.id) !== String(id));
      this._statuses = statuses;
      this._studios = studios;

      const statusOpts = statuses.map(s => `<option value="${s.id}" ${album && String(album.status_id) === String(s.id) ? 'selected' : ''}>${esc(s.name)}</option>`).join('');
      const studioOpts = studios.map(s => `<option value="${s.id}" ${album && String(album.studio_id) === String(s.id) ? 'selected' : ''}>${esc(s.name)}</option>`).join('');

      const btn = document.getElementById('pageActionBtn');
      btn.classList.add('hidden');

      el.innerHTML = `
        <div class="page-header">
          <h1 class="page-title">${isNew ? 'New Album' : esc(album.title || 'Album')}</h1>
          <a href="#/albums" class="btn btn-secondary btn-sm">← Back</a>
        </div>
        <div class="card" style="padding:20px">
          <div class="form-section">
            <div class="form-section-title">Core Fields</div>
            <div class="form-grid">
              <div class="form-field form-field-full">
                <label>Title *</label>
                <input id="fTitle" value="${esc(album?.title || '')}" placeholder="Album title">
              </div>
              <div class="form-field">
                <label>Studio</label>
                <select id="fStudio"><option value="">— none —</option>${studioOpts}</select>
                <button type="button" class="btn btn-secondary btn-sm" data-required-scope="write" onclick="AlbumsPage._openInlineStudio()">Create Studio</button>
              </div>
              <div class="form-field">
                <label>Status</label>
                <select id="fStatus"><option value="">— none —</option>${statusOpts}</select>
              </div>
              <div class="form-field">
                <label>Scene</label>
                <input id="fScene" value="${esc(album?.scene || '')}">
              </div>
              <div class="form-field">
                <label>Location</label>
                <input id="fLocation" value="${esc(album?.location || '')}">
              </div>
              <div class="form-field">
                <label>Capture Date</label>
                <input id="fCaptureDate" type="date" value="${esc(album?.capture_date || '')}">
              </div>
              <div class="form-field">
                <label>Publish Date</label>
                <input id="fPublishDate" type="date" value="${esc(album?.publish_date || '')}">
              </div>
              <div class="form-field">
                <label>Rating</label>
                <input id="fRating" type="number" min="0" value="${album?.rating ?? ''}">
              </div>
              <div class="form-field form-field-full">
                <label>Description</label>
                <textarea id="fDescription">${esc(album?.description || '')}</textarea>
              </div>
              <div class="form-field form-field-full">
                <label>Path</label>
                <input id="fPath" class="path-mono" value="${esc(album?.path || '')}">
                <button type="button" class="btn btn-secondary btn-sm" onclick="AlbumsPage._copyPath()">Copy path</button>
              </div>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">Models</div>
            <div id="modelsSection"></div>
            <button class="btn btn-sm btn-secondary" data-required-scope="write" style="margin-top:8px" onclick="AlbumsPage._openAddModel()">+ Add Model</button>
          </div>

          <div class="form-section">
            <div class="form-section-title">Belongs to / Related Releases</div>
            <div id="relationsSection"></div>
            <button class="btn btn-sm btn-secondary" data-required-scope="write" style="margin-top:8px" onclick="AlbumsPage._openAddRelation()">+ Add Relation</button>
          </div>

          ${!isNew ? `
          <details style="margin-bottom:16px">
            <summary style="cursor:pointer;font-size:.85rem;color:var(--ink-soft);margin-bottom:8px">Record Details</summary>
            <div class="record-details">
              <span class="record-detail-label">ID</span><span>${album.id}</span>
              <span class="record-detail-label">UUID</span><span class="path-mono">${esc(album.uuid || '')}</span>
              <span class="record-detail-label">Created</span><span>${esc(album.created_at || '')}</span>
              <span class="record-detail-label">Updated</span><span>${esc(album.updated_at || '')}</span>
            </div>
          </details>` : ''}

          <div class="detail-actions">
            <button class="btn btn-primary" data-required-scope="write" onclick="AlbumsPage._save()">Save</button>
            ${!isNew ? '<span class="feedback-reference">Album removal will be available through Digital Asset Trash.</span>' : ''}
          </div>
        </div>
      `;

      this._renderModelsSection();
      this._renderRelationsSection();

    } catch (e) {
      ui.renderPageError(el, e, 'this Album');
    }
  },

  _renderModelsSection() {
    const el = document.getElementById('modelsSection');
    if (!el) return;
    if (!this._editModels.length) { el.innerHTML = '<p style="color:var(--ink-soft);font-size:.88rem">No models added</p>'; return; }
    el.innerHTML = `<div class="table-wrap"><table><thead><tr>
      <th>Model</th><th>Age When Shot</th><th>Role</th><th>Remarks</th><th></th>
    </tr></thead><tbody>${this._editModels.map((m, i) => `
      <tr>
        <td>${esc(m.model_name || m.display_name || m.primary_name || `Model #${m.model_id}`)}</td>
        <td><input style="width:60px" value="${esc(m.age_when_shot || '')}" onchange="AlbumsPage._editModels[${i}].age_when_shot=this.value"></td>
        <td><input style="width:90px" value="${esc(m.role || '')}" onchange="AlbumsPage._editModels[${i}].role=this.value"></td>
        <td><input style="width:140px" value="${esc(m.remarks || '')}" onchange="AlbumsPage._editModels[${i}].remarks=this.value"></td>
        <td><button class="btn btn-sm btn-danger" data-required-scope="write" onclick="AlbumsPage._removeModel(${i})">×</button></td>
      </tr>`).join('')}</tbody></table></div>`;
  },

  _renderRelationsSection() {
    const el = document.getElementById('relationsSection');
    if (!el) return;
    if (!this._editRelations.length) { el.innerHTML = '<p style="color:var(--ink-soft);font-size:.88rem">No relations</p>'; return; }
    el.innerHTML = `<div class="table-wrap"><table><thead><tr>
      <th>Related Album</th><th>Type</th><th>Remarks</th><th></th>
    </tr></thead><tbody>${this._editRelations.map((r, i) => `
      <tr>
        <td>${esc(r.related_title || `Album #${r.related_album_id}`)}</td>
        <td><input style="width:100px" value="${esc(r.relation_type || 'BELONGS_TO')}" readonly></td>
        <td><input style="width:140px" value="${esc(r.remarks || '')}" onchange="AlbumsPage._editRelations[${i}].remarks=this.value"></td>
        <td><button class="btn btn-sm btn-danger" data-required-scope="write" onclick="AlbumsPage._removeRelation(${i})">×</button></td>
      </tr>`).join('')}</tbody></table></div>`;
  },

  _removeModel(i) { this._editModels.splice(i, 1); this._renderModelsSection(); },
  _removeRelation(i) { this._editRelations.splice(i, 1); this._renderRelationsSection(); },

  _openAddModel() {
    const opts = (this._allModels || []).map(m =>
      `<option value="${m.id}">${esc(m.display_name || m.primary_name)}</option>`).join('');
    showModal(`
      <h3 class="modal-title">Add Model</h3>
      <div class="form-grid">
        <div class="form-field form-field-full">
          <label>Model</label>
          <select id="mModelId"><option value="">— select —</option>${opts}</select>
          <button type="button" class="btn btn-secondary btn-sm" onclick="AlbumsPage._showInlineModelFields()">Create Model</button>
        </div>
        <div id="inlineModelFields" class="form-field form-field-full hidden"><label>New Model primary name</label><input id="mNewPrimaryName"></div>
        <div class="form-field"><label>Age When Shot</label><input id="mAge" type="number" min="18"></div>
        <div class="form-field"><label>Role</label><input id="mRole"></div>
        <div class="form-field form-field-full"><label>Remarks</label><input id="mRemarks"></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="AlbumsPage._confirmAddModel()">Add</button>
      </div>
    `);
  },

  _showInlineModelFields() { document.getElementById('inlineModelFields').classList.remove('hidden'); },

  async _confirmAddModel() {
    let model_id = document.getElementById('mModelId').value;
    const newName = document.getElementById('mNewPrimaryName')?.value?.trim();
    if (!model_id && newName) {
      const result = await ui.runAction('inline-model-create', () => api.post('/models', { primary_name: newName, display_name: newName }), { context: 'create the Model' });
      if (!result.ok) return;
      const created = result.value.model;
      this._allModels.push(created);
      model_id = String(created.id);
    }
    if (!model_id) { toast('Select a model', 'error'); return; }
    if (this._editModels.some(item => String(item.model_id) === model_id)) { toast('This Model is already linked', 'error'); return; }
    const m = (this._allModels || []).find(x => String(x.id) === model_id);
    this._editModels.push({
      model_id: parseInt(model_id),
      model_name: m ? (m.display_name || m.primary_name) : '',
      age_when_shot: document.getElementById('mAge').value || null,
      role: document.getElementById('mRole').value || null,
      remarks: document.getElementById('mRemarks').value || null,
    });
    closeModal();
    this._renderModelsSection();
  },

  _openAddRelation() {
    const opts = (this._allAlbums || []).map(a => `<option value="${a.id}">${esc(a.title)}${a.studio_name ? ` · ${esc(a.studio_name)}` : ''}</option>`).join('');
    showModal(`
      <h3 class="modal-title">Add Relation</h3>
      <div class="form-grid">
        <div class="form-field form-field-full">
          <label>Related Album</label>
          <select id="rAlbumId"><option value="">— select by title —</option>${opts}</select>
        </div>
        <div class="form-field"><label>Type</label><input id="rType" value="BELONGS_TO" readonly></div>
        <div class="form-field form-field-full"><label>Remarks</label><input id="rRemarks"></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="AlbumsPage._confirmAddRelation()">Add</button>
      </div>
    `);
  },

  _confirmAddRelation() {
    const related_album_id = document.getElementById('rAlbumId').value;
    if (!related_album_id) { toast('Select a related Album', 'error'); return; }
    if (String(this._currentId) === related_album_id) { toast('An Album cannot relate to itself', 'error'); return; }
    if (this._editRelations.some(item => String(item.related_album_id) === related_album_id && (item.relation_type || 'BELONGS_TO') === 'BELONGS_TO')) { toast('This Album relationship already exists', 'error'); return; }
    const related = (this._allAlbums || []).find(item => String(item.id) === related_album_id);
    this._editRelations.push({
      related_album_id: parseInt(related_album_id),
      related_title: related?.title || `Album #${related_album_id}`,
      relation_type: document.getElementById('rType').value || 'BELONGS_TO',
      remarks: document.getElementById('rRemarks').value || null,
    });
    closeModal();
    this._renderRelationsSection();
  },

  _openInlineStudio() {
    showModal(`
      <h3 class="modal-title">Create Studio</h3>
      <div class="form-field"><label>Name</label><input id="inlineStudioName"></div>
      <div class="form-field"><label>Website</label><input id="inlineStudioWebsite" type="url"></div>
      <div class="modal-footer"><button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button class="btn btn-primary" id="inlineStudioCreate" onclick="AlbumsPage._createInlineStudio()">Create and select</button></div>
    `);
  },

  async _copyPath() {
    const value = document.getElementById('fPath')?.value || '';
    if (!value) { toast('No path to copy', 'warning'); return; }
    try { await navigator.clipboard.writeText(value); toast('Path copied'); }
    catch { toast('This browser could not copy the path', 'error'); }
  },

  async _createInlineStudio() {
    const name = document.getElementById('inlineStudioName').value.trim();
    if (!name) { toast('Studio name is required', 'error'); return; }
    const result = await ui.runAction('inline-studio-create', () => api.post('/studios', {
      name, website: document.getElementById('inlineStudioWebsite').value || null, media_scope: 'p',
    }), { trigger: document.getElementById('inlineStudioCreate'), context: 'create the Studio' });
    if (!result.ok) return;
    const studio = result.value.studio;
    this._studios.push(studio);
    const select = document.getElementById('fStudio');
    select.insertAdjacentHTML('beforeend', `<option value="${studio.id}">${esc(studio.name)}</option>`);
    select.value = String(studio.id);
    closeModal();
  },

  async _save() {
    const title = document.getElementById('fTitle')?.value?.trim();
    if (!title) { toast('Title is required', 'error'); return; }

    const body = {
      title,
      studio_id: document.getElementById('fStudio')?.value ? parseInt(document.getElementById('fStudio').value) : null,
      status_id: document.getElementById('fStatus')?.value ? parseInt(document.getElementById('fStatus').value) : null,
      scene: document.getElementById('fScene')?.value || null,
      location: document.getElementById('fLocation')?.value || null,
      capture_date: document.getElementById('fCaptureDate')?.value || null,
      publish_date: document.getElementById('fPublishDate')?.value || null,
      rating: document.getElementById('fRating')?.value ? parseInt(document.getElementById('fRating').value) : null,
      description: document.getElementById('fDescription')?.value || null,
      path: document.getElementById('fPath')?.value || null,
      models: this._editModels.map(m => ({ model_id: m.model_id, age_when_shot: m.age_when_shot || null, role: m.role || null, remarks: m.remarks || null })),
      relations: this._editRelations.map(r => ({ related_album_id: r.related_album_id, relation_type: r.relation_type || null, remarks: r.remarks || null })),
    };

    try {
      if (this._currentId) {
        await api.put(`/albums/${this._currentId}`, body);
        toast('Album saved');
      } else {
        const res = await api.post('/albums', body);
        toast('Album created');
        navigate(`#/albums/${res.id}`);
      }
    } catch (e) {
      ui.toastError(e, 'save the Album');
    }
  },

};
