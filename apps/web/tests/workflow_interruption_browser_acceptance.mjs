/* UI-024–028 browser interruption and recovery acceptance. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require=createRequire(import.meta.url);const {chromium}=require('playwright');
const fixture=await startBrowserFixture({scenario:'entities',roles:['writer']});
const browser=await chromium.launch({headless:true});
async function connect(page){await page.goto(fixture.origin);await page.getByRole('button',{name:'Connect'}).click();await page.getByLabel('Approved device Token').fill(fixture.devices.writer.token);await page.getByRole('button',{name:'Validate and connect'}).click();await page.getByText(/DB OK/).waitFor();}

try{
  let context=await browser.newContext();let page=await context.newPage();await connect(page);

  await page.goto(`${fixture.origin}/#/models/new`);await page.locator('#fDisplayName').fill('Interrupted Model Draft');await page.locator('#fPrimaryName').fill('Interrupted Primary Name');
  const restartedState=await context.storageState();await context.close();context=await browser.newContext({storageState:restartedState});page=await context.newPage();await page.goto(`${fixture.origin}/#/models/new`);
  await page.getByText('Restored the Model draft saved in this browser.').waitFor();
  assert.equal(await page.locator('#fDisplayName').inputValue(),'Interrupted Model Draft');
  await page.getByRole('button',{name:'Save'}).click();await page.getByText('Model created').waitFor();
  assert.equal(await page.evaluate(()=>localStorage.getItem('curator.web.draft.v1.entity.model.new')),null);

  await page.goto(`${fixture.origin}/#/studios?q=Fixture&offset=50`);await page.reload();
  assert.match(page.url(),/#\/studios\?q=Fixture&offset=50$/);

  await page.goto(`${fixture.origin}/#/import/albums`);await page.locator('#iAction').selectOption('DATABASE_ONLY');
  await page.locator('#iModel').fill('Interrupted Import Model');await page.locator('#iAlbum').fill('Interrupted Import Album');await page.getByRole('button',{name:'+ Add to Batch'}).click();
  await page.reload();await page.getByText('Restored the Import workflow saved in this browser.').waitFor();await page.getByText('Batch (1 items)').waitFor();
  await page.getByRole('button',{name:'Abandon saved Import'}).click();await page.getByRole('button',{name:'Abandon draft'}).click();await page.getByText('Batch (1 items)').waitFor({state:'detached'});

  await page.goto(`${fixture.origin}/#/albums`);const first=page.getByRole('checkbox',{name:/Select /}).first();await first.check();await page.getByRole('button',{name:/Batch edit selected/}).click();
  await page.getByRole('heading',{name:/Batch edit/}).waitFor();await page.keyboard.press('Escape');await page.getByRole('heading',{name:/Batch edit/}).waitFor();
  await page.reload();await page.getByText(/Album batch edit review was interrupted before execution/).waitFor();

  await context.close();console.log('UI-024–028 workflow interruption browser acceptance: OK');
}finally{await browser.close();await fixture.stop();}
