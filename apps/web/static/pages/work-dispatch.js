const WorkDispatchPage = {
  _view: 'available',
  _candidates: [],
  _selected: new Set(),
  _workspaces: [],
  _configurations: [],
  _workerKinds: [],
  _preview: null,

  _configurationSummary(item) {
    return `<strong>${esc(item.name)}</strong><span class="config-model">${esc(item.model_identifier)} · <code>${esc(item.model_file)}</code></span>
      <span class="config-parameters">${item.sample_count} images · context ${item.context_size} · max ${item.max_tokens} tokens · image ${item.image_max_tokens} · temp ${item.temperature} · ${item.threads} threads · ${item.gpu_layers} GPU layers</span>
      <span class="config-prompts">Vision ${esc(item.vision_prompt_version)} · Writer ${esc(item.writer_prompt_version)}</span>`;
  },

  _stage(item) {
    if (item.review_state) return item.review_state;
    if (item.run_state === 'Completed') return 'Ready for review';
    if (item.run_state === 'Failed') return 'Failed';
    if (item.run_state === 'Cancelled') return 'Cancelled';
    if (item.result_state === 'AwaitingWriter') return 'Writer analysis';
    if (item.run_state === 'Claimed') return 'Preparing evidence / Vision analysis';
    return 'Waiting for Worker';
  },

  _itemRows(items, albumTitle = '') {
    return (items || []).map(item => {
      const config=item.configuration_snapshot || {};
      return `<tr><td>${esc(albumTitle || '—')}</td><td><strong>${esc(config.name || 'Unknown configuration')}</strong><div class="table-secondary"><code>${esc(config.model_file || '—')}</code></div></td>
        <td><span class="chip ${item.run_state === 'Failed' ? 'chip-error' : item.run_state === 'Completed' ? 'chip-ok' : 'chip-warn'}">${esc(this._stage(item))}</span><div class="table-secondary">Run ${esc(item.run_state)}${item.result_state ? ` · Result ${esc(item.result_state)}` : ''}</div></td>
        <td>${item.attempt_count}</td><td>${item.updated_at ? esc(new Date(item.updated_at).toLocaleString()) : '—'}${item.lease_expires_at ? `<div class="table-secondary">Lease until ${esc(new Date(item.lease_expires_at).toLocaleString())}</div>` : ''}</td>
        <td>${item.last_error ? `<span class="text-error">${esc(item.last_error)}</span>` : '—'}</td><td><a class="btn btn-secondary" href="#/ai-work-items/${esc(item.item_uuid)}/review">Open</a></td></tr>`;
    }).join('');
  },

  async render({ view = 'available' } = {}) {
    this._view = ['available', 'active', 'history'].includes(view) ? view : 'available';
    this._selected = new Set();
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading Work Dispatch…</div>';
    try {
      const [workspaces, configurations, kinds] = await Promise.all([
        api.get('/ai-workspaces'), api.get('/ai-model-configurations'), api.get('/work-dispatch/worker-kinds'),
      ]);
      this._workspaces = (workspaces.items || []).filter(item => item.lifecycle_state === 'Open');
      this._configurations = (configurations.items || []).filter(item => item.enabled);
      this._workerKinds = kinds.items || [];
      await this.loadView();
    } catch (error) { ui.renderPageError(el, error, 'Work Dispatch'); }
  },

  async renderGroup({ uuid }) {
    const el=document.getElementById('page-content'); el.innerHTML='<div class="loading">Loading Dispatch Group…</div>';
    try {
      const result=await api.get(`/work-dispatch/groups/${encodeURIComponent(uuid)}`); const detail=result.group; const group=detail.group;
      el.innerHTML=`<div class="page-header"><div><a href="#/work-dispatch">← Work Dispatch</a><h1 class="page-title">Dispatch Group</h1></div><div><button class="btn btn-secondary" onclick="WorkDispatchPage.renderGroup({uuid:'${esc(group.uuid)}'})">Refresh progress</button> <span class="chip">${esc(group.group_state)}</span></div></div>
        <div class="card workspace-summary"><p>Group: <code>${esc(group.uuid)}</code></p><p>Album #${group.album_id} · Worker ${esc(group.worker_kind)} · Version ${group.version}</p>
        ${detail.blockers.length ? `<div class="alert alert-warning">${detail.blockers.map(item=>esc(item.reason)).join(' · ')}</div>` : ''}
        <div class="table-wrap"><table class="work-progress"><thead><tr><th>Album</th><th>Configuration</th><th>Current stage</th><th>Attempts</th><th>Last activity</th><th>Failure</th><th>Details</th></tr></thead><tbody>${this._itemRows(detail.items, `Album #${group.album_id}`)}</tbody></table></div>
        <div class="detail-actions">
        ${detail.allowed_actions.map(action=>`<button class="btn ${action==='release'?'btn-primary':'btn-danger'}" onclick="WorkDispatchPage.closeGroup('${esc(group.uuid)}','${action}',${group.version},this)">${action}</button>`).join('')}</div></div>`;
    } catch(error){ui.renderPageError(el,error,'Dispatch Group');}
  },

  async closeGroup(uuid,action,version,trigger){
    const reason=window.prompt(`Reason to ${action} this Group:`); if(!reason?.trim())return;
    const result=await ui.runAction(`group-${action}`,()=>api.post(`/work-dispatch/groups/${uuid}/${action}`,{expected_version:version,reason:reason.trim()}),{trigger,context:`${action} the Dispatch Group`});
    if(result.ok)await this.renderGroup({uuid});
  },

  async loadView() {
    const el = document.getElementById('page-content');
    const q = document.getElementById('dispatchSearch')?.value?.trim() || '';
    const workerKind = document.getElementById('dispatchWorkerKind')?.value || this._workerKinds[0]?.worker_kind || '';
    try {
      if (this._view === 'available') {
        const result = await api.get(`/work-dispatch/candidates?worker_kind=${encodeURIComponent(workerKind)}&availability=available&limit=100${q ? `&q=${encodeURIComponent(q)}` : ''}`);
        this._candidates = result;
      } else {
        this._candidates = await api.get(`/work-dispatch/groups?view=${this._view}&worker_kind=${encodeURIComponent(workerKind)}&limit=100`);
      }
      this._renderShell({ q, workerKind });
    } catch (error) { ui.renderPageError(el, error, 'Work Dispatch'); }
  },

  _renderShell({ q = '', workerKind = '' } = {}) {
    const el = document.getElementById('page-content');
    const tabs = [['available','Available'],['active','Active'],['history','History']];
    el.innerHTML = `<div class="page-header"><div><h1 class="page-title">Album Work Dispatch</h1>
      <p class="page-subtitle">Assign selected Albums to a Worker without changing Album Status.</p></div>${this._view !== 'available' ? '<button class="btn btn-secondary" onclick="WorkDispatchPage.loadView()">Refresh progress</button>' : ''}</div>
      <div class="dispatch-tabs" role="tablist">${tabs.map(([key,label]) => `<button class="btn ${this._view === key ? 'btn-primary' : 'btn-secondary'}" onclick="WorkDispatchPage.changeView('${key}')">${label}</button>`).join('')}</div>
      <div class="filter-bar">
        <label>Worker <select id="dispatchWorkerKind" onchange="WorkDispatchPage.loadView()">${this._workerKinds.map(kind => `<option value="${esc(kind.worker_kind)}" ${kind.worker_kind === workerKind ? 'selected' : ''}>${esc(kind.worker_kind)}</option>`).join('')}</select></label>
        ${this._view === 'available' ? `<label>Album search <input id="dispatchSearch" value="${esc(q)}" placeholder="Title" onkeydown="if(event.key==='Enter') WorkDispatchPage.loadView()"></label><button class="btn btn-secondary" onclick="WorkDispatchPage.loadView()">Apply</button>` : ''}
      </div>
      ${this._view === 'available' ? this._availableHtml() : this._groupsHtml()}`;
  },

  _availableHtml() {
    const rows = Array.isArray(this._candidates) ? this._candidates : [];
    return `<div class="dispatch-controls card"><div class="form-grid">
      <div class="form-field"><label for="dispatchWorkspace">Open Workspace</label><select id="dispatchWorkspace">${this._workspaces.map(item => `<option value="${esc(item.uuid)}">${esc(item.title)}</option>`).join('')}</select></div>
      <div class="form-field form-field-full"><label>Model configurations</label><p class="field-help">Each selected configuration creates a separate comparable run for every selected Album.</p><div class="dispatch-configs">${this._configurations.map(item => `<label class="dispatch-config"><input type="checkbox" name="dispatchConfig" value="${esc(item.uuid)}"><span>${this._configurationSummary(item)}</span></label>`).join('') || 'No Active configuration'}</div></div>
      </div><div class="detail-actions"><button class="btn btn-secondary" onclick="WorkDispatchPage.selectPage()">Select current page</button>
      <button class="btn btn-secondary" onclick="WorkDispatchPage.selectFirst()">Select first N…</button>
      <button id="dispatchPreviewBtn" class="btn btn-primary" onclick="WorkDispatchPage.preview()" disabled>Preview dispatch</button>
      <span id="dispatchSelectionCount">0 Albums selected</span></div></div>
      <div class="card table-wrap"><table><thead><tr><th>Select</th><th>Album</th><th>Studio</th><th>Status</th><th>Eligibility</th><th>Warnings</th></tr></thead><tbody>
      ${rows.map(item => `<tr><td><input type="checkbox" data-dispatch-album="${item.id}" ${item.can_dispatch ? '' : 'disabled'} onchange="WorkDispatchPage.toggle(${item.id},this.checked)"></td>
        <td><a href="#/albums/${item.id}">${esc(item.title)}</a></td><td>${esc(item.studio_name || '—')}</td><td>${esc(item.status_name || '—')}</td>
        <td><span class="chip ${item.can_dispatch ? 'chip-ok' : 'chip-error'}">${esc(item.eligibility)}</span>${item.eligibility_reason ? `<div>${esc(item.eligibility_reason)}</div>` : ''}</td>
        <td>${(item.warnings || []).map(value => `<span class="chip chip-warn">${esc(value)}</span>`).join(' ') || '—'}</td></tr>`).join('') || '<tr><td colspan="6">No Albums are currently available for this Worker.</td></tr>'}
      </tbody></table></div>`;
  },

  _groupsHtml() {
    const rows = Array.isArray(this._candidates) ? this._candidates : [];
    return rows.map(group => `<section class="card dispatch-group-card"><div class="dispatch-group-heading"><div><a href="#/albums/${group.album_id}"><strong>${esc(group.album_title)}</strong></a><div class="table-secondary"><a href="#/work-dispatch/groups/${esc(group.uuid)}">Group details</a> · Workspace <a href="#/ai-workspaces/${esc(group.workspace_uuid)}">${esc(group.workspace_uuid)}</a></div></div><span class="chip ${group.group_state === 'Active' ? 'chip-warn' : 'chip-ok'}">${esc(group.group_state)}</span></div>
      <div class="table-wrap"><table class="work-progress"><thead><tr><th>Album</th><th>Configuration</th><th>Current stage</th><th>Attempts</th><th>Last activity</th><th>Failure</th><th>Details</th></tr></thead><tbody>${this._itemRows(group.items, group.album_title)}</tbody></table></div>
      <div class="dispatch-group-footer">${group.item_count} runs · ${group.open_review_count} open reviews · ${group.promotion_count} promotions${group.closure_operation_uuid ? ` · <a href="#/operations/${esc(group.closure_operation_uuid)}">Operation</a>` : ''}</div></section>`).join('') || `<div class="card empty-state">No ${esc(this._view)} Groups.</div>`;
  },

  changeView(view) { this._view = view; this._selected = new Set(); void this.loadView(); },
  toggle(id, checked) { if (checked) this._selected.add(id); else this._selected.delete(id); this._selectionChanged(); },
  _selectionChanged() {
    const count = this._selected.size;
    const label = document.getElementById('dispatchSelectionCount'); if (label) label.textContent = `${count} Albums selected`;
    const button = document.getElementById('dispatchPreviewBtn'); if (button) button.disabled = count === 0;
  },
  selectPage() {
    this._selected = new Set((Array.isArray(this._candidates) ? this._candidates : []).filter(item => item.can_dispatch).map(item => item.id));
    document.querySelectorAll('[data-dispatch-album]').forEach(input => { input.checked = this._selected.has(Number(input.dataset.dispatchAlbum)); });
    this._selectionChanged();
  },
  selectFirst() {
    const raw = window.prompt('How many currently filtered Albums should be selected? (1–100)', '10');
    const count = Number(raw); if (!Number.isInteger(count) || count < 1 || count > 100) { toast('Enter a number from 1 to 100.', 'error'); return; }
    this._selected = new Set((Array.isArray(this._candidates) ? this._candidates : []).filter(item => item.can_dispatch).slice(0,count).map(item => item.id));
    document.querySelectorAll('[data-dispatch-album]').forEach(input => { input.checked = this._selected.has(Number(input.dataset.dispatchAlbum)); });
    this._selectionChanged();
  },

  async preview() {
    const configurations = [...document.querySelectorAll('input[name="dispatchConfig"]:checked')].map(input => input.value);
    if (!configurations.length) { toast('Select at least one model configuration.', 'error'); return; }
    const result = await ui.runAction('dispatch-preview', () => api.post('/work-dispatch/preview', {
      worker_kind: document.getElementById('dispatchWorkerKind').value,
      workspace_uuid: document.getElementById('dispatchWorkspace').value,
      configuration_uuids: configurations, album_ids: [...this._selected],
    }), { context: 'preview Work Dispatch' });
    if (!result.ok) return;
    this._preview = result.value.preview;
    const preview = this._preview;
    ui.showReviewedAction(`<h3 id="modal-title" class="modal-title">Confirm Album Work Dispatch</h3>
      <div class="stats-grid"><div class="stat-card"><div class="stat-number">${preview.summary.albums}</div><div class="stat-label">Albums / Groups</div></div>
      <div class="stat-card"><div class="stat-number">${preview.summary.work_items}</div><div class="stat-label">Work Items</div></div></div>
      <p>Each Album receives one exclusive Group and reservation. Its Status will not change.</p>
      <ul>${preview.items.map(item => `<li>${esc(item.title)} — ${esc(item.eligibility)} ${(item.warnings || []).map(esc).join(', ')}</li>`).join('')}</ul>
      <label class="acknowledgement"><input id="dispatchAcknowledge" type="checkbox" onchange="document.getElementById('executeDispatchBtn').disabled=!this.checked"> I reviewed this zero-write preview.</label>
      <div class="modal-footer"><button class="btn btn-secondary" onclick="WorkDispatchPage.cancelPreview()">Cancel</button><button id="executeDispatchBtn" class="btn btn-danger" disabled onclick="WorkDispatchPage.execute(this)">Dispatch reviewed Albums</button></div>`, { key:'work-dispatch', label:'Album Work Dispatch review' });
  },
  cancelPreview() { this._preview = null; closeModal(); },
  async execute(trigger) {
    const result = await ui.runAction('dispatch-execute', () => api.post('/work-dispatch/execute', { preview_token: this._preview.preview_token }),
      { trigger, context: 'execute Work Dispatch' });
    if (!result.ok) return;
    const groups = result.value.result.groups || []; this._preview = null; closeModal();
    toast(`Dispatched ${groups.length} Album Group(s). Album Status was unchanged.`);
    this._view = 'active'; this._selected = new Set(); await this.loadView();
  },
};
