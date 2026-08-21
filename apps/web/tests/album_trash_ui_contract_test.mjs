import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(new URL('../static/pages/albums.js', import.meta.url), 'utf8');
const context = vm.createContext({
  window: { curatorPrincipal: { role:'writer' } }, document: { getElementById(){ return null; } },
  api:{},ui:{can:()=>true},console,esc:value=>String(value),toast(){},navigate(){},closeModal(){},
  URLSearchParams,Set,Number,Array,Promise,Date,encodeURIComponent,history:{replaceState(){}},clearTimeout,setTimeout,
});
vm.runInContext(`${source}\nthis.AlbumsPage=AlbumsPage;`, context, { filename:'albums.js' });
const page=context.AlbumsPage;

assert.match(source,/\/albums\/\$\{this\._currentId\}\/trash-readiness/);
assert.match(source,/\/albums\/\$\{albumId\}\/trash\/preview/);
assert.match(source,/api\.post\('\/albums\/trash\/execute', \{ preview_token: token \}\)/);
assert.match(source,/data-required-scope="write"/);
assert.match(source,/This is not database deletion/);
assert.match(source,/Album and Photo records and the Album business Status remain unchanged/);
assert.match(source,/ui\.hasUnsavedChanges\(\)/);
assert.match(source,/ui\.clearDraft\(this\._draftKey\(\)\)/);
assert.match(source,/ASSET_PREVIEW_EXPIRED.*ASSET_LIFECYCLE_STALE.*ASSET_SCOPE_CHANGED/);
assert.match(source,/showReviewedAction/);
assert.match(source,/executeAlbumTrashBtn.*disabled/);
assert.doesNotMatch(source,/api\.delete\(`?\/albums/);

assert.match(page._trashBlocker({code:'ACTIVE_WORK_RESERVATION',group_uuid:'group-1'}),/active AI Work reservation/);
assert.match(page._trashBlocker({code:'WORK_ITEM_NOT_TERMINAL',count:2}),/2 AI Work Item/);
assert.match(page._trashBlocker({code:'UNKNOWN'}),/UNKNOWN/);
assert.equal(page._formatBytes(512),'512 B');
assert.equal(page._formatBytes(2048),'2.0 KiB');

console.log('apps/web Album Trash UI contract: OK');
