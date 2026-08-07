const StatusesPage = {
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
            <td>${s.id}</td>
            <td><strong>${esc(s.name)}</strong></td>
            <td>${esc(s.description || '')}</td>
            <td>${s.album_count || 0}</td>
            <td>${s.workspace_album_count || 0}</td>
            <td class="actions-cell">
              <button class="btn btn-sm btn-secondary" onclick="StatusesPage._openEdit(${s.id}, '${esc(s.name)}', '${esc(s.description || '')}')">Edit</button>
              <button class="btn btn-sm btn-danger" ${used > 0 ? 'disabled title="In use"' : ''} onclick="StatusesPage._delete(${s.id})">Delete</button>
            </td>
          </tr>`;
      }).join('');

      el.innerHTML = `
        <div class="page-header">
          <h1 class="page-title">Statuses</h1>
        </div>
        <div class="card table-wrap">
          <table><thead><tr>
            <th>ID</th><th>Name</th><th>Description</th><th>Albums</th><th>Workspace</th><th>Actions</th>
          </tr></thead>
          <tbody>${rows || '<tr><td colspan="6" style="text-align:center;color:var(--ink-soft)">No statuses</td></tr>'}</tbody>
          </table>
        </div>
      `;
    } catch (e) {
      el.innerHTML = `<div class="error-msg">Error: ${esc(e.message)}</div>`;
    }
  },

  _openNew() {
    showModal(`
      <h3 class="modal-title">New Status</h3>
      <div class="form-grid">
        <div class="form-field form-field-full"><label>Name *</label><input id="sName" placeholder="e.g. Published"></div>
        <div class="form-field form-field-full"><label>Description</label><textarea id="sDesc"></textarea></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="StatusesPage._create()">Create</button>
      </div>
    `);
  },

  _openEdit(id, name, description) {
    showModal(`
      <h3 class="modal-title">Edit Status #${id}</h3>
      <div class="form-grid">
        <div class="form-field form-field-full"><label>Name *</label><input id="sName" value="${esc(name)}"></div>
        <div class="form-field form-field-full"><label>Description</label><textarea id="sDesc">${esc(description)}</textarea></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="StatusesPage._update(${id})">Save</button>
      </div>
    `);
  },

  async _create() {
    const name = document.getElementById('sName')?.value?.trim();
    if (!name) { toast('Name is required', 'error'); return; }
    try {
      await api.post('/statuses', { name, description: document.getElementById('sDesc')?.value || null });
      closeModal();
      toast('Status created');
      await this._load(document.getElementById('page-content'));
    } catch (e) {
      toast('Error: ' + e.message, 'error');
    }
  },

  async _update(id) {
    const name = document.getElementById('sName')?.value?.trim();
    if (!name) { toast('Name is required', 'error'); return; }
    try {
      await api.put(`/statuses/${id}`, { name, description: document.getElementById('sDesc')?.value || null });
      closeModal();
      toast('Status saved');
      await this._load(document.getElementById('page-content'));
    } catch (e) {
      toast('Error: ' + e.message, 'error');
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
      toast('Delete failed: ' + e.message, 'error');
    }
  },
};
