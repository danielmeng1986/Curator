import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require=createRequire(import.meta.url);const {chromium}=require('playwright');
const fixture=await startBrowserFixture({scenario:'work-dispatch-pagination',roles:['admin']});const browser=await chromium.launch({headless:true});
async function connect(page,token){await page.goto(fixture.origin);await page.getByRole('button',{name:'Connect'}).click();await page.getByLabel('Approved device Token').fill(token);await page.getByRole('button',{name:'Validate and connect'}).click();await page.getByText(/DB OK/).waitFor();}

try{
  const page=await browser.newPage();await connect(page,fixture.devices.admin.token);await page.goto(`${fixture.origin}/#/work-dispatch`);await page.getByRole('heading',{name:'Album Work Dispatch'}).waitFor();
  await page.getByText('Showing 1–50 of 55').waitFor();assert.equal(await page.locator('[data-dispatch-album]').count(),50);
  await page.getByRole('button',{name:'Next'}).click();await page.getByText('Showing 51–55 of 55').waitFor();assert.equal(await page.locator('[data-dispatch-album]').count(),5);
  await page.getByLabel('Status').selectOption({label:'TEMPORARY'});await page.getByText('Showing 1–50 of 55').waitFor();
  await page.getByLabel('Studio').selectOption({label:'Fixture Studio'});await page.getByLabel('Model').selectOption({label:'Fixture Model'});await page.getByText('Showing 1–50 of 55').waitFor();
  await page.getByRole('button',{name:'Select current page'}).click();await page.getByText('50 Albums selected').waitFor();
  await page.getByRole('button',{name:'Next'}).click();await page.getByText('0 Albums selected').waitFor();
  page.once('dialog',dialog=>dialog.accept('55'));await page.getByRole('button',{name:'Select first N…'}).click();await page.getByText('First 55 filtered Albums selected').waitFor();
  console.log('UI-032 Work Dispatch pagination browser acceptance: OK');
}finally{await browser.close();await fixture.stop();}
