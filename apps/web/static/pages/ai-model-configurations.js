const AIModelConfigurationsPage = {
  _items: [],

  async render() {
    const el=document.getElementById('page-content');
    const button=document.getElementById('pageActionBtn');
    button.textContent='+ New Configuration';button.classList.remove('hidden');button.onclick=()=>this.openForm();
    el.innerHTML='<div class="loading">Loading AI Model Configurations…</div>';
    await this.load();
  },

  async load() {
    const el=document.getElementById('page-content');
    try {
      const result=await api.get('/ai-model-configurations');this._items=result.items||[];
      el.innerHTML=`<div class="page-header"><div><a href="#/admin">← Administrator Center</a><h1 class="page-title">AI Model Configurations</h1>
        <p class="page-subtitle">Portable llama.cpp settings captured with every dispatched Work Item.</p></div></div>
        <div class="alert alert-warning"><code>model_file</code> is relative to each Worker's <code>--model-root</code>. Curator does not browse or validate files on a Worker host, and configurations must not contain Tokens or host-local secrets.</div>
        <div class="card table-wrap"><table><thead><tr><th>Name</th><th>Model</th><th>Runtime</th><th>Prompts</th><th>State</th><th>Updated</th><th>Actions</th></tr></thead><tbody>
        ${this._items.map(item=>`<tr><td><strong>${esc(item.name)}</strong><div class="table-secondary">Version ${item.version}</div></td>
          <td>${esc(item.model_identifier)}<div class="table-secondary"><code>${esc(item.model_file)}</code></div>${item.model_repository?`<div class="table-secondary">${esc(item.model_repository)}</div>`:''}</td>
          <td>${item.sample_count} images · context ${item.context_size}<div class="table-secondary">${item.threads} threads · ${item.gpu_layers} GPU layers · max ${item.max_tokens} · temp ${item.temperature}</div></td>
          <td>Vision ${esc(item.vision_prompt_version)}<div class="table-secondary">Writer ${esc(item.writer_prompt_version)}</div></td>
          <td><span class="chip ${item.enabled?'chip-ok':'chip-warn'}">${item.enabled?'Enabled':'Disabled'}</span></td>
          <td>${esc(new Date(item.updated_at).toLocaleString())}</td><td><button class="btn btn-sm btn-secondary" onclick="AIModelConfigurationsPage.openForm('${esc(item.uuid)}')">Edit</button>
          <button class="btn btn-sm ${item.enabled?'btn-danger':'btn-primary'}" onclick="AIModelConfigurationsPage.toggle('${esc(item.uuid)}')">${item.enabled?'Disable':'Enable'}</button></td></tr>`).join('')||'<tr><td colspan="7"><div class="empty-state">No AI Model Configuration exists. Create one before Preview dispatch.</div></td></tr>'}
        </tbody></table></div>`;
    } catch(error){ui.renderPageError(el,error,'AI Model Configurations');}
  },

  _number(id) { const raw=document.getElementById(id).value.trim();if(raw==='')return null;const value=Number(raw);return Number.isFinite(value)?value:null; },
  _fields(item={}) {
    const number=(key,fallback)=>item[key]??fallback;
    return `<div class="form-grid">
      <div class="form-field"><label for="aiConfigName">Name *</label><input id="aiConfigName" maxlength="120" value="${esc(item.name||'')}"></div>
      <div class="form-field"><label for="aiConfigIdentifier">Model identifier *</label><input id="aiConfigIdentifier" maxlength="200" value="${esc(item.model_identifier||'')}"></div>
      <div class="form-field form-field-full"><label for="aiConfigFile">Model file *</label><input id="aiConfigFile" maxlength="300" value="${esc(item.model_file||'')}" placeholder="qwen2.5-vl-7b/model.gguf"><p class="field-help">Portable path relative to the Worker's --model-root; absolute paths are rejected.</p></div>
      <div class="form-field form-field-full"><label for="aiConfigRepository">Model repository</label><input id="aiConfigRepository" maxlength="300" value="${esc(item.model_repository||'')}" placeholder="ggml-org/Qwen2.5-VL-7B-Instruct-GGUF"></div>
      <div class="form-field"><label for="aiConfigVisionPrompt">Vision prompt version *</label><input id="aiConfigVisionPrompt" maxlength="100" value="${esc(item.vision_prompt_version||'vision-v1')}"></div>
      <div class="form-field"><label for="aiConfigWriterPrompt">Writer prompt version *</label><input id="aiConfigWriterPrompt" maxlength="100" value="${esc(item.writer_prompt_version||'writer-v1')}"></div>
      <div class="form-field"><label for="aiConfigSamples">Sample count (1–32)</label><input id="aiConfigSamples" type="number" min="1" max="32" value="${number('sample_count',8)}"></div>
      <div class="form-field"><label for="aiConfigContext">Context size (512–262144)</label><input id="aiConfigContext" type="number" min="512" max="262144" value="${number('context_size',8192)}"></div>
      <div class="form-field"><label for="aiConfigThreads">Threads (1–256)</label><input id="aiConfigThreads" type="number" min="1" max="256" value="${number('threads',8)}"></div>
      <div class="form-field"><label for="aiConfigGpuLayers">GPU layers (0–999)</label><input id="aiConfigGpuLayers" type="number" min="0" max="999" value="${number('gpu_layers',999)}"></div>
      <div class="form-field"><label for="aiConfigMaxTokens">Maximum output tokens (1–32768)</label><input id="aiConfigMaxTokens" type="number" min="1" max="32768" value="${number('max_tokens',800)}"></div>
      <div class="form-field"><label for="aiConfigTemperature">Temperature (0–2)</label><input id="aiConfigTemperature" type="number" min="0" max="2" step="0.01" value="${number('temperature',0.2)}"></div>
      <div class="form-field"><label for="aiConfigImageTokens">Image maximum tokens (1–8192)</label><input id="aiConfigImageTokens" type="number" min="1" max="8192" value="${number('image_max_tokens',384)}"></div>
      <div class="form-field form-field-full"><label for="aiConfigAdditional">Additional parameters (JSON object)</label><textarea id="aiConfigAdditional" rows="4">${esc(JSON.stringify(item.additional_parameters||{},null,2))}</textarea><p class="field-help">Host paths, executables, Tokens, passwords, and secrets are rejected.</p></div>
    </div>`;
  },

  openForm(uuid=null) {
    const item=uuid?this._items.find(value=>value.uuid===uuid):null;if(uuid&&!item)return;
    showModal(`<h3 id="modal-title" class="modal-title">${item?'Edit':'New'} AI Model Configuration</h3>${this._fields(item||{})}
      <div class="modal-footer"><button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button id="aiConfigSave" class="btn btn-primary" onclick="AIModelConfigurationsPage.save('${item?esc(item.uuid):''}',this)">${item?'Save changes':'Create configuration'}</button></div>`,{wide:true});
  },

  _payload() {
    let additional_parameters;try{additional_parameters=JSON.parse(document.getElementById('aiConfigAdditional').value||'{}');}
    catch{throw new Error('Additional parameters must be a valid JSON object.');}
    if(!additional_parameters||Array.isArray(additional_parameters)||typeof additional_parameters!=='object')throw new Error('Additional parameters must be a JSON object.');
    return {name:document.getElementById('aiConfigName').value.trim(),model_identifier:document.getElementById('aiConfigIdentifier').value.trim(),
      model_file:document.getElementById('aiConfigFile').value.trim(),model_repository:document.getElementById('aiConfigRepository').value.trim()||null,
      vision_prompt_version:document.getElementById('aiConfigVisionPrompt').value.trim(),writer_prompt_version:document.getElementById('aiConfigWriterPrompt').value.trim(),
      sample_count:this._number('aiConfigSamples'),context_size:this._number('aiConfigContext'),threads:this._number('aiConfigThreads'),
      gpu_layers:this._number('aiConfigGpuLayers'),max_tokens:this._number('aiConfigMaxTokens'),temperature:this._number('aiConfigTemperature'),
      image_max_tokens:this._number('aiConfigImageTokens'),additional_parameters};
  },

  async save(uuid,trigger) {
    let payload;try{payload=this._payload();if(!payload.name||!payload.model_identifier||!payload.model_file||!payload.vision_prompt_version||!payload.writer_prompt_version)throw new Error('Complete every required field.');}
    catch(error){toast(error.message,'error');return;}
    const current=uuid?this._items.find(item=>item.uuid===uuid):null;if(current)payload.expected_version=current.version;
    const result=await ui.runAction('ai-model-configuration-save',()=>current?api.put(`/ai-model-configurations/${encodeURIComponent(uuid)}`,payload):api.post('/ai-model-configurations',payload),{trigger,context:`${current?'save':'create'} the AI Model Configuration`});
    if(!result.ok)return;closeModal();toast(current?'AI Model Configuration saved.':'AI Model Configuration created.');await this.load();
  },

  async toggle(uuid) {
    const item=this._items.find(value=>value.uuid===uuid);if(!item)return;
    if(!await confirmDialog(`${item.enabled?'Disable':'Enable'} ${item.name}? Historical Work Item snapshots will not change.`))return;
    const result=await ui.runAction(`ai-model-configuration-${item.enabled?'disable':'enable'}`,()=>api.post(`/ai-model-configurations/${encodeURIComponent(uuid)}/${item.enabled?'disable':'enable'}`,{expected_version:item.version}),{context:`${item.enabled?'disable':'enable'} the AI Model Configuration`});
    if(result.ok){toast(`AI Model Configuration ${item.enabled?'disabled':'enabled'}.`);await this.load();}
  },
};
