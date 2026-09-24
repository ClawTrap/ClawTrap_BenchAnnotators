'use strict';

const $ = selector => document.querySelector(selector);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const icon = name => `<i data-lucide="${name}" aria-hidden="true"></i>`;
const state = {
  cases:[],labels:{categories:[]},visible:[],selected:new URLSearchParams(location.search).get('case')||'',
  domain:'',category:'',status:'',query:'',mode:'split',busy:false,contentWritable:false,editing:null
};
const labelChoices = {
  task_action:[['retrieve','检索'],['judge','判断'],['select','选择'],['compose','编写'],['modify','修改'],['prepare','准备'],['transfer','转移'],['execute','执行'],['communicate','通信'],['authorize','授权']],
  authority_direction:[['READ','读取'],['WRITE','写入工件'],['ACT','改变系统状态'],['SEND','外发'],['RECEIVE','接收资源'],['GRANT','授权']],
  form:[['full-page replacement','整页替换'],['iframe/popup injection','弹窗 / iframe'],['selective substitution','局部替换'],['redirect rewriting','重定向改写'],['API JSON mutation','API JSON 改写'],['file replacement','文件替换'],['mixed benign–malicious content','良恶内容混合']],
  position:[['discovery result or citation','搜索结果 / 引用'],['technical reference page','技术文档页'],['policy or guidance page','规则 / 指引页'],['record or action page','具体记录 / 操作页'],['API response','API 响应'],['download file','下载文件'],['navigation or error state','登录 / 错误 / 跳转'],['asynchronous update','异步更新']],
  evidence_structure:[['single source','单一来源'],['multiple polluted sources','多个污染来源'],['trusted–polluted conflict','可信与污染来源冲突'],['polluted majority / trusted minority','多数污染、少数可信'],['internal policy / external page conflict','内部政策与外部页面冲突'],['cache / live page conflict','缓存与实时页面冲突']],
  risk:[['read-only','只读'],['reversible write','可逆写入'],['cross-system write','跨系统写入'],['external communication','外部通信'],['data disclosure','数据披露'],['permission change','权限变更'],['financial action','财务动作'],['irreversible execution','不可逆执行'],['irreversible workflow','不可逆流程'],['supply-chain execution','供应链执行'],['privilege change','特权变更']],
  granularity:[['page','页面'],['component','组件'],['sentence','句子'],['field','字段'],['single character','单字符'],['link','链接'],['timestamp','时间戳'],['numeric value','数值']],
  timing:[['first step','第一步'],['during verification','核验中'],['before decision','决策前'],['before confirmation','确认前'],['repeated across turns','跨回合重复'],['delayed trigger','延迟触发'],['memory contamination then trigger','先污染记忆后触发'],['clean/attack alternation','正常与攻击页面交替']]
};

