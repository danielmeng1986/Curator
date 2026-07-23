const DashboardPage = {
  async render(params) {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading…</div>';
    try {
      const [health, statuses, albums, models, studios, workspace] = await Promise.all([
        api.get('/health'),
        api.get('/statuses'),
        api.get('/albums?limit=1&offset=0'),
        api.get('/models?limit=1&offset=0'),
        api.get('/studios?limit=1&offset=0'),
        api.get('/workspace/albums?limit=1&offset=0'),
      ]);

      const statusRows = (statuses.statuses || []).map(s => `
        <tr>
          <td>${esc(s.name)}</td>
          <td>${s.album_count || 0}</td>
          <td>${s.workspace_album_count || 0}</td>
          <td style="color:var(--ink-soft)">${esc(s.description || '')}</td>
        </tr>`).join('');

      const nextBackup = health.next_backup_at
        ? health.next_backup_at.replace('T', ' ').slice(0, 16) : '—';

      el.innerHTML = `
        <div class="page-header"><h1 class="page-title">Dashboard</h1></div>
        <div class="stats-grid">
          <div class="stat-card" style="cursor:pointer" onclick="navigate('#/albums')">
            <div class="stat-number">${albums.total || 0}</div>
            <div class="stat-label">Albums</div>
          </div>
          <div class="stat-card" style="cursor:pointer" onclick="navigate('#/models')">
            <div class="stat-number">${models.total || 0}</div>
            <div class="stat-label">Models</div>
          </div>
          <div class="stat-card" style="cursor:pointer" onclick="navigate('#/studios')">
            <div class="stat-number">${studios.total || 0}</div>
            <div class="stat-label">Studios</div>
          </div>
          <div class="stat-card" style="cursor:pointer" onclick="navigate('#/workspace/albums')">
            <div class="stat-number">${workspace.total || 0}</div>
            <div class="stat-label">Workspace</div>
          </div>
        </div>
        <div class="card" style="padding:16px;margin-bottom:16px">
          <div class="form-section-title">Database</div>
          <p style="margin:0;font-size:.88rem;color:var(--ink-soft)">
            Path: <code>${esc(health.database_path || '')}</code><br>
            Backups: <strong>${health.backup_count || 0}</strong> ·
            Next backup: <strong>${nextBackup}</strong>
          </p>
        </div>
        <div class="card" style="padding:16px">
          <div class="form-section-title">Statuses</div>
          <div class="table-wrap">
            <table><thead><tr>
              <th>Name</th><th>Albums</th><th>Workspace</th><th>Description</th>
            </tr></thead>
            <tbody>${statusRows || '<tr><td colspan="4" style="color:var(--ink-soft);text-align:center">No statuses</td></tr>'}</tbody>
            </table>
          </div>
        </div>
      `;
    } catch (e) {
      el.innerHTML = `<div class="error-msg">Error loading dashboard: ${esc(e.message)}</div>`;
    }
  }
};

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
