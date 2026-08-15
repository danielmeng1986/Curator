import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const source=await readFile(new URL('../static/pages/workspace-review.js',import.meta.url),'utf8');
const app=await readFile(new URL('../static/app.js',import.meta.url),'utf8');
const index=await readFile(new URL('../static/index.html',import.meta.url),'utf8');
const values=new Map([
  ['reviewSelectedName',{value:'Golden Forest Morning'}],['reviewSelectionSource',{value:'HumanRevision'}],
  ['reviewRating',{value:'4'}],['reviewNotes',{value:'Useful composition analysis'}],['reviewReason',{value:'Needs another sample'}],
]);
const context=vm.createContext({window:{location:{hash:''}},document:{getElementById:id=>values.get(id)||null},console,
  api:{},ui:{saveDraft(){return true;},markDirty(){},clearDraft(){},clearDirty(){},loadDraft(){return null;}},esc:value=>String(value),toast(){},showModal(){},closeModal(){},URLSearchParams,Number,Object,Array,Promise,encodeURIComponent});
vm.runInContext(`${source}\nthis.WorkspaceReviewPage=WorkspaceReviewPage;`,context,{filename:'workspace-review.js'});
const page=context.WorkspaceReviewPage;

assert.match(app,/page: 'ai-reviews'.*scope: 'admin'/);
assert.match(app,/page: 'ai-review-detail'.*scope: 'admin'/);
assert.match(index,/AI Review/);
assert.match(source,/AI analysis · immutable/);
assert.match(source,/Human review · editable draft/);
assert.match(source,/System evidence and provenance/);
assert.match(source,/review\.allowed_actions\.includes/);
assert.match(source,/expected_version:r\.version/);
assert.match(source,/promotion\/preview/);
assert.match(source,/preview_token:token,confirmation/);
assert.match(source,/\+ New Workspace/);
assert.match(source,/api\.post\('\/ai-workspaces',\{title\}\)/);
assert.match(source,/album_analysis/);

page._detail={review:{work_item_uuid:'item-1'}};
page.saveDraft();
assert.equal(page._draft['item-1'].selected_name,'Golden Forest Morning');
assert.equal(page._draft['item-1'].selection_source,'HumanRevision');
assert.equal(page._draft['item-1'].rating,4);
assert.equal(page._draft['item-1'].reason,'Needs another sample');

console.log('apps/web Workspace Review UI contract: OK');
