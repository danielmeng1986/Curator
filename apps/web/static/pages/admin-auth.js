const AdminAuthPage = {
  _state: null,
  async render() {
    const el = document.getElementById('page-content');
    try {
      this._state = await api.get('/auth/admin/state');
      const registrations = this._state.registrations || [], renewals = this._state.renewals || [], tokens = this._state.tokens || [];
      el.innerHTML = `<div class="page-header"><div><a href="#/admin">← Administrator Center</a><h1 class="page-title">Devices and Tokens</h1></div></div>
        <div class="alert alert-warning">Existing Token plaintext and hashes are never available. Newly issued credentials are shown once in the approval result.</div>
        ${this._proofCard(this._state.registration_proof)}
        <div class="card" style="padding:16px;margin-bottom:16px"><div class="form-section-title">Pending registrations</div>
          <div class="table-wrap"><table><thead><tr><th>Device</th><th>Requested role</th><th>Requested scopes</th><th>Created</th><th>Decision</th></tr></thead><tbody>
          ${registrations.filter(item => item.status === 'PendingApproval').map(item => `<tr><td>${esc(item.device_name)}<br><span class="path-mono">${esc(item.device_identity)}</span></td>
            <td>${esc(item.requested_role)}</td><td>${esc(item.requested_scopes.join(', '))}</td><td>${esc(item.created_at)}</td><td>
            <select aria-label="Approved role for ${esc(item.device_name)}" id="role-${item.uuid}">${this._roleOptions(item.requested_role)}</select>
            <button class="btn btn-sm btn-primary" onclick="AdminAuthPage._approveRegistration('${item.uuid}')">Approve</button>
            <button class="btn btn-sm btn-danger" onclick="AdminAuthPage._rejectRegistration('${item.uuid}')">Reject</button></td></tr>`).join('') || '<tr><td colspan="5">No pending registrations</td></tr>'}</tbody></table></div></div>
        <div class="card" style="padding:16px;margin-bottom:16px"><div class="form-section-title">Renewal requests</div>
          <div class="table-wrap"><table><thead><tr><th>Request</th><th>Role / scopes</th><th>Created</th><th>Decision</th></tr></thead><tbody>
          ${renewals.filter(item => item.status === 'PendingApproval').map(item => `<tr><td class="path-mono">${esc(item.uuid)}</td><td>${esc(item.requested_role)} · ${esc(item.requested_scopes.join(', '))}</td><td>${esc(item.created_at)}</td><td>
            <button class="btn btn-sm btn-primary" onclick="AdminAuthPage._renewal('${item.uuid}','approve')">Approve</button><button class="btn btn-sm btn-danger" onclick="AdminAuthPage._renewal('${item.uuid}','reject')">Reject</button></td></tr>`).join('') || '<tr><td colspan="4">No pending renewals</td></tr>'}</tbody></table></div></div>
        <div class="card" style="padding:16px"><div class="form-section-title">Token metadata</div>
          <div class="table-wrap"><table><thead><tr><th>Device</th><th>Token</th><th>Scopes</th><th>Expires</th><th>State</th><th></th></tr></thead><tbody>
          ${tokens.map(item => `<tr><td>${esc(item.device_name)}</td><td class="path-mono">${esc(item.uuid)}</td><td>${esc(item.scopes.join(', '))}</td><td>${esc(item.expires_at)}</td>
            <td><span class="chip ${item.revoked_at ? 'chip-error' : 'chip-ok'}">${item.revoked_at ? 'Revoked' : new Date(item.expires_at) <= new Date() ? 'Expired' : item.replaced_by_uuid ? 'Replaced' : 'Active'}</span></td><td>
            ${!item.revoked_at && new Date(item.expires_at) > new Date() ? `<button class="btn btn-sm btn-danger" onclick="AdminAuthPage._revoke('${item.uuid}')">Revoke</button>` : ''}</td></tr>`).join('') || '<tr><td colspan="6">No Tokens</td></tr>'}</tbody></table></div></div>`;
    } catch (error) { ui.renderPageError(el, error, 'Device and Token administration'); }
  },
  _proofCard(state) {
    const label = state?.active ? 'Active' : state ? 'Disabled' : 'Not configured';
    return `<div class="card" style="padding:16px;margin-bottom:16px"><div class="form-section-title">Registration access</div>
      <p>The Registration Proof lets a browser request Reader or Writer access. It never grants access without approval.</p>
      <p>Status: <span class="chip">${label}</span>${state?.created_at ? ` · Created ${esc(state.created_at)}` : ''}${state?.last_used_at ? ` · Last used ${esc(state.last_used_at)}` : ''}</p>
      <button class="btn btn-primary" onclick="AdminAuthPage._generateProof()">${state ? 'Rotate Registration Proof' : 'Generate Registration Proof'}</button>
      ${state?.active ? '<button class="btn btn-danger" onclick="AdminAuthPage._disableProof()">Disable</button>' : ''}</div>`;
  },
  async _generateProof() {
    if (!await ui.confirmDialog({ title: this._state.registration_proof ? 'Rotate Registration Proof' : 'Generate Registration Proof', message: 'The new value is shown once. Rotation immediately invalidates the previous proof but does not affect approved Tokens.', confirmLabel: this._state.registration_proof ? 'Rotate' : 'Generate' })) return;
    const result = await ui.runAction('registration-proof-generate', () => api.post(`/auth/admin/registration-proof/${this._state.registration_proof ? 'rotate' : 'generate'}`, {}), { context: 'generate Registration Proof' });
    if (!result.ok) return;
    showModal(`<h3 class="modal-title">Registration Proof shown once</h3><p>Copy this value to an approved credential manager. It cannot be displayed again.</p><pre class="one-time-token" id="issuedRegistrationProof"></pre><div class="modal-footer"><button class="btn btn-primary" onclick="AdminAuthPage._closeIssued()">I stored it securely</button></div>`);
    document.getElementById('issuedRegistrationProof').textContent = result.value.registration_proof;
  },
  async _disableProof() {
    if (!await ui.confirmDialog({ title: 'Disable Registration Proof', message: 'New device requests will be rejected. Existing approved Tokens remain valid.', confirmLabel: 'Disable' })) return;
    const result = await ui.runAction('registration-proof-disable', () => api.post('/auth/admin/registration-proof/disable', {}), { context: 'disable Registration Proof' });
    if (result.ok) await this.render();
  },
  _roleOptions(requested) {
    const rank = { reader: 0, writer: 1, admin: 2 };
    return ['reader','writer','admin'].filter(role => rank[role] <= rank[requested]).map(role => `<option value="${role}" ${role === requested ? 'selected' : ''}>${role}</option>`).join('');
  },
  _scopes(role) { return { reader: ['read'], writer: ['read','write'], admin: ['read','write','admin'] }[role]; },
  async _approveRegistration(uuid) {
    const role = document.getElementById(`role-${uuid}`).value;
    const result = await ui.runAction(`registration-${uuid}`, () => api.post(`/auth/admin/registrations/${uuid}/approve`, {
      approved_role: role, approved_scopes: this._scopes(role),
    }), { context: 'approve the device registration' });
    if (result.ok) {
      if (result.value.client_owned) { toast('Device approved. The requesting browser can now connect.', 'ok'); await this.render(); }
      else this._showIssued(result.value, 'Device Token issued once');
    }
  },
  async _rejectRegistration(uuid) {
    if (!await ui.confirmDialog({ title: 'Reject registration', message: 'Reject this pending device without issuing a Token?', confirmLabel: 'Reject' })) return;
    const result = await ui.runAction(`registration-${uuid}`, () => api.post(`/auth/admin/registrations/${uuid}/reject`, {}), { context: 'reject the registration' });
    if (result.ok) { toast('Registration rejected'); await this.render(); }
  },
  async _renewal(uuid, action) {
    if (!await ui.confirmDialog({ title: `${action} renewal`, message: `${action} this Token renewal request?`, confirmLabel: action })) return;
    const result = await ui.runAction(`renewal-${uuid}`, () => api.post(`/auth/admin/renewals/${uuid}/${action}`, {}), { context: `${action} the Token renewal` });
    if (!result.ok) return;
    if (action === 'approve') this._showIssued(result.value, 'Replacement Token issued once');
    else { toast('Renewal rejected'); await this.render(); }
  },
  _showIssued(issued, title) {
    showModal(`<h3 id="modal-title" class="modal-title">${esc(title)}</h3><p>Copy this credential to the approved device now. It cannot be retrieved again.</p>
      <pre id="adminIssuedToken" class="one-time-token"></pre><div class="modal-footer"><button class="btn btn-primary" onclick="AdminAuthPage._closeIssued()">I stored it securely</button></div>`);
    document.getElementById('adminIssuedToken').textContent = issued.token;
  },
  async _closeIssued() { closeModal(); await this.render(); },
  async _revoke(uuid) {
    const result = await AdminCenterPage.confirmHighRisk({ title: 'Revoke Device Token', impact: 'The device immediately loses access. The final usable Admin Token is protected by the Backend.',
      confirmationPhrase: 'REVOKE', actionKey: `revoke-${uuid}`, execute: () => api.post(`/auth/admin/tokens/${uuid}/revoke`, {}) });
    if (result?.ok) { toast('Token revoked'); await this.render(); }
  },
};
