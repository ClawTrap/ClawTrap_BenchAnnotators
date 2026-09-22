'use strict';
const $ = s => document.querySelector(s);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = name => `<i data-lucide="${name}" aria-hidden="true"></i>`;
const labels = {'':'未审核',accepted:'已保留',needs_discussion:'待讨论',discarded:'已排除'};
const params = new URLSearchParams(location.search);
const readonly = params.get('mode') === 'view';
const state = {rows:[],visible:[],selected:params.get('case')||'',category:'',status:document.body.dataset.view==='benchmark'?'accepted':'',asset:0,mode:'split',busy:false,drafts:new Map()};
const draftKey = id => `clawtrap-design-review:${document.body.dataset.user}:${id}`;
const icons = () => window.lucide?.createIcons();
function safeURL(value) { try {const u=new URL(value,location.origin);return value&&['https:','http:'].includes(u.protocol)?u.href:'';}catch{return '';}}
function link(value,label) {const url=safeURL(value);return url?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)}${icon('arrow-up-right')}</a>`:'';}
function option(value,label,current) {return `<option value="${esc(value)}" ${value===current?'selected':''}>${esc(label)}</option>`;}
function current() {return state.rows.find(r=>r.id===state.selected);}
function toast(message) {$('#toast').textContent=message;$('#toast').classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').classList.remove('show'),3500);}
async function api(url,options) {
  const response=await fetch(url,options);
  if(response.status===401){location.assign('/login');throw new Error('登录已失效');}
  const result=await response.json();if(!response.ok)throw new Error(result.error||'请求失败');return result;
}
function draft(r) {
  if(state.drafts.has(r.id))return state.drafts.get(r.id);
  try {const saved=JSON.parse(sessionStorage.getItem(draftKey(r.id)));if(saved){state.drafts.set(r.id,saved);return saved;}}catch{}
  return r.assessment||{};
}
function render() {
  state.visible=state.rows.filter(r=>(!state.category||r.scenario_key===state.category)&&(!state.status||(state.status==='pending'?!r.decision:r.decision===state.status)));
  if(!state.visible.some(r=>r.id===state.selected)){state.selected=state.visible[0]?.id||'';state.asset=0;}
  const r=current(),index=state.visible.findIndex(x=>x.id===state.selected);
  const categories=[...new Map(state.rows.map(x=>[x.scenario_key,x.scenario_title])).entries()];
  $('#progress').textContent=`${state.rows.filter(x=>x.decision).length} / ${state.rows.length} 已审核`;
  $('#app').innerHTML=`<section class="toolbar" aria-label="题目选择">
    <label class="category-select"><span>类型</span><select id="category" ${state.busy?'disabled':''}>${option('','全部类型',state.category)}${categories.map(([k,v])=>option(k,v,state.category)).join('')}</select></label>
    <label class="case-select"><span>题目</span><select id="case-select" ${state.busy?'disabled':''}>${state.visible.map((x,i)=>option(x.id,`${String(i+1).padStart(2,'0')} · ${x.id}`,state.selected)).join('')||option('','暂无题目','')}</select></label>
    <select id="status" aria-label="审核状态" ${state.busy?'disabled':''}>${option('','全部状态',state.status)}${option('pending','未审核',state.status)}${Object.entries(labels).filter(([k])=>k).map(([k,v])=>option(k,v,state.status)).join('')}</select>
    <div class="case-nav"><span>${r?index+1:0} / ${state.visible.length}</span><button class="icon" data-action="prev" title="上一题" aria-label="上一题" ${index<=0||state.busy?'disabled':''}>${icon('chevron-left')}</button><button class="icon" data-action="next" title="下一题" aria-label="下一题" ${index>=state.visible.length-1||state.busy?'disabled':''}>${icon('chevron-right')}</button></div></section>
    ${r?`<section class="brief"><div class="heading"><div><div class="eyebrow">${esc(r.domain_title)}</div><h1>${esc(r.scenario_title)}</h1><div class="identity">${esc(r.id)}<span title="原始类别标签">${esc(r.declared_workflow)}</span></div></div><span class="status ${esc(r.decision||'pending')}">${labels[r.decision]||labels['']}</span></div>
      <div class="brief-columns"><section><h2>任务</h2><p>${esc(r.task)}</p><div id="task-files"></div></section><section><h2>攻击描述</h2><p>${esc(r.transformation||r.target)}</p>${r.original||r.changed?`<dl class="changes"><dt>原始</dt><dd>${esc(r.original||'见原始页面')}</dd><dt>攻击</dt><dd>${esc(r.changed||'见攻击页面')}</dd></dl>`:''}</section></div></section>
      <section class="previews" aria-label="HTML 页面对照"><div class="preview-toolbar"><h2>页面对照</h2><div class="preview-options">${(r.assets||[]).length>1?`<select id="asset" aria-label="预览资产">${r.assets.map((a,i)=>option(String(i),a.title||`页面 ${i+1}`,String(state.asset))).join('')}</select>`:''}<div class="segmented">${[['split','并排'],['clean','原始'],['attack','攻击']].map(([k,v])=>`<button data-mode="${k}" aria-pressed="${state.mode===k}">${v}</button>`).join('')}</div></div></div><div id="frames"></div></section>
      ${judgment(r)}`:'<section class="empty"><h1>没有匹配的题目</h1><button data-action="reset">查看全部题目</button></section>'}`;
  if(r){renderFrames();loadFiles(r);const u=new URL(location);u.searchParams.set('case',r.id);u.searchParams.set('dataset',r.dataset);history.replaceState(null,'',u);}
  icons();
}
function renderFrames() {
  const r=current(),assets=r.assets||[];state.asset=Math.min(state.asset,Math.max(0,assets.length-1));const asset=assets[state.asset];
  if(!asset){$('#frames').innerHTML='<div class="empty">未登记可预览的 HTML</div>';return;}
  const before=asset.before_url||(asset.url||'').replace('/attack-assets/','/clean-assets/');
  const sources=r.source_urls?.length?r.source_urls:[{url:r.source}];
  const frame=(url,title,kind)=>`<section class="snapshot"><header><strong><span class="dot ${kind}"></span>${title}</strong><div>${kind==='clean'?sources.slice(0,2).map((s,i)=>link(s.url,i?'其他来源':'原网页')).join(''):''}${link(url,'独立打开')}</div></header>${safeURL(url)?`<iframe src="${esc(safeURL(url))}" title="${title}" sandbox="allow-scripts" referrerpolicy="no-referrer"></iframe>`:'<p>缺少页面地址</p>'}</section>`;
  $('#frames').className=`snapshot-grid ${state.mode==='split'?'split':''}`;
  $('#frames').innerHTML=(state.mode!=='attack'?frame(before,'原始 HTML','clean'):'')+(state.mode!=='clean'?frame(asset.url,'攻击 HTML','attack'):'');
  document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===state.mode)));icons();
}
async function loadFiles(r) {
  try {const data=await api(`/api/review/cases/${encodeURIComponent(r.id)}`);if(state.selected!==r.id)return;
    const files=data.case.task_file_previews||[];
    $('#task-files').innerHTML=files.length?`<details><summary>任务附件 · ${files.length}</summary>${files.map(f=>`<div class="task-file"><strong>${esc(f.key)}</strong><pre>${esc(f.error||f.text)}</pre></div>`).join('')}</details>`:'';
  }catch(e){if(state.selected===r.id)$('#task-files').textContent=`任务附件加载失败：${e.message}`;}
}
function judgment(r) {
  const value=draft(r);
  return `<section class="judgment"><div class="judgment-title"><h2>审核判定</h2><span id="save-state">${state.drafts.has(r.id)?'有未保存的备注':r.decision?'已保存':'未审核'}</span></div>
    <div class="judgment-body"><label class="notes-label" for="notes">备注 <span>可选</span><textarea id="notes" rows="2" maxlength="12000" placeholder="记录需要修改的问题" ${readonly||state.busy?'disabled':''}>${esc(value.notes??r.comment??'')}</textarea></label>
    <div class="judgment-actions">${readonly?'<span>只读查看</span>':`<div class="decisions"><button data-decision="discarded" ${state.busy?'disabled':''}>${icon('x')}排除</button><button data-decision="needs_discussion" ${state.busy?'disabled':''}>${icon('message-circle')}待讨论</button><button class="primary" data-decision="accepted" ${state.busy?'disabled':''}>${icon('check')}保留并下一题</button></div><div class="secondary-actions"><button class="text-button" data-action="save" ${state.busy?'disabled':''}>${icon('save')}保存备注</button>${r.decision?`<button class="text-button" data-decision="clear" ${state.busy?'disabled':''}>${icon('undo-2')}撤销判定</button>`:''}</div>`}</div></div></section>`;
}
function capture() {
  if(readonly||!$('#notes'))return;const r=current();
  // Keep existing detailed assessments when only editing a note.
  const value={...draft(r),notes:$('#notes').value};state.drafts.set(r.id,value);
  try{sessionStorage.setItem(draftKey(r.id),JSON.stringify(value));}catch{}
  $('#save-state').textContent='有未保存的备注';
}
async function save(decision) {
  if(state.busy||readonly)return;capture();const r=current(),id=r.id;
  const index=state.visible.findIndex(x=>x.id===id),next=state.visible[index+1]?.id;
  state.busy=true;document.querySelectorAll('button,select,textarea').forEach(n=>n.disabled=true);$('#save-state').textContent='正在保存…';
  try {
    const result=await api(`/api/review/cases/${encodeURIComponent(id)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({assessment:state.drafts.get(id),...(decision?{decision}:{})})});
    Object.assign(r,result);state.drafts.delete(id);try{sessionStorage.removeItem(draftKey(id));}catch{}
    if(decision&&decision!=='clear'&&next){state.selected=next;state.asset=0;}
    state.busy=false;render();if(decision&&decision!=='clear')window.scrollTo({top:0});toast(decision?'判定已保存':'备注已保存');
  }catch(e){state.busy=false;render();toast(`保存失败：${e.message}`);}
}
document.addEventListener('input',e=>{if(e.target.id==='notes')capture();});
document.addEventListener('change',e=>{
  if(state.busy)return;
  if(e.target.id==='asset'){state.asset=Number(e.target.value);renderFrames();return;}
  if(e.target.id==='category'){state.category=e.target.value;state.asset=0;render();}
  if(e.target.id==='status'){state.status=e.target.value;state.asset=0;render();}
  if(e.target.id==='case-select'){state.selected=e.target.value;state.asset=0;render();}
});
document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b||state.busy)return;
  if(b.dataset.mode){state.mode=b.dataset.mode;renderFrames();return;}
  if(b.dataset.decision){save(b.dataset.decision);return;}
  const action=b.dataset.action;
  if(action==='save')save();
  if(action==='retry')location.reload();
  if(action==='reset'){state.category='';state.status='';render();}
  if(action==='prev'||action==='next'){const i=state.visible.findIndex(r=>r.id===state.selected),r=state.visible[i+(action==='next'?1:-1)];if(r){state.selected=r.id;state.asset=0;render();window.scrollTo({top:0});}}
});
window.addEventListener('beforeunload',e=>{if(state.drafts.size){e.preventDefault();e.returnValue='';}});
(async()=>{try{const data=await api('/api/review/catalog');state.rows=data.cases;render();}catch(e){$('#app').innerHTML='<div class="empty">题目加载失败</div>';$('#app-error').hidden=false;$('#app-error').innerHTML=`${esc(e.message)} <button data-action="retry">重试</button>`;}})();
