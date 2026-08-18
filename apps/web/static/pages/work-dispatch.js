const WorkDispatchPage = {
  _view: 'available',
  _candidates: [],
  _selected: new Set(),
  _workspaces: [],
  _configurations: [],
  _workerKinds: [],
  _statuses: [],
  _studios: [],
  _models: [],
  _meta: { total:0, limit:50, offset:0 },
  _state: {
    available:{status_id:'',studio_id:'',model_id:'',limit:50,offset:0},
    active:{limit:50,offset:0},review:{limit:50,offset:0},closure:{limit:50,offset:0},history:{limit:50,offset:0},
  },
  _selectionMode: 'ids',
  _firstN: null,
  _preview: null,
  _pollTimer: null,
  _pollGeneration: 0,
  _pollDelay: 5000,
  _pollInFlight: false,
  _selectionAnchorId: null,

  _configurationSummary(item) {
    return `<strong>${esc(item.name)}</strong><span class="config-model">${esc(item.model_identifier)} · <code>${esc(item.model_file)}</code></span>
      <span class="config-parameters">${item.sample_count} images · context ${item.context_size} · max ${item.max_tokens} tokens · image ${item.image_max_tokens} · temp ${item.temperature} · ${item.threads} threads · ${item.gpu_layers} GPU layers</span>
      <span class="config-prompts">Vision ${esc(item.vision_prompt_version)} · Writer ${esc(item.writer_prompt_version)} · Profile version ${esc(item.instruction_profile_version_uuid||'default')}</span>`;
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
      const retry=item.run_state === 'Failed'
        ? `<button class="btn btn-primary" onclick="WorkDispatchPage.retryItem('${esc(item.item_uuid)}',${item.version},this)">Retry</button>`
        : '';
      const cancel=item.run_state === 'Failed'
        ? `<button class="btn btn-danger" onclick="WorkDispatchPage.cancelItem('${esc(item.item_uuid)}',${item.version},this)">Cancel</button>`
        : '';
      return `<tr><td>${esc(albumTitle || '—')}</td><td><strong>${esc(config.name || 'Unknown configuration')}</strong><div class="table-secondary"><code>${esc(config.model_file || '—')}</code></div><div class="table-secondary">${esc(config.instruction_profile?.profile_name||'Legacy prompt')} · v${esc(config.instruction_profile?.version||'—')}</div></td>
        <td><span class="chip ${item.run_state === 'Failed' ? 'chip-error' : item.run_state === 'Completed' ? 'chip-ok' : 'chip-warn'}">${esc(this._stage(item))}</span><div class="table-secondary">Run ${esc(item.run_state)}${item.result_state ? ` · Result ${esc(item.result_state)}` : ''}</div></td>
        <td>${item.attempt_count}</td><td>${item.updated_at ? esc(new Date(item.updated_at).toLocaleString()) : '—'}${item.lease_expires_at ? `<div class="table-secondary">Lease until ${esc(new Date(item.lease_expires_at).toLocaleString())}</div>` : ''}</td>
        <td>${item.last_error ? `<span class="text-error">${esc(item.last_error)}</span>` : '—'}</td><td><div class="detail-actions"><a class="btn btn-secondary" href="#/ai-work-items/${esc(item.item_uuid)}/review">Open</a>${retry}${cancel}</div></td></tr>`;
    }).join('');
  },

  async retryItem(uuid,version,trigger) {
    const result=await ui.runAction(`work-item-retry-${uuid}`,()=>api.post(`/ai-work-items/${encodeURIComponent(uuid)}/retry`,{expected_version:version}),{trigger,context:'retry the failed Work Item'});
    if(!result.ok)return;
    toast('Work Item returned to the Worker queue.');
    const groupMatch=window.location.hash.match(/^#\/work-dispatch\/groups\/([^/?]+)/);
    if(groupMatch)await this.renderGroup({uuid:decodeURIComponent(groupMatch[1])});
    else await this.loadView();
  },

  async cancelItem(uuid,version,trigger) {
    if(!await ui.confirmDialog({title:'Cancel failed Work Item?',message:'This removes only this failed run from Worker processing. The Dispatch Group and its other runs are preserved, so the Album remains reserved. To dispatch the Album again, finish the Group in Closure and choose Release Group.',confirmLabel:'Cancel Work Item',danger:true}))return;
    const result=await ui.runAction(`work-item-cancel-${uuid}`,()=>api.post(`/ai-work-items/${encodeURIComponent(uuid)}/cancel`,{expected_version:version}),{trigger,context:'cancel the failed Work Item'});
    if(!result.ok)return;
    toast('Work Item cancelled. The Album remains reserved by this Group; use Closure → Release Group to make it Available again.');
    const groupMatch=window.location.hash.match(/^#\/work-dispatch\/groups\/([^/?]+)/);
    if(groupMatch)await this.renderGroup({uuid:decodeURIComponent(groupMatch[1])});
    else await this.loadView();
  },

  async render({ view = 'available' } = {}) {
    this._view = ['available', 'active', 'review', 'closure', 'history'].includes(view) ? view : 'available';
    this._selected = new Set();
    this._selectionMode='ids';this._firstN=null;
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading Work Dispatch…</div>';
    try {
      const [workspaces, configurations, kinds, statuses, studios, models] = await Promise.all([
        api.get('/ai-workspaces'), api.get('/ai-model-configurations'), api.get('/work-dispatch/worker-kinds'),
        api.get('/statuses'),api.get('/studios?limit=100'),api.get('/models?limit=100'),
      ]);
      this._workspaces = (workspaces.items || []).filter(item => item.lifecycle_state === 'Open');
      this._configurations = (configurations.items || []).filter(item => item.enabled);
      this._workerKinds = kinds.items || [];
      this._statuses=statuses.statuses||[];this._studios=studios.studios||[];this._models=models.models||[];
      await this.loadView();
    } catch (error) { ui.renderPageError(el, error, 'Work Dispatch'); }
  },

  async renderGroup({ uuid }) {
    this._stopPolling();
    const el=document.getElementById('page-content'); el.innerHTML='<div class="loading">Loading Dispatch Group…</div>';
    try {
      const result=await api.get(`/work-dispatch/groups/${encodeURIComponent(uuid)}`); const detail=result.group; const group=detail.group;
      el.innerHTML=`<div class="page-header"><div><a href="#/work-dispatch">← Work Dispatch</a><h1 class="page-title">Dispatch Group</h1></div><div><button class="btn btn-secondary" onclick="WorkDispatchPage.refreshGroup('${esc(group.uuid)}',true)">Refresh progress</button> <span id="dispatchGroupState" class="chip">${esc(group.group_state)}</span><div id="dispatchAutoRefreshStatus" class="table-secondary" role="status">Auto refresh on</div></div></div>
        <div class="card workspace-summary"><p>Group: <code>${esc(group.uuid)}</code></p><p>Album #${group.album_id} · Worker ${esc(group.worker_kind)} · Version ${group.version}</p>
        <div id="dispatchGroupBlockers">${this._groupBlockersHtml(detail)}</div>
        <div class="table-wrap"><table class="work-progress"><thead><tr><th>Album</th><th>Configuration</th><th>Current stage</th><th>Attempts</th><th>Last activity</th><th>Failure</th><th>Details</th></tr></thead><tbody id="dispatchGroupProgressRows">${this._itemRows(detail.items, `Album #${group.album_id}`)}</tbody></table></div>
        <div id="dispatchGroupNextStep">${this._groupNextStepHtml(detail)}</div>
        <div id="dispatchGroupActions" class="detail-actions">${this._groupActionsHtml(detail)}</div></div>`;
      if(group.group_state==='Active')this._startPolling(`group:${group.uuid}`,()=>this.refreshGroup(group.uuid,false),()=>window.location.hash===`#/work-dispatch/groups/${group.uuid}`);
    } catch(error){ui.renderPageError(el,error,'Dispatch Group');}
  },

  _groupBlockersHtml(detail){return detail.blockers.length?`<div class="alert alert-warning">${detail.blockers.map(item=>esc(item.reason)).join(' · ')}</div>`:'';},
  _groupNextStepHtml(detail){
    const items=detail.items||[];const actions=detail.allowed_actions||[];
    const cancelled=items.filter(item=>item.run_state==='Cancelled').length;
    const workerOpen=items.some(item=>['Pending','Claimed','Failed'].includes(item.run_state));
    if(actions.includes('release'))return `<div class="alert alert-info"><strong>Ready to return this Album to Available.</strong> ${cancelled===items.length?'All Work Items are cancelled. ':'Worker and review work is complete. '}Choose <strong>Release Group</strong> to free the Album reservation so it can be dispatched again.</div>`;
    if(cancelled&&workerOpen)return '<div class="alert alert-info"><strong>The Album is still reserved.</strong> Cancelling a Work Item preserves this Group. Finish, retry, or cancel the remaining Worker runs; when the Group reaches Closure, choose <strong>Release Group</strong> to make the Album Available again.</div>';
    if(actions.includes('abandon'))return '<div class="alert alert-warning"><strong>Choose the scope of recovery.</strong> Retry or cancel individual failed Work Items to preserve this Group. <strong>Abandon Group</strong> closes the entire Group and frees the Album reservation for a new dispatch.</div>';
    return '';
  },
  _groupActionsHtml(detail){const group=detail.group;const labels={release:'Release Group',abandon:'Abandon Group',cancel:'Cancel Group'};return detail.allowed_actions.map(action=>`<button class="btn ${action==='release'?'btn-primary':'btn-danger'}" onclick="WorkDispatchPage.closeGroup('${esc(group.uuid)}','${action}',${group.version},this)">${labels[action]||action}</button>`).join('');},
  async refreshGroup(uuid,manual=false){
    const result=await api.get(`/work-dispatch/groups/${encodeURIComponent(uuid)}`);const detail=result.group;const group=detail.group;
    const rows=document.getElementById('dispatchGroupProgressRows');if(!rows)return false;
    const focused=document.activeElement;const deferred=Boolean(focused&&rows.contains(focused));
    if(!deferred)rows.innerHTML=this._itemRows(detail.items,`Album #${group.album_id}`);
    const state=document.getElementById('dispatchGroupState');if(state)state.textContent=group.group_state;
    for(const [id,html] of [['dispatchGroupBlockers',this._groupBlockersHtml(detail)],['dispatchGroupNextStep',this._groupNextStepHtml(detail)],['dispatchGroupActions',this._groupActionsHtml(detail)]]){
      const target=document.getElementById(id);if(target&&(!focused||!target.contains(focused)))target.innerHTML=html;
    }
    if(manual)this._setPollStatus('Progress refreshed manually.');
    if(group.group_state!=='Active')this._stopPolling();
    return group.group_state==='Active'?(deferred?'deferred':true):false;
  },

  async closeGroup(uuid,action,version,trigger){
    const reason=window.prompt(`Reason to ${action} this Group:`); if(!reason?.trim())return;
    const result=await ui.runAction(`group-${action}`,()=>api.post(`/work-dispatch/groups/${uuid}/${action}`,{expected_version:version,reason:reason.trim()}),{trigger,context:`${action} the Dispatch Group`});
    if(result.ok)await this.renderGroup({uuid});
  },

  async loadView() {
    const el = document.getElementById('page-content');
    const workerKind = document.getElementById('dispatchWorkerKind')?.value || this._workerKinds[0]?.worker_kind || '';
    const state=this._state[this._view];
    try {
      if (this._view === 'available') {
        const params=new URLSearchParams({worker_kind:workerKind,availability:'available',limit:String(state.limit),offset:String(state.offset)});
        for(const key of ['status_id','studio_id','model_id'])if(state[key])params.set(key,state[key]);
        const result = await api.get(`/work-dispatch/candidates?${params}`);
        this._candidates = result.items||[];this._meta={total:result.total||0,limit:result.limit||state.limit,offset:state.offset};
      } else {
        const result=await api.get(`/work-dispatch/groups?view=${this._view}&worker_kind=${encodeURIComponent(workerKind)}&limit=${state.limit}&offset=${state.offset}`);
        this._candidates=result.items||[];this._meta={total:result.total||0,limit:result.limit||state.limit,offset:state.offset};
      }
      this._renderShell({ workerKind });
    } catch (error) { ui.renderPageError(el, error, 'Work Dispatch'); }
  },

  _renderShell({ workerKind = '' } = {}) {
    const el = document.getElementById('page-content');
    const tabs = [['available','Available'],['active','Worker Queue'],['review','Review'],['closure','Closure'],['history','History']];
    el.innerHTML = `<div class="page-header"><div><h1 class="page-title">Album Work Dispatch</h1>
      <p class="page-subtitle">Assign selected Albums to a Worker without changing Album Status.</p></div>${this._view !== 'available' ? `<div><button class="btn btn-secondary" onclick="WorkDispatchPage.refreshProgress(true)">Refresh progress</button>${this._view==='active'?'<div id="dispatchAutoRefreshStatus" class="table-secondary" role="status">Auto refresh on</div>':''}</div>` : ''}</div>
      <div class="dispatch-tabs" role="tablist">${tabs.map(([key,label]) => `<button class="btn ${this._view === key ? 'btn-primary' : 'btn-secondary'}" onclick="WorkDispatchPage.changeView('${key}')">${label}</button>`).join('')}</div>
      <div class="filter-bar">
        <label>Worker <select id="dispatchWorkerKind" onchange="WorkDispatchPage.workerChanged()">${this._workerKinds.map(kind => `<option value="${esc(kind.worker_kind)}" ${kind.worker_kind === workerKind ? 'selected' : ''}>${esc(kind.worker_kind)}</option>`).join('')}</select></label>
        ${this._view === 'available' ? this._filterHtml() : ''}
        <label>Per page <select id="dispatchPageSize" onchange="WorkDispatchPage.pageSizeChanged(this.value)">${[25,50,100].map(value=>`<option value="${value}" ${this._meta.limit===value?'selected':''}>${value}</option>`).join('')}</select></label>
      </div>
      <div id="dispatchPaginationTop">${this._paginationHtml()}</div><div id="dispatchViewContent">${this._view === 'available' ? this._availableHtml() : this._groupsHtml()}</div><div id="dispatchPagination">${this._paginationHtml()}</div>`;
    if(this._view==='active')this._startPolling('active',()=>this.refreshProgress(false),()=>window.location.hash.startsWith('#/work-dispatch')&&this._view==='active');
    else this._stopPolling();
  },

  async refreshProgress(manual=false){
    if(this._view!=='active'){if(manual)await this.loadView();return false;}
    const workerKind=document.getElementById('dispatchWorkerKind')?.value||this._workerKinds[0]?.worker_kind||'';const state=this._state.active;
    const result=await api.get(`/work-dispatch/groups?view=active&worker_kind=${encodeURIComponent(workerKind)}&limit=${state.limit}&offset=${state.offset}`);
    this._candidates=result.items||[];this._meta={total:result.total||0,limit:result.limit||state.limit,offset:state.offset};
    const content=document.getElementById('dispatchViewContent');const pagination=document.getElementById('dispatchPagination');const paginationTop=document.getElementById('dispatchPaginationTop');
    if(!content||!pagination||!paginationTop)return false;
    if(document.activeElement&&content.contains(document.activeElement))return 'deferred';
    const scrollX=window.scrollX,scrollY=window.scrollY;
    content.innerHTML=this._groupsHtml();pagination.innerHTML=this._paginationHtml();paginationTop.innerHTML=this._paginationHtml();window.scrollTo(scrollX,scrollY);
    if(manual)this._setPollStatus('Progress refreshed manually.');
    return this._candidates.some(group=>group.group_state==='Active');
  },

  _setPollStatus(message){const status=document.getElementById('dispatchAutoRefreshStatus');if(status)status.textContent=message;},
  _stopPolling(){this._pollGeneration+=1;if(this._pollTimer)clearTimeout(this._pollTimer);this._pollTimer=null;this._pollInFlight=false;},
  _startPolling(key,refresh,isCurrent){
    this._stopPolling();const generation=this._pollGeneration;this._pollDelay=5000;
    const schedule=()=>{if(generation!==this._pollGeneration)return;this._pollTimer=setTimeout(tick,this._pollDelay);};
    const tick=async()=>{
      if(generation!==this._pollGeneration||!isCurrent())return this._stopPolling();
      if(document.hidden){this._setPollStatus('Auto refresh paused while this tab is hidden.');this._pollDelay=5000;schedule();return;}
      if(this._pollInFlight){schedule();return;}this._pollInFlight=true;
      try{const keepPolling=await refresh();this._pollDelay=5000;this._setPollStatus(keepPolling==='deferred'?'Progress update waiting until the active control loses focus.':`Auto refresh on · updated ${new Date().toLocaleTimeString()}`);if(!keepPolling)return this._stopPolling();}
      catch{this._pollDelay=Math.min(this._pollDelay===5000?10000:this._pollDelay*2,30000);this._setPollStatus(`Auto refresh delayed · retrying in ${this._pollDelay/1000}s`);}
      finally{this._pollInFlight=false;}schedule();
    };
    this._setPollStatus('Auto refresh on');schedule();
  },

  _filterHtml(){const state=this._state.available;const options=(items,value,label)=>`<option value="">All ${label}</option>${items.map(item=>`<option value="${item.id}" ${String(value)===String(item.id)?'selected':''}>${esc(item.name||item.display_name||item.primary_name)}</option>`).join('')}`;
    return `<label>Status <select id="dispatchStatusFilter" onchange="WorkDispatchPage.filterChanged()">${options(this._statuses,state.status_id,'statuses')}</select></label>
      <label>Studio <select id="dispatchStudioFilter" onchange="WorkDispatchPage.filterChanged()">${options(this._studios,state.studio_id,'studios')}</select></label>
      <label>Model <select id="dispatchModelFilter" onchange="WorkDispatchPage.filterChanged()">${options(this._models,state.model_id,'models')}</select></label>
      <button class="btn btn-secondary" onclick="WorkDispatchPage.clearFilters()">Clear filters</button>`;},

  _paginationHtml(){const {total,limit,offset}=this._meta;const start=total?offset+1:0,end=Math.min(offset+limit,total);const page=total?Math.floor(offset/limit)+1:1,pages=Math.max(1,Math.ceil(total/limit));return `<div class="pagination">
    <span>Showing ${start}–${end} of ${total}</span><button class="btn btn-secondary" ${page<=1?'disabled':''} onclick="WorkDispatchPage.goToPage(1)">First</button>
    <button class="btn btn-secondary" ${page<=1?'disabled':''} onclick="WorkDispatchPage.changePage(-1)">Previous</button><span>Page ${page} of ${pages}</span>
    <label class="pagination-jump">Go to page <input type="number" min="1" max="${pages}" value="${page}" aria-label="Go to page" onkeydown="if(event.key==='Enter')WorkDispatchPage.goToPage(this.value)"></label>
    <button class="btn btn-secondary" onclick="WorkDispatchPage.goToPage(this.previousElementSibling.querySelector('input').value)">Go</button>
    <button class="btn btn-secondary" ${page>=pages?'disabled':''} onclick="WorkDispatchPage.changePage(1)">Next</button><button class="btn btn-secondary" ${page>=pages?'disabled':''} onclick="WorkDispatchPage.goToPage(${pages})">Last</button></div>`;},

  _availableHtml() {
    const rows = Array.isArray(this._candidates) ? this._candidates : [];
    const noWorkspace=!this._workspaces.length;
    return `<div class="dispatch-controls card">${noWorkspace?'<div class="alert alert-warning">No Open AI Workspace exists. Create one before Preview dispatch. <a class="btn btn-primary" href="#/ai-workspaces">Create Workspace</a></div>':''}<div class="form-grid">
      <div class="form-field"><label for="dispatchWorkspace">Open Workspace</label><select id="dispatchWorkspace" onchange="WorkDispatchPage._selectionChanged()" ${noWorkspace?'disabled':''}>${this._workspaces.map(item => `<option value="${esc(item.uuid)}">${esc(item.title)}</option>`).join('')}${noWorkspace?'<option value="">No Open Workspace</option>':''}</select></div>
      <div class="form-field form-field-full"><label>Model configurations</label><p class="field-help">Each selected configuration creates a separate comparable run for every selected Album.</p><div class="dispatch-configs">${this._configurations.map(item => `<label class="dispatch-config"><input type="checkbox" name="dispatchConfig" value="${esc(item.uuid)}"><span>${this._configurationSummary(item)}</span></label>`).join('') || '<div class="empty-state">No enabled AI Model Configuration exists. <a class="btn btn-primary" href="#/admin/ai-model-configurations">Create model configuration</a></div>'}</div></div>
      </div><div class="detail-actions"><button class="btn btn-secondary" onclick="WorkDispatchPage.selectPage()">Select current page</button>
      <button class="btn btn-secondary" onclick="WorkDispatchPage.selectFirst()">Select first N…</button>
      <button id="dispatchPreviewBtn" class="btn btn-primary" onclick="WorkDispatchPage.preview()" disabled>Preview dispatch</button>
      <span id="dispatchSelectionCount">0 Albums selected</span></div></div>
      <div class="card table-wrap"><table><thead><tr><th><label><input id="dispatchSelectPage" type="checkbox" aria-label="Select all Albums on current page" onclick="WorkDispatchPage.togglePage(this.checked)"> Select</label></th><th>Album</th><th>Studio</th><th>Status</th><th>Eligibility</th><th>Warnings</th></tr></thead><tbody>
      ${rows.map(item => `<tr><td><input type="checkbox" aria-label="Select ${esc(item.title)}" data-dispatch-album="${item.id}" ${item.can_dispatch ? '' : 'disabled'} onclick="WorkDispatchPage.toggle(${item.id},this.checked,event)"></td>
        <td><a href="#/albums/${item.id}">${esc(item.title)}</a></td><td>${esc(item.studio_name || '—')}</td><td>${esc(item.status_name || '—')}</td>
        <td><span class="chip ${item.can_dispatch ? 'chip-ok' : 'chip-error'}">${esc(item.eligibility)}</span>${item.eligibility_reason ? `<div>${esc(item.eligibility_reason)}</div>` : ''}</td>
        <td>${(item.warnings || []).map(value => `<span class="chip chip-warn">${esc(value)}</span>`).join(' ') || '—'}</td></tr>`).join('') || '<tr><td colspan="6">No Albums are currently available for this Worker.</td></tr>'}
      </tbody></table></div>`;
  },

  _groupsHtml() {
    const rows = Array.isArray(this._candidates) ? this._candidates : [];
    return rows.map(group => `<section class="card dispatch-group-card"><div class="dispatch-group-heading"><div><a href="#/albums/${group.album_id}"><strong>${esc(group.album_title)}</strong></a><div class="table-secondary"><a href="#/work-dispatch/groups/${esc(group.uuid)}">Group details</a> · Workspace <a href="#/ai-workspaces/${esc(group.workspace_uuid)}">${esc(group.workspace_uuid)}</a></div></div><span class="chip ${group.group_state === 'Active' ? 'chip-warn' : 'chip-ok'}">${esc(group.group_state)}</span></div>
      <div class="table-wrap"><table class="work-progress"><thead><tr><th>Album</th><th>Configuration</th><th>Current stage</th><th>Attempts</th><th>Last activity</th><th>Failure</th><th>Details</th></tr></thead><tbody>${this._itemRows(group.items, group.album_title)}</tbody></table></div>
      <div class="dispatch-group-footer">${group.item_count} runs · ${group.open_review_count} open reviews · ${group.promotion_count} promotions${group.closure_operation_uuid ? ` · <a href="#/operations/${esc(group.closure_operation_uuid)}">Operation</a>` : ''}</div></section>`).join('') || `<div class="card empty-state">${this._view==='active'?'No Work Items currently need AI Worker action.':this._view==='review'?'No Groups are waiting for review.':this._view==='closure'?'No Groups are ready for closure.':`No ${esc(this._view)} Groups.`}</div>`;
  },

  changeView(view) { this._view = view; this._resetSelection(); void this.loadView(); },
  _resetSelection(){this._selected=new Set();this._selectionMode='ids';this._firstN=null;this._selectionAnchorId=null;},
  workerChanged(){this._state[this._view].offset=0;this._resetSelection();void this.loadView();},
  filterChanged(){const state=this._state.available;state.status_id=document.getElementById('dispatchStatusFilter').value;state.studio_id=document.getElementById('dispatchStudioFilter').value;state.model_id=document.getElementById('dispatchModelFilter').value;state.offset=0;this._resetSelection();void this.loadView();},
  clearFilters(){Object.assign(this._state.available,{status_id:'',studio_id:'',model_id:'',offset:0});this._resetSelection();void this.loadView();},
  pageSizeChanged(value){const size=Number(value);if(![25,50,100].includes(size))return;this._state[this._view].limit=size;this._state[this._view].offset=0;this._resetSelection();void this.loadView();},
  changePage(direction){const state=this._state[this._view];const next=state.offset+direction*state.limit;if(next<0||next>=this._meta.total)return;state.offset=next;this._resetSelection();void this.loadView();},
  goToPage(value){const page=Number(value),pages=Math.max(1,Math.ceil(this._meta.total/this._meta.limit));if(!Number.isInteger(page)||page<1||page>pages){toast(`Enter a page from 1 to ${pages}.`,'error');return;}const state=this._state[this._view];state.offset=(page-1)*state.limit;this._resetSelection();void this.loadView();},
  toggle(id, checked, event={}) {
    this._selectionMode='ids';this._firstN=null;
    const rows=Array.isArray(this._candidates)?this._candidates:[];
    const current=rows.findIndex(item=>item.id===id);
    const anchor=rows.findIndex(item=>item.id===this._selectionAnchorId);
    if(event.shiftKey&&current>=0&&anchor>=0){
      const [start,end]=current<anchor?[current,anchor]:[anchor,current];
      rows.slice(start,end+1).filter(item=>item.can_dispatch).forEach(item=>checked?this._selected.add(item.id):this._selected.delete(item.id));
    }else if(checked)this._selected.add(id);else this._selected.delete(id);
    this._selectionAnchorId=id;this._syncAlbumCheckboxes();this._selectionChanged();
  },
  _syncAlbumCheckboxes(){document.querySelectorAll('[data-dispatch-album]').forEach(input=>{input.checked=this._selected.has(Number(input.dataset.dispatchAlbum));});},
  _selectionChanged() {
    const count = this._selectionMode==='first_n'?this._firstN:this._selected.size;
    const label = document.getElementById('dispatchSelectionCount'); if (label) label.textContent = this._selectionMode==='first_n'?`First ${count} filtered Albums selected`:`${count} Albums selected`;
    const workspace=document.getElementById('dispatchWorkspace')?.value;
    const button = document.getElementById('dispatchPreviewBtn'); if (button) button.disabled = !count||!workspace;
    const pageToggle=document.getElementById('dispatchSelectPage');
    if(pageToggle){const eligible=(Array.isArray(this._candidates)?this._candidates:[]).filter(item=>item.can_dispatch);const selected=eligible.filter(item=>this._selected.has(item.id)).length;pageToggle.checked=eligible.length>0&&selected===eligible.length;pageToggle.indeterminate=selected>0&&selected<eligible.length;pageToggle.disabled=!eligible.length;}
  },
  selectPage() {
    this._selectionMode='ids';this._firstN=null;this._selectionAnchorId=null;
    this._selected = new Set((Array.isArray(this._candidates) ? this._candidates : []).filter(item => item.can_dispatch).map(item => item.id));
    this._syncAlbumCheckboxes();this._selectionChanged();
  },
  togglePage(checked){if(checked)return this.selectPage();this._selectionMode='ids';this._firstN=null;this._selectionAnchorId=null;this._selected.clear();this._syncAlbumCheckboxes();this._selectionChanged();},
  selectFirst() {
    const raw = window.prompt('How many Albums from the complete filtered result should be selected? (1–100)', '10');
    const count = Number(raw); if (!Number.isInteger(count) || count < 1 || count > 100) { toast('Enter a number from 1 to 100.', 'error'); return; }
    this._selectionMode='first_n';this._firstN=count;this._selected=new Set();document.querySelectorAll('[data-dispatch-album]').forEach(input=>{input.checked=false;});
    this._selectionChanged();
  },

  async preview() {
    const workspace=document.getElementById('dispatchWorkspace')?.value;
    if(!workspace){toast('Create and select an Open AI Workspace before Preview dispatch.','error');return;}
    const configurations = [...document.querySelectorAll('input[name="dispatchConfig"]:checked')].map(input => input.value);
    if (!configurations.length) { toast('Select at least one model configuration.', 'error'); return; }
    const state=this._state.available;const filters={};for(const key of ['status_id','studio_id','model_id'])if(state[key])filters[key]=state[key];
    const selection=this._selectionMode==='first_n'?{filters,first_n:this._firstN}:{album_ids:[...this._selected]};
    const result = await ui.runAction('dispatch-preview', () => api.post('/work-dispatch/preview', {
      worker_kind: document.getElementById('dispatchWorkerKind').value,
      workspace_uuid: workspace,
      configuration_uuids: configurations, ...selection,
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
    this._view = 'active'; this._resetSelection(); await this.loadView();
  },
};
