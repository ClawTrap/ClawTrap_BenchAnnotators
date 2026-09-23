'use strict';

const $ = selector => document.querySelector(selector);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const icon = name => `<i data-lucide="${name}" aria-hidden="true"></i>`;
const state = {
  cases:[],labels:{categories:[]},visible:[],selected:new URLSearchParams(location.search).get('case')||'',
  domain:'',category:'',status:'',query:'',mode:'split',busy:false,contentWritable:false,editing:null
};
const labelChoices = {
  form:[['full-page replacement','整页替换'],['iframe/popup injection','弹窗 / iframe'],['selective substitution','局部替换'],['redirect rewriting','重定向改写'],['API JSON mutation','API JSON 改写'],['file replacement','文件替换'],['mixed benign–malicious content','良恶内容混合']],
  position:[['search results','搜索结果'],['target webpage','目标网页'],['third-party citation','第三方引用'],['API response','API 响应'],['download file','下载文件'],['login page','登录页'],['checkout page','结算页'],['error page','错误页'],['redirect chain','重定向链'],['asynchronous update','异步更新']],
  evidence_structure:[['single source','单一来源'],['multiple polluted sources','多个污染来源'],['trusted–polluted conflict','可信与污染来源冲突'],['polluted majority / trusted minority','多数污染、少数可信'],['internal policy / external page conflict','内部政策与外部页面冲突'],['cache / live page conflict','缓存与实时页面冲突']],
  risk:[['read-only','只读'],['reversible write','可逆写入'],['cross-system write','跨系统写入'],['external communication','外部通信'],['data disclosure','数据披露'],['permission change','权限变更'],['financial action','财务动作'],['irreversible execution','不可逆执行']],
  timing:[['first step','第一步'],['before decision','决策前'],['before confirmation','确认前'],['repeated across turns','跨回合重复'],['delayed trigger','延迟触发'],['memory contamination then trigger','先污染记忆后触发'],['clean/attack alternation','正常与攻击交替']]
};

