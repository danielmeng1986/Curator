const AdminTrashPage = {
  _restoreToken: '',
  _includeRestored: false,
  _assetState: '',

  _query() {
    const params = new URLSearchParams();
    if (this._includeRestored) params.set('include_restored', 'true');
    if (this._assetState) params.set('asset_state', this._assetState);
    const query = params.toString(); return query ? `?${query}` : '';
  },

  async renderList() {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading Digital Asset Trash…</div>';
    try {
      const result = await api.get(`/admin/digital-asset-trash${this._query()}`);
      const items = result.items || [];
      el.innerHTML = `<div class="page-header"><h1 class="page-title">Digital Asset Trash</h1></div>
        <div class="alert alert-warning">This is recoverable Digital Asset Trash. It is separate from Repair Quarantine and database Restore. Album records and business status remain retained.</div>
        <div class="card" style="padding:16px;margin-bottom:16px"><div style="display:flex;gap:12px;align-items:end;flex-wrap:wrap">
          <div class="form-field" style="margin:0"><label for="trashAssetState">Asset state</label><select id="trashAssetState">
            <option value="">All current states</option>${['TRASHED','MISSING','NEEDS_REPAIR','DELETED','PRESENT'].map(state => `<option ${this._assetState === state ? 'selected' : ''}>${state}</option>`).join('')}</select></div>
          <label><input id="trashIncludeRestored" type="checkbox" ${this._includeRestored ? 'checked' : ''}> Include restored history</label>
          <button class="btn btn-secondary" onclick="AdminTrashPage.applyFilters()">Apply filters</button>
          <button class="btn btn-danger" onclick="AdminTrashPage.previewEmptyTrash(this)" ${items.some(item=>item.can_purge) ? '' : 'disabled'}>Review eligible purge</button></div></div>
        <div class="card table-wrap"><table><thead><tr><th>Review</th><th>Album</th><th>Business status</th><th>Catalog</th><th>Assets</th><th>Scope</th><th>Retention / hold</th><th>Actions</th></tr></thead><tbody>
          ${items.map(item => `<tr><td>${item.can_purge ? `<input class="trash-purge-selection" type="checkbox" value="${esc(item.uuid)}" aria-label="Select ${esc(item.title)} for permanent purge">` : '—'}</td><td><a href="#/admin/trash/${encodeURIComponent(item.uuid)}">${esc(item.title)}</a></td>
            <td>${esc(item.status_id ?? 'Not set')}</td><td><span class="chip ${item.catalog_state === 'TRASHED' ? 'chip-warn' : 'chip-ok'}">${esc(item.catalog_state)}</span></td>
            <td><span class="chip ${item.asset_state === 'TRASHED' ? 'chip-warn' : item.asset_state === 'PRESENT' ? 'chip-ok' : 'chip-error'}">${esc(item.asset_state)}</span></td>
            <td>${esc(item.photo_count)} Photos · ${esc(item.byte_count)} bytes</td><td>${item.hold_at ? `Held: ${esc(item.hold_reason)}` : `Until ${esc(item.retention_until)}`}</td>
            <td><div style="display:flex;gap:6px;flex-wrap:wrap">${item.allowed_actions.includes('restore') ? `<button class="btn btn-primary btn-sm" onclick="AdminTrashPage.previewRestore('${esc(item.uuid)}',this)">Review restore</button>` : ''}${item.allowed_actions.includes('purge') ? `<button class="btn btn-danger btn-sm" onclick="AdminTrashPage.previewPurge('${esc(item.uuid)}',this)">Review purge</button>` : ''}</div>${!item.allowed_actions.length ? esc(item.restore_blockers?.[0]?.message || 'Historical evidence only') : ''}</td></tr>`).join('') || '<tr><td colspan="8">No Digital Asset Trash items match these filters.</td></tr>'}</tbody></table></div>`;
    } catch (error) { ui.renderPageError(el, error, 'Digital Asset Trash'); }
  },

  applyFilters() {
    this._includeRestored=Boolean(document.getElementById('trashIncludeRestored')?.checked);
    this._assetState=document.getElementById('trashAssetState')?.value || '';
    return this.renderList();
  },

  async renderDetail({ uuid }) {
    const el = document.getElementById('page-content');
    try {
      const result = await api.get(`/admin/digital-asset-trash/${encodeURIComponent(uuid)}`); const item = result.item;
      el.innerHTML = `<div class="page-header"><div><a href="#/admin/trash">← Digital Asset Trash</a><h1 class="page-title">${esc(item.title)}</h1></div></div>
        <div class="alert alert-warning">Album business status, catalog visibility, and digital-asset availability are independent facts.</div>
        <div class="stats-grid"><div class="stat-card"><div class="stat-number">${esc(item.status_id ?? '—')}</div><div class="stat-label">Business status</div></div>
          <div class="stat-card"><div class="stat-number">${esc(item.catalog_state)}</div><div class="stat-label">Catalog state</div></div>
          <div class="stat-card"><div class="stat-number">${esc(item.asset_state)}</div><div class="stat-label">Asset state</div></div></div>
        <div class="card" style="padding:20px;margin-bottom:16px"><div class="form-section-title">Retained evidence</div>
          <p><strong>Album UUID:</strong> ${esc(item.album_uuid)}</p><p><strong>Reviewed scope:</strong> ${esc(item.photo_count)} Photos · ${esc(item.byte_count)} bytes</p>
          <p><strong>Retention deadline:</strong> ${esc(item.retention_until)}</p><p><strong>Hold:</strong> ${item.hold_at ? `${esc(item.hold_reason)} · ${esc(item.hold_at)}` : 'None'}</p>
          <p>Trash Operation: <a href="#/operations/${esc(item.trash_operation_uuid)}">${esc(item.trash_operation_uuid)}</a></p>
          ${item.restore_operation_uuid ? `<p>Latest Restore Operation: <a href="#/operations/${esc(item.restore_operation_uuid)}">${esc(item.restore_operation_uuid)}</a></p>` : ''}
          ${item.purge_operation_uuid ? `<p>Purge Operation: <a href="#/operations/${esc(item.purge_operation_uuid)}">${esc(item.purge_operation_uuid)}</a> · permanently removed ${esc(item.purge_photo_count)} Photos / ${esc(item.purge_byte_count)} bytes at ${esc(item.purged_at)}</p>` : ''}</div>
        <div class="card" style="padding:20px"><div class="form-section-title">Backend-authorized actions</div>
          ${item.restore_blockers?.length ? `<ul>${item.restore_blockers.map(blocker => `<li><strong>${esc(blocker.code)}</strong> — ${esc(blocker.message)}</li>`).join('')}</ul>` : '<p>Assets are eligible for reviewed restore to their original managed location.</p>'}
          <div style="display:flex;gap:8px;flex-wrap:wrap">${item.allowed_actions.includes('restore') ? `<button class="btn btn-primary" onclick="AdminTrashPage.previewRestore('${esc(item.uuid)}',this)">Review restore</button>` : ''}
          ${item.allowed_actions.includes('purge') ? `<button class="btn btn-danger" onclick="AdminTrashPage.previewPurge('${esc(item.uuid)}',this)">Review permanent purge</button>` : ''}
          ${item.allowed_actions.includes('hold') ? `<button class="btn btn-secondary" onclick="AdminTrashPage.hold('${esc(item.uuid)}',${item.lifecycle_version},this)">Place hold</button>` : ''}
          ${item.allowed_actions.includes('release_hold') ? `<button class="btn btn-secondary" onclick="AdminTrashPage.releaseHold('${esc(item.uuid)}',${item.lifecycle_version},this)">Release hold</button>` : ''}</div></div>`;
    } catch (error) { ui.renderPageError(el, error, 'Digital Asset Trash item'); }
  },

  async previewRestore(uuid, trigger) {
    const result = await ui.runAction('asset-restore-preview', () => api.post(`/admin/digital-asset-trash/${encodeURIComponent(uuid)}/restore/preview`, {}), { trigger, context:'review asset restore' });
    if (!result.ok) return; const preview=result.value.preview; this._restoreToken=preview.preview_token; const item=preview.item;
    ui.showReviewedAction(`<h3 id="modal-title" class="modal-title">Restore Album assets?</h3><p><strong>${esc(item.title)}</strong> and ${esc(item.photo_count)} retained Photo records will return to the active catalog.</p>
      <p>${esc(item.byte_count)} reviewed bytes will move to the original managed location. Existing content is never overwritten.</p>
      <div class="modal-footer"><button class="btn btn-secondary" onclick="AdminTrashPage.cancelRestore()">Cancel</button><button id="executeAssetRestore" class="btn btn-primary" onclick="AdminTrashPage.executeRestore(this)">Execute reviewed restore</button></div>`, { key:'digital-asset-restore', label:'Digital Asset Trash restore review' });
  },
  cancelRestore() { this._restoreToken=''; closeModal(); },
  async executeRestore(trigger) {
    const result=await ui.runAction('asset-restore-execute',()=>api.post('/admin/digital-asset-trash/restore/execute',{preview_token:this._restoreToken}),{trigger,context:'restore Album assets'});
    if (!result.ok) return; this._restoreToken=''; closeModal(); toast('Album assets restored'); window.location.hash='#/admin/trash';
  },
  async hold(uuid, version, trigger) {
    const reason=window.prompt('Reason for preserving these assets:'); if (!reason?.trim()) return;
    const result=await ui.runAction('asset-trash-hold',()=>api.post(`/admin/digital-asset-trash/${encodeURIComponent(uuid)}/hold`,{expected_version:version,reason:reason.trim()}),{trigger,context:'place asset lifecycle hold'});
    if (result.ok) await this.renderDetail({uuid});
  },
  async releaseHold(uuid, version, trigger) {
    if (!window.confirm('Release this lifecycle hold? The item will again be eligible for restore and, after retention review, purge.')) return;
    const result=await ui.runAction('asset-trash-release-hold',()=>api.post(`/admin/digital-asset-trash/${encodeURIComponent(uuid)}/release-hold`,{expected_version:version}),{trigger,context:'release asset lifecycle hold'});
    if (result.ok) await this.renderDetail({uuid});
  },

  async previewPurge(uuid, trigger) {
    const result=await ui.runAction('asset-purge-preview',()=>api.post(`/admin/digital-asset-trash/${encodeURIComponent(uuid)}/purge/preview`,{}),{trigger,context:'review permanent asset purge'});
    if (!result.ok) return; const preview=result.value.preview; const item=preview.item;
    const decision=await AdminCenterPage.confirmHighRisk({title:'Permanently purge Album assets',
      impact:`${item.title}: permanently delete ${item.photo_count} Photos / ${item.byte_count} bytes. Album, Photo, business status, and Operation evidence remain. This cannot be undone.`,
      confirmationPhrase:`PURGE ${item.title}`,actionKey:'asset-purge-execute',
      execute:()=>api.post('/admin/digital-asset-trash/purge/execute',{preview_token:preview.preview_token})});
    if (decision.ok) { toast('Digital assets permanently purged'); await this.renderDetail({uuid}); }
  },

  async previewEmptyTrash(trigger) {
    const trashUuids=[...document.querySelectorAll('.trash-purge-selection:checked')].map(input=>input.value);
    if (!trashUuids.length) { toast('Select at least one Backend-eligible Trash item','warn'); return; }
    const result=await ui.runAction('asset-purge-batch-preview',()=>api.post('/admin/digital-asset-trash/purge/batch/preview',{trash_uuids:trashUuids}),{trigger,context:'review eligible Trash scope'});
    if (!result.ok) return; const preview=result.value.preview;
    if (!preview.preview_token) { toast('No selected items remain eligible for purge','warn'); return; }
    const summary=preview.summary;
    const decision=await AdminCenterPage.confirmHighRisk({title:'Empty reviewed Digital Asset Trash scope',
      impact:`Permanently delete ${summary.eligible} Album asset unit(s), ${summary.photo_count} Photos, and ${summary.byte_count} bytes. ${summary.excluded} changed or ineligible item(s) will not be touched. Database evidence remains.`,
      confirmationPhrase:`EMPTY TRASH ${summary.eligible}`,actionKey:'asset-purge-batch-execute',
      execute:()=>api.post('/admin/digital-asset-trash/purge/batch/execute',{preview_token:preview.preview_token})});
    if (decision.ok) { const outcome=decision.value.result.summary; toast(`Purge completed: ${outcome.succeeded} succeeded, ${outcome.failed} failed`,outcome.failed?'warn':'ok'); await this.renderList(); }
  },
};
