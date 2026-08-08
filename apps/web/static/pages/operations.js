const OperationsPage = {
  _cursor: '',
  _nextCursor: '',
  _cursorStack: [],
  _filters: { status: '', operation_type: '', started_from: '', started_to: '' },

  async renderList() {
    document.getElementById('pageActionBtn').classList.add('hidden');
    const params = new URLSearchParams((window.location.hash.split('?')[1] || ''));
    this._filters = {
      status: params.get('status') || '', operation_type: params.get('operation_type') || '',
      started_from: params.get('started_from') || '', started_to: params.get('started_to') || '',
    };
    this._cursor = '';
    this._cursorStack = [];
    await this._loadList();
  },

  _query() {
    const params = new URLSearchParams({ limit: '25' });
    Object.entries(this._filters).forEach(([key, value]) => { if (value) params.set(key, value); });
    if (this._cursor) params.set('cursor', this._cursor);
    return params.toString();
  },

  async _loadList() {
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading Operation history…</div>';
    try {
      const result = await api.get(`/operations?${this._query()}`);
      this._nextCursor = result.meta?.pagination?.next_cursor || '';
      const rows = (result.operations || []).map(operation => `<tr>
        <td><a href="#/operations/${encodeURIComponent(operation.uuid)}" class="path-mono">${esc(operation.uuid)}</a></td>
        <td>${esc(operation.operation_type)}</td><td><span class="chip ${this._statusClass(operation.status)}">${esc(operation.status)}</span></td>
        <td>${esc(operation.summary || '—')}</td><td>${esc(this._formatTime(operation.started_at))}</td>
      </tr>`).join('');
      const pagination = result.meta?.pagination || {};
      el.innerHTML = `
        <div class="page-header"><h1 class="page-title">Operations</h1></div>
        <div class="card" style="padding:16px;margin-bottom:16px">
          <div class="form-grid">
            <div class="form-field"><label for="opStatus">Status</label><select id="opStatus"><option value="">All</option>
              ${['Pending','Running','Succeeded','Failed','NeedsRepair','Cancelled'].map(v => `<option ${this._filters.status === v ? 'selected' : ''}>${v}</option>`).join('')}</select></div>
            <div class="form-field"><label for="opType">Operation type</label><input id="opType" value="${esc(this._filters.operation_type)}" placeholder="e.g. import"></div>
            <div class="form-field"><label for="opFrom">Started from</label><input id="opFrom" type="datetime-local" value="${esc(this._localDate(this._filters.started_from))}"></div>
            <div class="form-field"><label for="opTo">Started to</label><input id="opTo" type="datetime-local" value="${esc(this._localDate(this._filters.started_to))}"></div>
          </div>
          <div style="display:flex;gap:8px;margin-top:12px"><button class="btn btn-primary" onclick="OperationsPage._applyFilters()">Filter</button>
            <button class="btn btn-secondary" onclick="OperationsPage._clearFilters()">Clear</button></div>
        </div>
        <div class="card table-wrap"><table><thead><tr><th>Operation</th><th>Type</th><th>Status</th><th>Summary</th><th>Started</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="5" style="text-align:center;color:var(--ink-soft)">No Operations match these filters</td></tr>'}</tbody></table></div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px">
          <span style="font-size:.82rem;color:var(--ink-soft)">${pagination.total ?? 0} matching Operations</span><div style="display:flex;gap:8px">
          <button class="btn btn-secondary" ${this._cursorStack.length ? '' : 'disabled'} onclick="OperationsPage._previousPage()">← Previous</button>
          <button class="btn btn-secondary" ${this._nextCursor ? '' : 'disabled'} onclick="OperationsPage._nextPage()">Next →</button></div></div>`;
    } catch (error) { ui.renderPageError(el, error, 'Operation history'); }
  },

  _statusClass(status) {
    return status === 'Succeeded' ? 'chip-ok' : status === 'NeedsRepair' ? 'chip-warn' : ['Failed','Cancelled'].includes(status) ? 'chip-error' : '';
  },
  _formatTime(value) { return value ? new Date(value).toLocaleString() : '—'; },
  _localDate(value) { return value ? value.slice(0, 16) : ''; },

  _applyFilters() {
    const localIso = id => { const value = document.getElementById(id)?.value; return value ? new Date(value).toISOString() : ''; };
    this._filters = { status: document.getElementById('opStatus').value,
      operation_type: document.getElementById('opType').value.trim(), started_from: localIso('opFrom'), started_to: localIso('opTo') };
    const params = new URLSearchParams();
    Object.entries(this._filters).forEach(([key, value]) => { if (value) params.set(key, value); });
    window.location.hash = `#/operations${params.size ? `?${params}` : ''}`;
  },
  _clearFilters() { window.location.hash = '#/operations'; if (window.location.hash === '#/operations') this.renderList(); },
  _nextPage() { if (!this._nextCursor) return; this._cursorStack.push(this._cursor); this._cursor = this._nextCursor; this._loadList(); },
  _previousPage() { if (!this._cursorStack.length) return; this._cursor = this._cursorStack.pop(); this._loadList(); },

  async renderDetail({ uuid }) {
    document.getElementById('pageActionBtn').classList.add('hidden');
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading Operation…</div>';
    try {
      const result = await api.get(`/operations/${encodeURIComponent(uuid)}`);
      const op = result.operation;
      const links = [
        op.related_operation_uuid && ['Related Operation', `#/operations/${op.related_operation_uuid}`, op.related_operation_uuid],
        op.parent_operation_uuid && ['Parent Operation', `#/operations/${op.parent_operation_uuid}`, op.parent_operation_uuid],
        op.issue_uuid && ['Issue', `#/issues/${op.issue_uuid}`, op.issue_uuid],
        op.repair_uuid && ['Repair', `#/repairs/${op.repair_uuid}`, op.repair_uuid],
      ].filter(Boolean);
      const unavailable = [['Entity', op.entity_uuid], ['Import', op.import_uuid], ['Batch', op.batch_uuid]].filter(([, value]) => value);
      el.innerHTML = `
        <div class="page-header"><div><a href="#/operations">← Operations</a><h1 class="page-title">Operation Detail</h1></div></div>
        <div class="card" style="padding:20px;margin-bottom:16px"><div style="display:flex;gap:10px;align-items:center">
          <span class="chip ${this._statusClass(op.status)}">${esc(op.status)}</span><strong>${esc(op.operation_type)}</strong></div>
          <p>${esc(op.summary || 'No summary recorded.')}</p><div class="path-mono">${esc(op.uuid)}</div></div>
        <div class="card" style="padding:20px;margin-bottom:16px"><div class="form-section-title">Durable outcome</div>
          <dl class="detail-list"><dt>Initiator</dt><dd>${esc(op.initiator || '—')}</dd><dt>Started</dt><dd>${esc(this._formatTime(op.started_at))}</dd>
          <dt>Ended</dt><dd>${esc(this._formatTime(op.ended_at))}</dd><dt>Error category</dt><dd>${esc(op.error_category || '—')}</dd>
          <dt>Error code</dt><dd>${esc(op.error_code || '—')}</dd><dt>Repair state</dt><dd>${esc(op.repair_state || '—')}</dd></dl>
          ${Object.hasOwn(op, 'recovery_context') && op.recovery_context ? `<div class="alert alert-warning"><strong>Recovery context</strong><br>${esc(op.recovery_context)}</div>` : ''}</div>
        <div class="card" style="padding:20px"><div class="form-section-title">Traceability</div>
          ${links.map(([label, href, value]) => `<p><strong>${label}:</strong> <a href="${href}">${esc(value)}</a></p>`).join('')}
          ${unavailable.map(([label, value]) => `<p><strong>${label}:</strong> <span class="path-mono">${esc(value)}</span> <span style="color:var(--ink-soft)">(detail route unavailable)</span></p>`).join('')}
          ${!links.length && !unavailable.length ? '<p style="color:var(--ink-soft)">No related record identifiers were retained.</p>' : ''}
        </div>`;
    } catch (error) { ui.renderPageError(el, error, 'Operation detail'); }
  },
};
