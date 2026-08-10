const AdminCenterPage = {
  async render() {
    const el = document.getElementById('page-content');
    document.getElementById('pageActionBtn').classList.add('hidden');
    el.innerHTML = '<div class="loading">Loading Administrator Center…</div>';
    try {
      const [health, backups, quarantine, operations] = await Promise.all([
        api.get('/health'), api.get('/backups'), api.get('/quarantine-items'), api.get('/operations?limit=5'),
      ]);
      const cards = [
        ['Devices and Tokens', 'Review registrations, renewals, roles, scopes, and revocation.', '#/admin/devices', 'Available'],
        ['Backups and Snapshots', 'Inspect and create Backend-controlled recovery points.', '#/admin/backups', 'Available'],
        ['Database Restore', 'Protected restore from a verified recovery point.', '#/admin/restore', 'Available'],
        ['Repair Quarantine', `${(quarantine.items || []).filter(item => !item.restored_at).length} item(s) currently isolated.`, '#/quarantine', 'Available'],
        ['Operation History', 'Read durable administrative and workflow outcomes.', '#/operations?operation_type=backup', 'Available'],
        ['AI Work Dispatch', 'Select available Albums and assign exclusive Worker Groups.', '#/work-dispatch', 'Available'],
      ];
      el.innerHTML = `<div class="page-header"><h1 class="page-title">Administrator Center</h1></div>
        <div class="alert alert-warning">Administrative actions can affect authentication and recovery. This center never displays stored Token secrets or arbitrary filesystem paths.</div>
        <div class="stats-grid">
          <div class="stat-card"><div class="stat-number">${backups.items?.length || 0}</div><div class="stat-label">Recovery points</div></div>
          <div class="stat-card"><div class="stat-number">${(quarantine.items || []).filter(item => !item.restored_at).length}</div><div class="stat-label">Quarantined conflicts</div></div>
          <div class="stat-card"><div class="stat-number">${operations.operations?.length || 0}</div><div class="stat-label">Recent Operations shown</div></div>
        </div>
        <div class="card" style="padding:20px;margin-bottom:16px"><div class="form-section-title">Backend readiness</div>
          <p>Database: <strong>${health.db_exists ? 'Ready' : 'Unavailable'}</strong> · Backup retention: <strong>${esc(backups.retention_days)} days</strong></p></div>
        <div class="stats-grid">${cards.map(([title, description, href, status]) => `<div class="card" style="padding:20px">
          <div class="form-section-title">${esc(title)}</div><p>${esc(description)}</p><p><span class="chip ${status === 'Available' ? 'chip-ok' : 'chip-warn'}">${esc(status)}</span></p>
          ${status === 'Available' ? `<a class="btn btn-secondary" href="${href}">Open</a>` : '<button class="btn btn-secondary" disabled>Not available yet</button>'}</div>`).join('')}</div>`;
    } catch (error) { ui.renderPageError(el, error, 'Administrator Center'); }
  },

  async confirmHighRisk({ title, impact, confirmationPhrase, execute, actionKey }) {
    return new Promise(resolve => {
      showModal(`<h3 id="modal-title" class="modal-title">${esc(title)}</h3><p>${esc(impact)}</p>
        <div class="form-field"><label for="adminConfirmPhrase">Type <strong>${esc(confirmationPhrase)}</strong> to continue</label>
          <input id="adminConfirmPhrase" autocomplete="off"></div><div class="modal-footer">
          <button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button id="adminHighRiskExecute" class="btn btn-danger" disabled>Execute reviewed action</button></div>`);
      const input = document.getElementById('adminConfirmPhrase'); const trigger = document.getElementById('adminHighRiskExecute');
      input.oninput = () => { trigger.disabled = input.value !== confirmationPhrase; };
      trigger.onclick = async () => {
        const result = await ui.runAction(actionKey, execute, { trigger, context: title });
        if (result.ok) closeModal(); resolve(result);
      };
    });
  },
};