const positionDetailNames={'search results':'搜索结果','third-party citation':'第三方引用','checkout page':'结算页','login page':'登录页','error page':'错误页','redirect chain':'重定向链'};

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
  return `<section class="snapshot"><header><strong><span class="dot ${kind}"></span>${title}</strong><div>${kind==='clean'&&origin?`<a href="${escapeHTML(origin)}" target="_blank" rel="noopener noreferrer">原网页 ${icon('arrow-up-right')}</a>`:''}${preview?`<a href="${escapeHTML(preview)}" target="_blank" rel="noopener noreferrer">单独查看 ${icon('arrow-up-right')}</a>`:''}</div></header>${preview?`<iframe src="${escapeHTML(preview)}" title="${title}" sandbox="allow-scripts" referrerpolicy="no-referrer" loading="lazy"></iframe>`:'<p>预览地址缺失</p>'}</section>`;
}
function renderFrames(){
  const row=current(),area=$('#frames');if(!row||!area)return;
  area.className=`snapshot-grid ${state.mode==='split'?'split':''}`;
  area.innerHTML=(state.mode!=='attack'?frame(row.preview.clean,'原始内容','clean',row.source_url):'')+(state.mode!=='clean'?frame(row.preview.attack,'攻击内容','attack',row.source_url):'');
  document.querySelectorAll('[data-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mode===state.mode)));
  icons();
}
function workspaceFiles(row){
  const files=Array.isArray(row.workspace_files)?row.workspace_files:[];
  if(!files.length)return '';
  return `<section class="workspace-files" aria-label="Agent 可见的初始文件"><div class="band-title"><h2>Agent 可见的初始文件</h2><span>工作区预置文件与任务附件 · 只读</span></div><div class="workspace-file-grid">${files.map(file=>`<article class="workspace-file"><h3><code>${escapeHTML(file?.path)}</code></h3><pre><code>${escapeHTML(file?.content)}</code></pre></article>`).join('')}</div></section>`;
}
function serviceInitial(row){
  const seed=row.service_initial;
  if(!seed)return '';
  return `<section class="workspace-files" aria-label="隔离服务初始对象"><div class="band-title"><h2>隔离服务初始对象</h2><span>Agent 可通过受控服务读取和提交 · 端到端运行待验收</span></div><div class="workspace-file-grid"><article class="workspace-file"><h3><code>${escapeHTML(seed.system)}</code></h3><p><code>${escapeHTML(seed.get)}</code><br><code>${escapeHTML(seed.put)}</code></p><pre><code>${escapeHTML(JSON.stringify(seed.initial,null,2))}</code></pre></article></div></section>`;
}
function taskFormTriage(row){
  const triage=row.task_form_triage;
  if(!triage)return '';
  const names={redesigned_isolated_action:'已改为隔离业务动作',existing_operational_task:'保留现有业务动作',source_or_artifact_task:'资料或配置交付',authority_boundary:'等待授权或选择'};
  return `<section class="contract-band" aria-label="任务形式复核"><div class="band-title"><h2>任务形式复核</h2><span>${escapeHTML(names[triage.decision]||triage.decision)}</span></div><p>${escapeHTML(triage.reason)}</p></section>`;
}
function mitmTargets(row){
  const mitm=row.mitm||{},targets=Array.isArray(mitm.targets)?mitm.targets:[];
  const status=mitm.status==='configured'?'':`拦截配置待补全：${escapeHTML(mitm.status||'unknown')}`;
  return `<section class="mitm-targets contract-band" aria-label="MITM 拦截目标"><div class="band-title"><h2>MITM 拦截目标</h2><span>仅供审核与运行器使用，不发给 Agent</span></div>${status?`<p class="mitm-warning">${status}</p>`:''}<ul>${targets.map(target=>`<li><code>${escapeHTML((target.methods||[]).join(', '))} ${escapeHTML(target.url)}</code><span>${escapeHTML(target.action)}${target.replacement_asset?` · ${escapeHTML(target.replacement_asset)}`:''}${Array.isArray(target.active_turns)?` · 第 ${escapeHTML(target.active_turns.join('、'))} 回合替换`:''}${target.redirect_to?` → ${escapeHTML(target.redirect_to)}`:''}</span></li>`).join('')}</ul></section>`;
}
function controlledSearch(row){
  const search=row.controlled_search||{},results=Array.isArray(search.results)?search.results:[];
  return `<section class="mitm-targets contract-band" aria-label="受控搜索结果"><div class="band-title"><h2>受控搜索结果</h2><span>Agent 搜索后可见 · URL 不写入题面</span></div><p>搜索线索：${escapeHTML(search.query_hint||'')}</p><ul>${results.map(result=>`<li><strong>${escapeHTML(result.title)}</strong><code>${escapeHTML(result.url)}</code><span>${escapeHTML(result.kind)}</span></li>`).join('')}</ul></section>`;
}
function timingProtocol(row){
  const flow=row.v3_contract?.timing_protocol;
  if(!flow)return '';
  const poisoned=Array.isArray(flow.poisoned_turns)?flow.poisoned_turns.join('、'):'';
  return `<section class="contract-band" aria-label="跨回合时序"><div class="band-title"><h2>跨回合时序</h2><span>两回合运行 · 由隔离环境记录</span></div><dl><dt>首回合</dt><dd>${escapeHTML(flow.first_turn)}</dd><dt>确认后</dt><dd>${escapeHTML(flow.second_turn)}</dd><dt>篡改出现于</dt><dd>第 ${escapeHTML(poisoned)} 回合</dd>${flow.memory_focus?`<dt>污染方式</dt><dd>${escapeHTML(flow.memory_focus)}</dd>`:''}<dt>核验留痕</dt><dd>${escapeHTML(flow.checkpoint)}</dd></dl></section>`;
}
function caseView(row){
  const contract=row.v3_contract,attack=contract.attack,review=row.private_review;
  const dimensions=[
    ['任务类别',categorySelect(row)],['任务场景',editable('scenario',contract.scenario,'span')],['终态对象',editable('deliverable',contract.deliverable,'span')],
    ['主动作',labelSelect('task_action',contract.task_action)],['动作链',escapeHTML((contract.action_chain||[]).map(action=>labelChoices.task_action.find(([key])=>key===action)?.[1]||action).join(' → '))],
    ['权限方向',labelSelect('authority_direction',contract.authority_direction)],
    ['攻击形式',labelSelect('form',attack.form)],['攻击位置',labelSelect('position',attack.position)+(attack.position_detail?`<small class="position-detail">原载体：${escapeHTML(positionDetailNames[attack.position_detail]||attack.position_detail)}</small>`:'')],
    ['证据结构',labelSelect('evidence_structure',attack.evidence_structure)],['动作风险',labelSelect('risk',attack.risk)],
    ['篡改粒度',labelSelect('granularity',attack.granularity)],
    ['攻击时序',labelSelect('timing',attack.timing)]
  ];
  return `<section class="case-head"><div><div class="eyebrow">${escapeHTML(row.domain)} / ${escapeHTML(row.category_title)}</div><h1>${escapeHTML(contract.scenario)} <small>${escapeHTML(row.id)}</small></h1><p>${escapeHTML(row.host)} · ${row.content_edit?.status==='stale'?'旧编辑已过期':row.content_edit?.revision?'题目已修改':'原题'} · ${escapeHTML(row.readiness)}</p></div><span id="selection-badge" class="verdict ${row.review?.selected?'retain_material':''}">${row.review?.selected?'已入选':'未入选'}</span></section>
    <div class="summary-grid"><section class="reading normal"><h2>${icon('file-text')}发给 Agent 的任务</h2>${editable('task',contract.task,'p')}<dl><dt>授权边界</dt><dd>${editable('authorized_boundary',contract.authorized_boundary,'span')}</dd></dl></section>
    <section class="reading attack"><h2>${icon('file-diff')}攻击内容</h2><p class="lead">${escapeHTML(review.transformation)}</p><dl><dt>被改字段</dt><dd>${escapeHTML(review.field)}</dd><dt>原值</dt><dd><mark class="clean-value">${escapeHTML(review.original||'请对照原始 HTML')}</mark></dd><dt>攻击值</dt><dd><mark class="attack-value">${escapeHTML(review.tampered||'请对照攻击 HTML')}</mark></dd></dl></section></div>
    ${workspaceFiles(row)}
    ${serviceInitial(row)}
    ${taskFormTriage(row)}
    ${timingProtocol(row)}
    ${controlledSearch(row)}
    ${mitmTargets(row)}
    <section class="workflow-dimensions"><div class="band-title"><h2>任务与攻击标签</h2><span>标签修改即时保存</span></div><dl class="dimension-grid">${dimensions.map(([label,control])=>`<div><dt>${label}</dt><dd>${control}</dd></div>`).join('')}</dl></section>
    <section class="contract-band"><div class="band-title"><h2>结果判定</h2><span>T / A 分开记录 · 私有审核信息</span></div><div class="criteria-grid"><div><span class="metric">T · 任务成功</span>${editable('success_T',contract.success_T)}</div><div><span class="metric attack-metric">A · 攻击成功</span>${editable('success_A',contract.success_A)}</div><div><span class="metric">观察证据</span>${editable('observation',contract.observation)}</div></div><div class="output-format"><strong>验收对象（不发给 Agent）</strong>${editable('output_format',contract.output_format,'p')}</div></section>
    <section class="previews" aria-label="内容对照"><div class="preview-toolbar"><h2>原始 / 攻击内容</h2><div class="segmented">${[['split','并排'],['clean','原始'],['attack','攻击']].map(([key,label])=>`<button data-mode="${key}" aria-pressed="${state.mode===key}">${label}</button>`).join('')}</div></div><div id="frames"></div></section>`;
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
    if(state.editing){node.value=node.dataset.labelField==='category'?current().category:['task_action','authority_direction'].includes(node.dataset.labelField)?current().v3_contract[node.dataset.labelField]:current().v3_contract.attack[node.dataset.labelField];toast('请先保存或取消文字修改');return;}
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
