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
];

function navigate(hash) {
  window.location.hash = hash;
}

function route() {
  const hash = window.location.hash || '#/';

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
        default:                renderNotFound();
      }
      return;
    }
  }
  renderNotFound();
}

function renderPage(promise) {
  void Promise.resolve(promise)
    .then(() => ui.applyPermissions(document, window.curatorPrincipal))
    .catch(renderRequestError);
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

function showModal(html) {
  return ui.showModal(html);
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
      ${principal && !renewal ? '<button class="btn btn-secondary" id="connectionRenew">Request renewal</button>' : ''}
      ${connection.hasToken ? '<button class="btn btn-danger" id="connectionDisconnect">Disconnect</button>' : ''}
      <button class="btn btn-secondary" id="connectionCancel">Close</button>
      <button class="btn btn-primary" id="connectionSave">Validate and connect</button>
    </div>
  `);
  document.getElementById('connectionCancel').onclick = closeModal;
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

async function checkBootstrap() {
  try {
    const data = await api.bootstrapStatus();
    window.curatorBootstrapState = data.bootstrap;
    const button = document.getElementById('connectionBtn');
    if (!data.bootstrap.initialized && !api.getConnection().hasToken) {
      button.textContent = 'Initialize administrator';
      button.classList.add('btn-accent');
      button.classList.remove('btn-secondary');
    } else {
      button.textContent = window.curatorPrincipal
        ? `${window.curatorPrincipal.device_name} · ${window.curatorPrincipal.role}`
        : 'Connect';
      button.classList.remove('btn-accent');
      button.classList.add('btn-secondary');
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
window.addEventListener('load', () => {
  document.getElementById('connectionBtn').onclick = openConnectionSettings;
  void checkBootstrap();
  void refreshPrincipal().then(route);
  checkHealth();
  setInterval(checkHealth, 60000);
});
