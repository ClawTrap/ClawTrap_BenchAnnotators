'use strict';

const $ = selector => document.querySelector(selector);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const state = {rows:[],domain:'',scope:'all'};
const label = {task_action:'主动作',authority_direction:'权限方向',form:'攻击形式',position:'攻击位置',evidence_structure:'证据结构',risk:'动作风险',granularity:'篡改粒度',timing:'攻击时序'};
const actionNames = {retrieve:'检索',judge:'判断',select:'选择',compose:'编写',modify:'修改',prepare:'准备',transfer:'转移',execute:'执行',communicate:'通信',authorize:'授权'};
const formNames = {'full-page replacement':'整页替换','iframe/popup injection':'弹窗 / iframe','selective substitution':'局部替换','mixed benign–malicious content':'良恶内容混合','redirect rewriting':'重定向改写','API JSON mutation':'API JSON 改写','file replacement':'文件替换'};
const positionNames = {'discovery result or citation':'搜索结果 / 引用','technical reference page':'技术文档页','policy or guidance page':'规则 / 指引页','record or action page':'具体记录 / 操作页','API response':'API 响应','download file':'下载文件','navigation or error state':'登录 / 错误 / 跳转','asynchronous update':'异步更新'};
const riskNames = {'read-only':'只读','reversible write':'可逆写入','cross-system write':'跨系统写入','external communication':'外部通信','data disclosure':'数据披露','permission change':'权限变更','financial action':'财务动作','irreversible execution':'不可逆执行'};
const granularityNames = {page:'页面',component:'组件',sentence:'句子',field:'字段','single character':'单字符',link:'链接',timestamp:'时间戳','numeric value':'数值'};
const timingNames = {'first step':'第一步','during verification':'核验中','before decision':'决策前','before confirmation':'确认前','repeated across turns':'跨回合重复','delayed trigger':'延迟触发','memory contamination then trigger':'先污染记忆后触发','clean/attack alternation':'正常与攻击页面交替'};

