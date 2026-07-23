const ModelsPage = {
  _listState: { q: '', limit: 50, offset: 0 },

  async renderList(params) {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading…</div>';

    const btn = document.getElementById('pageActionBtn');
    btn.textContent = '+ New Model';
    btn.classList.remove('hidden');
    btn.onclick = () => navigate('#/models/new');

    await this._loadList(el);
  },

  async _loadList(el) {
    const s = this._listState;
    const qs = new URLSearchParams({ q: s.q, limit: s.limit, offset: s.offset });
    const data = await api.get('/models?' + qs);
    const models = data.models || [];
    const total = data.total || 0;

    const rows = models.map(m => `
      <tr onclick="navigate('#/models/${m.id}')">
        <td>${esc(m.display_name || '')}</td>
        <td>${esc(m.primary_name || '')}</td>
        <td>${esc(m.country || '')}</td>
        <td>${esc(m.ethnicity || '')}</td>
        <td>${esc(m.eye_color || '')}</td>
        <td>${esc(m.natural_hair_color || '')}</td>
        <td style="color:var(--ink-soft);font-size:.8rem">${esc(m.updated_at ? m.updated_at.slice(0,10) : '')}</td>
      </tr>`).join('');

    const page = Math.floor(s.offset / s.limit) + 1;
    const totalPages = Math.ceil(total / s.limit) || 1;

    el.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">Models <span style="font-weight:400;font-size:1rem;color:var(--ink-soft)">(${total})</span></h1>
      </div>
      <div class="filter-bar">
        <input type="search" id="modelQ" value="${esc(s.q)}" placeholder="Search by name…" style="min-width:220px">
        <button class="btn btn-secondary btn-sm" onclick="ModelsPage._applyFilter()">Search</button>
      </div>
      <div class="card table-wrap">
        <table><thead><tr>
          <th>Display Name</th><th>Primary Name</th><th>Country</th><th>Ethnicity</th><th>Eyes</th><th>Hair</th><th>Updated</th>
        </tr></thead>
        <tbody>${rows || '<tr><td colspan="7" style="text-align:center;color:var(--ink-soft)">No models found</td></tr>'}</tbody>
        </table>
      </div>
      <div class="pagination">
        <button class="btn btn-secondary btn-sm" ${s.offset===0?'disabled':''} onclick="ModelsPage._prevPage()">← Prev</button>
        <span class="page-info">Page ${page} / ${totalPages} · ${total} total</span>
        <button class="btn btn-secondary btn-sm" ${s.offset+s.limit>=total?'disabled':''} onclick="ModelsPage._nextPage()">Next →</button>
      </div>
    `;

    let debounce;
    document.getElementById('modelQ').addEventListener('input', e => {
      clearTimeout(debounce);
      debounce = setTimeout(() => { this._listState.q = e.target.value; this._listState.offset = 0; this._loadList(el); }, 350);
    });
  },

  _applyFilter() { this._listState.offset = 0; this._loadList(document.getElementById('page-content')); },
  _prevPage() { this._listState.offset = Math.max(0, this._listState.offset - this._listState.limit); this._loadList(document.getElementById('page-content')); },
  _nextPage() { this._listState.offset += this._listState.limit; this._loadList(document.getElementById('page-content')); },

  async renderDetail({ id }) {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading…</div>';
    const isNew = !id;

    try {
      let model = null, albums = [];
      if (!isNew) {
        const d = await api.get(`/models/${id}`);
        model = d.model;
        albums = d.albums || [];
      }

      const btn = document.getElementById('pageActionBtn');
      btn.classList.add('hidden');

      const albumRows = albums.map(a => `
        <tr onclick="navigate('#/albums/${a.id}')">
          <td>${esc(a.title || '')}</td>
          <td>${esc(a.studio_name || '')}</td>
          <td>${esc(a.capture_date || '')}</td>
          <td>${a.age_when_shot || ''}</td>
          <td>${esc(a.role || '')}</td>
        </tr>`).join('');

      el.innerHTML = `
        <div class="page-header">
          <h1 class="page-title">${isNew ? 'New Model' : esc(model.display_name || model.primary_name || 'Model')}</h1>
          <a href="#/models" class="btn btn-secondary btn-sm">← Back</a>
        </div>
        <div class="card" style="padding:20px">
          <div class="form-section">
            <div class="form-section-title">Identity</div>
            <div class="form-grid">
              <div class="form-field">
                <label>Display Name</label>
                <input id="fDisplayName" value="${esc(model?.display_name || '')}">
              </div>
              <div class="form-field">
                <label>Primary Name *</label>
                <input id="fPrimaryName" value="${esc(model?.primary_name || '')}">
              </div>
              <div class="form-field">
                <label>Country</label>
                <input id="fCountry" value="${esc(model?.country || '')}">
              </div>
              <div class="form-field">
                <label>Ethnicity</label>
                <input id="fEthnicity" value="${esc(model?.ethnicity || '')}">
              </div>
              <div class="form-field">
                <label>Eye Color</label>
                <input id="fEyeColor" value="${esc(model?.eye_color || '')}">
              </div>
              <div class="form-field">
                <label>Natural Hair Color</label>
                <input id="fHairColor" value="${esc(model?.natural_hair_color || '')}">
              </div>
              <div class="form-field form-field-full">
                <label>Description</label>
                <textarea id="fDescription">${esc(model?.description || '')}</textarea>
              </div>
            </div>
          </div>

          ${!isNew ? `
          <details style="margin-bottom:16px">
            <summary style="cursor:pointer;font-size:.85rem;color:var(--ink-soft);margin-bottom:8px">Record Details</summary>
            <div class="record-details">
              <span class="record-detail-label">ID</span><span>${model.id}</span>
              <span class="record-detail-label">UUID</span><span class="path-mono">${esc(model.uuid || '')}</span>
              <span class="record-detail-label">Created</span><span>${esc(model.created_at || '')}</span>
              <span class="record-detail-label">Updated</span><span>${esc(model.updated_at || '')}</span>
            </div>
          </details>` : ''}

          <div class="detail-actions">
            <button class="btn btn-primary" onclick="ModelsPage._save()">Save</button>
            ${!isNew ? `<button class="btn btn-danger" onclick="ModelsPage._delete(${id})">Delete Model</button>` : ''}
          </div>
        </div>

        ${!isNew ? `
        <div class="card" style="padding:16px;margin-top:16px">
          <div class="form-section-title">Albums featuring this model (${albums.length})</div>
          <div class="table-wrap">
            <table><thead><tr><th>Title</th><th>Studio</th><th>Capture Date</th><th>Age</th><th>Role</th></tr></thead>
            <tbody>${albumRows || '<tr><td colspan="5" style="text-align:center;color:var(--ink-soft)">No albums</td></tr>'}</tbody>
            </table>
          </div>
        </div>` : ''}
      `;
    } catch (e) {
      el.innerHTML = `<div class="error-msg">Error: ${esc(e.message)}</div>`;
    }
  },

  async _save() {
    const primary_name = document.getElementById('fPrimaryName')?.value?.trim();
    if (!primary_name) { toast('Primary name is required', 'error'); return; }
    const body = {
      display_name: document.getElementById('fDisplayName')?.value || null,
      primary_name,
      description: document.getElementById('fDescription')?.value || null,
      country: document.getElementById('fCountry')?.value || null,
      ethnicity: document.getElementById('fEthnicity')?.value || null,
      eye_color: document.getElementById('fEyeColor')?.value || null,
      natural_hair_color: document.getElementById('fHairColor')?.value || null,
    };
    try {
      const hash = window.location.hash;
      const m = hash.match(/#\/models\/(\d+)$/);
      if (m) {
        await api.put(`/models/${m[1]}`, body);
        toast('Model saved');
      } else {
        const res = await api.post('/models', body);
        toast('Model created');
        navigate(`#/models/${res.id}`);
      }
    } catch (e) {
      toast('Save failed: ' + e.message, 'error');
    }
  },

  async _delete(id) {
    const ok = await confirmDialog('Delete this model?');
    if (!ok) return;
    try {
      await api.del(`/models/${id}`);
      toast('Model deleted');
      navigate('#/models');
    } catch (e) {
      toast('Delete failed: ' + e.message, 'error');
    }
  },
};
