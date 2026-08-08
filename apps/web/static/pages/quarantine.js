const QuarantinePage = {
  _previewToken: '',

  async renderList() {
    const el = document.getElementById('page-content');
    try {
      const result = await api.get('/quarantine-items');
      el.innerHTML = `<div class="page-header"><h1 class="page-title">Repair Quarantine</h1></div>
        <div class="alert alert-warning">Repair Quarantine temporarily isolates filesystem conflicts. It is not Digital Asset Trash and does not resolve its Issue.</div>
        <div class="card table-wrap"><table><thead><tr><th>Item</th><th>Original managed path</th><th>Repair</th><th>Created</th><th>Retention</th><th>State</th></tr></thead><tbody>
          ${(result.items || []).map(item => `<tr><td><a href="#/quarantine/${item.uuid}">${esc(item.uuid)}</a></td><td class="path-mono">${esc(item.original_path)}</td>
            <td><a href="#/repairs/${item.repair_uuid}">${esc(item.repair_uuid || '—')}</a></td><td>${esc(item.created_at)}</td><td>${esc(item.expires_at)}</td>
            <td><span class="chip ${item.restored_at ? 'chip-ok' : 'chip-warn'}">${item.restored_at ? 'Restored' : item.hold ? 'Held' : 'Isolated'}</span></td></tr>`).join('') || '<tr><td colspan="6">No quarantined repair items</td></tr>'}</tbody></table></div>`;
    } catch (error) { ui.renderPageError(el, error, 'Repair Quarantine'); }
  },

  async renderDetail({ uuid }) {
    const el = document.getElementById('page-content');
    try {
      const result = await api.get(`/quarantine-items/${encodeURIComponent(uuid)}`); const item = result.item;
      const files = String(item.inventory || '').split('\n').filter(Boolean);
      el.innerHTML = `<div class="page-header"><div><a href="#/quarantine">← Repair Quarantine</a><h1 class="page-title">Quarantine Item</h1></div></div>
        <div class="card" style="padding:20px;margin-bottom:16px"><span class="chip ${item.restored_at ? 'chip-ok' : 'chip-warn'}">${item.restored_at ? 'Restored' : 'Isolated'}</span>
          <p><strong>Original managed path:</strong> <span class="path-mono">${esc(item.original_path)}</span></p><p><strong>Reason:</strong> ${esc(item.reason)}</p>
          <p><strong>Created:</strong> ${esc(item.created_at)} · <strong>Expires:</strong> ${esc(item.expires_at)}</p></div>
        <div class="card" style="padding:20px;margin-bottom:16px"><div class="form-section-title">Intact content inventory (${files.length})</div>
          <ul>${files.map(file => `<li class="path-mono">${esc(file)}</li>`).join('') || '<li>No files recorded</li>'}</ul></div>
        <div class="card" style="padding:20px"><div class="form-section-title">Traceability and actions</div>
          <p>Repair: <a href="#/repairs/${item.repair_uuid}">${esc(item.repair_uuid || '—')}</a></p><p>Quarantine Operation: <a href="#/operations/${item.operation_uuid}">${esc(item.operation_uuid)}</a></p>
          ${item.restore_operation_uuid ? `<p>Restore Operation: <a href="#/operations/${item.restore_operation_uuid}">${esc(item.restore_operation_uuid)}</a></p>` : ''}
          ${item.restored_at ? `<p>Restored to <span class="path-mono">${esc(item.restore_destination)}</span> at ${esc(item.restored_at)}.</p>` : `<button class="btn btn-primary" onclick="QuarantinePage.previewRestore('${esc(item.uuid)}')">Review restore to original path</button>`}</div>`;
    } catch (error) { ui.renderPageError(el, error, 'Quarantine item'); }
  },

  async previewQuarantine(repairUuid) {
    const reason = window.prompt('Reason for isolating this repair conflict:'); if (!reason?.trim()) return;
    const result = await ui.runAction('quarantine-preview', () => api.post('/quarantine/preview', {
      action: 'quarantine', repair_uuid: repairUuid, reason: reason.trim(),
    }), { context: 'preview the Quarantine move' });
    if (result.ok) this._showPreview(result.value.preview);
  },

  async previewRestore(itemUuid) {
    const result = await ui.runAction('quarantine-preview', () => api.post('/quarantine/preview', {
      action: 'restore', item_uuid: itemUuid,
    }), { context: 'preview the Quarantine restore' });
    if (result.ok) this._showPreview(result.value.preview);
  },

  _showPreview(preview) {
    this._previewToken = preview.preview_token;
    const target = preview.managed_path || preview.managed_destination;
    showModal(`<h3 id="modal-title" class="modal-title">Confirm ${esc(preview.action)} preview</h3>
      <p><strong>Managed path:</strong> <span class="path-mono">${esc(target)}</span></p>
      ${preview.file_count !== undefined ? `<p><strong>Files:</strong> ${preview.file_count}</p>` : ''}<p>${esc(preview.consequence)}</p>
      <p style="color:var(--ink-soft)">Preview ${esc(preview.preview_uuid)} expires ${esc(preview.expires_at)}.</p>
      <div class="modal-footer"><button class="btn btn-secondary" onclick="QuarantinePage.cancelPreview()">Cancel</button>
        <button id="executeQuarantineBtn" class="btn btn-danger" onclick="QuarantinePage.executePreview(this)">Execute reviewed ${esc(preview.action)}</button></div>`);
  },

  cancelPreview() { this._previewToken = ''; closeModal(); },
  async executePreview(trigger) {
    const token = this._previewToken;
    const result = await ui.runAction('quarantine-execute', () => api.post('/quarantine/execute', { preview_token: token }),
      { trigger, context: 'execute the reviewed Quarantine action' });
    if (!result.ok) return;
    this._previewToken = ''; closeModal(); toast(`Quarantine ${result.value.action} completed`);
    window.location.hash = `#/quarantine/${result.value.item.uuid}`;
  },
};
