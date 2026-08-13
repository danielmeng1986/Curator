const AdminBackupsPage = {
  async render() {
    const el = document.getElementById('page-content');
    const action = document.getElementById('pageActionBtn');
    action.textContent = 'Create recovery point'; action.classList.remove('hidden');
    action.onclick = () => this.openCreate();
    el.innerHTML = '<div class="loading">Loading recovery points…</div>';
    try {
      const data = await api.get('/backups');
      const items = data.items || [];
      el.innerHTML = `<div class="page-header"><div><a href="#/admin">← Administrator Center</a>
        <h1 class="page-title">Backups and Snapshots</h1></div></div>
        <div class="alert alert-warning">Recovery points are discovered and controlled by the Backend. File paths and arbitrary deletion are not available here.</div>
        <div class="card" style="padding:20px;margin-bottom:16px"><strong>${items.length}</strong> recovery point(s) · ordinary retention ${esc(data.retention_days)} days
          <button id="previewCleanup" class="btn btn-danger" style="float:right">Review retention cleanup</button></div>
        <div class="table-wrap"><table><thead><tr><th>Recovery point</th><th>Created</th><th>Reason / tag</th><th>Retention</th><th>Verification</th><th>Actions</th></tr></thead>
        <tbody>${items.map(item => `<tr data-identity="${esc(item.identity)}"><td><strong>${esc(item.filename)}</strong><br><small>${esc(item.identity)}</small></td>
          <td>${esc(item.created_at ? new Date(item.created_at).toLocaleString() : 'Unknown')}</td><td>${esc(item.reason || '—')}<br><small>${esc(item.tag || 'No tag')}</small></td>
          <td><span class="chip ${item.protection_state === 'protected' ? 'chip-warn' : ''}">${esc(item.protection_state)}</span><br><small>${esc(item.retention_class)} · ${item.cleanup_eligible ? 'cleanup eligible' : 'retained'}</small></td>
          <td><span class="chip ${item.verification_state === 'verified' ? 'chip-ok' : item.verification_state === 'failed' ? 'chip-error' : ''}">${esc(item.verification_state)}</span></td>
          <td><button class="btn btn-secondary btn-sm verify-recovery">Verify</button></td></tr>`).join('') || '<tr><td colspan="6">No recovery points yet.</td></tr>'}</tbody></table></div>`;
      document.getElementById('previewCleanup').onclick = () => this.reviewCleanup();
      el.querySelectorAll('.verify-recovery').forEach(button => { button.onclick = async () => {
        const identity = button.closest('tr').dataset.identity;
        const result = await ui.runAction('verify-recovery-point', () => api.post(`/backups/${identity}/verify`, {}), { trigger: button, context: 'verify recovery point' });
        if (result.ok) { toast(result.value.verification.verification_state === 'verified' ? 'Recovery point verified' : 'Recovery point verification failed', result.value.verification.verification_state === 'verified' ? 'ok' : 'error'); await this.render(); }
      }; });
    } catch (error) { ui.renderPageError(el, error, 'Backups and Snapshots'); }
  },

  openCreate() {
    showModal(`<h3 id="modal-title" class="modal-title">Create recovery point</h3>
      <div class="form-field"><label for="backupReason">Reason</label><input id="backupReason" value="manual"></div>
      <div class="form-field"><label for="backupTag">Tag (optional)</label><input id="backupTag"></div>
      <p>The Backend chooses and controls the storage location.</p><div class="modal-footer"><button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button id="createBackup" class="btn btn-primary">Create</button></div>`);
    document.getElementById('createBackup').onclick = async event => {
      const result = await ui.runAction('create-recovery-point', () => api.post('/backup', { reason: document.getElementById('backupReason').value, tag: document.getElementById('backupTag').value }), { trigger: event.currentTarget, context: 'create recovery point' });
      if (result.ok) { closeModal(); toast('Recovery point created'); await this.render(); }
    };
  },

  async reviewCleanup() {
    const result = await ui.runAction('preview-snapshot-cleanup', () => api.post('/backups/cleanup/preview', {}), { context: 'review retention cleanup' });
    if (!result.ok) return;
    const preview = result.value.preview;
    ui.showReviewedAction(`<h3 id="modal-title" class="modal-title">Review retention cleanup</h3>
      <p><strong>${preview.summary.eligible}</strong> expired, unprotected recovery point(s) are eligible.</p>
      <ul>${preview.items.map(item => `<li>${esc(item.filename)} — ${esc(item.created_at || 'unknown')}</li>`).join('') || '<li>Nothing will be deleted.</li>'}</ul>
      <p>Only the reviewed identities above can be removed. This preview expires and can be used once.</p>
      <div class="form-field"><label for="cleanupPhrase">Type <strong>CLEANUP</strong> to continue</label><input id="cleanupPhrase" autocomplete="off"></div>
      <div class="modal-footer"><button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button id="executeCleanup" class="btn btn-danger" disabled>Execute reviewed cleanup</button></div>`, { key:'backup-retention-cleanup', label:'Retention cleanup review' });
    const input = document.getElementById('cleanupPhrase'); const button = document.getElementById('executeCleanup');
    input.oninput = () => { button.disabled = input.value !== 'CLEANUP'; };
    button.onclick = async () => {
      const execution = await ui.runAction('execute-snapshot-cleanup', () => api.post('/backups/cleanup/execute', { preview_token: preview.preview_token }), { trigger: button, context: 'execute retention cleanup' });
      if (execution.ok) { closeModal(); const failed = execution.value.failed.length; toast(failed ? `Cleanup partially completed: ${failed} failed` : `Cleanup completed: ${execution.value.deleted.length} removed`, failed ? 'error' : 'ok'); await this.render(); }
    };
  },
};