function icons(){window.lucide?.createIcons();}
function toast(message){const node=$('#toast');node.textContent=message;node.classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.classList.remove('show'),3500);}
async function api(url,options){const response=await fetch(url,options);if(response.status===401){location.assign('/login');throw new Error('登录已失效');}const data=await response.json();if(!response.ok)throw new Error(data.error||'请求失败');return data;}
function option(value,label,current){return `<option value="${escapeHTML(value)}" ${value===current?'selected':''}>${escapeHTML(label)}</option>`;}
function current(){return state.cases.find(row=>row.id===state.selected);}
function selectedCount(){return state.cases.filter(row=>row.review?.selected).length;}
function safeURL(value,preview=false){try{const url=new URL(value,location.origin);if(preview)return url.origin===location.origin&&/^\/(clean|attack)-assets\//.test(url.pathname)?url.href:'';return ['http:','https:'].includes(url.protocol)?url.href:'';}catch{return '';}}
function editable(key,value,tag='p'){
  return `<${tag} class="inline-editable" data-edit-field="${key}" ${state.contentWritable?'tabindex="0" title="双击修改"':''}>${escapeHTML(value)}</${tag}>`;
}
function categorySelect(row){
  const groups=[...new Set(state.labels.categories.map(item=>item.domain))];
  return `<select data-label-field="category" aria-label="任务类别" ${state.contentWritable?'':'disabled'}>${groups.map(domain=>`<optgroup label="${escapeHTML(domain)}">${state.labels.categories.filter(item=>item.domain===domain).map(item=>option(item.key,`${item.number}. ${item.title}`,row.category)).join('')}</optgroup>`).join('')}</select>`;
}
function labelSelect(key,value){
  const choices=labelChoices[key]||[];
  const all=choices.some(([choice])=>choice===value)?choices:[[value,value],...choices];
  return `<select data-label-field="${key}" aria-label="${escapeHTML(key)}" ${state.contentWritable?'':'disabled'}>${all.map(([choice,label])=>option(choice,label,value)).join('')}</select>`;
}
function frame(url,title,kind,source){
  const preview=safeURL(url,true),origin=safeURL(source);
  return `<section class="snapshot"><header><strong><span class="dot ${kind}"></span>${title}</strong><div>${kind==='clean'&&origin?`<a href="${escapeHTML(origin)}" target="_blank" rel="noopener noreferrer">原网页 ${icon('arrow-up-right')}</a>`:''}${preview?`<a href="${escapeHTML(preview)}" target="_blank" rel="noopener noreferrer">单独查看 ${icon('arrow-up-right')}</a>`:''}</div></header>${preview?`<iframe src="${escapeHTML(preview)}" title="${title}" sandbox="allow-scripts" referrerpolicy="no-referrer" loading="lazy"></iframe>`:'<p>HTML 预览地址缺失</p>'}</section>`;
}
function renderFrames(){
  const row=current(),area=$('#frames');if(!row||!area)return;
  area.className=`snapshot-grid ${state.mode==='split'?'split':''}`;
  area.innerHTML=(state.mode!=='attack'?frame(row.preview.clean,'原始 HTML','clean',row.source_url):'')+(state.mode!=='clean'?frame(row.preview.attack,'攻击 HTML','attack',row.source_url):'');
  document.querySelectorAll('[data-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mode===state.mode)));
  icons();
}
function caseView(row){
  const contract=row.v3_contract,attack=contract.attack,review=row.private_review;
  const dimensions=[
    ['任务类别',categorySelect(row)],['任务场景',editable('scenario',contract.scenario,'span')],['交付产物',editable('deliverable',contract.deliverable,'span')],
    ['攻击形式',labelSelect('form',attack.form)],['攻击位置',labelSelect('position',attack.position)],
    ['证据结构',labelSelect('evidence_structure',attack.evidence_structure)],['动作风险',labelSelect('risk',attack.risk)],
    ['攻击时序',labelSelect('timing',attack.timing)]
  ];
  return `<section class="case-head"><div><div class="eyebrow">${escapeHTML(row.domain)} / ${escapeHTML(row.category_title)}</div><h1>${escapeHTML(contract.scenario)} <small>${escapeHTML(row.id)}</small></h1><p>${escapeHTML(row.host)} · ${row.content_edit?.revision?'题目已修改':'原题'} · ${escapeHTML(row.readiness)}</p></div><span id="selection-badge" class="verdict ${row.review?.selected?'retain_material':''}">${row.review?.selected?'已入选':'未入选'}</span></section>
    <div class="summary-grid"><section class="reading normal"><h2>${icon('file-text')}发给 Agent 的任务</h2>${editable('task',contract.task,'p')}<div class="output-format"><strong>交付方式</strong>${editable('output_format',contract.output_format,'p')}</div><dl><dt>授权边界</dt><dd>${editable('authorized_boundary',contract.authorized_boundary,'span')}</dd><dt>任务入口</dt><dd><a href="${escapeHTML(safeURL(row.source_url))}" target="_blank" rel="noopener noreferrer">${escapeHTML(row.source_url)} ${icon('arrow-up-right')}</a></dd></dl></section>
    <section class="reading attack"><h2>${icon('file-diff')}攻击内容</h2><p class="lead">${escapeHTML(review.transformation)}</p><dl><dt>被改字段</dt><dd>${escapeHTML(review.field)}</dd><dt>原值</dt><dd><mark class="clean-value">${escapeHTML(review.original||'请对照原始 HTML')}</mark></dd><dt>攻击值</dt><dd><mark class="attack-value">${escapeHTML(review.tampered||'请对照攻击 HTML')}</mark></dd></dl></section></div>
    <section class="workflow-dimensions"><div class="band-title"><h2>任务与攻击标签</h2><span>标签修改即时保存</span></div><dl class="dimension-grid">${dimensions.map(([label,control])=>`<div><dt>${label}</dt><dd>${control}</dd></div>`).join('')}</dl></section>
    <section class="contract-band"><div class="band-title"><h2>结果判定</h2><span>T / A 分开记录</span></div><div class="criteria-grid"><div><span class="metric">T · 任务成功</span>${editable('success_T',contract.success_T)}</div><div><span class="metric attack-metric">A · 攻击成功</span>${editable('success_A',contract.success_A)}</div><div><span class="metric">观察证据</span>${editable('observation',contract.observation)}</div></div></section>
    <section class="previews" aria-label="HTML 页面对照"><div class="preview-toolbar"><h2>原始 / 攻击 HTML</h2><div class="segmented">${[['split','并排'],['clean','原始'],['attack','攻击']].map(([key,label])=>`<button data-mode="${key}" aria-pressed="${state.mode===key}">${label}</button>`).join('')}</div></div><div id="frames"></div></section>`;
}
function render(){
  state.visible=state.cases.filter(row=>(!state.domain||row.domain===state.domain)&&(!state.category||row.category===state.category)&&(!state.status||(state.status==='selected'?row.review?.selected:!row.review?.selected))&&(!state.query||`${row.id} ${row.category_title} ${row.v3_contract.scenario} ${row.private_review.field} ${row.host}`.toLowerCase().includes(state.query.toLowerCase())));
  if(!state.visible.some(row=>row.id===state.selected))state.selected=state.visible[0]?.id||'';
  const row=current(),index=state.visible.findIndex(item=>item.id===state.selected);
  const domains=[...new Set(state.labels.categories.map(item=>item.domain))];
  const categories=state.labels.categories.filter(item=>!state.domain||item.domain===state.domain);
  $('#progress').textContent=`${selectedCount()} / ${state.cases.length} 已入选`;
  $('#app').innerHTML=`<section class="toolbar" aria-label="筛选题目">
    <label><span>大类</span><select id="domain">${option('','全部领域',state.domain)}${domains.map(domain=>option(domain,domain,state.domain)).join('')}</select></label>
    <label><span>小类</span><select id="category">${option('','全部题型',state.category)}${categories.map(item=>option(item.key,item.title,state.category)).join('')}</select></label>
    <label><span>题目</span><select id="case-select">${state.visible.map((item,i)=>option(item.id,`${String(i+1).padStart(2,'0')} · ${item.id}`,state.selected)).join('')}</select></label>
    <label class="search-label"><span>查找</span><input id="search" value="${escapeHTML(state.query)}" placeholder="ID、站点或字段"></label>
    <select id="status" aria-label="入选筛选">${option('','全部',state.status)}${option('selected','已入选',state.status)}${option('unselected','未入选',state.status)}</select>
    <a class="export-link" href="/api/contracts/selected-export" target="_blank" rel="noopener">导出入选</a>
    <div class="case-nav"><span>${row?index+1:0} / ${state.visible.length}</span><button class="icon" data-nav="prev" title="上一题" aria-label="上一题" ${index<=0?'disabled':''}>${icon('chevron-left')}</button><button class="icon" data-nav="next" title="下一题" aria-label="下一题" ${index<0||index>=state.visible.length-1?'disabled':''}>${icon('chevron-right')}</button></div>
    ${row?`<label class="selection-control"><input id="select-case" type="checkbox" ${row.review?.selected?'checked':''} ${state.contentWritable?'':'disabled'}><span>选中进入 Benchmark</span></label>`:''}
  </section>${row?caseView(row):'<div class="empty">没有匹配的题目</div>'}`;
  if(row){const url=new URL(location);url.searchParams.set('case',row.id);history.replaceState(null,'',url);renderFrames();}
  icons();
}
function openEditor(node){
  if(!state.contentWritable||state.editing||state.busy)return;
  const key=node.dataset.editField,row=current();if(!row)return;
  const original=String(row.v3_contract[key]||'');state.editing={caseId:row.id,key,original};
  const wrapper=document.createElement('div');wrapper.className='inline-edit';
  const textarea=document.createElement('textarea');textarea.id='inline-text';textarea.value=original;textarea.rows=key==='task'?7:Math.min(5,Math.max(2,original.split('\n').length));textarea.maxLength=key==='task'?12000:4000;textarea.setAttribute('aria-label',`修改${key}`);
  const actions=document.createElement('div');actions.className='inline-edit-actions';actions.innerHTML=`<button data-edit-action="cancel">取消</button><button class="primary" data-edit-action="save">${icon('save')}保存修改</button>`;
  wrapper.append(textarea,actions);node.replaceWith(wrapper);textarea.focus();textarea.select();icons();
}
async function patchContent(change){
  const row=current();if(!row||state.busy)return false;
  state.busy=true;
  try{
    await api(`/api/contracts/cases/${encodeURIComponent(row.id)}/content`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({...change,status:'confirmed',revision:row.content_edit?.revision||0})});
    const data=await api('/api/contracts/catalog');state.cases=data.cases;state.labels=data.label_options;state.contentWritable=data.content_writable;
    const updated=state.cases.find(item=>item.id===row.id);
    if(state.category&&updated?.category!==state.category)state.category='';
    if(state.domain&&updated?.domain!==state.domain)state.domain='';
    state.editing=null;state.busy=false;render();toast('修改已保存');return true;
  }catch(error){state.busy=false;if(!state.editing)render();toast(`保存失败：${error.message}`);return false;}
}
function saveEditor(){
  if(!state.editing||state.busy)return;
  const value=$('#inline-text')?.value.trim();
  if(!value){toast('内容不能为空');return;}
  if(value===state.editing.original){state.editing=null;render();return;}
  patchContent({fields:{[state.editing.key]:value}});
}
async function saveSelection(checked){
  const row=current();if(!row||state.busy)return;
  state.busy=true;
  try{
    const response=await api(`/api/contracts/cases/${encodeURIComponent(row.id)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({selected:checked})});
    row.review=response.review;state.busy=false;
    if(state.status){render();}else{
      $('#progress').textContent=`${selectedCount()} / ${state.cases.length} 已入选`;
      const badge=$('#selection-badge');badge.textContent=checked?'已入选':'未入选';badge.classList.toggle('retain_material',checked);
      $('#select-case').disabled=false;
    }
    toast(checked?'已选中进入 Benchmark':'已取消入选');
  }catch(error){state.busy=false;const checkbox=$('#select-case');if(checkbox){checkbox.checked=!checked;checkbox.disabled=false;}toast(`保存失败：${error.message}`);}
}
document.addEventListener('dblclick',event=>{const node=event.target.closest('[data-edit-field]');if(node)openEditor(node);});
document.addEventListener('keydown',event=>{
  if(event.target.matches('[data-edit-field]')&&event.key==='Enter'){event.preventDefault();openEditor(event.target);}
  if(event.target.id==='inline-text'&&event.key==='Escape'){state.editing=null;render();}
  if(event.target.id==='inline-text'&&event.key==='Enter'&&(event.metaKey||event.ctrlKey)){event.preventDefault();saveEditor();}
});
document.addEventListener('click',event=>{
  const button=event.target.closest('button');if(!button||state.busy)return;
  if(button.dataset.editAction){if(button.dataset.editAction==='save')saveEditor();else{state.editing=null;render();}return;}
  if(button.dataset.mode){state.mode=button.dataset.mode;renderFrames();return;}
  if(button.dataset.nav){if(state.editing){toast('请先保存或取消修改');return;}const index=state.visible.findIndex(item=>item.id===state.selected),next=state.visible[index+(button.dataset.nav==='next'?1:-1)];if(next){state.selected=next.id;render();window.scrollTo({top:0});}}
});
document.addEventListener('change',event=>{
  const node=event.target;
  if(node.id==='select-case'){node.disabled=true;saveSelection(node.checked);return;}
  if(node.dataset.labelField){
    if(state.editing){node.value=node.dataset.labelField==='category'?current().category:current().v3_contract.attack[node.dataset.labelField];toast('请先保存或取消文字修改');return;}
    patchContent({labels:{[node.dataset.labelField]:node.value}});return;
  }
  if(state.editing){node.value={'domain':state.domain,'category':state.category,'status':state.status,'case-select':state.selected}[node.id]??node.value;toast('请先保存或取消文字修改');return;}
  if(node.id==='domain'){state.domain=node.value;state.category='';}
  else if(node.id==='category')state.category=node.value;
  else if(node.id==='status')state.status=node.value;
  else if(node.id==='case-select')state.selected=node.value;
  else return;
  render();
});
let searchTimer;
document.addEventListener('input',event=>{if(event.target.id==='search'&&!state.editing){clearTimeout(searchTimer);const value=event.target.value;searchTimer=setTimeout(()=>{state.query=value;render();$('#search')?.focus();},280);}});
window.addEventListener('beforeunload',event=>{if(state.editing&&$('#inline-text')?.value.trim()!==state.editing.original){event.preventDefault();event.returnValue='';}});
(async()=>{try{const data=await api('/api/contracts/catalog');state.cases=data.cases;state.labels=data.label_options;state.contentWritable=data.content_writable;render();}catch(error){$('#app').innerHTML=`<div class="empty">加载失败：${escapeHTML(error.message)}</div>`;}})();
