const StudiosPage = {
  _listState: { q: '', limit: 50, offset: 0 },

  async renderList(params) {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading…</div>';

    const btn = document.getElementById('pageActionBtn');
    btn.textContent = '+ New Studio';
    btn.classList.remove('hidden');
    btn.onclick = () => navigate('#/studios/new');

    const query = new URLSearchParams((window.location.hash.split('?')[1] || ''));
    this._listState.q = query.get('q') || '';
    this._listState.offset = Math.max(0, Number(query.get('offset') || 0));
    await this._loadList(el);
  },

  async _loadList(el) {
    const s = this._listState;
    const qs = new URLSearchParams({ q: s.q, limit: s.limit, offset: s.offset });
    const data = await api.get('/studios?' + qs);
    const studios = data.studios || [];
    const total = data.total || 0;

    const rows = studios.map(st => `
      <tr onclick="navigate('#/studios/${st.id}')">
        <td>${esc(st.name || '')}</td>
        <td>${esc(st.media_scope || '')}</td>
        <td><a href="${esc(st.website || '')}" target="_blank" onclick="event.stopPropagation()">${esc(st.website || '')}</a></td>
        <td style="color:var(--ink-soft);font-size:.8rem;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(st.description || '')}</td>
        <td style="color:var(--ink-soft);font-size:.8rem">${esc(st.updated_at ? st.updated_at.slice(0,10) : '')}</td>
      </tr>`).join('');

    const page = Math.floor(s.offset / s.limit) + 1;
    const totalPages = Math.ceil(total / s.limit) || 1;

    el.innerHTML = `
      <div class="page-header">
        <h1 class="page-title">Studios <span style="font-weight:400;font-size:1rem;color:var(--ink-soft)">(${total})</span></h1>
      </div>
      <div class="filter-bar">
        <input type="search" id="studioQ" value="${esc(s.q)}" placeholder="Search by name…" style="min-width:220px">
        <button class="btn btn-secondary btn-sm" onclick="StudiosPage._applyFilter()">Search</button>
      </div>
      <div class="card table-wrap">
        <table><thead><tr>
          <th>Name</th><th>Scope</th><th>Website</th><th>Description</th><th>Updated</th>
        </tr></thead>
        <tbody>${rows || '<tr><td colspan="5" style="text-align:center;color:var(--ink-soft)">No studios found</td></tr>'}</tbody>
        </table>
      </div>
      <div class="pagination">
        <button class="btn btn-secondary btn-sm" ${s.offset===0?'disabled':''} onclick="StudiosPage._prevPage()">← Prev</button>
        <span class="page-info">Page ${page} / ${totalPages} · ${total} total</span>
        <button class="btn btn-secondary btn-sm" ${s.offset+s.limit>=total?'disabled':''} onclick="StudiosPage._nextPage()">Next →</button>
      </div>
    `;

    let debounce;
    document.getElementById('studioQ').addEventListener('input', e => {
      clearTimeout(debounce);
      debounce = setTimeout(() => { this._listState.q = e.target.value; this._listState.offset = 0; this._syncListHash(); this._loadList(el); }, 350);
    });
  },

  _syncListHash() { const q = new URLSearchParams(); if (this._listState.q) q.set('q', this._listState.q); if (this._listState.offset) q.set('offset', this._listState.offset); history.replaceState(null, '', `#/studios${q.size ? `?${q}` : ''}`); },
  _applyFilter() { this._listState.offset = 0; this._syncListHash(); this._loadList(document.getElementById('page-content')); },
  _prevPage() { this._listState.offset = Math.max(0, this._listState.offset - this._listState.limit); this._syncListHash(); this._loadList(document.getElementById('page-content')); },
  _nextPage() { this._listState.offset += this._listState.limit; this._syncListHash(); this._loadList(document.getElementById('page-content')); },

  async renderDetail({ id }) {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading…</div>';
    const isNew = !id;

    try {
      let studio = null, albums = [];
      if (!isNew) {
        const d = await api.get(`/studios/${id}`);
        studio = d.studio;
        albums = d.albums || [];
      }

      const btn = document.getElementById('pageActionBtn');
      btn.classList.add('hidden');

      const albumRows = albums.map(a => `
        <tr onclick="navigate('#/albums/${a.id}')">
          <td>${esc(a.title || '')}</td>
          <td>${esc(a.publish_date || '')}</td>
          <td>${esc(a.capture_date || '')}</td>
          <td>${a.rating != null ? '★'.repeat(Math.min(5, a.rating)) : ''}</td>
          <td><span class="chip">${esc(a.status_name || '')}</span></td>
        </tr>`).join('');

      el.innerHTML = `
        <div class="page-header">
          <h1 class="page-title">${isNew ? 'New Studio' : esc(studio.name || 'Studio')}</h1>
          <a href="#/studios" class="btn btn-secondary btn-sm">← Back</a>
        </div>
        <div class="card" style="padding:20px">
          <div class="form-section">
            <div class="form-section-title">Studio Details</div>
            <div class="form-grid">
              <div class="form-field">
                <label>Name *</label>
                <input id="fName" value="${esc(studio?.name || '')}">
              </div>
              <div class="form-field">
                <label>Media Scope</label>
                <select id="fScope">
                  <option value="p" ${studio?.media_scope === 'p' ? 'selected' : ''}>p (photos)</option>
                  <option value="v" ${studio?.media_scope === 'v' ? 'selected' : ''}>v (video)</option>
                  <option value="p+v" ${studio?.media_scope === 'p+v' ? 'selected' : ''}>p+v (both)</option>
                </select>
              </div>
              <div class="form-field form-field-full">
                <label>Website</label>
                <input id="fWebsite" type="url" value="${esc(studio?.website || '')}" placeholder="https://…">
              </div>
              <div class="form-field form-field-full">
                <label>Description</label>
                <textarea id="fDescription">${esc(studio?.description || '')}</textarea>
              </div>
            </div>
          </div>

          ${!isNew ? `
          <details style="margin-bottom:16px">
            <summary style="cursor:pointer;font-size:.85rem;color:var(--ink-soft);margin-bottom:8px">Record Details</summary>
            <div class="record-details">
              <span class="record-detail-label">ID</span><span>${studio.id}</span>
              <span class="record-detail-label">UUID</span><span class="path-mono">${esc(studio.uuid || '')}</span>
              <span class="record-detail-label">Created</span><span>${esc(studio.created_at || '')}</span>
              <span class="record-detail-label">Updated</span><span>${esc(studio.updated_at || '')}</span>
            </div>
          </details>` : ''}

          <div class="detail-actions">
            <button class="btn btn-primary" data-required-scope="write" onclick="StudiosPage._save()">Save</button>
            ${!isNew ? `<button class="btn btn-danger" data-required-scope="write" onclick="StudiosPage._delete(${id})">Delete Studio</button>` : ''}
          </div>
        </div>

        ${!isNew ? `
        <div class="card" style="padding:16px;margin-top:16px">
          <div class="form-section-title">Albums from this studio (${albums.length})</div>
          <div class="table-wrap">
            <table><thead><tr><th>Title</th><th>Published</th><th>Captured</th><th>Rating</th><th>Status</th></tr></thead>
            <tbody>${albumRows || '<tr><td colspan="5" style="text-align:center;color:var(--ink-soft)">No albums</td></tr>'}</tbody>
            </table>
          </div>
        </div>` : ''}
      `;
      this._bindDraft(id, studio?.updated_at || null);
    } catch (e) {
      ui.renderPageError(el, e, 'this Studio');
    }
  },

  _draftKey(id = null) { return `entity.studio.${id || 'new'}`; },
  _draftBody() { return { name:fName.value, scope:fScope.value, website:fWebsite.value, description:fDescription.value }; },
  _bindDraft(id, updatedAt) {
    const key=this._draftKey(id); const saved=ui.loadDraft(key);
    if(saved && (!updatedAt || saved.metadata?.updatedAt===updatedAt)) { const d=saved.data;fName.value=d.name||'';fScope.value=d.scope||'p';fWebsite.value=d.website||'';fDescription.value=d.description||'';ui.markDirty(key,'this Studio',()=>ui.clearDraft(key));toast('Restored the Studio draft saved in this browser.','warning'); }
    else if(saved){ui.clearDraft(key);toast('An older Studio draft was discarded because the record changed.','warning');}
    document.querySelector('.card').addEventListener('input',()=>{ui.saveDraft(key,this._draftBody(),{updatedAt});ui.markDirty(key,'this Studio',()=>ui.clearDraft(key));});
  },

  async _save() {
    const name = document.getElementById('fName')?.value?.trim();
    if (!name) { toast('Name is required', 'error'); return; }
    const body = {
      name,
      media_scope: document.getElementById('fScope')?.value || 'p',
      website: document.getElementById('fWebsite')?.value || null,
      description: document.getElementById('fDescription')?.value || null,
    };
    try {
      const hash = window.location.hash;
      const m = hash.match(/#\/studios\/(\d+)$/);
      if (m) {
        await api.put(`/studios/${m[1]}`, body);
        ui.clearDraft(this._draftKey(m[1])); ui.clearDirty();
        toast('Studio saved');
      } else {
        const res = await api.post('/studios', body);
        ui.clearDraft(this._draftKey()); ui.clearDirty();
        toast('Studio created');
        navigate(`#/studios/${res.id}`);
      }
    } catch (e) {
      ui.toastError(e, 'save the Studio');
    }
  },

  async _delete(id) {
    const ok = await confirmDialog('Delete this studio? Albums referencing it will be blocked from deletion.');
    if (!ok) return;
    try {
      await api.del(`/studios/${id}`);
      toast('Studio deleted');
      navigate('#/studios');
    } catch (e) {
      ui.toastError(e, 'delete the Studio');
    }
  },
};
