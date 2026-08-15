import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require=createRequire(import.meta.url);const {chromium}=require('playwright');
const fixture=await startBrowserFixture({scenario:'future-ai-workspace',roles:['admin','writer']});const browser=await chromium.launch({headless:true});
async function connect(page,token){await page.goto(fixture.origin);await page.getByRole('button',{name:'Connect'}).click();await page.getByLabel('Approved device Token').fill(token);await page.getByRole('button',{name:'Validate and connect'}).click();await page.getByText(/DB OK/).waitFor();}

try{
  const denied=await browser.newPage();await connect(denied,fixture.devices.writer.token);await denied.goto(`${fixture.origin}/#/admin/ai-model-configurations`);await denied.getByRole('heading',{name:'Permission denied'}).waitFor();await denied.close();
  const page=await browser.newPage();await connect(page,fixture.devices.admin.token);await page.goto(`${fixture.origin}/#/work-dispatch`);await page.getByRole('heading',{name:'Album Work Dispatch'}).waitFor();
  await page.getByRole('link',{name:'Create model configuration'}).click();await page.getByRole('heading',{name:'AI Model Configurations'}).waitFor();await page.getByRole('button',{name:'+ New Configuration'}).click();
  await page.getByLabel('Name *').fill('Local Qwen 7B');await page.getByLabel('Model identifier *').fill('qwen2.5-vl-7b-q4');
  await page.getByLabel('Model file *').fill('qwen2.5-vl-7b/Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf');await page.getByRole('button',{name:'Create configuration'}).click();
  await page.getByText('AI Model Configuration created.').waitFor();await page.getByText('Local Qwen 7B',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Edit'}).click();const listed=await fixture.request('/ai-model-configurations',{role:'admin'});const config=listed.payload.data.items[0];
  const external=await fixture.request(`/ai-model-configurations/${config.uuid}`,{method:'PUT',role:'admin',body:{expected_version:config.version,temperature:0.1}});assert.equal(external.status,200);
  await page.getByRole('button',{name:'Save changes'}).click();await page.getByText(/action conflicts with current state/i).waitFor();await page.getByRole('button',{name:'Cancel'}).click();await page.reload();await page.getByText('Local Qwen 7B',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Edit'}).click();await page.getByLabel('Temperature (0–2)').fill('0');await page.getByLabel('GPU layers (0–999)').fill('0');await page.getByRole('button',{name:'Save changes'}).click();await page.getByText('AI Model Configuration saved.').waitFor();
  await page.getByRole('button',{name:'Disable'}).click();await page.getByRole('button',{name:'Confirm'}).click();await page.getByText('Disabled',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Enable'}).click();await page.getByRole('button',{name:'Confirm'}).click();await page.getByText('Enabled',{exact:true}).waitFor();
  await page.goto(`${fixture.origin}/#/work-dispatch`);await page.getByText('Local Qwen 7B',{exact:true}).waitFor();
  console.log('UI-031 AI Model Configuration browser acceptance: OK');
}finally{await browser.close();await fixture.stop();}
