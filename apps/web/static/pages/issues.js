const IssuesPage = {
  _issue: null,
  _repair: null,

  async renderList() {
    const el = document.getElementById('page-content');
    const params = new URLSearchParams(window.location.hash.split('?')[1] || '');
    const state = params.get('state') || '';
    try {
      const result = await api.get(`/issues${state ? `?state=${encodeURIComponent(state)}` : ''}`);
      el.innerHTML = `<div class="page-header"><h1 class="page-title">Issues</h1><a href="#/repairs" class="btn btn-secondary">Repair Cases</a></div>
        <div class="card" style="padding:16px;margin-bottom:16px"><label for="issueState">State</label>
          <select id="issueState" onchange="window.location.hash='#/issues'+(this.value?'?state='+this.value:'')"><option value="">All</option>
            ${['Open','InProgress','Resolved','Archived'].map(v => `<option ${state === v ? 'selected' : ''}>${v}</option>`).join('')}</select></div>
        <div class="card table-wrap"><table><thead><tr><th>Issue</th><th>Category</th><th>State</th><th>Priority</th><th>Owner</th><th>Description</th></tr></thead>
          <tbody>${(result.items || []).map(item => `<tr><td><a href="#/issues/${item.uuid}">${esc(item.uuid)}</a></td><td>${esc(item.category)}</td>
            <td><span class="chip">${esc(item.state)}</span></td><td>${esc(item.priority)}</td><td>${esc(item.owner || 'Unassigned')}</td><td>${esc(item.description)}</td></tr>`).join('') || '<tr><td colspan="6">No Issues</td></tr>'}</tbody></table></div>`;
    } catch (error) { ui.renderPageError(el, error, 'Issues'); }
  },

  async renderDetail({ uuid }) {
    const el = document.getElementById('page-content');
    try {
      const result = await api.get(`/issues/${encodeURIComponent(uuid)}`); this._issue = result.issue;
      const item = this._issue;
      el.innerHTML = `<div class="page-header"><div><a href="#/issues">← Issues</a><h1 class="page-title">Issue Detail</h1></div></div>
        <div class="card" style="padding:20px;margin-bottom:16px"><span class="chip">${esc(item.state)}</span> <strong>${esc(item.category)}</strong>
          <p>${esc(item.description)}</p><p><strong>Suggested resolution:</strong> ${esc(item.suggested_resolution || '—')}</p>
          <p><strong>Owner:</strong> ${esc(item.owner || 'Unassigned')} · <strong>Priority:</strong> ${esc(item.priority)}</p></div>
        <div class="card" style="padding:20px;margin-bottom:16px"><div class="form-section-title">Allowed decisions</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">${item.allowed_actions.map(action => `<button class="btn ${['resolve','archive'].includes(action) ? 'btn-danger' : 'btn-primary'}" onclick="IssuesPage._issueDecision('${action}')">${esc(action.replaceAll('_',' '))}</button>`).join('') || '<span>No decisions are currently permitted.</span>'}</div></div>
        <div class="card" style="padding:20px"><div class="form-section-title">Traceability</div>
          ${item.affected_operation ? `<p>Operation: <a href="#/operations/${item.affected_operation}">${esc(item.affected_operation)}</a></p>` : ''}
          ${(item.links || []).map(link => `<p>${esc(link.relationship)}: <span class="path-mono">${esc(link.target_uuid)}</span></p>`).join('') || '<p>No additional links.</p>'}</div>`;
    } catch (error) { ui.renderPageError(el, error, 'Issue detail'); }
  },

  async _issueDecision(action) {
    const body = { action, expected_updated_at: this._issue.updated_at };
    if (action === 'assign') {
      const owner = window.prompt('Owner name (blank clears ownership):'); if (owner === null) return; body.owner = owner.trim() || null;
    } else if (action === 'resolve') {
      const evidence = window.prompt('Resolution verification evidence:'); if (!evidence?.trim()) return; body.verification = evidence.trim();
    } else if (!await ui.confirmDialog({ title: 'Confirm Issue decision', message: `Apply ${action.replaceAll('_',' ')} to this Issue?`, confirmLabel: 'Apply', danger: action === 'archive' })) return;
    const result = await ui.runAction('issue-decision', () => api.post(`/issues/${this._issue.uuid}/decisions`, body), { context: 'apply the Issue decision' });
    if (result.ok) { toast('Issue decision recorded'); await this.renderDetail({ uuid: this._issue.uuid }); }
  },

  async renderRepairs() {
    const el = document.getElementById('page-content');
    try {
      const result = await api.get('/repairs');
      el.innerHTML = `<div class="page-header"><h1 class="page-title">Repair Cases</h1><a href="#/issues" class="btn btn-secondary">Issues</a></div>
        <div class="card table-wrap"><table><thead><tr><th>Repair</th><th>Category</th><th>State</th><th>Created</th></tr></thead><tbody>
          ${(result.items || []).map(item => `<tr><td><a href="#/repairs/${item.uuid}">${esc(item.uuid)}</a></td><td>${esc(item.category)}</td><td><span class="chip">${esc(item.state)}</span></td><td>${esc(item.created_at)}</td></tr>`).join('') || '<tr><td colspan="4">No Repair cases</td></tr>'}</tbody></table></div>`;
    } catch (error) { ui.renderPageError(el, error, 'Repair cases'); }
  },

  async renderRepairDetail({ uuid }) {
    const el = document.getElementById('page-content');
    try {
      const result = await api.get(`/repairs/${encodeURIComponent(uuid)}`); this._repair = result.repair; const item = this._repair;
      el.innerHTML = `<div class="page-header"><div><a href="#/repairs">← Repair Cases</a><h1 class="page-title">Repair Detail</h1></div></div>
        <div class="card" style="padding:20px;margin-bottom:16px"><span class="chip">${esc(item.state)}</span> <strong>${esc(item.category)}</strong>
          ${Object.hasOwn(item,'expected_path') ? `<p><strong>Expected managed path:</strong> <span class="path-mono">${esc(item.expected_path || '—')}</span></p><p><strong>Failure:</strong> ${esc(item.failure_reason || '—')}</p>` : '<p>Operational path evidence is hidden for this role.</p>'}
          ${item.confirmation ? `<p><strong>Confirmation:</strong> ${esc(item.confirmation)}</p>` : ''}${item.verification_result ? `<p><strong>Verification:</strong> ${esc(item.verification_result)}</p>` : ''}</div>
        <div class="card" style="padding:20px;margin-bottom:16px"><div class="form-section-title">Backend-approved decisions</div><div style="display:flex;gap:8px;flex-wrap:wrap">
          ${item.allowed_actions.map(action => `<button class="btn ${action === 'ignore' ? 'btn-danger' : 'btn-primary'}" onclick="IssuesPage._repairDecision('${action}')">${esc(action.replaceAll('_',' '))}</button>`).join('') || '<span>No decisions are currently permitted.</span>'}</div></div>
        ${item.suppression_candidate ? `<div class="card" style="padding:20px;margin-bottom:16px"><div class="form-section-title">Admin suppression</div><p>Scope: <span class="path-mono">${esc(item.suppression_candidate.scope_path)}</span></p><button class="btn btn-secondary" onclick="IssuesPage._createSuppression()">Create bounded suppression</button></div>` : ''}
        ${item.quarantine_candidate ? `<div class="card" style="padding:20px;margin-bottom:16px"><div class="form-section-title">Repair Quarantine</div><p>Approved candidate: <span class="path-mono">${esc(item.quarantine_candidate.managed_path)}</span></p><p>This isolates a conflict; it does not resolve the Issue.</p><button class="btn btn-danger" onclick="QuarantinePage.previewQuarantine('${esc(item.uuid)}')">Review Quarantine move</button></div>` : ''}
        <div class="card" style="padding:20px"><div class="form-section-title">Traceability</div>${item.operation_uuid ? `<p>Original Operation: <a href="#/operations/${item.operation_uuid}">${esc(item.operation_uuid)}</a></p>` : '<p>No original Operation link.</p>'}</div>`;
    } catch (error) { ui.renderPageError(el, error, 'Repair detail'); }
  },

  async _repairDecision(action) {
    const body = { action, expected_updated_at: this._repair.updated_at };
    if (action === 'confirm') { const value = window.prompt('Confirmation of reviewed action and evidence:'); if (!value?.trim()) return; body.confirmation = value.trim(); }
    else if (action.startsWith('verify_')) { const value = window.prompt('Verification evidence:'); if (!value?.trim()) return; body.verification = value.trim(); }
    else if (!await ui.confirmDialog({ title: 'Confirm Repair decision', message: `Apply ${action.replaceAll('_',' ')}? This records a decision; it does not infer filesystem success.`, confirmLabel: 'Apply', danger: action === 'ignore' })) return;
    const result = await ui.runAction('repair-decision', () => api.post(`/repairs/${this._repair.uuid}/decisions`, body), { context: 'apply the Repair decision' });
    if (result.ok) { toast('Repair decision recorded'); await this.renderRepairDetail({ uuid: this._repair.uuid }); }
  },

  async _createSuppression() {
    const reason = window.prompt('Suppression reason:'); if (!reason?.trim()) return;
    const days = window.prompt('Expiry in days (1–30):', '7'); if (!days) return;
    const count = Number(days); if (!Number.isInteger(count) || count < 1 || count > 30) { toast('Expiry must be 1–30 days', 'error'); return; }
    const candidate = this._repair.suppression_candidate;
    const result = await ui.runAction('repair-suppression', () => api.post('/repair-suppressions', {
      ...candidate, reason: reason.trim(), expires_at: new Date(Date.now() + count * 86400000).toISOString(),
    }), { context: 'create the Repair suppression' });
    if (result.ok) toast('Bounded suppression created');
  },
};
