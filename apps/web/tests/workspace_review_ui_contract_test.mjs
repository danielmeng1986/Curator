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
const apiCalls=[];
const context=vm.createContext({window:{location:{hash:''}},document:{getElementById:id=>values.get(id)||null},console,
  api:{async post(path,body){apiCalls.push({path,body});return {translations:{configured:true,cached_count:1,missing_count:0,items:[{source_text:'Golden Forest Morning',translated_text:'金色森林清晨',cached:true}]}};}},ui:{saveDraft(){return true;},markDirty(){},clearDraft(){},clearDirty(){},loadDraft(){return null;}},esc:value=>String(value),toast(){},showModal(){},closeModal(){},URLSearchParams,Map,Number,Object,Array,Promise,encodeURIComponent});
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
assert.match(source,/preview_token:token,acknowledged:true/);
assert.match(source,/promotionAcknowledgement/);
assert.match(source,/Next review/);
assert.match(source,/curator\.ai-review\.queue/);
assert.match(source,/_resolveNextReview/);
assert.match(source,/IntersectionObserver/);
assert.match(source,/_evidenceActive<3/);
assert.match(source,/api\.getBlob\(`\/ai-evidence\/\$\{encodeURIComponent\(uuid\)\}\/content`\)/);
assert.match(source,/URL\.revokeObjectURL/);
assert.match(source,/createImageBitmap/);
assert.match(source,/Image preview ended after Promotion/);
assert.match(source,/_startPolling/);
assert.match(source,/document\.hidden/);
assert.match(source,/\+ New Workspace/);
assert.match(source,/api\.post\('\/ai-workspaces',\{title\}\)/);
assert.match(source,/album_analysis/);
assert.match(source,/Show Chinese translations/);
assert.match(source,/Hide Chinese translations/);
assert.match(source,/Machine-generated Chinese translations are for review assistance only/);
assert.match(source,/lang="zh-Hans"/);
assert.match(source,/api\.post\(`\/ai-work-items\/\$\{encodeURIComponent\(uuid\)\}\/review-translations`,\{\}\)/);
assert.doesNotMatch(source,/api-free\.deepl\.com|api\.deepl\.com|DeepL-Auth-Key/);

assert.equal(
  page._configurationSnapshot({configuration_snapshot_json:'{"instruction_profile":{"profile_name":"Curator Default"}}'}).instruction_profile.profile_name,
  'Curator Default',
);
assert.equal(
  page._configurationSnapshot({configuration_snapshot:{instruction_profile:{version:1}}}).instruction_profile.version,
  1,
);
assert.equal(Object.keys(page._configurationSnapshot({configuration_snapshot_json:'not-json'})).length,0);

page._detail={review:{work_item_uuid:'item-1'}};
page.saveDraft();
assert.equal(page._draft['item-1'].selected_name,'Golden Forest Morning');
assert.equal(page._draft['item-1'].selection_source,'HumanRevision');
assert.equal(page._draft['item-1'].rating,4);
assert.equal(page._draft['item-1'].reason,'Needs another sample');

page._queueItems=[{work_item_uuid:'item-1',state:'Approved'},{work_item_uuid:'item-2',state:'ReadyForReview'}];
assert.equal(await page._resolveNextReview('item-1'),'item-2');

page._detail={review:{work_item_uuid:'item-1'},translations:{configured:true,cached_count:0,missing_count:1,items:[{source_text:'Golden Forest Morning',translated_text:null,cached:false}]}};
page.saveDraft=()=>{};page._renderDetail=()=>{};
await page.showChineseTranslations();
assert.equal(apiCalls.length,1);assert.equal(apiCalls[0].path,'/ai-work-items/item-1/review-translations');
assert.equal(page._detail.translations.items[0].source_text,'Golden Forest Morning');
assert.equal(page._detail.translations.items[0].translated_text,'金色森林清晨');
page.hideChineseTranslations();assert.equal(page._translationsVisible,false);
context.api.post=async()=>{const error=new Error('Translation provider unavailable');error.code='TRANSLATION_PROVIDER_UNAVAILABLE';throw error;};
page._detail.translations={configured:true,cached_count:0,missing_count:1,items:[{source_text:'Golden Forest Morning',translated_text:null,cached:false}]};
await page.showChineseTranslations();
assert.equal(page._translationError,'Translation provider unavailable');
assert.equal(page._detail.review.work_item_uuid,'item-1');
assert.equal(page._draft['item-1'].selected_name,'Golden Forest Morning');

console.log('apps/web Workspace Review UI contract: OK');