function count(rows,key){const result=new Map();for(const row of rows){const value=key(row);result.set(value,(result.get(value)||0)+1);}return [...result].sort((a,b)=>b[1]-a[1]||String(a[0]).localeCompare(String(b[0])));}
function pct(part,total){return total?`${(part*100/total).toFixed(1)}%`:'0%';}
function option(value,text,current){return `<option value="${escapeHTML(value)}" ${value===current?'selected':''}>${escapeHTML(text)}</option>`;}
function metric(number,title,detail=''){return `<div class="report-metric"><strong>${escapeHTML(number)}</strong><span>${title}</span>${detail?`<small>${escapeHTML(detail)}</small>`:''}</div>`;}
function bars(rows,field,names={},limit=12){
  const values=count(rows,row=>field==='task_action'||field==='authority_direction'?row.v3_contract[field]:row.v3_contract.attack[field]);
  const visible=values.slice(0,limit),other=values.slice(limit);
  if(other.length)visible.push([`其他 ${other.length} 种标签`,other.reduce((sum,[,n])=>sum+n,0)]);
  return `<section class="report-band"><div class="section-heading"><h2>${label[field]}</h2><span>${values.length} 种标签</span></div><div class="bars">${visible.map(([key,n])=>`<div class="bar-row"><span title="${escapeHTML(key)}">${escapeHTML(names[key]||key)}</span><div class="bar-track"><i style="width:${pct(n,rows.length)}"></i></div><strong>${n}</strong><small>${pct(n,rows.length)}</small></div>`).join('')}</div></section>`;
}
function categoryTable(rows){
  const groups=count(rows,row=>row.category),byKey=new Map([...rows].reverse().map(row=>[row.category,row]));
  return `<section class="report-band"><div class="section-heading"><h2>${groups.length} 类场景覆盖</h2><span>按当前题目标签统计</span></div><div class="report-table-scroll"><table><thead><tr><th>类别</th><th>题目</th><th>来源网站</th><th>主动作分布</th><th>最多的攻击形式</th><th>最常见攻击位置</th><th>已入选</th></tr></thead><tbody>${groups.sort((a,b)=>byKey.get(a[0]).category_number-byKey.get(b[0]).category_number).map(([key,n])=>{
    const related=rows.filter(row=>row.category===key),first=byKey.get(key),forms=count(related,row=>row.v3_contract.attack.form),actions=count(related,row=>row.v3_contract.task_action),positions=count(related,row=>row.v3_contract.attack.position);
    return `<tr><td><a href="/contract-review?case=${encodeURIComponent(first.id)}">${first.category_number}. ${escapeHTML(first.category_title)}</a><small>${escapeHTML(first.domain)}</small></td><td>${n}</td><td>${new Set(related.map(row=>row.host)).size}</td><td>${actions.length} 种 · ${escapeHTML(actionNames[actions[0]?.[0]]||actions[0]?.[0]||'—')} ${pct(actions[0]?.[1]||0,n)}</td><td>${escapeHTML(formNames[forms[0]?.[0]]||forms[0]?.[0]||'—')} · ${pct(forms[0]?.[1]||0,n)}</td><td>${escapeHTML(positionNames[positions[0]?.[0]]||positions[0]?.[0]||'—')} · ${pct(positions[0]?.[1]||0,n)}</td><td>${related.filter(row=>row.review?.selected).length}</td></tr>`;
  }).join('')}</tbody></table></div></section>`;
}
function sourceTable(rows){
  const sites=count(rows,row=>row.host||'未知');
  return `<section class="report-band"><div class="section-heading"><h2>来源网站集中度</h2><span>前 15 个站点 · 共 ${sites.length} 个站点</span></div><div class="report-table-scroll"><table><thead><tr><th>站点</th><th>题目数</th><th>占比</th><th>涉及类别</th></tr></thead><tbody>${sites.slice(0,15).map(([host,n])=>`<tr><td>${escapeHTML(host)}</td><td>${n}</td><td>${pct(n,rows.length)}</td><td>${new Set(rows.filter(row=>row.host===host).map(row=>row.category)).size}</td></tr>`).join('')}</tbody></table></div></section>`;
}
function render(){
  const all=state.rows,rows=all.filter(row=>(!state.domain||row.domain===state.domain)&&(state.scope==='all'||row.review?.selected));
  const domains=[...new Set(all.map(row=>row.domain))];
  const forms=count(rows,row=>row.v3_contract.attack.form),positions=count(rows,row=>row.v3_contract.attack.position),actions=count(rows,row=>row.v3_contract.task_action);
  $('#progress').textContent=`${all.filter(row=>row.review?.selected).length} / ${all.length} 已入选`;
  $('#app').innerHTML=`<div class="report-heading"><div><div class="eyebrow">WORKFLOW CONTRACTS · V3</div><h1>多样性报告</h1><p>统计当前 ${all.length} 道新题及已保存的标签修改，不包含旧版审核池。</p></div><a class="report-action" href="/contract-review">返回题目审核</a></div>
    <div class="report-filters"><label>领域 <select id="report-domain">${option('','全部领域',state.domain)}${domains.map(domain=>option(domain,domain,state.domain)).join('')}</select></label><div class="segmented" aria-label="统计范围"><button data-scope="all" aria-pressed="${state.scope==='all'}">全部题目</button><button data-scope="selected" aria-pressed="${state.scope==='selected'}">已入选</button></div></div>
    <section class="report-metrics">${metric(rows.length,'当前范围题目',`${all.length} 道候选`)}${metric(new Set(rows.map(row=>row.category)).size,'覆盖类别')}${metric(new Set(rows.map(row=>row.host)).size,'来源网站')}${metric(actions.length,'主动作类型')}${metric(actions[0]?pct(actions[0][1],rows.length):'—','最大动作占比',actions[0]?(actionNames[actions[0][0]]||actions[0][0]):'')}${metric(forms[0]?pct(forms[0][1],rows.length):'—','最大攻击形式占比',forms[0]?(formNames[forms[0][0]]||forms[0][0]):'')}</section>
    ${rows.length?`<div class="report-two-column">${bars(rows,'task_action',actionNames,10)}${bars(rows,'authority_direction',{},6)}</div>${bars(rows,'form',formNames)}${bars(rows,'position',positionNames)}<div class="report-two-column">${bars(rows,'evidence_structure',{},8)}${bars(rows,'timing',timingNames,8)}</div><div class="report-two-column">${bars(rows,'risk',riskNames,8)}${bars(rows,'granularity',granularityNames,8)}</div>${categoryTable(rows)}${sourceTable(rows)}`:'<div class="empty">当前筛选条件下没有题目</div>'}`;
}
document.addEventListener('change',event=>{if(event.target.id==='report-domain'){state.domain=event.target.value;render();}});
document.addEventListener('click',event=>{const button=event.target.closest('[data-scope]');if(button){state.scope=button.dataset.scope;render();}});
(async()=>{try{const response=await fetch('/api/contracts/catalog');if(response.status===401){location.assign('/login');return;}const data=await response.json();if(!response.ok)throw new Error(data.error||'加载失败');state.rows=data.cases;render();}catch(error){$('#app').innerHTML=`<div class="empty">报告加载失败：${escapeHTML(error.message)}</div>`;}})();
