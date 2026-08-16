const WorkspaceReviewPage = {
  _detail: null,
  _draft: {},
  _draftStale: false,
  _queueItems: [],
  _queueHash: '#/ai-reviews',
  _promotionSuccess: null,
  _runtimeGeneration: 0,
  _pollTimer: null,
  _pollDelay: 5000,
  _pollInFlight: false,
  _evidenceObserver: null,
  _evidenceQueue: [],
  _evidenceActive: 0,
  _evidenceUrls: new Map(),
  _previewUrl: null,

  async renderWorkspaces() {
    this._stopRuntime();
    const el = document.getElementById('page-content');
    el.innerHTML = '<div class="loading">Loading AI Workspaces…</div>';
    try {
      const result = await api.get('/ai-workspaces');
      el.innerHTML = `<div class="page-header"><div><h1 class="page-title">AI Workspaces</h1><p class="page-subtitle">Create an Open Workspace before dispatching Albums for AI analysis.</p></div><div><button class="btn btn-primary" onclick="WorkspaceReviewPage.openCreateWorkspace()">+ New Workspace</button> <a class="btn btn-secondary" href="#/work-dispatch">Dispatch Albums</a></div></div>
        <div class="card table-wrap"><table><thead><tr><th>Workspace</th><th>Dataset</th><th>Lifecycle</th><th>Created</th><th>Review</th></tr></thead><tbody>
        ${(result.items || []).map(item => `<tr><td><a href="#/ai-workspaces/${esc(item.uuid)}">${esc(item.title)}</a></td><td>${esc(item.dataset_type)} · ${esc(item.schema_version)}</td>
          <td><span class="chip ${item.lifecycle_state === 'Open' ? 'chip-ok' : ''}">${esc(item.lifecycle_state)}</span></td><td>${esc(item.created_at)}</td><td><a href="#/ai-reviews?workspace_uuid=${esc(item.uuid)}">Open queue</a></td></tr>`).join('') || '<tr><td colspan="5">No AI Workspaces.</td></tr>'}
        </tbody></table></div>`;
    } catch (error) { ui.renderPageError(el,error,'AI Workspaces'); }
  },

  openCreateWorkspace() {
    showModal(`<h3 id="modal-title" class="modal-title">New AI Workspace</h3>
      <div class="form-field"><label for="aiWorkspaceTitle">Workspace title *</label><input id="aiWorkspaceTitle" maxlength="200" placeholder="Album Name Analysis — 2026-08"></div>
      <p class="field-help">The Workspace will be created as <strong>Open</strong> for the <code>album_analysis</code> dataset, schema version 1.</p>
      <div class="modal-footer"><button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="WorkspaceReviewPage.createWorkspace(this)">Create Workspace</button></div>`);
    document.getElementById('aiWorkspaceTitle')?.focus();
  },

  async createWorkspace(trigger) {
    const title=document.getElementById('aiWorkspaceTitle').value.trim();
    if(!title){toast('Enter a Workspace title.','error');return;}
    const result=await ui.runAction('ai-workspace-create',()=>api.post('/ai-workspaces',{title}),{trigger,context:'create the AI Workspace'});
    if(!result.ok)return;
    closeModal();toast('AI Workspace created.');await this.renderWorkspaces();
  },

  async renderWorkspace({ uuid }) {
    this._stopRuntime();
    const el = document.getElementById('page-content'); el.innerHTML = '<div class="loading">Loading Workspace overview…</div>';
    try {
      const result = await api.get(`/ai-workspaces/${encodeURIComponent(uuid)}/overview`); const view = result.overview;
      const summary = view.summary; const preflight = view.closure_preflight;
      el.innerHTML = `<div class="page-header"><div><a href="#/ai-workspaces">← AI Workspaces</a><h1 class="page-title">${esc(view.workspace.title)}</h1></div>
        <span class="chip ${view.workspace.lifecycle_state === 'Open' ? 'chip-ok' : ''}">${esc(view.workspace.lifecycle_state)}</span></div>
        <div class="stats-grid"><div class="stat-card"><div class="stat-number">${summary.total_groups}</div><div class="stat-label">Groups</div></div>
        <div class="stat-card"><div class="stat-number">${summary.total_items}</div><div class="stat-label">Work Items</div></div><div class="stat-card"><div class="stat-number">${summary.promotion_count}</div><div class="stat-label">Promotions</div></div></div>
        <div class="card workspace-summary"><div class="form-section-title">Review and lifecycle</div>
          <p>Review states: ${Object.entries(summary.review_state_counts).map(([key,value]) => `${esc(key)} ${value}`).join(' · ') || 'No reviews'}</p>
          <p>Outcome: <strong>${esc(preflight.outcome_classification)}</strong> · retention: <strong>${esc(preflight.retention_classification)}</strong></p>
          ${preflight.blockers.length ? `<div class="alert alert-warning">${preflight.blockers.length} blocker(s) prevent closure.</div>` : ''}
          <div class="detail-actions"><a class="btn btn-primary" href="#/ai-reviews?workspace_uuid=${esc(uuid)}">Review queue</a><a class="btn btn-secondary" href="#/work-dispatch">Dispatch</a>
          ${view.allowed_actions.includes('close') ? `<button class="btn btn-danger" onclick="WorkspaceReviewPage.transitionWorkspace('${esc(uuid)}','close',${view.workspace.version},this)">Close Workspace</button>` : ''}
          ${view.allowed_actions.includes('archive') ? `<button class="btn btn-danger" onclick="WorkspaceReviewPage.transitionWorkspace('${esc(uuid)}','archive',${view.workspace.version},this)">Archive Workspace</button>` : ''}</div></div>`;
    } catch (error) { ui.renderPageError(el,error,'Workspace overview'); }
  },

  async transitionWorkspace(uuid, action, version, trigger) {
    const reason = window.prompt(`Reason to ${action} this Workspace:`); if (!reason?.trim()) return;
    const result = await ui.runAction(`workspace-${action}`, () => api.post(`/ai-workspaces/${uuid}/${action}`, { expected_version:version, reason:reason.trim() }), { trigger, context:`${action} the Workspace` });
    if (result.ok) await this.renderWorkspace({ uuid });
  },

  async renderQueue() {
    this._stopRuntime();
    const el = document.getElementById('page-content'); el.innerHTML = '<div class="loading">Loading AI review queue…</div>';
    const params = new URLSearchParams((window.location.hash.split('?')[1] || ''));
    const state = params.get('state') || ''; const workspace = params.get('workspace_uuid') || ''; const q = params.get('q') || '';
    this._queueHash=window.location.hash || '#/ai-reviews';
    try { window.sessionStorage.setItem('curator.ai-review.queue',this._queueHash); } catch { /* in-memory fallback */ }
    try {
      const query = new URLSearchParams({ limit:'100' }); if (state) query.set('state',state); if (workspace) query.set('workspace_uuid',workspace); if (q) query.set('q',q);
      const rows = await api.get(`/ai-reviews?${query}`);
      this._queueItems=Array.isArray(rows)?rows:[];
      el.innerHTML = `<div class="page-header"><h1 class="page-title">AI Review Queue</h1><div><a class="btn btn-secondary" href="#/ai-workspaces">Workspaces</a><div id="reviewAutoRefreshStatus" class="table-secondary" role="status">Auto refresh on</div></div></div>
        <div class="filter-bar"><label>State <select id="reviewState"><option value="">All</option>${['ReadyForReview','InReview','Approved','Rejected','ReworkRequested'].map(value => `<option ${value === state ? 'selected' : ''}>${value}</option>`).join('')}</select></label>
        <label>Search <input id="reviewSearch" value="${esc(q)}" placeholder="Album or configuration"></label><button class="btn btn-secondary" onclick="WorkspaceReviewPage.applyQueueFilters('${esc(workspace)}')">Apply</button></div>
        <div class="card table-wrap"><table><thead><tr><th>Album</th><th>Configuration</th><th>State</th><th>Updated</th><th>Action</th></tr></thead><tbody id="reviewQueueRows">${this._queueRowsHtml(this._queueItems)}</tbody></table></div>`;
      this._startPolling(()=>this._refreshQueue(query),()=>window.location.hash.startsWith('#/ai-reviews'));
    } catch (error) { ui.renderPageError(el,error,'AI review queue'); }
  },

  applyQueueFilters(workspace) {
    const query = new URLSearchParams(); const state = document.getElementById('reviewState').value; const q = document.getElementById('reviewSearch').value.trim();
    if (workspace) query.set('workspace_uuid',workspace); if (state) query.set('state',state); if (q) query.set('q',q);
    window.location.hash = `#/ai-reviews${query.size ? `?${query}` : ''}`;
  },

  async renderDetail({ uuid }) {
    this._stopRuntime();
    const el = document.getElementById('page-content'); el.innerHTML = '<div class="loading">Loading review evidence…</div>';
    if(this._promotionSuccess?.completedUuid!==uuid)this._promotionSuccess=null;
    try { const result = await api.get(`/ai-work-items/${encodeURIComponent(uuid)}/review`); this._detail = result.review; this._renderDetail(); }
    catch (error) { ui.renderPageError(el,error,'AI review'); }
  },

  _writer() { return this._detail.results.find(stage => stage.stage === 'Writer'); },
  _vision() { return this._detail.results.find(stage => stage.stage === 'Vision'); },
  _configurationSnapshot(item) {
    if(!item)return {};
    if(item.configuration_snapshot&&typeof item.configuration_snapshot==='object')return item.configuration_snapshot;
    if(typeof item.configuration_snapshot_json!=='string')return {};
    try{return JSON.parse(item.configuration_snapshot_json);}catch{return {};}
  },
  _queueRowsHtml(rows){return rows.map(item => `<tr><td><a href="#/albums/${item.album_id}">${esc(item.album_title)}</a></td><td>${esc(item.configuration_name)}</td>
    <td><span class="chip ${item.state === 'Approved' ? 'chip-ok' : item.state === 'Rejected' ? 'chip-error' : 'chip-warn'}">${esc(item.state)}</span></td><td>${esc(item.updated_at)}</td>
    <td><a class="btn btn-sm btn-primary" href="#/ai-work-items/${esc(item.work_item_uuid)}/review">Review details</a></td></tr>`).join('')||'<tr><td colspan="5">No reviews match these filters.</td></tr>';},
  _renderDetail() {
    this._stopRuntime();
    const d = this._detail; const review = d.review; const writer = this._writer(); const vision = this._vision();
    const instructionProfile=this._configurationSnapshot(d.item).instruction_profile;
    const recommendations = writer?.payload?.suggested_names || [];
    const evidence = d.evidence_history?.evidence || [];
    const key=this._draftKey(review.work_item_uuid); const saved=ui.loadDraft(key);
    if(!this._draft[review.work_item_uuid]&&saved){this._draft[review.work_item_uuid]=saved.data;this._draftStale=saved.metadata?.reviewVersion!==review.version;ui.markDirty(key,'this AI Review',()=>ui.clearDraft(key));toast(this._draftStale?'Restored an AI Review draft created before the current review state changed.':'Restored the AI Review draft saved in this browser.','warning');}
    else if(!saved){this._draftStale=false;}
    else if(saved.metadata?.reviewVersion===review.version){this._draftStale=false;}
    const draft = this._draft[review.work_item_uuid] || { selected_name:review.selected_name || recommendations[0] || '', selection_source:'Recommendation', rating:review.rating || 5, notes:review.notes || '', reason:'' };
    this._draft[review.work_item_uuid] = draft;
    const el = document.getElementById('page-content');
    const queueHref=this._savedQueueHash(); const success=this._promotionSuccess?.completedUuid===review.work_item_uuid?this._promotionSuccess:null;
    const previewRetired=d.promotions.some(item=>item.outcome==='Promoted');
    el.innerHTML = `<div class="page-header"><div><a href="${esc(queueHref)}">← Review Queue</a><h1 class="page-title">${esc(d.item.album_title)}</h1></div><div><span class="chip">${esc(review.state)}</span><div id="reviewAutoRefreshStatus" class="table-secondary" role="status">Auto refresh on</div></div></div>
      ${success?`<section class="card alert alert-success" aria-live="polite"><strong>Album name Promotion completed.</strong><p>Durable result: <strong>${esc(d.item.album_title)}</strong> · ${d.promotions.length} Promotion record(s) · ${d.operations.length} linked Operation(s).</p><div class="detail-actions">${success.nextUuid?`<button class="btn btn-primary" onclick="WorkspaceReviewPage.openNextReview('${esc(success.nextUuid)}')">Next review</button>`:'<span>There are no more eligible reviews in the current queue.</span>'}<a class="btn btn-secondary" href="${esc(queueHref)}">Return to queue</a></div></section>`:''}
      <div class="review-grid"><section class="card review-panel ai-output"><div class="form-section-title">AI analysis · immutable</div>
        <p><strong>Configuration:</strong> ${esc(d.item.configuration_name)}</p><p><strong>Scene:</strong> ${esc(vision?.payload?.scene || '—')}</p>
        <p><strong>People:</strong> ${esc(JSON.stringify(vision?.payload?.people || {}))}</p><p><strong>Location:</strong> ${esc(vision?.payload?.location_environment || '—')}</p>
        <p><strong>Summary:</strong> ${esc(writer?.payload?.album_summary || '—')}</p><p><strong>Description:</strong> ${esc(writer?.payload?.description || '—')}</p>
        <div><strong>AI recommendations:</strong>${recommendations.map(name => `<label class="recommendation"><input type="radio" name="recommendedName" value="${esc(name)}" ${draft.selected_name === name ? 'checked' : ''} onchange="WorkspaceReviewPage.chooseRecommendation(this.value)"> ${esc(name)}</label>`).join('')}</div></section>
      <section class="card review-panel human-decision"><div class="form-section-title">Human review · editable draft</div>
        ${this._draftStale?'<div class="alert alert-warning">This local draft predates the current Backend review state. Rebase it deliberately before submitting.<div class="detail-actions"><button class="btn btn-secondary" onclick="WorkspaceReviewPage.discardDraft()">Discard local draft</button><button class="btn btn-primary" onclick="WorkspaceReviewPage.rebaseDraft()">Keep text and rebase</button></div></div>':''}
        <div class="form-field"><label for="reviewSelectedName">Final Album name</label><input id="reviewSelectedName" value="${esc(draft.selected_name)}" oninput="WorkspaceReviewPage.saveDraft()"></div>
        <div class="form-field"><label for="reviewSelectionSource">Selection source</label><select id="reviewSelectionSource" onchange="WorkspaceReviewPage.saveDraft()"><option ${draft.selection_source === 'Recommendation' ? 'selected' : ''}>Recommendation</option><option ${draft.selection_source === 'HumanRevision' ? 'selected' : ''}>HumanRevision</option></select></div>
        <div class="form-field"><label for="reviewRating">Rating (1–5)</label><input id="reviewRating" type="number" min="1" max="5" value="${draft.rating}" oninput="WorkspaceReviewPage.saveDraft()"></div>
        <div class="form-field"><label for="reviewNotes">Administrator evaluation</label><textarea id="reviewNotes" oninput="WorkspaceReviewPage.saveDraft()">${esc(draft.notes)}</textarea></div>
        <div class="form-field"><label for="reviewReason">Reason (required for Reject/Rework)</label><textarea id="reviewReason" oninput="WorkspaceReviewPage.saveDraft()">${esc(draft.reason)}</textarea></div>
        <div class="detail-actions">${review.allowed_actions.includes('start') ? `<button class="btn btn-primary" onclick="WorkspaceReviewPage.startReview(this)">Begin review</button>` : ''}
        ${review.allowed_actions.includes('approve') ? `<button class="btn btn-primary" ${this._draftStale?'disabled':''} onclick="WorkspaceReviewPage.decide('approve',this)">Approve selection</button><button class="btn btn-danger" ${this._draftStale?'disabled':''} onclick="WorkspaceReviewPage.decide('reject',this)">Reject</button><button class="btn btn-secondary" ${this._draftStale?'disabled':''} onclick="WorkspaceReviewPage.decide('request_rework',this)">Request rework</button>` : ''}
        ${review.state === 'Approved' && !d.promotions.some(item => item.outcome === 'Promoted') ? '<button class="btn btn-danger" onclick="WorkspaceReviewPage.previewPromotion(this)">Review Promotion</button>' : ''}</div></section></div>
      <section class="card review-panel system-evidence"><div class="form-section-title">System evidence and provenance</div>
        <p>Work Item: <code>${esc(review.work_item_uuid)}</code> · Group: <a href="#/work-dispatch/groups/${esc(d.group_uuid)}">${esc(d.group_uuid || '—')}</a></p>
        <p>AI Instruction Profile: ${instructionProfile?`<strong>${esc(instructionProfile.profile_name)}</strong> · v${esc(instructionProfile.version)} · <code>${esc(String(instructionProfile.content_hash||'').slice(0,16))}…</code>`:'Legacy code-owned prompt (no Profile snapshot)'}</p>
        ${previewRetired?'<div class="alert alert-info">Image preview ended after Promotion. Immutable Manifest metadata remains available.</div>':''}
        <div class="evidence-grid">${evidence.map(item => `<button type="button" class="evidence-card evidence-preview" data-evidence-uuid="${esc(item.uuid)}" data-evidence-filename="${esc(item.filename)}" ${item.availability!=='Available'||previewRetired?'disabled':''} onclick="WorkspaceReviewPage.openEvidencePreview('${esc(item.uuid)}','${esc(item.filename)}')"><span class="evidence-image-placeholder">${previewRetired?'Preview retired':item.availability==='Available'?'Loading preview…':'Preview unavailable'}</span><strong>${esc(item.filename)}</strong><span class="chip ${item.availability === 'Available' ? 'chip-ok' : 'chip-error'}">${esc(item.availability)}</span><small>${esc(item.mime_type)} · ${item.size_bytes} bytes</small></button>`).join('') || 'No evidence Manifest available.'}</div>
        <p>Decisions: ${d.decisions.length} · Promotions: ${d.promotions.length} · Operations: ${d.operations.map(item => `<a href="#/operations/${esc(item.uuid)}">${esc(item.operation_type)}</a>`).join(' · ') || '—'} · Issues: ${d.issues.map(item => `<a href="#/issues/${esc(item.uuid)}">${esc(item.category)}</a>`).join(' · ') || '—'}</p>
        ${d.successor_work_item_uuid ? `<p>Rework successor: <a href="#/ai-work-items/${esc(d.successor_work_item_uuid)}/review">${esc(d.successor_work_item_uuid)}</a></p>` : ''}</section>`;
    if(!previewRetired)this._startEvidenceLoading();
    this._startPolling(()=>this._refreshDetail(review.work_item_uuid),()=>window.location.hash===`#/ai-work-items/${review.work_item_uuid}/review`);
  },

  chooseRecommendation(value) { const input = document.getElementById('reviewSelectedName'); input.value = value; document.getElementById('reviewSelectionSource').value = 'Recommendation'; this.saveDraft(); },
  _draftKey(uuid){return `ai-review.${uuid}`;},
  saveDraft() {
    if (!this._detail) return; const uuid = this._detail.review.work_item_uuid;
    this._draft[uuid] = { selected_name:document.getElementById('reviewSelectedName')?.value || '', selection_source:document.getElementById('reviewSelectionSource')?.value || 'Recommendation', rating:Number(document.getElementById('reviewRating')?.value || 0), notes:document.getElementById('reviewNotes')?.value || '', reason:document.getElementById('reviewReason')?.value || '' };
    ui.saveDraft(this._draftKey(uuid),this._draft[uuid],{reviewVersion:this._detail.review.version});ui.markDirty(this._draftKey(uuid),'this AI Review',()=>ui.clearDraft(this._draftKey(uuid)));
  },
  rebaseDraft(){this._draftStale=false;this.saveDraft();this._renderDetail();},
  discardDraft(){const uuid=this._detail.review.work_item_uuid;delete this._draft[uuid];this._draftStale=false;ui.clearDraft(this._draftKey(uuid));ui.clearDirty();this._renderDetail();},
  routeChanged(hash){if(!hash.startsWith('#/ai-reviews')&&!/^#\/ai-work-items\/[^/]+\/review$/.test(hash))this._stopRuntime();},
  _setRuntimeStatus(message){const status=document.getElementById('reviewAutoRefreshStatus');if(status)status.textContent=message;},
  _stopRuntime(){
    this._runtimeGeneration+=1;if(this._pollTimer)clearTimeout(this._pollTimer);this._pollTimer=null;this._pollInFlight=false;
    this._evidenceObserver?.disconnect();this._evidenceObserver=null;this._evidenceQueue=[];this._evidenceActive=0;
    for(const url of this._evidenceUrls.values())URL.revokeObjectURL(url);this._evidenceUrls.clear();
    if(this._previewUrl){URL.revokeObjectURL(this._previewUrl);this._previewUrl=null;}
  },
  _startPolling(refresh,isCurrent){
    const generation=this._runtimeGeneration;this._pollDelay=5000;
    const schedule=()=>{if(generation===this._runtimeGeneration)this._pollTimer=setTimeout(tick,this._pollDelay);};
    const tick=async()=>{
      if(generation!==this._runtimeGeneration||!isCurrent())return;
      if(document.hidden){this._setRuntimeStatus('Auto refresh paused while this tab is hidden.');schedule();return;}
      if(this._pollInFlight){schedule();return;}this._pollInFlight=true;
      try{const outcome=await refresh();this._pollDelay=5000;this._setRuntimeStatus(outcome==='deferred'?'New state is waiting until editing focus leaves the form.':`Auto refresh on · updated ${new Date().toLocaleTimeString()}`);}
      catch{this._pollDelay=Math.min(this._pollDelay===5000?10000:this._pollDelay*2,30000);this._setRuntimeStatus(`Auto refresh delayed · retrying in ${this._pollDelay/1000}s`);}
      finally{this._pollInFlight=false;}schedule();
    };
    this._setRuntimeStatus('Auto refresh on');schedule();
  },
  async _refreshQueue(query){
    const rows=await api.get(`/ai-reviews?${query}`);const next=Array.isArray(rows)?rows:[];const target=document.getElementById('reviewQueueRows');if(!target)return;
    this._queueItems=next;if(document.activeElement&&target.contains(document.activeElement))return 'deferred';target.innerHTML=this._queueRowsHtml(next);
  },
  async _refreshDetail(uuid){
    const result=await api.get(`/ai-work-items/${encodeURIComponent(uuid)}/review`);const next=result.review;
    const before=this._detail;const unchanged=before&&before.review.version===next.review.version&&before.item.version===next.item.version&&before.results.length===next.results.length&&before.promotions.length===next.promotions.length;
    if(unchanged)return;
    const editor=document.querySelector('.human-decision');if(editor&&document.activeElement&&editor.contains(document.activeElement))return 'deferred';
    this._detail=next;this._renderDetail();
  },
  _startEvidenceLoading(){
    const cards=[...document.querySelectorAll('.evidence-preview:not(:disabled)')];
    const enqueue=card=>{if(card.dataset.evidenceQueued)return;card.dataset.evidenceQueued='true';this._evidenceQueue.push(card);this._drainEvidenceQueue();};
    if('IntersectionObserver' in window){this._evidenceObserver=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){this._evidenceObserver.unobserve(entry.target);enqueue(entry.target);}}),{rootMargin:'240px'});cards.forEach(card=>this._evidenceObserver.observe(card));}
    else cards.forEach(enqueue);
  },
  _drainEvidenceQueue(){while(this._evidenceActive<3&&this._evidenceQueue.length){const card=this._evidenceQueue.shift();this._evidenceActive+=1;this._loadEvidenceThumbnail(card).finally(()=>{this._evidenceActive-=1;this._drainEvidenceQueue();});}},
  async _loadEvidenceThumbnail(card){
    const generation=this._runtimeGeneration,uuid=card.dataset.evidenceUuid;
    try{const source=await api.getBlob(`/ai-evidence/${encodeURIComponent(uuid)}/content`);const thumb=await this._makeThumbnail(source);if(generation!==this._runtimeGeneration)return;
      const url=URL.createObjectURL(thumb);this._evidenceUrls.set(uuid,url);const placeholder=card.querySelector('.evidence-image-placeholder');if(placeholder)placeholder.innerHTML=`<img src="${url}" alt="Preview of ${esc(card.dataset.evidenceFilename)}" loading="lazy">`;
    }catch(error){if(generation!==this._runtimeGeneration)return;const placeholder=card.querySelector('.evidence-image-placeholder');if(placeholder)placeholder.textContent=error.code==='EVIDENCE_CONTENT_RETIRED'?'Preview retired':'Preview unavailable';card.disabled=true;}
  },
  async _makeThumbnail(blob){
    if(typeof createImageBitmap!=='function')return blob;const bitmap=await createImageBitmap(blob);const scale=Math.min(1,640/bitmap.width,420/bitmap.height);const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(bitmap.width*scale));canvas.height=Math.max(1,Math.round(bitmap.height*scale));const context=canvas.getContext('2d');context.drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();return await new Promise(resolve=>canvas.toBlob(value=>resolve(value||blob),'image/jpeg',0.82));
  },
  async openEvidencePreview(uuid,filename){
    if(this._previewUrl){URL.revokeObjectURL(this._previewUrl);this._previewUrl=null;}
    try{const blob=await api.getBlob(`/ai-evidence/${encodeURIComponent(uuid)}/content`);this._previewUrl=URL.createObjectURL(blob);showModal(`<h3 id="modal-title" class="modal-title">${esc(filename)}</h3><div class="evidence-full-preview"><img src="${this._previewUrl}" alt="Full preview of ${esc(filename)}"></div><div class="modal-footer"><button class="btn btn-primary" onclick="WorkspaceReviewPage.closeEvidencePreview()">Close preview</button></div>`);}
    catch(error){toast(error.message||'Image preview is unavailable.','error');}
  },
  closeEvidencePreview(){if(this._previewUrl){URL.revokeObjectURL(this._previewUrl);this._previewUrl=null;}closeModal();},
  async startReview(trigger) { const r=this._detail.review; const result=await ui.runAction('review-start',()=>api.post(`/ai-work-items/${r.work_item_uuid}/review/start`,{expected_version:r.version}),{trigger,context:'begin AI review'}); if(result.ok){this._detail=result.value.review;this.saveDraft();this._renderDetail();} },
  async decide(action,trigger) {
    this.saveDraft(); const r=this._detail.review; const draft=this._draft[r.work_item_uuid];
    const body={expected_version:r.version,action,rating:draft.rating,notes:draft.notes,reason:draft.reason};
    if(action==='approve') Object.assign(body,{selected_name:draft.selected_name,selection_source:draft.selection_source});
    const result=await ui.runAction(`review-${action}`,()=>api.post(`/ai-work-items/${r.work_item_uuid}/review/decision`,body),{trigger,context:`${action} AI review`});
    if(result.ok){delete this._draft[r.work_item_uuid];ui.clearDraft(this._draftKey(r.work_item_uuid));ui.clearDirty();this._draftStale=false;this._detail=result.value.review;this._renderDetail();}
  },
  async previewPromotion(trigger) {
    const uuid=this._detail.review.work_item_uuid; const nextUuid=await this._resolveNextReview(uuid); const result=await ui.runAction('promotion-preview',()=>api.post(`/ai-work-items/${uuid}/promotion/preview`,{}),{trigger,context:'preview Album name Promotion'}); if(!result.ok)return;
    const preview=result.value.preview; ui.showReviewedAction(`<h3 id="modal-title" class="modal-title">Confirm Album Name Promotion</h3><p>Current: <strong>${esc(preview.current.title)}</strong></p><p>Result: <strong>${esc(preview.resulting.title)}</strong> · Status ${esc(preview.resulting.status_name || preview.resulting.status_id)}</p>
      <label class="acknowledgement"><input id="promotionAcknowledgement" type="checkbox" onchange="document.getElementById('executePromotionBtn').disabled=!this.checked"> I confirm this Album name and Status change.</label><div class="modal-footer"><button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button id="executePromotionBtn" class="btn btn-danger" disabled onclick="WorkspaceReviewPage.executePromotion('${esc(preview.preview_token)}','${esc(nextUuid||'')}',this)">Confirm & Rename</button></div>`, { key:`ai-promotion-${uuid}`, label:'Album name Promotion review' });
  },
  _savedQueueHash(){try{return window.sessionStorage.getItem('curator.ai-review.queue')||this._queueHash||'#/ai-reviews';}catch{return this._queueHash||'#/ai-reviews';}},
  async _resolveNextReview(currentUuid){
    let rows=this._queueItems;
    if(!rows.some(item=>item.work_item_uuid===currentUuid)){
      const params=new URLSearchParams((this._savedQueueHash().split('?')[1]||''));params.set('limit','100');
      try{const result=await api.get(`/ai-reviews?${params}`);rows=Array.isArray(result)?result:[];}catch{return null;}
    }
    const eligible=item=>item.work_item_uuid!==currentUuid&&['ReadyForReview','InReview','Approved'].includes(item.state);
    const index=rows.findIndex(item=>item.work_item_uuid===currentUuid);
    const ordered=index<0?rows:[...rows.slice(index+1),...rows.slice(0,index)];
    return ordered.find(eligible)?.work_item_uuid||null;
  },
  openNextReview(uuid){this._promotionSuccess=null;window.location.hash=`#/ai-work-items/${encodeURIComponent(uuid)}/review`;},
  async executePromotion(token,nextUuid,trigger) { const completedUuid=this._detail.review.work_item_uuid; const result=await ui.runAction('promotion-execute',()=>api.post('/ai-promotions/execute',{preview_token:token,acknowledged:true}),{trigger,context:'promote Album name'}); if(result.ok){closeModal();this._promotionSuccess={completedUuid,nextUuid:nextUuid||null};await this.renderDetail({uuid:completedUuid});} },
};
