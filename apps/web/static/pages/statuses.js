const StatusesPage = {
  _draftKey: 'entity.status.current',
  async render(params) {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading…</div>';

    const btn = document.getElementById('pageActionBtn');
    btn.textContent = '+ New Status';
    btn.classList.remove('hidden');
    btn.onclick = () => this._openNew();

    await this._load(el);
  },

  async _load(el) {
    try {
      const data = await api.get('/statuses');
      const statuses = data.statuses || [];

      const rows = statuses.map(s => {
        const used = (s.album_count || 0) + (s.workspace_album_count || 0);
        return `
          <tr>
            <td><strong>${esc(s.name)}</strong></td>
            <td>${esc(s.description || '')}</td>
            <td>${s.album_count || 0}</td>
            <td>${s.workspace_album_count || 0}</td>
            <td class="actions-cell">
              <button class="btn btn-sm btn-secondary" data-required-scope="write" onclick="StatusesPage._openEdit(${s.id}, '${esc(s.name)}', '${esc(s.description || '')}')">Edit</button>
              <button class="btn btn-sm btn-danger" data-required-scope="write" ${used > 0 ? 'disabled title="In use"' : ''} onclick="StatusesPage._delete(${s.id})">Delete</button>
            </td>
          </tr>`;
      }).join('');

      el.innerHTML = `
        <div class="page-header">
          <h1 class="page-title">Statuses</h1>
        </div>
        ${ui.loadDraft(this._draftKey)?'<div class="alert alert-warning">A Status draft is saved in this browser. <button class="btn btn-sm btn-primary" onclick="StatusesPage._resumeDraft()">Resume Status draft</button> <button class="btn btn-sm btn-secondary" onclick="StatusesPage._discardDraft()">Discard</button></div>':''}
        <div class="card table-wrap">
          <table><thead><tr>
            <th>Name</th><th>Description</th><th>Albums</th><th>Historical Workspace</th><th>Actions</th>
          </tr></thead>
          <tbody>${rows || '<tr><td colspan="5" style="text-align:center;color:var(--ink-soft)">No statuses</td></tr>'}</tbody>
          </table>
        </div>
      `;
    } catch (e) {
      ui.renderPageError(el, e, 'Statuses');
    }
  },

  _openNew() {
    const saved=ui.loadDraft(this._draftKey);const draft=saved?.data?.id?null:saved?.data;
    showModal(`
      <h3 class="modal-title">New Status</h3>
      <div class="form-grid">
        <div class="form-field form-field-full"><label>Name *</label><input id="sName" value="${esc(draft?.name||'')}" placeholder="e.g. Published"></div>
        <div class="form-field form-field-full"><label>Description</label><textarea id="sDesc">${esc(draft?.description||'')}</textarea></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeModal()">Close and keep draft</button>
        <button class="btn btn-primary" onclick="StatusesPage._create()">Create</button>
      </div>
    `);
    this._bindDraft(null);
  },

  _openEdit(id, name, description) {
    const saved=ui.loadDraft(this._draftKey);const draft=String(saved?.data?.id||'')===String(id)?saved.data:null;
    showModal(`
      <h3 class="modal-title">Edit Status</h3>
      <div class="form-grid">
        <div class="form-field form-field-full"><label>Name *</label><input id="sName" value="${esc(draft?.name??name)}"></div>
        <div class="form-field form-field-full"><label>Description</label><textarea id="sDesc">${esc(draft?.description??description)}</textarea></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeModal()">Close and keep draft</button>
        <button class="btn btn-primary" onclick="StatusesPage._update(${id})">Save</button>
      </div>
    `);
    this._bindDraft(id);
  },

  _bindDraft(id){const save=()=>{ui.saveDraft(this._draftKey,{id,name:document.getElementById('sName').value,description:document.getElementById('sDesc').value});ui.markDirty(this._draftKey,'this Status',()=>ui.clearDraft(this._draftKey));};document.getElementById('sName').addEventListener('input',save);document.getElementById('sDesc').addEventListener('input',save);},
  _resumeDraft(){const draft=ui.loadDraft(this._draftKey)?.data;if(!draft)return;if(draft.id){const row=[...document.querySelectorAll('tbody tr')].find(item=>item.querySelector('button')?.getAttribute('onclick')?.includes(`_openEdit(${draft.id},`));if(row)row.querySelector('button').click();else this._discardDraft();}else this._openNew();},
  async _discardDraft(){ui.clearDraft(this._draftKey);ui.clearDirty();closeModal();await this._load(document.getElementById('page-content'));},

  async _create() {
    const name = document.getElementById('sName')?.value?.trim();
    if (!name) { toast('Name is required', 'error'); return; }
    try {
      await api.post('/statuses', { name, description: document.getElementById('sDesc')?.value || null });
      ui.clearDraft(this._draftKey);ui.clearDirty();
      closeModal();
      toast('Status created');
      await this._load(document.getElementById('page-content'));
    } catch (e) {
      ui.toastError(e, 'create the Status');
    }
  },

  async _update(id) {
    const name = document.getElementById('sName')?.value?.trim();
    if (!name) { toast('Name is required', 'error'); return; }
    try {
      await api.put(`/statuses/${id}`, { name, description: document.getElementById('sDesc')?.value || null });
      ui.clearDraft(this._draftKey);ui.clearDirty();
      closeModal();
      toast('Status saved');
      await this._load(document.getElementById('page-content'));
    } catch (e) {
      ui.toastError(e, 'save the Status');
    }
  },

  async _delete(id) {
    const ok = await confirmDialog('Delete this status?');
    if (!ok) return;
    try {
      await api.del(`/statuses/${id}`);
      toast('Status deleted');
      await this._load(document.getElementById('page-content'));
    } catch (e) {
      ui.toastError(e, 'delete the Status');
    }
  },
};
