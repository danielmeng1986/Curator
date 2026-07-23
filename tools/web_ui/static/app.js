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
  { pattern: /^#\/workspace\/albums$/, page: 'workspace-list', params: [] },
  { pattern: /^#\/workspace\/albums\/(\d+)$/, page: 'workspace-detail', params: ['id'] },
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
        case 'dashboard':       DashboardPage.render(paramValues); break;
        case 'albums-list':     AlbumsPage.renderList(paramValues); break;
        case 'album-new':       AlbumsPage.renderDetail({ id: null }); break;
        case 'album-detail':    AlbumsPage.renderDetail(paramValues); break;
        case 'models-list':     ModelsPage.renderList(paramValues); break;
        case 'model-new':       ModelsPage.renderDetail({ id: null }); break;
        case 'model-detail':    ModelsPage.renderDetail(paramValues); break;
        case 'studios-list':    StudiosPage.renderList(paramValues); break;
        case 'studio-new':      StudiosPage.renderDetail({ id: null }); break;
        case 'studio-detail':   StudiosPage.renderDetail(paramValues); break;
        case 'statuses':        StatusesPage.render(paramValues); break;
        case 'workspace-list':  WorkspacePage.renderList(paramValues); break;
        case 'workspace-detail':WorkspacePage.renderDetail(paramValues); break;
        case 'import':          ImportPage.render(paramValues); break;
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
  } catch {
    document.getElementById('healthDot').className = 'health-dot error';
    document.getElementById('healthText').textContent = 'DB Error';
  }
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
  route();
  checkHealth();
  setInterval(checkHealth, 60000);
});
