const AdminRestorePage = {
  async render() {
    const el = document.getElementById('page-content');
    document.getElementById('pageActionBtn').classList.add('hidden');
    el.innerHTML = '<div class="loading">Loading verified recovery points…</div>';
    try {
      const data = await api.get('/backups');
      const verified = (data.items || []).filter(item => item.verification_state === 'verified');
      el.innerHTML = `<div class="page-header"><div><a href="#/admin">← Administrator Center</a><h1 class="page-title">Database Restore</h1></div></div>
        <div class="alert alert-warning"><strong>High-impact action.</strong> Restore replaces the active Curator database. A protected safety recovery point is created and verified first.</div>
        <div class="card" style="padding:20px;margin-bottom:16px"><p>Select a Backend-listed, verified recovery point. Uploaded files and browser paths cannot be used.</p></div>
        <div class="table-wrap"><table><thead><tr><th>Verified recovery point</th><th>Created</th><th>Reason / tag</th><th>Action</th></tr></thead><tbody>
        ${verified.map(item => `<tr data-identity="${esc(item.identity)}"><td><strong>${esc(item.filename)}</strong><br><small>${esc(item.identity)}</small></td>
          <td>${esc(item.created_at ? new Date(item.created_at).toLocaleString() : 'Unknown')}</td><td>${esc(item.reason || '—')}<br><small>${esc(item.tag || 'No tag')}</small></td>
          <td><button class="btn btn-danger restore-review">Review Restore</button></td></tr>`).join('') || '<tr><td colspan="4">No verified recovery point is available. Verify one in Backups and Snapshots first.</td></tr>'}
        </tbody></table></div>`;
      el.querySelectorAll('.restore-review').forEach(button => { button.onclick = () => this.review(button.closest('tr').dataset.identity, button); });
    } catch (error) { ui.renderPageError(el, error, 'Database Restore'); }
  },
  async review(identity, trigger) {
    const result = await ui.runAction('preview-database-restore', () => api.post('/backups/restore/preview', { identity }), { trigger, context: 'review database Restore' });
    if (!result.ok) return;
    const preview = result.value.preview;
    ui.showReviewedAction(`<h3 id="modal-title" class="modal-title">Confirm Database Restore</h3>
      <div class="alert alert-warning">The active database will be replaced by <strong>${esc(preview.target.filename)}</strong>. Current browser data becomes stale.</div>
      <p>A protected pre-Restore recovery point will be created and verified before replacement. Success requires a post-Restore database integrity check.</p>
      <div class="form-field"><label for="restorePhrase">Type <strong>${esc(preview.confirmation_phrase)}</strong></label><input id="restorePhrase" autocomplete="off"></div>
      <div class="modal-footer"><button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button id="executeRestore" class="btn btn-danger" disabled>Restore reviewed database</button></div>`, { key:'database-restore', label:'Database Restore review' });
    const input = document.getElementById('restorePhrase'); const execute = document.getElementById('executeRestore');
    input.oninput = () => { execute.disabled = input.value !== preview.confirmation_phrase; };
    execute.onclick = async () => {
      const execution = await ui.runAction('execute-database-restore', () => api.post('/backups/restore/execute', { preview_token: preview.preview_token, confirmation: input.value }), { trigger: execute, context: 'restore database' });
      if (!execution.ok) return;
      api.clearToken(); window.curatorPrincipal = null;
      showModal(`<h3 id="modal-title" class="modal-title">Database Restore verified</h3>
        <p>The database passed integrity verification. Protective recovery point: <strong>${esc(execution.value.safety_recovery_point)}</strong>.</p>
        <p>Cached administrative data and the current browser connection were cleared. Reconnect with a Token valid in the restored database.</p>
        <div class="modal-footer"><button id="restoreReconnect" class="btn btn-primary">Reconnect</button></div>`);
      document.getElementById('restoreReconnect').onclick = () => { closeModal(); void checkBootstrap(); void checkHealth(); route(); openConnectionSettings(); };
    };
  },
};
