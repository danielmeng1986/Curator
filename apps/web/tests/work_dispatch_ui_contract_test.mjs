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
  Set, Number, Array, Promise, encodeURIComponent,
});
vm.runInContext(`${pageSource}\nthis.WorkDispatchPage = WorkDispatchPage;`, context, { filename:'work-dispatch.js' });
const page = context.WorkDispatchPage;

assert.match(appSource, /page: 'work-dispatch'.*scope: 'admin'/);
assert.match(indexSource, /AI Work Dispatch/);
assert.match(indexSource, /pages\/work-dispatch\.js/);
assert.match(pageSource, /availability=available/);
assert.match(pageSource, /Status will not change/);
assert.match(pageSource, /preview_token/);
assert.match(pageSource, /configuration_uuids/);
assert.match(pageSource, /view=\$\{this\._view\}/);

elements.set('dispatchSelectionCount', { textContent:'' });
elements.set('dispatchPreviewBtn', { disabled:true });
page.toggle(12, true);
assert.equal(page._selected.has(12), true);
assert.equal(elements.get('dispatchSelectionCount').textContent, '1 Albums selected');
assert.equal(elements.get('dispatchPreviewBtn').disabled, false);
page.toggle(12, false);
assert.equal(elements.get('dispatchPreviewBtn').disabled, true);

page._candidates = [
  { id:1, can_dispatch:true }, { id:2, can_dispatch:false }, { id:3, can_dispatch:true },
];
page.selectPage();
assert.deepEqual([...page._selected], [1,3]);

console.log('apps/web Work Dispatch UI contract: OK');
