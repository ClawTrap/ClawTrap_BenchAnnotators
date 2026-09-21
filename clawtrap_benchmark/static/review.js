'use strict';
const $ = (s, root=document) => root.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = name => `<i data-lucide="${name}" aria-hidden="true"></i>`;
const labels = {accepted:'已保留', discarded:'已排除', needs_discussion:'待讨论', '':'未审核'};
const issues = {title_only:'仅换标题', no_downstream:'下游动作不足', template_repeat:'模板重复', source_repeat:'来源重复', wrong_scenario:'偏离自身类别', weak_causality:'攻击因果不清', obvious_clue:'攻击线索过强', render_problem:'快照渲染异常', unclear_evaluation:'判定依据不清'};
const params = new URLSearchParams(location.search);
const state = {rows:[], visible:[], domain:'', scenario:'', status:'', search:'',
  cohort:null, selected:params.get('case') || '', tab:'intent', preview:'split',
  view:document.body.dataset.view, compare:new Set(), details:new Map(),
  drafts:new Map(), busy:false, request:0, asset:0};
const readonly = params.get('mode') === 'view';
const draftKey = id => `clawtrap-design-review:${document.body.dataset.user}:${id}`;
function icons() { window.lucide?.createIcons(); }
async function api(url, options) {
  const response = await fetch(url, options);
  if (response.status === 401) { location.assign('/login'); throw new Error('登录已失效'); }
  let value;
  try { value = await response.json(); } catch { throw new Error(`服务暂不可用（HTTP ${response.status}）`); }
  if (!response.ok) throw new Error(value.error || '请求失败');
  return value;
}
function toast(message) { $('#toast').textContent=message; $('#toast').classList.add('show'); clearTimeout(toast.timer); toast.timer=setTimeout(()=>$('#toast').classList.remove('show'), 3200); }
function fail(error) { const node=$('#app-error'); node.hidden=false; node.innerHTML=`${icon('circle-alert')}<span>${esc(error.message)}</span><button data-action="retry">重试加载</button>`; icons(); }
function url(value) {
  if (!value) return '';
  try { const u=new URL(value,location.origin); return ['http:','https:'].includes(u.protocol)?u.href:''; } catch { return ''; }
}
function link(value,label) { const safe=url(value); return safe?`<a href="${esc(safe)}" target="_blank" rel="noopener noreferrer">${esc(label)}${icon('arrow-up-right')}</a>`:''; }
function counts(rows, key) { const map=new Map(); rows.forEach(r=>{const k=r[key]||'未记录'; map.set(k,(map.get(k)||0)+1);}); return [...map].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])); }
function options(items,current,placeholder) { return `<option value="">${placeholder}</option>`+items.map(([value,name])=>`<option value="${esc(value)}" ${value===current?'selected':''}>${esc(name)}</option>`).join(''); }
function badge(row) { return `<span class="status ${esc(row.decision || 'pending')}"><span></span>${labels[row.decision]||'未审核'}</span>`; }
function displayTitle(r) { return r.title || r.id; }
function filtered() {
  const query=state.search.trim().toLowerCase();
  return state.rows.filter(r=>(state.view!=='benchmark'||r.selected) && (!state.domain||r.domain===state.domain) &&
    (!state.scenario||r.scenario_key===state.scenario) && (!state.status||(state.status==='pending'?!r.decision:r.decision===state.status)) &&
    (!state.cohort||r[state.cohort.key]===state.cohort.value) &&
    (!query||[r.title,r.id,r.task,r.field,r.scenario_key,r.host,r.original,r.changed].join(' ').toLowerCase().includes(query)));
}
function filterBar() {
  const domainItems=[...new Map(state.rows.map(r=>[r.domain,r.domain_title])).entries()];
  const scenarioRows=state.rows.filter(r=>!state.domain||r.domain===state.domain);
  const scenarioItems=[...new Map(scenarioRows.map(r=>[r.scenario_key,r.scenario_title])).entries()];
  return `<section class="filterbar" aria-label="筛选题目">
    <label class="search">${icon('search')}<input id="search" placeholder="搜索题目、标签或改动值" value="${esc(state.search)}" aria-label="搜索题目"></label>
    <label><span>领域</span><select id="domain">${options(domainItems,state.domain,'全部领域')}</select></label>
    <label class="scenario-filter"><span>自身类别</span><select id="scenario">${options(scenarioItems,state.scenario,'全部类别')}</select></label>
    <label><span>结论</span><select id="status">${options(Object.entries(labels).filter(([k])=>k).map(([k,v])=>[k,v]).concat([['pending','未审核']]),state.status,'全部状态')}</select></label>
    <button class="icon" data-action="reset" title="清除筛选" aria-label="清除筛选">${icon('filter-x')}</button>
  </section>`;
}
function shell() {
  $('#app').innerHTML=`${filterBar()}<div id="cohort"></div><div id="workspace"></div>`;
  $('#search').addEventListener('input',e=>{state.search=e.target.value; refresh();});
  for (const field of ['domain','scenario','status']) $(`#${field}`).addEventListener('change',e=>{
    state[field]=e.target.value; if(field==='domain'){state.scenario=''; const focused=field; shell(); $(`#${focused}`)?.focus();} refresh();
  });
  refresh();
}
function refresh() {
  state.visible=filtered();
  $('#cohort').innerHTML=state.cohort?`<div class="cohort">${icon('list-filter')}<span>${esc(state.cohort.label)} · ${esc(state.cohort.value)} · ${state.visible.length} 题</span><button class="icon" data-action="clear-cohort" aria-label="清除聚类筛选">${icon('x')}</button></div>`:'';
  if(state.view==='review') renderReview(); else renderOverview();
  icons();
}
function renderReview() {
  const queueScroll = {top:$('.queue-items')?.scrollTop||0,left:$('.queue-items')?.scrollLeft||0};
  if(!state.visible.some(r=>r.id===state.selected)) {state.selected=state.visible[0]?.id||''; state.asset=0;}
  const r=state.visible.find(r=>r.id===state.selected);
  $('#workspace').className='review-layout';
  $('#workspace').innerHTML=`<aside class="case-queue"><div class="queue-heading"><strong>审核队列</strong><span>${state.visible.length} / ${state.rows.length}</span></div>
    <div class="queue-items">${state.visible.map((item,i)=>`<button class="queue-item ${item.id===state.selected?'active':''}" data-case="${esc(item.id)}" aria-current="${item.id===state.selected?'true':'false'}"><span class="queue-index">${String(i+1).padStart(2,'0')}</span><span class="queue-text"><strong>${esc(displayTitle(item))}</strong><small>${esc(item.host)}</small>${badge(item)}</span></button>`).join('')||'<p class="empty">没有匹配的题目</p>'}</div></aside>
    <section class="case-main" id="case-main">${r?mainCase(r):'<div class="empty"><h2>当前筛选下没有题目</h2><button data-action="reset">清除筛选</button></div>'}</section>
    ${r?judgment(r):''}`;
  const queue=$('.queue-items');if(queue){queue.scrollTop=queueScroll.top;queue.scrollLeft=queueScroll.left;}
  if(r) {
    const u=new URL(location);u.searchParams.set('case',r.id);u.searchParams.set('dataset',r.dataset);history.replaceState(null,'',u);
    loadDetails(r);
  }
}
function mainCase(r) {
  const index=state.visible.findIndex(x=>x.id===r.id);
  return `<div class="case-heading"><div><div class="eyebrow">${esc(r.domain_title)}</div><h1>${esc(r.scenario_title)}</h1><code class="case-id">${esc(r.id)}</code></div>
    <div class="case-nav"><span>${index+1} / ${state.visible.length}</span><button class="icon" data-action="prev" title="上一题" aria-label="上一题" ${state.visible.length<2?'disabled':''}>${icon('chevron-left')}</button><button class="icon" data-action="next" title="下一题" aria-label="下一题" ${state.visible.length<2?'disabled':''}>${icon('chevron-right')}</button></div></div>
    <div class="own-label"><span>原始类别标签</span><code>${esc(r.declared_workflow)}</code></div>
    <nav class="tabs" aria-label="题目内容">${[['intent','设计核对'],['snapshot','页面对照'],['materials','题面与判定'],['peers','同类比较']].map(([k,v])=>`<button data-tab="${k}" class="${state.tab===k?'active':''}" aria-pressed="${state.tab===k}">${v}</button>`).join('')}</nav>
    <div class="case-content" id="case-content">${tabContent(r)}</div>`;
}
function tabContent(r) {
  if(state.tab==='snapshot') return snapshot(r);
  if(state.tab==='materials') return materials(r);
  if(state.tab==='peers') return peers(r);
  const guide=r.guide;
  return `<section class="intent-section"><div class="section-label"><span class="step">01</span><h2>这一类别应当测什么</h2></div>
    <p class="lead">${esc(guide?.action || r.target)}</p>
    ${guide?`<dl class="inline-facts"><dt>设计中的攻击对象</dt><dd>${esc(guide.fields)}</dd></dl>`:''}
    <div class="prompt-question">这道题的任务和攻击，是否真实围绕 <strong>${esc(r.declared_workflow)}</strong> 展开？</div></section>
    <section class="intent-section"><div class="section-label"><span class="step">02</span><h2>这道题实际做了什么</h2></div>
      <h3>用户任务</h3><p class="preserve">${esc(r.task)}</p>
      <h3>攻击变化</h3>${factPair(r)}
      <p class="muted preserve">${esc(r.transformation)}</p>
      ${r.timing?`<dl class="inline-facts"><dt>触发时点</dt><dd>${esc(r.timing)}</dd></dl>`:''}
      <button class="text-action" data-tab="snapshot">查看原始与攻击页面 ${icon('arrow-right')}</button>
    </section>
    <section class="intent-section"><div class="section-label"><span class="step">03</span><h2>预期结果与实际判定</h2></div>
      <p class="preserve">${esc(r.target)}</p>${outcomes(r)}
      <details><summary>出题逻辑</summary><p class="preserve">${esc(r.logic)}</p></details>
    </section>
    <section class="intent-section"><div class="section-label"><span class="step">04</span><h2>同类中的独特性</h2></div>
      ${r.flags.map(f=>`<p class="observation">${icon('search-check')}<span>${esc(f)}</span></p>`).join('')}
      <div class="peer-summary">${peerStats(r)}</div>
      <button class="text-action" data-tab="peers">比较同类题目 ${icon('arrow-right')}</button>
    </section>`;
}
function factPair(r) {
  if(!r.original&&!r.changed) return `<p class="preserve">${esc(r.transformation)}</p>`;
  return `<div class="fact-pair"><div><span class="fact-label"><span class="dot clean"></span>原始值</span><p>${esc(r.original||'未单独声明')}</p></div><div><span class="fact-label"><span class="dot attack"></span>攻击值</span><p>${esc(r.changed||'未单独声明')}</p></div></div>`;
}
function outcomes(r) { return Object.keys(r.outcomes).length?`<dl class="outcomes">${Object.entries(r.outcomes).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`:'<p class="muted">具体成功 / 失败标准见题面与判定。</p>'; }
function snapshot(r) {
  const assets=r.assets||[];state.asset=Math.min(state.asset,Math.max(assets.length-1,0));const asset=assets[state.asset];
  if(!asset) return '<div class="empty">此题没有登记可预览资产。</div>';
  const before=asset.before_url||(asset.url||'').replace('/attack-assets/','/clean-assets/');
  const frame=(src,title,kind)=>`<section class="snapshot-pane"><header><strong><span class="dot ${kind}"></span>${title}</strong>${link(src,'独立打开')}</header>${url(src)?`<iframe src="${esc(url(src))}" sandbox="allow-scripts" title="${title}" loading="lazy" referrerpolicy="no-referrer"></iframe>`:'<p class="empty">缺少快照地址</p>'}</section>`;
  return `<div class="snapshot-tools"><select id="asset" aria-label="页面资产">${assets.map((a,i)=>`<option value="${i}" ${i===state.asset?'selected':''}>${esc(a.title||'页面 '+(i+1))}</option>`).join('')}</select>
    <div class="segmented">${[['split','并排'],['clean','原始'],['attack','攻击']].map(([k,v])=>`<button data-preview="${k}" class="${state.preview===k?'active':''}" aria-pressed="${state.preview===k}">${v}</button>`).join('')}</div></div>
    <div class="source-links">${(r.source_urls.length?r.source_urls:[{url:r.source,label:'原网页'}]).slice(0,5).map(s=>link(s.url,s.label||'原网页')).join('')}</div>
    <details class="change-summary"><summary>改动值与攻击说明</summary>${factPair(r)}<p>${esc(r.transformation)}</p></details>
    <div class="snapshot-grid ${state.preview==='split'?'split':''}">${state.preview!=='attack'?frame(before,'原始快照','clean'):''}${state.preview!=='clean'?frame(asset.url,'攻击快照','attack'):''}</div>`;
}
async function loadDetails(r) {
  if(state.details.has(r.id)) return;
  const request=++state.request;
  try {
    const data=await api(`/api/review/cases/${encodeURIComponent(r.id)}`);state.details.set(r.id,data.case);
    if(state.selected===r.id&&state.tab==='materials'&&request===state.request) {$('#case-content').innerHTML=materials(r);icons();}
  } catch(e) { if(state.selected===r.id) toast(e.message); }
}
function materialList(title,items) { return `<section class="intent-section"><h2>${title}</h2><ul class="text-list">${(items||[]).map(s=>`<li>${esc(s)}</li>`).join('')||'<li>未记录</li>'}</ul></section>`; }
function materials(r) {
  const c=state.details.get(r.id);if(!c)return '<p class="loading">正在读取题目材料…</p>';
  return `<section class="intent-section"><h2>完整题面</h2><p class="preserve">${esc(c.task)}</p><h3>任务目标</h3><p class="preserve">${esc(c.target)}</p></section>
    <section class="intent-section"><h2>题面引用文件</h2>${(c.task_file_previews||[]).map(p=>`<details open><summary><code>${esc(p.key)}</code></summary><p>${esc(p.description)}</p>${p.error?`<p class="alert">${esc(p.error)}</p>`:`<pre>${esc(p.text)}</pre>`}</details>`).join('')||'<p>无引用文件</p>'}</section>
    ${materialList('防御成功状态',c.success_states)}${materialList('防御失败状态',c.failure_states)}${materialList('评分依据',c.graders)}
    <section class="intent-section"><details><summary>原始题目 JSON</summary><pre>${esc(JSON.stringify(c,null,2))}</pre></details></section>`;
}
function peerStats(r) {
  const same=state.rows.filter(x=>x.scenario_key===r.scenario_key);
  return `<span><strong>${same.length}</strong> 同类别</span><span><strong>${same.filter(x=>x.pattern===r.pattern).length}</strong> 同改动模式</span><span><strong>${same.filter(x=>x.source&&x.source===r.source).length}</strong> 同来源页</span>`;
}
function peers(r) {
  const rows=state.rows.filter(x=>x.scenario_key===r.scenario_key);
  return `<div class="section-top"><h2>同类别 · ${rows.length} 题</h2><button data-action="compare" ${state.compare.size<2?'disabled':''}>${icon('columns-3')}对照 (${state.compare.size}/3)</button></div>
    <div class="peer-summary">${peerStats(r)}</div>${caseTable(rows)}`;
}
function draftFor(r) {
  if(state.drafts.has(r.id)) return state.drafts.get(r.id);
  try { const stored=JSON.parse(sessionStorage.getItem(draftKey(r.id)));if(stored){state.drafts.set(r.id,stored);return stored;} } catch {}
  return r.assessment||{};
}
function judgment(r) {
  const value=draftFor(r), check=value.checks||{};
  const questions=[['intent','符合自身类别','任务与攻击是否围绕该 workflow 标签？'],['causality','攻击能改变结果','被篡改的信息是否影响任务决定或安全边界？'],['realism','内容与页面可信','情境是否自然，快照是否可正常审核？'],['diversity','同类中有区分度','是否存在实质变化，而不只是换实体或标题？']];
  return `<aside class="judgment"><div class="judgment-head"><h2>审核判断</h2>${badge(r)}</div><form id="assessment">
    <fieldset ${readonly?'disabled':''}>${questions.map(([key,title,question],i)=>`<div class="check-row"><label for="check-${key}"><span class="check-no">${i+1}</span>${title}</label><p>${question}</p><select id="check-${key}" name="${key}" aria-label="${title}">${options([['pass','符合'],['question','存疑'],['fail','不符合']],check[key]||'','未判断')}</select></div>`).join('')}
    <details class="issue-picker" ${(value.issues||[]).length?'open':''}><summary>问题标签 <span>${(value.issues||[]).length||''}</span></summary>${Object.entries(issues).map(([key,label])=>`<label><input type="checkbox" name="issue" value="${key}" ${(value.issues||[]).includes(key)?'checked':''}>${label}</label>`).join('')}</details>
    <label class="notes-label" for="notes">审核备注</label><textarea id="notes" name="notes" rows="4" maxlength="12000" placeholder="记录具体偏离点、重复题目或需修改之处">${esc(value.notes ?? r.comment ?? '')}</textarea>
    </fieldset></form>
    <div class="save-state" id="save-state">${state.drafts.has(r.id)?'有未保存的审核意见':value.updated_at?'已保存 · '+esc(value.reviewer||''): '尚无审核意见'}</div>
    ${readonly?'<p class="muted">只读查看</p>':`<div class="judgment-actions"><button data-action="save" ${state.busy?'disabled':''}>${icon('save')}保存意见</button><button class="primary" data-decision="accepted" ${state.busy?'disabled':''}>${icon('check')}保留并下一题</button><div class="decision-pair"><button data-decision="needs_discussion" ${state.busy?'disabled':''}>${icon('message-circle')}待讨论</button><button data-decision="discarded" ${state.busy?'disabled':''}>${icon('x')}排除</button></div>${r.decision?'<button class="text-action" data-decision="clear">撤销结论</button>':''}</div>`}</aside>`;
}
function capture() {
  const form=$('#assessment');if(!form||readonly)return;
  const data=new FormData(form), assessment={checks:{},issues:data.getAll('issue'),notes:data.get('notes')||''};
  ['intent','causality','realism','diversity'].forEach(k=>assessment.checks[k]=data.get(k)||'');
  state.drafts.set(state.selected,assessment);try{sessionStorage.setItem(draftKey(state.selected),JSON.stringify(assessment));}catch{}
  $('#save-state').textContent='有未保存的审核意见';
}
async function save(decision) {
  if(state.busy||readonly)return;capture();const id=state.selected;const r=state.rows.find(x=>x.id===id);if(!r)return;
  state.busy=true;document.querySelectorAll('.judgment-actions button').forEach(b=>b.disabled=true);
  try {
    const result=await api(`/api/review/cases/${encodeURIComponent(id)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({assessment:state.drafts.get(id), ...(decision?{decision}:{})})});
    Object.assign(r,result);state.drafts.delete(id);sessionStorage.removeItem(draftKey(id));state.details.delete(id);
    if(decision&&decision!=='clear'){const i=state.visible.findIndex(x=>x.id===id);state.selected=state.visible[(i+1)%state.visible.length]?.id||id;state.asset=0;}
    state.busy=false;refresh();if(decision&&decision!=='clear')window.scrollTo({top:0});toast(decision?'审核结论已保存':'审核意见已保存');
  } catch(e) {state.busy=false;document.querySelectorAll('.judgment-actions button').forEach(b=>b.disabled=false);toast('保存失败：'+e.message);}
}
function metric(value,label,extra='') {return `<div class="metric"><strong>${value}</strong><span>${label}</span>${extra?`<small>${esc(extra)}</small>`:''}</div>`;}
function distribution(key,title,rows) {
  const data=counts(rows,key).slice(0,8),max=data[0]?.[1]||1;
  return `<section class="distribution"><h2>${title}</h2>${data.map(([value,count])=>`<button class="bar-row" data-cohort-key="${key}" data-cohort-value="${esc(value)}" data-cohort-label="${title}"><span>${esc(value)}</span><div class="bar-track"><div style="width:${Math.round(count/max*100)}%"></div></div><strong>${count}</strong></button>`).join('')||'<p class="muted">无数据</p>'}</section>`;
}
function renderOverview() {
  const rows=state.visible, selected=rows.filter(r=>r.selected).length, patterns=counts(rows,'pattern'),sources=counts(rows,'host');
  const largest=patterns[0], reviewed=rows.filter(r=>r.decision).length;
  $('#workspace').className='overview';
  $('#workspace').innerHTML=`<div class="overview-heading"><div><div class="eyebrow">CORPUS REVIEW</div><h1>${state.view==='benchmark'?'入选集合':'多样性总览'}</h1><p>${state.view==='benchmark'?'已保留题目的分布与审核记录':'按题目自身类别，检查来源、改动模式与任务模板的集中程度'}</p></div><button data-action="export">${icon('download')}导出审核记录</button></div>
    <section class="metrics">${metric(rows.length,'当前题目',state.rows.length+' 题总量')}${metric(new Set(rows.map(r=>r.scenario_key)).size,'自身类别')}${metric(new Set(rows.map(r=>r.host)).size,'来源网站')}${metric(largest?Math.round(largest[1]/Math.max(rows.length,1)*100)+'%':'—','最大改动模式占比',largest?.[0]||'')}${metric(reviewed,'已审核',selected+' 题保留')}</section>
    <div class="distribution-grid">${distribution('pattern','改动模式',rows)}${distribution('host','来源网站',rows)}</div>
    <section class="coverage"><div class="section-top"><h2>类别覆盖与集中度</h2><span class="muted">统计提示，不作自动质量判定</span></div><div class="table-scroll"><table><thead><tr><th>自身类别 / workflow</th><th>题目</th><th>来源网站</th><th>最大模式占比</th><th>已审核</th></tr></thead><tbody>${counts(rows,'scenario_key').map(([key,count])=>{
      const subset=rows.filter(r=>r.scenario_key===key),dominant=counts(subset,'pattern')[0];
      return `<tr><td><button class="table-link" data-cohort-key="scenario_key" data-cohort-value="${esc(key)}" data-cohort-label="自身类别">${esc(subset[0].scenario_title)}</button><code>${esc(key)}</code></td><td>${count}</td><td>${new Set(subset.map(r=>r.host)).size}</td><td><span class="concentration">${Math.round(dominant[1]/count*100)}%</span><small>${esc(dominant[0])}</small></td><td>${subset.filter(r=>r.decision).length} / ${count}</td></tr>`;
    }).join('')}</tbody></table></div></section>
    <details class="template-groups"><summary>重复任务模板候选 · ${counts(rows,'task_pattern').filter(([,n])=>n>1).length} 组</summary><p class="muted">按题面文本归一化分组：仅替换 URL、反引号内容、引用 key 和数字；不代表语义重复结论。</p>${counts(rows,'task_pattern').filter(([,n])=>n>1).slice(0,20).map(([value,n])=>`<button class="template-row" data-cohort-key="task_pattern" data-cohort-value="${esc(value)}" data-cohort-label="任务模板"><strong>${n} 题</strong><span>${esc(value)}</span>${icon('arrow-right')}</button>`).join('')}</details>
    <section class="case-browser"><div class="section-top"><h2>题目明细 <span class="muted">${rows.length}</span></h2><button data-action="compare" ${state.compare.size<2?'disabled':''}>${icon('columns-3')}对照 (${state.compare.size}/3)</button></div>${caseTable(rows)}</section>`;
}
function caseTable(rows) {
  return `<div class="table-scroll"><table class="case-table"><thead><tr><th>对照</th><th>题目 / 自身类别</th><th>来源与模式</th><th>被改动值</th><th>结论</th></tr></thead><tbody>${rows.map(r=>`<tr><td><input type="checkbox" data-compare="${esc(r.id)}" aria-label="加入对照 ${esc(r.id)}" ${state.compare.has(r.id)?'checked':''}></td><td><button class="table-link" data-case="${esc(r.id)}">${esc(displayTitle(r))}</button><code>${esc(r.scenario_key)}</code><small>${esc(r.id)}</small></td><td>${esc(r.host)}<small>${esc(r.pattern)}</small></td><td><div class="table-original">${esc(r.original||r.field)}</div><div class="table-changed">${esc(r.changed||'见攻击说明')}</div></td><td>${badge(r)}</td></tr>`).join('')||'<tr><td colspan="5">没有匹配的题目</td></tr>'}</tbody></table></div>`;
}
function compare() {
  const rows=state.rows.filter(r=>state.compare.has(r.id));if(rows.length<2)return;
  $('#comparison').innerHTML=`<div class="compare-grid" style="--columns:${rows.length}">${rows.map(r=>`<article><h2>${esc(displayTitle(r))}</h2><code>${esc(r.id)}</code><h3>自身类别</h3><p>${esc(r.scenario_key)}</p><h3>用户任务</h3><p>${esc(r.task)}</p><h3>原始值 → 攻击值</h3>${factPair(r)}<h3>攻击变化</h3><p>${esc(r.transformation)}</p><h3>判定目标</h3><p>${esc(r.target)}</p><h3>来源与模式</h3><p>${esc(r.host)} · ${esc(r.pattern)}</p><button data-case="${esc(r.id)}">打开审核 ${icon('arrow-right')}</button></article>`).join('')}</div>`;
  $('#compare-dialog').showModal();icons();
}
function select(id) {
  if(state.busy)return;
  if(state.view!=='review'){location.assign(`/review?case=${encodeURIComponent(id)}`);return;}
  state.selected=id;state.asset=0;renderReview();icons();$('.queue-item.active')?.scrollIntoView({block:'nearest',inline:'nearest'});window.scrollTo({top:0});
}
function exportRecords() {
  const data={exported_at:new Date().toISOString(),release:state.release,case_count:state.visible.length,
    records:state.visible.map(r=>({id:r.id,dataset:r.dataset,domain:r.domain,workflow:r.scenario_key,decision:r.decision,assessment:r.assessment}))};
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),href=URL.createObjectURL(blob),a=document.createElement('a');
  a.href=href;a.download='clawtrap-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(href),1000);
}
document.addEventListener('input',e=>{if(e.target.closest('#assessment'))capture();});
document.addEventListener('change',e=>{
  if(e.target.matches('[data-compare]')){const id=e.target.dataset.compare;if(e.target.checked){if(state.compare.size>=3){e.target.checked=false;toast('最多同时对照 3 题');return;}state.compare.add(id);}else state.compare.delete(id);if(state.view==='review'){$('#case-content').innerHTML=peers(state.rows.find(r=>r.id===state.selected));icons();}else refresh();}
  if(e.target.id==='asset'){state.asset=Number(e.target.value);$('#case-content').innerHTML=snapshot(state.rows.find(r=>r.id===state.selected));icons();}
});
document.addEventListener('click',e=>{
  const node=e.target.closest('button');if(!node)return;
  if(node.dataset.case){$('#compare-dialog').close();select(node.dataset.case);return;}
  if(node.dataset.tab){state.tab=node.dataset.tab;renderReview();icons();return;}
  if(node.dataset.preview){state.preview=node.dataset.preview;$('#case-content').innerHTML=snapshot(state.rows.find(r=>r.id===state.selected));icons();return;}
  if(node.dataset.decision){save(node.dataset.decision);return;}
  if(node.dataset.cohortKey){state.cohort={key:node.dataset.cohortKey,value:node.dataset.cohortValue,label:node.dataset.cohortLabel};refresh();window.scrollTo({top:0});return;}
  const action=node.dataset.action;
  if(action==='save')save();
  if(action==='compare')compare();
  if(action==='close-compare')$('#compare-dialog').close();
  if(action==='clear-cohort'){state.cohort=null;refresh();}
  if(action==='reset'){Object.assign(state,{domain:'',scenario:'',status:'',search:'',cohort:null});shell();}
  if(action==='export')exportRecords();
  if(action==='retry')location.reload();
  if(action==='next'||action==='prev'){const i=state.visible.findIndex(r=>r.id===state.selected),n=state.visible.length;if(n)select(state.visible[(i+(action==='next'?1:-1)+n)%n].id);}
});
window.addEventListener('beforeunload',e=>{if(state.drafts.size){e.preventDefault();e.returnValue='';}});
async function init() {
  try {
    const data=await api('/api/review/catalog');state.rows=data.cases;state.release=data.release;
    const dataset=params.get('dataset');if(dataset&&!state.selected){const r=state.rows.find(r=>r.dataset===dataset||r.group===dataset);if(r)state.scenario=r.scenario_key;}
    shell();
  } catch(e){$('#app').innerHTML='<div class="empty">题目加载失败</div>';fail(e);}
}
init();
