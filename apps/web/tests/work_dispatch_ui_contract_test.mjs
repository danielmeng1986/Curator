import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const pageSource = await readFile(new URL('../static/pages/work-dispatch.js', import.meta.url), 'utf8');
const appSource = await readFile(new URL('../static/app.js', import.meta.url), 'utf8');
const indexSource = await readFile(new URL('../static/index.html', import.meta.url), 'utf8');

const elements = new Map();
const document = {
  getElementById(id) { return elements.get(id) || null; },
  querySelectorAll() { return []; },
};
const context = vm.createContext({
  window: { prompt: () => '10' }, document, console,
  api: {}, ui: {}, esc: value => String(value), toast() {}, showModal() {}, closeModal() {},
  Set, Number, Array, Promise, encodeURIComponent, URLSearchParams,
});
vm.runInContext(`${pageSource}\nthis.WorkDispatchPage = WorkDispatchPage;`, context, { filename:'work-dispatch.js' });
const page = context.WorkDispatchPage;

assert.match(appSource, /page: 'work-dispatch'.*scope: 'admin'/);
assert.match(indexSource, /AI Work Dispatch/);
assert.match(indexSource, /pages\/work-dispatch\.js/);
assert.match(pageSource, /availability:'available'/);
assert.match(pageSource, /dispatchStatusFilter/);
assert.match(pageSource, /dispatchStudioFilter/);
assert.match(pageSource, /dispatchModelFilter/);
assert.match(pageSource, /Showing \$\{start\}–\$\{end\} of \$\{total\}/);
assert.match(pageSource, /first_n:this\._firstN/);
assert.doesNotMatch(pageSource, /Album search/);
assert.match(pageSource, /Status will not change/);
assert.match(pageSource, /preview_token/);
assert.match(pageSource, /configuration_uuids/);
assert.match(pageSource, /view=\$\{this\._view\}/);
assert.match(pageSource, /image_max_tokens/);
assert.match(pageSource, /Preparing evidence \/ Vision analysis/);
assert.match(pageSource, /Writer analysis/);
assert.match(pageSource, /Waiting for Worker/);
assert.match(pageSource, /Refresh progress/);
assert.match(pageSource, /Auto refresh on/);
assert.match(pageSource, /document\.hidden/);
assert.match(pageSource, /Math\.min\(this\._pollDelay===5000\?10000:this\._pollDelay\*2,30000\)/);
assert.match(pageSource, /clearTimeout\(this\._pollTimer\)/);
assert.match(pageSource, /dispatchViewContent/);
assert.match(pageSource, /dispatchGroupProgressRows/);
assert.match(pageSource, />Retry<\/button>/);
assert.match(pageSource, /\/ai-work-items\/\$\{encodeURIComponent\(uuid\)\}\/retry/);
assert.match(pageSource, /No Open AI Workspace exists/);
assert.match(pageSource, /Create and select an Open AI Workspace/);

const configHtml=page._configurationSummary({name:'Balanced',model_identifier:'qwen',model_file:'qwen.gguf',sample_count:8,
  context_size:4096,max_tokens:800,image_max_tokens:384,temperature:0.2,threads:8,gpu_layers:20,
  vision_prompt_version:'v1',writer_prompt_version:'w1'});
assert.match(configHtml,/qwen\.gguf/);assert.match(configHtml,/context 4096/);assert.match(configHtml,/384/);
assert.equal(page._stage({run_state:'Pending'}),'Waiting for Worker');
assert.equal(page._stage({run_state:'Claimed',result_state:'AwaitingWriter'}),'Writer analysis');
assert.equal(page._stage({run_state:'Completed',review_state:'ReadyForReview'}),'ReadyForReview');
const failedRows=page._itemRows([{item_uuid:'item-1',version:3,run_state:'Failed',attempt_count:1,configuration_snapshot:{name:'Balanced',model_file:'qwen.gguf'}}],'Fixture Album');
assert.match(failedRows,/>Retry<\/button>/);assert.match(failedRows,/retryItem\('item-1',3,this\)/);
const pendingRows=page._itemRows([{item_uuid:'item-2',version:1,run_state:'Pending',attempt_count:0,configuration_snapshot:{name:'Balanced',model_file:'qwen.gguf'}}],'Fixture Album');
assert.doesNotMatch(pendingRows,/>Retry<\/button>/);

elements.set('dispatchSelectionCount', { textContent:'' });
elements.set('dispatchPreviewBtn', { disabled:true });
elements.set('dispatchWorkspace', { value:'workspace-1' });
page.toggle(12, true);
assert.equal(page._selected.has(12), true);
assert.equal(elements.get('dispatchSelectionCount').textContent, '1 Albums selected');
assert.equal(elements.get('dispatchPreviewBtn').disabled, false);
page.toggle(12, false);
assert.equal(elements.get('dispatchPreviewBtn').disabled, true);
elements.get('dispatchWorkspace').value='';page.toggle(12,true);
assert.equal(elements.get('dispatchPreviewBtn').disabled,true);
elements.get('dispatchWorkspace').value='workspace-1';page.toggle(12,false);

page._candidates = [
  { id:1, can_dispatch:true }, { id:2, can_dispatch:false }, { id:3, can_dispatch:true },
];
page.selectPage();
assert.deepEqual([...page._selected], [1,3]);

page._meta={total:121,limit:50,offset:50};
assert.match(page._paginationHtml(),/Showing 51–100 of 121/);
assert.match(page._paginationHtml(),/Page 2 of 3/);

page._state.available={status_id:'2',studio_id:'1',model_id:'3',limit:50,offset:50};
page._resetSelection();page._selectionMode='first_n';page._firstN=75;
assert.equal(page._selectionMode,'first_n');assert.equal(page._firstN,75);

console.log('apps/web Work Dispatch UI contract: OK');
