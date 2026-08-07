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
  const message = api.isAuthenticationError(error)
    ? 'Authorization is required. Select Connect and provide an approved device token.'
    : `Unable to load this view: ${esc(error.message || 'Backend request failed.')}`;
  document.getElementById('page-content').innerHTML = `<div class="error-msg">${message}</div>`;
}

// ─── Toast ────────────────────────────────────────────────────────────────────

function toast(msg, type = 'ok', duration = 3500) {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), duration);
}

// ─── Modal ────────────────────────────────────────────────────────────────────

function showModal(html) {
  const overlay = document.getElementById('modal-overlay');
  const box = document.getElementById('modal-box');
  box.innerHTML = html;
  overlay.classList.remove('hidden');
  overlay.onclick = (e) => { if (e.target === overlay) closeModal(); };
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  document.getElementById('modal-box').innerHTML = '';
}

function confirmDialog(msg) {
  return new Promise(resolve => {
    showModal(`
      <h3 class="modal-title">Confirm</h3>
      <p style="margin:0 0 4px">${msg}</p>
      <div class="modal-footer">
        <button class="btn btn-secondary" id="confirmNo">Cancel</button>
        <button class="btn btn-danger" id="confirmYes">Confirm</button>
      </div>
    `);
    document.getElementById('confirmYes').onclick = () => { closeModal(); resolve(true); };
    document.getElementById('confirmNo').onclick  = () => { closeModal(); resolve(false); };
  });
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
    checkHealth();
    route();
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
  route();
  checkHealth();
  setInterval(checkHealth, 60000);
});
