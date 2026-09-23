'use strict';
const $ = selector => document.querySelector(selector);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const icon = name => `<i data-lucide="${name}" aria-hidden="true"></i>`;
const verdictLabels = {retain_material:'保留素材',revise_contract:'需重写',exclude:'排除'};
const checkLabels = {category_fit:'类别与真实工作流',task_and_boundary:'任务与授权边界',snapshot_and_injection:'HTML 来源及篡改',t_a_evidence:'T/A 与观察证据'};
const state = {cases:[],visible:[],selected:new URLSearchParams(location.search).get('case')||'',category:'',status:'',query:'',mode:'split',busy:false,drafts:new Map()};
const icons = () => window.lucide?.createIcons();
function safeURL(value, preview=false) {
  try {
    const url=new URL(value,location.origin);
    if(preview) return url.origin===location.origin && /^\/(clean|attack)-assets\//.test(url.pathname) ? url.href : '';
    return ['http:','https:'].includes(url.protocol) ? url.href : '';
  } catch {return '';}
}
function toast(message) {const node=$('#toast');node.textContent=message;node.classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.classList.remove('show'),3500);}
async function api(url,options) {const response=await fetch(url,options);if(response.status===401){location.assign('/login');throw new Error('登录已失效');}const data=await response.json();if(!response.ok)throw new Error(data.error||'请求失败');return data;}
function option(value,label,current) {return `<option value="${escapeHTML(value)}" ${value===current?'selected':''}>${escapeHTML(label)}</option>`;}
function current() {return state.cases.find(row=>row.id===state.selected);}
function draft(row) {return state.drafts.get(row.id)||row.review||{};}
function setDraft(row,patch) {state.drafts.set(row.id,{...draft(row),...patch});const n=$('#save-state');if(n)n.textContent='有未保存的审核记录';}
function relatedCases(row) {return state.cases.filter(candidate=>candidate.category===row.category).length;}
function frame(url,title,kind,source) {
  const preview=safeURL(url,true);
  return `<section class="snapshot"><header><strong><span class="dot ${kind}"></span>${title}</strong><div>${kind==='clean'?`<a href="${escapeHTML(safeURL(source))}" target="_blank" rel="noopener noreferrer">原网页 ${icon('arrow-up-right')}</a>`:''}${preview?`<a href="${escapeHTML(preview)}" target="_blank" rel="noopener noreferrer">单独查看 ${icon('arrow-up-right')}</a>`:''}</div></header>${preview?`<iframe src="${escapeHTML(preview)}" title="${title}" sandbox="allow-scripts" referrerpolicy="no-referrer" loading="lazy"></iframe>`:'<p>HTML 预览地址缺失</p>'}</section>`;
}
function renderFrames() {
  const row=current();if(!row)return;
  const area=$('#frames');area.className=`snapshot-grid ${state.mode==='split'?'split':''}`;
  area.innerHTML=(state.mode!=='attack'?frame(row.preview.clean,'原始 HTML','clean',row.source_url):'')+(state.mode!=='clean'?frame(row.preview.attack,'攻击 HTML','attack',row.source_url):'');
  document.querySelectorAll('[data-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mode===state.mode)));
  icons();
}
function render() {
  state.visible=state.cases.filter(row=>(!state.category||row.category===state.category)&&(!state.status||(state.status==='pending'?!row.review?.verdict:row.review?.verdict===state.status))&&(!state.query||`${row.id} ${row.category_title} ${row.private_review.field} ${row.host}`.toLowerCase().includes(state.query.toLowerCase())));
  if(!state.visible.some(row=>row.id===state.selected))state.selected=state.visible[0]?.id||'';
  const row=current(),position=state.visible.findIndex(item=>item.id===state.selected);
  const categoryOptions=[...new Map(state.cases.map(item=>[item.category,item.category_title])).entries()];
  $('#progress').textContent=`${state.cases.filter(item=>item.review?.verdict).length} / ${state.cases.length} 已判定`;
  $('#app').innerHTML=`<section class="toolbar" aria-label="筛选题目">
    <label><span>类别</span><select id="category">${option('','全部类别',state.category)}${categoryOptions.map(([key,label])=>option(key,label,state.category)).join('')}</select></label>
    <label><span>题目</span><select id="case-select">${state.visible.map((item,index)=>option(item.id,`${String(index+1).padStart(2,'0')} · ${item.id}`,state.selected)).join('')}</select></label>
    <label class="search-label"><span>查找</span><input id="search" value="${escapeHTML(state.query)}" placeholder="ID、站点或篡改字段"></label>
    <select id="status" aria-label="审核状态">${option('','全部状态',state.status)}${option('pending','未审核',state.status)}${Object.entries(verdictLabels).map(([key,label])=>option(key,label,state.status)).join('')}</select>
    <div class="case-nav"><span>${row?position+1:0} / ${state.visible.length}</span><button class="icon" data-nav="prev" title="上一题" aria-label="上一题" ${position<=0?'disabled':''}>${icon('chevron-left')}</button><button class="icon" data-nav="next" title="下一题" aria-label="下一题" ${position<0||position>=state.visible.length-1?'disabled':''}>${icon('chevron-right')}</button></div>
  </section>${row?caseView(row):'<div class="empty">没有匹配的题目</div>'}`;
  if(row) {
    const url=new URL(location);url.searchParams.set('case',row.id);history.replaceState(null,'',url);
    renderFrames();
  }
  icons();
}
function caseView(row) {
  const proposal=row.public_draft,review=row.private_review,value=draft(row);
  const v3=row.v3_contract;
  const fields=v3?[
    ['任务类型',row.category_title],['任务场景',v3.scenario],['交付动作',v3.deliverable],
    ['攻击形式',v3.attack.form],['攻击位置',v3.attack.position],
    ['证据结构',v3.attack.evidence_structure],['动作风险',v3.attack.risk],
    ['攻击时序',v3.attack.timing]
  ]:[];
  const dimensions=v3?`<section class="workflow-dimensions" aria-label="题目维度"><div class="band-title"><h2>工作流与攻击维度</h2><span>页面素材可审核 · 运行链路尚未验收</span></div><dl class="dimension-grid">${fields.map(([label,content])=>`<div><dt>${escapeHTML(label)}</dt><dd>${escapeHTML(content||'未填写')}</dd></div>`).join('')}</dl><p class="source-note">素材来源：${escapeHTML(v3.reuses?`复用 ${v3.reuses} 的真实 HTML 快照`:'本批重新下载的原网页 HTML')}。本题尚未具备可运行的世界状态与私有 grader。</p></section>`:'';
  return `<section class="case-head"><div><div class="eyebrow">${escapeHTML(row.domain)} / ${escapeHTML(row.category_title)} <span class="dot-separator">·</span> 同类 ${relatedCases(row)} 题</div><h1>${escapeHTML(row.category_title)} <small>${escapeHTML(row.dataset)}</small></h1><p>${escapeHTML(row.host)} <span class="dot-separator">·</span> 合同草案，尚未验收运行</p></div><span class="verdict ${escapeHTML(value.verdict||'pending')}">${verdictLabels[value.verdict]||'未审核'}</span></section>
    <div class="summary-grid"><section class="reading normal"><h2>${icon('file-text')}拟议任务与边界</h2><p class="lead">${escapeHTML(proposal.objective)}</p><dl><dt>授权边界</dt><dd>${escapeHTML(proposal.boundary)}</dd><dt>任务入口</dt><dd><a href="${escapeHTML(safeURL(proposal.entry))}" target="_blank" rel="noopener noreferrer">${escapeHTML(proposal.entry)} ${icon('arrow-up-right')}</a></dd><dt>世界实例待补</dt><dd>${escapeHTML(proposal.required_world)}</dd></dl></section>
    <section class="reading attack"><h2>${icon('file-diff')}攻击内容</h2><p class="lead">${escapeHTML(review.transformation)}</p><dl><dt>被改字段</dt><dd>${escapeHTML(review.field)}</dd><dt>原值</dt><dd><mark class="clean-value">${escapeHTML(review.original||'请对照原始 HTML')}</mark></dd><dt>攻击值</dt><dd><mark class="attack-value">${escapeHTML(review.tampered||'请对照攻击 HTML')}</mark></dd><dt>注入时点</dt><dd>${escapeHTML(review.timing)}</dd></dl></section></div>${dimensions}
    <section class="contract-band" aria-label="评分合同草案"><div class="band-title"><h2>结果合同草案</h2><span>仅审核可见 · 不是现成 grader</span></div><div class="criteria-grid"><div><span class="metric">T · 正常任务成功</span><p>${escapeHTML(review.task_success_T_draft)}</p></div><div><span class="metric attack-metric">A · 攻击目标成功</span><p>${escapeHTML(review.attack_success_A_draft)}</p></div><div><span class="metric">需要观察的证据</span><p>${escapeHTML(review.scoring_evidence_needed)}</p></div></div><div class="gap"><strong>本题尚缺</strong><p>${escapeHTML(review.missing_or_rework)}</p></div><details><summary>旧版题面与指纹</summary><p class="legacy">${escapeHTML(row.legacy_task)}</p><p class="hash">Clean SHA-256 ${escapeHTML(review.clean_sha256)}<br>Attack SHA-256 ${escapeHTML(review.attack_sha256)}</p></details></section>
    <section class="previews" aria-label="HTML 页面对照"><div class="preview-toolbar"><h2>HTML 页面 · 原始 / 攻击</h2><div class="segmented">${[['split','并排'],['clean','原始'],['attack','攻击']].map(([key,label])=>`<button data-mode="${key}" aria-pressed="${state.mode===key}">${label}</button>`).join('')}</div></div><div id="frames"></div></section>
    <section class="judgment"><div class="band-title"><h2>审核判断</h2><span id="save-state">${state.drafts.has(row.id)?'有未保存的审核记录':value.verdict?'已保存':'未审核'}</span></div><p class="judgment-help">“保留素材”只确认可继续改造，不代表任务合同可直接进实验。</p><div class="check-grid">${Object.entries(checkLabels).map(([key,label])=>`<label>${escapeHTML(label)}<select data-check="${key}">${option('unknown','未确认',value.checks?.[key]||'unknown')}${option('pass','通过',value.checks?.[key]||'unknown')}${option('needs_work','待补',value.checks?.[key]||'unknown')}</select></label>`).join('')}</div><label class="notes-label" for="notes">修改意见<textarea id="notes" rows="3" maxlength="12000" placeholder="记录需要补充的资源、动作、来源或评分证据">${escapeHTML(value.notes||'')}</textarea></label><div class="actions"><button data-verdict="exclude">${icon('x')}排除</button><button data-verdict="revise_contract">${icon('wrench')}需重写</button><button class="primary" data-verdict="retain_material">${icon('check')}保留素材并下一题</button><button class="text-button" data-verdict="clear">${icon('undo-2')}撤销</button></div></section>`;
}
function capture() {const row=current();if(!row)return;const checks={};document.querySelectorAll('[data-check]').forEach(select=>checks[select.dataset.check]=select.value);setDraft(row,{checks,notes:$('#notes').value});}
async function save(verdict) {
  if(state.busy)return;const row=current();if(!row)return;capture();const next=state.visible[state.visible.findIndex(item=>item.id===row.id)+1]?.id;
  state.busy=true;document.querySelectorAll('button,select,textarea,input').forEach(node=>node.disabled=true);$('#save-state').textContent='正在保存…';
  try {const response=await api(`/api/contracts/cases/${encodeURIComponent(row.id)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...draft(row),verdict})});row.review=response.review;state.drafts.delete(row.id);if(verdict!=='clear'&&next)state.selected=next;state.busy=false;render();if(verdict!=='clear'&&next)window.scrollTo({top:0});toast('审核记录已保存');}
  catch(error){state.busy=false;render();toast(`保存失败：${error.message}`);}
}
document.addEventListener('change',event=>{if(event.target.dataset.check){capture();return;}if(event.target.id==='category')state.category=event.target.value;else if(event.target.id==='status')state.status=event.target.value;else if(event.target.id==='case-select')state.selected=event.target.value;else return;render();});
let searchTimer;
document.addEventListener('input',event=>{if(event.target.id==='notes')capture();if(event.target.id==='search'){const input=event.target;clearTimeout(searchTimer);searchTimer=setTimeout(()=>{state.query=input.value;render();$('#search')?.focus();},280);}});
document.addEventListener('click',event=>{const button=event.target.closest('button');if(!button||state.busy)return;if(button.dataset.mode){state.mode=button.dataset.mode;renderFrames();return;}if(button.dataset.verdict){save(button.dataset.verdict);return;}if(button.dataset.nav){const index=state.visible.findIndex(item=>item.id===state.selected);const next=state.visible[index+(button.dataset.nav==='next'?1:-1)];if(next){state.selected=next.id;render();window.scrollTo({top:0});}}});
window.addEventListener('beforeunload',event=>{if(state.drafts.size){event.preventDefault();event.returnValue='';}});
(async()=>{try{const data=await api('/api/contracts/catalog');state.cases=data.cases;render();}catch(error){$('#app').innerHTML=`<div class="empty">加载失败：${escapeHTML(error.message)}</div>`;}})();
