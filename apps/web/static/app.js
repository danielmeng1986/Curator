// ─── Router ──────────────────────────────────────────────────────────────────

const ROUTES = [
  { pattern: /^#\/$/, page: 'dashboard', params: [] },
  { pattern: /^#\/albums$/, page: 'albums-list', params: [] },
  { pattern: /^#\/albums\/new$/, page: 'album-new', params: [] },
  { pattern: /^#\/albums\/(\d+)$/, page: 'album-detail', params: ['id'] },
  { pattern: /^#\/models$/, page: 'models-list', params: [] },
  { pattern: /^#\/models\/new$/, page: 'model-new', params: [] },
  { pattern: /^#\/models\/(\d+)$/, page: 'model-detail', params: ['id'] },
  { pattern: /^#\/studios$/, page: 'studios-list', params: [] },
  { pattern: /^#\/studios\/new$/, page: 'studio-new', params: [] },
  { pattern: /^#\/studios\/(\d+)$/, page: 'studio-detail', params: ['id'] },
  { pattern: /^#\/statuses$/, page: 'statuses', params: [] },
  { pattern: /^#\/import\/albums$/, page: 'import', params: [] },
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

      updateNavActive(hash);

      const btn = document.getElementById('pageActionBtn');
      btn.classList.add('hidden');
      btn.textContent = '';
      btn.onclick = null;

      switch (r.page) {
        case 'dashboard':       void DashboardPage.render(paramValues).catch(renderRequestError); break;
        case 'albums-list':     void AlbumsPage.renderList(paramValues).catch(renderRequestError); break;
        case 'album-new':       void AlbumsPage.renderDetail({ id: null }).catch(renderRequestError); break;
        case 'album-detail':    void AlbumsPage.renderDetail(paramValues).catch(renderRequestError); break;
        case 'models-list':     void ModelsPage.renderList(paramValues).catch(renderRequestError); break;
        case 'model-new':       void ModelsPage.renderDetail({ id: null }).catch(renderRequestError); break;
        case 'model-detail':    void ModelsPage.renderDetail(paramValues).catch(renderRequestError); break;
        case 'studios-list':    void StudiosPage.renderList(paramValues).catch(renderRequestError); break;
        case 'studio-new':      void StudiosPage.renderDetail({ id: null }).catch(renderRequestError); break;
        case 'studio-detail':   void StudiosPage.renderDetail(paramValues).catch(renderRequestError); break;
        case 'statuses':        void StatusesPage.render(paramValues).catch(renderRequestError); break;
        case 'import':          void ImportPage.render(paramValues).catch(renderRequestError); break;
        default:                renderNotFound();
      }
      return;
    }
  }
  renderNotFound();
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
  showModal(`
    <h3 class="modal-title">Connect to Curator</h3>
    <div class="form-field">
      <label>Backend URL</label>
      <input id="backendUrl" value="${esc(connection.backendUrl)}" placeholder="Same origin when empty">
    </div>
    <div class="form-field">
      <label>Approved device token</label>
      <input id="deviceToken" type="password" placeholder="${connection.hasToken ? 'Stored locally; enter a replacement to change it' : 'Required'}">
    </div>
    <p style="font-size:.8rem;color:var(--ink-soft)">Stored only in this browser profile; never in source files.</p>
    <div class="modal-footer">
      <button class="btn btn-secondary" id="connectionCancel">Cancel</button>
      <button class="btn btn-primary" id="connectionSave">Save</button>
    </div>
  `);
  document.getElementById('connectionCancel').onclick = closeModal;
  document.getElementById('connectionSave').onclick = () => {
    const token = document.getElementById('deviceToken').value;
    api.configure({ backendUrl: document.getElementById('backendUrl').value, ...(token ? { token } : {}) });
    closeModal();
    void checkBootstrap();
    void checkHealth();
    route();
  };
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
      button.textContent = 'Connect';
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
      route();
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
  route();
  checkHealth();
  setInterval(checkHealth, 60000);
});
