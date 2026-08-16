// ─── Router ──────────────────────────────────────────────────────────────────

const ROUTES = [
  { pattern: /^#\/$/, page: 'dashboard', params: [] },
  { pattern: /^#\/albums(?:\?.*)?$/, page: 'albums-list', params: [] },
  { pattern: /^#\/albums\/new$/, page: 'album-new', params: [] },
  { pattern: /^#\/albums\/(\d+)$/, page: 'album-detail', params: ['id'] },
  { pattern: /^#\/models(?:\?.*)?$/, page: 'models-list', params: [] },
  { pattern: /^#\/models\/new$/, page: 'model-new', params: [] },
  { pattern: /^#\/models\/(\d+)$/, page: 'model-detail', params: ['id'] },
  { pattern: /^#\/studios(?:\?.*)?$/, page: 'studios-list', params: [] },
  { pattern: /^#\/studios\/new$/, page: 'studio-new', params: [] },
  { pattern: /^#\/studios\/(\d+)$/, page: 'studio-detail', params: ['id'] },
  { pattern: /^#\/statuses$/, page: 'statuses', params: [] },
  { pattern: /^#\/import\/albums$/, page: 'import', params: [], scope: 'write' },
  { pattern: /^#\/operations(?:\?.*)?$/, page: 'operations-list', params: [] },
  { pattern: /^#\/operations\/([^/?]+)$/, page: 'operation-detail', params: ['uuid'] },
  { pattern: /^#\/issues(?:\?.*)?$/, page: 'issues-list', params: [] },
  { pattern: /^#\/issues\/([^/?]+)$/, page: 'issue-detail', params: ['uuid'] },
  { pattern: /^#\/repairs(?:\?.*)?$/, page: 'repairs-list', params: [] },
  { pattern: /^#\/repairs\/([^/?]+)$/, page: 'repair-detail', params: ['uuid'] },
  { pattern: /^#\/quarantine$/, page: 'quarantine-list', params: [], scope: 'admin' },
  { pattern: /^#\/quarantine\/([^/?]+)$/, page: 'quarantine-detail', params: ['uuid'], scope: 'admin' },
  { pattern: /^#\/admin$/, page: 'admin-center', params: [], scope: 'admin' },
  { pattern: /^#\/admin\/devices$/, page: 'admin-devices', params: [], scope: 'admin' },
  { pattern: /^#\/admin\/backups$/, page: 'admin-backups', params: [], scope: 'admin' },
  { pattern: /^#\/admin\/restore$/, page: 'admin-restore', params: [], scope: 'admin' },
  { pattern: /^#\/admin\/ai-model-configurations$/, page: 'admin-ai-model-configurations', params: [], scope: 'admin' },
  { pattern: /^#\/admin\/ai-instruction-profiles$/, page: 'admin-ai-instruction-profiles', params: [], scope: 'admin' },
  { pattern: /^#\/work-dispatch(?:\?view=(available|active|history))?$/, page: 'work-dispatch', params: ['view'], scope: 'admin' },
  { pattern: /^#\/work-dispatch\/groups\/([^/?]+)$/, page: 'work-dispatch-group', params: ['uuid'], scope: 'admin' },
  { pattern: /^#\/ai-workspaces$/, page: 'ai-workspaces', params: [], scope: 'admin' },
  { pattern: /^#\/ai-workspaces\/([^/?]+)$/, page: 'ai-workspace-detail', params: ['uuid'], scope: 'admin' },
  { pattern: /^#\/ai-reviews(?:\?.*)?$/, page: 'ai-reviews', params: [], scope: 'admin' },
  { pattern: /^#\/ai-work-items\/([^/?]+)\/review$/, page: 'ai-review-detail', params: ['uuid'], scope: 'admin' },
];

function navigate(hash) {
  void ui.confirmNavigation(() => { window.location.hash = hash; });
}

function route() {
  const hash = window.location.hash || '#/';
  WorkspaceReviewPage.routeChanged?.(hash);

  for (const r of ROUTES) {
    const m = hash.match(r.pattern);
    if (m) {
      const paramValues = {};
      r.params.forEach((name, i) => { paramValues[name] = m[i + 1]; });

      if (r.scope && !ui.can(window.curatorPrincipal?.role, r.scope)) {
        const hasToken = api.getConnection().hasToken;
        renderRequestError(new api.Error(
          hasToken ? 'AUTHORIZATION_INSUFFICIENT_SCOPE' : 'AUTHENTICATION_MISSING_TOKEN',
          hasToken ? 'This device does not have permission.' : 'A device Token is required.',
          hasToken ? 403 : 401,
        ));
        return;
      }

      updateNavActive(hash);

      const btn = document.getElementById('pageActionBtn');
      btn.classList.add('hidden');
      btn.textContent = '';
      btn.onclick = null;

      switch (r.page) {
        case 'dashboard':       renderPage(DashboardPage.render(paramValues)); break;
        case 'albums-list':     renderPage(AlbumsPage.renderList(paramValues)); break;
        case 'album-new':       renderPage(AlbumsPage.renderDetail({ id: null })); break;
        case 'album-detail':    renderPage(AlbumsPage.renderDetail(paramValues)); break;
        case 'models-list':     renderPage(ModelsPage.renderList(paramValues)); break;
        case 'model-new':       renderPage(ModelsPage.renderDetail({ id: null })); break;
        case 'model-detail':    renderPage(ModelsPage.renderDetail(paramValues)); break;
        case 'studios-list':    renderPage(StudiosPage.renderList(paramValues)); break;
        case 'studio-new':      renderPage(StudiosPage.renderDetail({ id: null })); break;
        case 'studio-detail':   renderPage(StudiosPage.renderDetail(paramValues)); break;
        case 'statuses':        renderPage(StatusesPage.render(paramValues)); break;
        case 'import':          renderPage(ImportPage.render(paramValues)); break;
        case 'operations-list': renderPage(OperationsPage.renderList(paramValues)); break;
        case 'operation-detail': renderPage(OperationsPage.renderDetail(paramValues)); break;
        case 'issues-list':     renderPage(IssuesPage.renderList(paramValues)); break;
        case 'issue-detail':    renderPage(IssuesPage.renderDetail(paramValues)); break;
        case 'repairs-list':    renderPage(IssuesPage.renderRepairs(paramValues)); break;
        case 'repair-detail':   renderPage(IssuesPage.renderRepairDetail(paramValues)); break;
        case 'quarantine-list': renderPage(QuarantinePage.renderList(paramValues)); break;
        case 'quarantine-detail': renderPage(QuarantinePage.renderDetail(paramValues)); break;
        case 'admin-center':    renderPage(AdminCenterPage.render(paramValues)); break;
        case 'admin-devices':   renderPage(AdminAuthPage.render(paramValues)); break;
        case 'admin-backups':   renderPage(AdminBackupsPage.render(paramValues)); break;
        case 'admin-restore':   renderPage(AdminRestorePage.render(paramValues)); break;
        case 'admin-ai-model-configurations': renderPage(AIModelConfigurationsPage.render(paramValues)); break;
        case 'admin-ai-instruction-profiles': renderPage(AIInstructionProfilesPage.render(paramValues)); break;
        case 'work-dispatch':   renderPage(WorkDispatchPage.render(paramValues)); break;
        case 'work-dispatch-group': renderPage(WorkDispatchPage.renderGroup(paramValues)); break;
        case 'ai-workspaces':   renderPage(WorkspaceReviewPage.renderWorkspaces(paramValues)); break;
        case 'ai-workspace-detail': renderPage(WorkspaceReviewPage.renderWorkspace(paramValues)); break;
        case 'ai-reviews':      renderPage(WorkspaceReviewPage.renderQueue(paramValues)); break;
        case 'ai-review-detail': renderPage(WorkspaceReviewPage.renderDetail(paramValues)); break;
        default:                renderNotFound();
      }
      return;
    }
  }
  renderNotFound();
}

function renderPage(promise) {
  void Promise.resolve(promise)
    .then(() => { ui.applyPermissions(document, window.curatorPrincipal); void refreshIssueBadge(); })
    .catch(renderRequestError);
}

async function refreshIssueBadge() {
  const badge = document.getElementById('issueBadge');
  if (!badge || !api.getConnection().hasToken) return;
  try {
    const [open, active] = await Promise.all([api.get('/issues?state=Open'), api.get('/issues?state=InProgress')]);
    const count = (open.items || []).length + (active.items || []).length;
    badge.textContent = String(count); badge.classList.toggle('hidden', count === 0);
  } catch { badge.classList.add('hidden'); }
}

function updateNavActive(hash) {
  document.querySelectorAll('.rail-link').forEach(a => {
    a.classList.remove('active');
    const href = a.getAttribute('href');
    if (href === '#/' && hash === '#/') { a.classList.add('active'); return; }
    if (href !== '#/' && hash.startsWith(href)) { a.classList.add('active'); }
  });
}

function renderNotFound() {
  document.getElementById('page-content').innerHTML =
    '<div style="padding:40px;text-align:center;color:#888">Page not found</div>';
}

function renderRequestError(error) {
  ui.renderPageError(document.getElementById('page-content'), error, 'this view');
}

// ─── Toast ────────────────────────────────────────────────────────────────────

function toast(msg, type = 'ok', duration = 3500) {
  return ui.toast(msg, type, duration);
}

// ─── Modal ────────────────────────────────────────────────────────────────────

function showModal(html, options) {
  return ui.showModal(html, options);
}

function closeModal() {
  return ui.closeModal();
}

function confirmDialog(msg) {
  return ui.confirmDialog(msg);
}

// ─── Health check ─────────────────────────────────────────────────────────────

async function checkHealth() {
  try {
    const data = await api.get('/health');
    document.getElementById('healthDot').className = 'health-dot ok';
    document.getElementById('healthText').textContent =
      `DB OK · ${data.backup_count || 0} backups`;
  } catch (error) {
    document.getElementById('healthDot').className = 'health-dot error';
    document.getElementById('healthText').textContent =
      api.isAuthenticationError(error) ? 'Authorization required' : 'Backend unavailable';
  }
}

function openConnectionSettings() {
  if (window.curatorBootstrapState && !window.curatorBootstrapState.initialized) {
    openAdministratorBootstrap();
    return;
  }
  if (!window.curatorPrincipal && api.getPendingEnrollment()) {
    showPendingEnrollment();
    return;
  }
  const connection = api.getConnection();
  const principal = window.curatorPrincipal;
  const expiry = principal?.expires_at ? new Date(principal.expires_at).toLocaleString() : 'Unknown';
  const renewal = principal?.renewal;
  showModal(`
    <h3 class="modal-title">Connect to Curator</h3>
    ${principal ? `<div class="connection-summary">
      <strong>${esc(principal.device_name)}</strong>
      <span class="chip">${esc(principal.role)}</span>
      <div>Scopes: ${esc(principal.scopes.join(', '))}</div>
      <div>Expires: ${esc(expiry)}</div>
      <div>Renewal: ${renewal ? `Pending · ${esc(renewal.uuid)}` : 'Not requested'}</div>
    </div>` : '<p>No valid device connection is active.</p>'}
    <div class="form-field">
      <label for="backendUrl">Backend URL</label>
      <input id="backendUrl" value="${esc(connection.backendUrl)}" placeholder="Same origin when empty">
    </div>
    <div class="form-field">
      <label for="deviceToken">Approved device Token</label>
      <input id="deviceToken" type="password" autocomplete="off" placeholder="${connection.hasToken ? 'Enter a validated replacement to change it' : 'Required'}">
    </div>
    <p style="font-size:.8rem;color:var(--ink-soft)">A replacement is validated before the current connection changes.</p>
    <div class="modal-footer">
      ${!principal ? '<button class="btn btn-secondary" id="connectionRequestAccess">Request device access</button>' : ''}
      ${principal && !renewal ? '<button class="btn btn-secondary" id="connectionRenew">Request renewal</button>' : ''}
      ${connection.hasToken ? '<button class="btn btn-danger" id="connectionDisconnect">Disconnect</button>' : ''}
      <button class="btn btn-secondary" id="connectionCancel">Close</button>
      <button class="btn btn-primary" id="connectionSave">Validate and connect</button>
    </div>
  `);
  document.getElementById('connectionCancel').onclick = closeModal;
  document.getElementById('connectionRequestAccess')?.addEventListener('click', openDeviceAccessRequest);
  document.getElementById('connectionDisconnect')?.addEventListener('click', () => {
    api.clearToken();
    window.curatorPrincipal = null;
    closeModal();
    ui.applyPermissions(document, null);
    void checkBootstrap();
    void checkHealth();
    route();
  });
  document.getElementById('connectionRenew')?.addEventListener('click', async (event) => {
    const result = await ui.runAction(
      'request-token-renewal',
      () => api.post('/auth/renewals', { device_identity: principal.device_identity }),
      { trigger: event.currentTarget, context: 'request Token renewal' },
    );
    if (result.ok) {
      await refreshPrincipal();
      closeModal();
      toast('Token renewal requested. An administrator must approve it.', 'ok');
    }
  });
  document.getElementById('connectionSave').onclick = async (event) => {
    const token = document.getElementById('deviceToken').value;
    const nextBackendUrl = document.getElementById('backendUrl').value.trim();
    if (!token) { toast('Enter an approved device Token to connect or replace the current Token.', 'error'); return; }
    const result = await ui.runAction(
      'validate-device-connection',
      () => api.validateConnection({ backendUrl: nextBackendUrl, token }),
      { trigger: event.currentTarget, context: 'validate the device connection' },
    );
    document.getElementById('deviceToken').value = '';
    if (!result.ok) return;
    api.configure({ backendUrl: nextBackendUrl, token });
    window.curatorPrincipal = result.value;
    closeModal();
    void checkBootstrap();
    void checkHealth();
    route();
  };
}

function openDeviceAccessRequest() {
  const pending = api.getPendingEnrollment();
  if (pending) { showPendingEnrollment(); return; }
  showModal(`
    <h3 class="modal-title">Request device access</h3>
    <p>An Administrator must approve this browser profile. The Registration Proof permits a request; it is not a Device Token.</p>
    <div class="form-field"><label for="accessDeviceName">Device name</label><input id="accessDeviceName" value="${esc(navigator.userAgent.includes('Chrome') ? 'Chrome Writer' : 'Web Browser')}" autocomplete="off"></div>
    <div class="form-field"><label for="accessRole">Requested role</label><select id="accessRole"><option value="writer">Writer</option><option value="reader">Reader</option></select></div>
    <div class="form-field"><label for="accessProof">Registration Proof</label><input id="accessProof" type="password" autocomplete="off"></div>
    <div class="modal-footer"><button class="btn btn-secondary" id="accessCancel">Cancel</button><button class="btn btn-primary" id="accessSubmit">Request access</button></div>`);
  document.getElementById('accessCancel').onclick = closeModal;
  document.getElementById('accessSubmit').onclick = async event => {
    const proofInput = document.getElementById('accessProof');
    const result = await ui.runAction('request-device-access', () => api.requestDeviceAccess({
      deviceName: document.getElementById('accessDeviceName').value.trim(),
      role: document.getElementById('accessRole').value, registrationProof: proofInput.value,
    }), { trigger: event.currentTarget, context: 'request device access' });
    proofInput.value = '';
    if (result.ok) showPendingEnrollment();
  };
}

function showPendingEnrollment() {
  const pending = api.getPendingEnrollment();
  if (!pending) { openDeviceAccessRequest(); return; }
  const connectionButton = document.getElementById('connectionBtn');
  connectionButton.textContent = 'Check registration status';
  connectionButton.classList.add('btn-accent');
  connectionButton.classList.remove('btn-secondary');
  showModal(`<h3 class="modal-title">Waiting for Administrator approval</h3>
    <p><strong>${esc(pending.deviceName)}</strong> requested <span class="chip">${esc(pending.role)}</span>.</p>
    <p id="enrollmentStatus">Pending approval. You may close this window and return later in this browser profile.</p>
    <div class="modal-footer"><button class="btn btn-secondary" id="enrollmentClose">Close</button><button class="btn btn-primary" id="enrollmentCheck">Check status</button></div>`);
  document.getElementById('enrollmentClose').onclick = closeModal;
  document.getElementById('enrollmentCheck').onclick = async event => {
    const result = await ui.runAction('check-enrollment', () => api.enrollmentStatus(), { trigger: event.currentTarget, context: 'check enrollment status' });
    if (!result.ok) return;
    if (result.value.status === 'Approved') {
      window.curatorPrincipal = result.value.principal; closeModal();
      connectionButton.textContent = `${result.value.principal.device_name} · ${result.value.principal.role}`;
      connectionButton.classList.remove('btn-accent');
      connectionButton.classList.add('btn-secondary');
      ui.applyPermissions(document, result.value.principal);
      toast(`Device approved and connected as ${result.value.principal.role}.`, 'ok');
      void checkHealth(); route();
    } else document.getElementById('enrollmentStatus').textContent = `Registration status: ${result.value.status}`;
  };
}

async function refreshPrincipal() {
  if (!api.getConnection().hasToken) {
    window.curatorPrincipal = null;
    ui.applyPermissions(document, null);
    return null;
  }
  try {
    const data = await api.get('/auth/me');
    window.curatorPrincipal = data.principal;
    const button = document.getElementById('connectionBtn');
    button.textContent = `${data.principal.device_name} · ${data.principal.role}`;
    ui.applyPermissions(document, data.principal);
    return data.principal;
  } catch (error) {
    window.curatorPrincipal = null;
    const button = document.getElementById('connectionBtn');
    button.textContent = api.isAuthenticationError(error) ? 'Reconnect' : 'Connect';
    ui.applyPermissions(document, null);
    return null;
  }
}

function refreshConnectionButton() {
  const button = document.getElementById('connectionBtn');
  if (api.getPendingEnrollment() && !window.curatorPrincipal) {
    button.textContent = 'Check registration status';
    button.classList.add('btn-accent');
    button.classList.remove('btn-secondary');
    return;
  }
  button.textContent = window.curatorPrincipal
    ? `${window.curatorPrincipal.device_name} · ${window.curatorPrincipal.role}`
    : 'Connect';
  button.classList.remove('btn-accent');
  button.classList.add('btn-secondary');
}

async function checkBootstrap() {
  // Local enrollment recovery must not depend on a network round trip. This
  // also restores requests saved by a previous Web build immediately.
  refreshConnectionButton();
  try {
    const data = await api.bootstrapStatus();
    window.curatorBootstrapState = data.bootstrap;
    const button = document.getElementById('connectionBtn');
    if (!api.getPendingEnrollment() && !data.bootstrap.initialized && !api.getConnection().hasToken) {
      button.textContent = 'Initialize administrator';
      button.classList.add('btn-accent');
      button.classList.remove('btn-secondary');
    }
  } catch {
    window.curatorBootstrapState = null;
  }
}

function openAdministratorBootstrap() {
  const state = window.curatorBootstrapState || {};
  ui.showModal(`
    <h3 class="modal-title">Initialize Curator administrator</h3>
    <p>On the Backend host, run <code>python3 -m apps.backend auth create-bootstrap-code</code>. Enter the one-time Code below within ten minutes.</p>
    ${state.code_available ? '' : '<div class="feedback feedback-warning"><p>No active Bootstrap Code is available yet.</p></div>'}
    <div class="form-field">
      <label for="bootstrapDeviceName">Administrator device name</label>
      <input id="bootstrapDeviceName" value="Local Administrator" autocomplete="off">
    </div>
    <div class="form-field" style="margin-top:12px">
      <label for="bootstrapCode">Bootstrap Code</label>
      <input id="bootstrapCode" type="password" autocomplete="one-time-code" placeholder="Required">
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" id="bootstrapCancel">Cancel</button>
      <button class="btn btn-primary" id="bootstrapSubmit">Initialize</button>
    </div>
  `);
  document.getElementById('bootstrapCancel').onclick = closeModal;
  document.getElementById('bootstrapSubmit').onclick = async (event) => {
    const codeInput = document.getElementById('bootstrapCode');
    const deviceName = document.getElementById('bootstrapDeviceName').value.trim();
    const code = codeInput.value;
    if (!deviceName || !code) { toast('Device name and Bootstrap Code are required.', 'error'); return; }
    const result = await ui.runAction('administrator-bootstrap', () => api.completeBootstrap({
      code,
      device_name: deviceName,
      device_identity: api.getDeviceIdentity(),
    }), { trigger: event.currentTarget, context: 'initialize the administrator' });
    codeInput.value = '';
    if (!result.ok) return;
    const issued = result.value;
    api.configure({ token: issued.token });
    window.curatorBootstrapState = { initialized: true, code_available: false };
    ui.showModal(`
      <h3 class="modal-title">Administrator initialized</h3>
      <div class="feedback feedback-warning">
        <p>This Admin Token is shown once. It is already stored in this browser profile; copy it to secure storage before continuing.</p>
      </div>
      <pre class="one-time-token" id="issuedAdminToken"></pre>
      <label class="acknowledgement"><input type="checkbox" id="bootstrapAcknowledged"> I have stored the Token securely.</label>
      <div class="modal-footer"><button class="btn btn-primary" id="bootstrapFinish" disabled>Continue</button></div>
    `, { dismissible: false });
    document.getElementById('issuedAdminToken').textContent = issued.token;
    document.getElementById('bootstrapAcknowledged').onchange = (changeEvent) => {
      document.getElementById('bootstrapFinish').disabled = !changeEvent.target.checked;
    };
    document.getElementById('bootstrapFinish').onclick = () => {
      closeModal();
      void checkBootstrap();
      void checkHealth();
      void refreshPrincipal().then(route);
    };
  };
}

// ─── Global search (simple: navigate to albums with q param) ──────────────────

document.getElementById('globalSearch').addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    const q = e.target.value.trim();
    if (q) navigate(`#/albums?q=${encodeURIComponent(q)}`);
  }
});

// ─── Init ─────────────────────────────────────────────────────────────────────

window.addEventListener('hashchange', route);
window.addEventListener('beforeunload', event => {
  if (!ui.hasUnsavedChanges()) return;
  event.preventDefault();
  event.returnValue = '';
});
document.addEventListener('click', event => {
  const link = event.target.closest?.('a[href^="#/"]');
  if (!link || !ui.hasUnsavedChanges()) return;
  event.preventDefault();
  void ui.confirmNavigation(() => { window.location.hash = link.getAttribute('href'); });
});
window.addEventListener('load', () => {
  document.getElementById('connectionBtn').onclick = openConnectionSettings;
  refreshConnectionButton();
  void checkBootstrap();
  void refreshPrincipal().then(route);
  checkHealth();
  setInterval(checkHealth, 60000);
  ui.recoverInterruptedReview();
});
