const AlbumsPage = {
  _editModels: [],
  _editRelations: [],
  _listState: { q: '', studio_id: '', status_id: '', model_id: '', sort: 'updated_at', limit: 50, offset: 0 },

  async renderList(params) {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading…</div>';

    // Read hash params
    const hash = window.location.hash;
    const qm = hash.indexOf('?');
    if (qm !== -1) {
      const sp = new URLSearchParams(hash.slice(qm + 1));
      if (sp.get('q')) this._listState.q = sp.get('q');
    }

    const btn = document.getElementById('pageActionBtn');
    btn.textContent = '+ New Album';
    btn.classList.remove('hidden');
    btn.onclick = () => navigate('#/albums/new');

    try {
      const [statusesData, studiosData] = await Promise.all([
        api.get('/statuses'),
        api.get('/studios?limit=500'),
      ]);
      const statuses = statusesData.statuses || [];
      const studios = studiosData.studios || [];
      this._statuses = statuses;
      this._studios = studios;
      await this._loadList(el, statuses, studios);
    } catch (e) {
      el.innerHTML = `<div class="error-msg">Error: ${esc(e.message)}</div>`;
    }
  },

  async _loadList(el, statuses, studios) {
    const s = this._listState;
    const qs = new URLSearchParams({
      q: s.q, studio_id: s.studio_id, status_id: s.status_id,
      sort: s.sort, limit: s.limit, offset: s.offset,
    });
    if (s.model_id) qs.set('model_id', s.model_id);
    const data = await api.get('/albums?' + qs);
    const albums = data.albums || [];
    const total = data.total || 0;

    const statusOpts = statuses.map(s2 => `<option value="${s2.id}" ${String(s.status_id) === String(s2.id) ? 'selected' : ''}>${esc(s2.name)}</option>`).join('');
    const studioOpts = studios.map(s2 => `<option value="${s2.id}" ${String(s.studio_id) === String(s2.id) ? 'selected' : ''}>${esc(s2.name)}</option>`).join('');

    const rows = albums.map(a => `
      <tr onclick="navigate('#/albums/${a.id}')">
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
        <select id="albumSort">
          <option value="updated_at" ${s.sort==='updated_at'?'selected':''}>Updated</option>
          <option value="publish_date" ${s.sort==='publish_date'?'selected':''}>Published</option>
          <option value="capture_date" ${s.sort==='capture_date'?'selected':''}>Captured</option>
          <option value="title" ${s.sort==='title'?'selected':''}>Title</option>
          <option value="rating" ${s.sort==='rating'?'selected':''}>Rating</option>
        </select>
        <button class="btn btn-secondary btn-sm" onclick="AlbumsPage._applyFilter()">Filter</button>
      </div>
      <div class="card table-wrap">
        <table><thead><tr>
          <th>Title</th><th>Studio</th><th>Status</th><th>Models</th><th>Capture Date</th><th>Rating</th><th>Path</th>
        </tr></thead>
        <tbody>${rows || '<tr><td colspan="7" style="text-align:center;color:var(--ink-soft)">No albums found</td></tr>'}</tbody>
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
    document.getElementById('albumSort').addEventListener('change', e => { this._listState.sort = e.target.value; this._listState.offset = 0; });
  },

  _applyFilter() {
    this._listState.offset = 0;
    this._loadList(document.getElementById('page-content'), this._statuses || [], this._studios || []);
  },
  _prevPage() { this._listState.offset = Math.max(0, this._listState.offset - this._listState.limit); this._loadList(document.getElementById('page-content'), this._statuses || [], this._studios || []); },
  _nextPage() { this._listState.offset += this._listState.limit; this._loadList(document.getElementById('page-content'), this._statuses || [], this._studios || []); },

  async renderDetail({ id }) {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading…</div>';
    const isNew = !id;

    try {
      const [statusesData, studiosData, modelsData] = await Promise.all([
        api.get('/statuses'),
        api.get('/studios?limit=500'),
        api.get('/models?limit=1000'),
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
                <label>Rating (1–5)</label>
                <input id="fRating" type="number" min="1" max="5" value="${album?.rating ?? ''}">
              </div>
              <div class="form-field form-field-full">
                <label>Description</label>
                <textarea id="fDescription">${esc(album?.description || '')}</textarea>
              </div>
              <div class="form-field form-field-full">
                <label>Path</label>
                <input id="fPath" class="path-mono" value="${esc(album?.path || '')}">
              </div>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">Models</div>
            <div id="modelsSection"></div>
            <button class="btn btn-sm btn-secondary" style="margin-top:8px" onclick="AlbumsPage._openAddModel()">+ Add Model</button>
          </div>

          <div class="form-section">
            <div class="form-section-title">Relations</div>
            <div id="relationsSection"></div>
            <button class="btn btn-sm btn-secondary" style="margin-top:8px" onclick="AlbumsPage._openAddRelation()">+ Add Relation</button>
          </div>

          ${!isNew ? `
          <div class="form-section">
            <div class="form-section-title">Photos (${photos.length})</div>
            <div class="sub-table-section">
              ${photos.length ? `<div class="table-wrap"><table><thead><tr><th>Filename</th><th>Size</th><th>Captured</th><th></th></tr></thead>
              <tbody>${photos.map(p => `<tr>
                <td class="path-mono">${esc(p.filename)}</td>
                <td>${p.width && p.height ? `${p.width}×${p.height}` : ''}</td>
                <td>${esc(p.capture_time || '')}</td>
                <td><button class="btn btn-sm btn-danger" onclick="AlbumsPage._deletePhoto(${p.id})">×</button></td>
              </tr>`).join('')}</tbody></table></div>` : '<p style="color:var(--ink-soft);font-size:.88rem">No photos</p>'}
            </div>
          </div>` : ''}

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
            <button class="btn btn-primary" onclick="AlbumsPage._save()">Save</button>
            ${!isNew ? `<button class="btn btn-danger" onclick="AlbumsPage._delete(${id})">Delete Album</button>` : ''}
          </div>
        </div>
      `;

      this._renderModelsSection();
      this._renderRelationsSection();

    } catch (e) {
      el.innerHTML = `<div class="error-msg">Error: ${esc(e.message)}</div>`;
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
        <td><button class="btn btn-sm btn-danger" onclick="AlbumsPage._removeModel(${i})">×</button></td>
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
        <td><input style="width:100px" value="${esc(r.relation_type || '')}" onchange="AlbumsPage._editRelations[${i}].relation_type=this.value"></td>
        <td><input style="width:140px" value="${esc(r.remarks || '')}" onchange="AlbumsPage._editRelations[${i}].remarks=this.value"></td>
        <td><button class="btn btn-sm btn-danger" onclick="AlbumsPage._removeRelation(${i})">×</button></td>
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
        </div>
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

  _confirmAddModel() {
    const model_id = document.getElementById('mModelId').value;
    if (!model_id) { toast('Select a model', 'error'); return; }
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
    showModal(`
      <h3 class="modal-title">Add Relation</h3>
      <div class="form-grid">
        <div class="form-field form-field-full">
          <label>Related Album ID</label>
          <input id="rAlbumId" type="number" min="1" placeholder="Enter album ID">
        </div>
        <div class="form-field"><label>Type</label><input id="rType" value="BELONGS_TO"></div>
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
    if (!related_album_id) { toast('Enter album ID', 'error'); return; }
    this._editRelations.push({
      related_album_id: parseInt(related_album_id),
      related_title: `Album #${related_album_id}`,
      relation_type: document.getElementById('rType').value || 'BELONGS_TO',
      remarks: document.getElementById('rRemarks').value || null,
    });
    closeModal();
    this._renderRelationsSection();
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
      toast('Save failed: ' + e.message, 'error');
    }
  },

  async _delete(id) {
    const ok = await confirmDialog('Delete this album? This will also remove all its models, relations, and photos.');
    if (!ok) return;
    try {
      await api.del(`/albums/${id}`);
      toast('Album deleted');
      navigate('#/albums');
    } catch (e) {
      toast('Delete failed: ' + e.message, 'error');
    }
  },

  async _deletePhoto(photoId) {
    const ok = await confirmDialog('Delete this photo record?');
    if (!ok) return;
    try {
      await api.del(`/photos/${photoId}`);
      toast('Photo deleted');
      this.renderDetail({ id: this._currentId });
    } catch (e) {
      toast('Delete failed: ' + e.message, 'error');
    }
  },
};
