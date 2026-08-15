import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const pageSource=await readFile(new URL('../static/pages/ai-model-configurations.js',import.meta.url),'utf8');
const appSource=await readFile(new URL('../static/app.js',import.meta.url),'utf8');
const indexSource=await readFile(new URL('../static/index.html',import.meta.url),'utf8');
const context=vm.createContext({document:{getElementById(){return null;}},api:{},ui:{},window:{},console,
  esc:value=>String(value),showModal(){},closeModal(){},toast(){},confirmDialog:async()=>true,Date,JSON,Number,Array,Promise,encodeURIComponent});
vm.runInContext(`${pageSource}\nthis.AIModelConfigurationsPage=AIModelConfigurationsPage;`,context);
const page=context.AIModelConfigurationsPage;

assert.match(appSource,/admin-ai-model-configurations'.*scope: 'admin'/);
assert.match(indexSource,/pages\/ai-model-configurations\.js/);
for(const field of ['model_file','model_repository','vision_prompt_version','writer_prompt_version','sample_count','context_size','threads','gpu_layers','max_tokens','temperature','image_max_tokens','additional_parameters'])assert.match(pageSource,new RegExp(field));
assert.match(pageSource,/relative to each Worker's <code>--model-root<\/code>/);
assert.match(pageSource,/Historical Work Item snapshots will not change/);
assert.match(pageSource,/AI_MODEL_CONFIGURATION_STALE|save the AI Model Configuration|expected_version/);
const html=page._fields({gpu_layers:0,temperature:0,additional_parameters:{}});
assert.match(html,/id="aiConfigGpuLayers"[^>]*value="0"/);assert.match(html,/id="aiConfigTemperature"[^>]*value="0"/);
console.log('apps/web AI Model Configuration UI contract: OK');
