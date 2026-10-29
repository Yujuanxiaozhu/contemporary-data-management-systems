// Persistent per-payload intent keys: uncertain failures keep the same key and form.
function intentSlot(path,method,data){return 'survey-intent:'+method+':'+path+':'+JSON.stringify(data);}
function intentKey(raw){
  if(raw&&raw.startsWith('{')){try{const record=JSON.parse(raw);if(typeof record.key==='string')return record.key;}catch(_){}}
  return raw;
}
function confirmIntentNavigation(event){
  // pageshow confirms the new document, never the old document's navigation call.
  if(event.persisted)return;
  const slots=[];for(let i=0;i<sessionStorage.length;i++)slots.push(sessionStorage.key(i));
  for(const slot of slots){
    if(!slot||!slot.startsWith('survey-intent:'))continue;
    try{
      const record=JSON.parse(sessionStorage.getItem(slot)),nav=record.navigation;
      if(!nav||nav.path!==location.pathname||typeof record.key!=='string')continue;
      const node=document.querySelector(nav.kind==='survey'?'#survey-data':'#family-data');
      if(!node)continue;
      const loaded=JSON.parse(node.textContent);
      const valid=nav.kind==='survey'?loaded.id===nav.id&&Number.isInteger(loaded.schema_version)&&loaded.schema_version>=nav.schema
        :nav.kind==='family'&&loaded&&loaded.question_id===nav.id;
      if(valid)sessionStorage.removeItem(slot);
    }catch(_){/* Unconfirmed, inaccessible or malformed storage never clears an intent. */}
  }
}
if(typeof addEventListener==='function')addEventListener('pageshow',confirmIntentNavigation);
async function intentApi(path,method,data,retain=false){
  const slot=intentSlot(path,method,data);
  let key=intentKey(sessionStorage.getItem(slot));
  if(!key){key=crypto.randomUUID();sessionStorage.setItem(slot,key);}
  const result=await api(path,method,data,{'Idempotency-Key':key});
  if(!retain)sessionStorage.removeItem(slot);return result;
}
(function(){
  const find=s=>document.querySelector(s);
  // These records live only in this document and survive its BFCache restoration.
  const navigations=new Map();
  if(typeof addEventListener==='function')addEventListener('pageshow',event=>{
    if(!event.persisted)return;
    for(const button of navigations.keys()){button.dataset.keepDisabled='false';button.disabled=false;}
  });
  async function pageIntent(button,path,method,body,refresh){
    const slot=intentSlot(path,method,body),previous=navigations.get(button);
    if(previous){
      const stored=sessionStorage.getItem(previous.slot);
      if(stored!==null){
        if(slot!==previous.slot||intentKey(stored)!==previous.key)throw new Error('上次操作尚未确认，请保留原内容重试。');
      }else if(slot===previous.slot){
        // The matching target already confirmed this intent; revisit it without another write.
        // A cancelled or failed revisit has no uncertain write and must remain retryable.
        button.dataset.keepDisabled='false';
        if(previous.navigation.reload)location.reload();else location.href=previous.navigation.path;
        return;
      }else navigations.delete(button);
    }
    const result=await intentApi(path,method,body,true);
    button.dataset.keepDisabled='true';
    try{
      const navigation=await refresh(result);
      if(navigation){
        const key=intentKey(sessionStorage.getItem(slot));
        sessionStorage.setItem(slot,JSON.stringify({key,navigation}));
        navigations.set(button,{slot,key,navigation});
        if(navigation.reload)location.reload();else location.href=navigation.path;
        return; // href/reload returning does not acknowledge the target document.
      }
    }catch(error){throw new Error('请求已成功，但刷新失败；请重新加载页面，勿重复创建。'+error.message);}
    sessionStorage.removeItem(intentSlot(path,method,body));
  }
  async function pages(path){
    const items=[];let cursor=null;
    do{const result=await api(path+(path.includes('?')?'&':'?')+'limit=100'+(cursor?'&cursor='+encodeURIComponent(cursor):''));
      items.push(...result.items);cursor=result.next_cursor;}while(cursor!==null);
    return items;
  }
  async function busy(button,action){if(button.disabled)return;button.disabled=true;try{await action();}catch(e){message(e);}finally{button.disabled=button.dataset.keepDisabled==='true';}}
  function renderCrossStats(result){
    const lines=['统计范围：本人问卷','统计单位：有效回答次数'];
    for(const version of result.versions){const s=version.statistics;lines.push('版本 v'+version.version_no+' · 有效回答次数：'+s.answered_count);
      if(s.options)for(const option of s.options)lines.push(option.label+'：'+option.count+(option.percentage===undefined?'':'（'+option.percentage.toFixed(2)+'%）'));
      if(s.total_selections!==undefined)lines.push('总选择次数：'+s.total_selections);
      if(s.type==='number')lines.push('最小值：'+(s.min??'无')+'；最大值：'+(s.max??'无')+'；平均值：'+(s.average??'无'));
      if(s.type==='text')for(const value of s.values)lines.push(value);
    }return lines.join('\n');
  }
  function typeFields(form){for(const block of form.querySelectorAll('[data-for]'))block.hidden=!block.dataset.for.split(' ').includes(form.elements.type.value);}
  function readDefinition(form){
    const f=form.elements,type=f.type.value,result={type,title:f.title.value,required:f.required.checked,options:[],validation:{}};
    if(type.includes('choice'))result.options=f.options.value.split('\n').filter(s=>s.trim()).map(s=>{
      const i=s.indexOf('|');if(i<0)throw new Error('选项请按 id|文字 填写');return{id:s.slice(0,i).trim(),label:s.slice(i+1).trim()};});
    for(const key of rulesByType[type])if(f[key].value!=='')result.validation[key]=Number(f[key].value);
    if(type==='number')result.validation.integer_only=f.integer_only.checked;
    return result;
  }
  const familyData=find('#family-data');
  if(familyData){
    let family=JSON.parse(familyData.textContent),versions=[];const form=find('#bank-question-form');
    form.elements.type.onchange=()=>typeFields(form);typeFields(form);
    function fill(v){form.reset();for(const key of ['type','title'])form.elements[key].value=v.definition[key];
      form.elements.required.checked=v.definition.required;form.elements.options.value=v.definition.options.map(o=>o.id+'|'+o.label).join('\n');
      for(const [k,value] of Object.entries(v.definition.validation))if(k==='integer_only')form.elements[k].checked=value;else form.elements[k].value=value;
      typeFields(form);find('#bank-form-title').textContent='更新现有题目（当前 v'+v.version_no+'，保存将创建新版本）';}
    async function loadFamily(){
      family=await api('/api/questions/'+family.question_id);versions=await pages('/api/questions/'+family.question_id+'/versions');
      const history=find('#version-history');history.replaceChildren();
      for(const v of versions){const section=document.createElement('section'),text=document.createElement('pre');
        text.textContent='v'+v.version_no+(v.question_version_id===family.latest_committed_version_id?' · 当前最新版':'')+'\n'+v.question_version_id+'\n'+v.created_at+'\nparent: '+(v.parent_version_id||'无')+'\nrestored_from: '+(v.restored_from||'无')+'\n'+JSON.stringify(v.definition,null,2);section.append(text);
        const restore=document.createElement('button');restore.type='button';restore.textContent='恢复此版本（创建新版本）';
        restore.onclick=()=>{if(!confirm('恢复 v'+v.version_no+' 会创建新版本，历史版本和已有问卷不变。继续？'))return;
          busy(restore,()=>pageIntent(restore,'/api/questions/'+family.question_id+'/restore','POST',{source_version_id:v.question_version_id,expected_revision:family.revision},async()=>{await loadFamily();message('恢复成功，已创建新版本');}));};
        section.append(restore);
        if(find('#share-controls-enabled')){
          const panel=document.createElement('div'),name=document.createElement('input'),grant=document.createElement('button'),list=document.createElement('button'),entries=document.createElement('div');
          name.placeholder='接收者用户名';grant.type=list.type='button';grant.textContent='分享此版本';list.textContent='查看共享对象';
          grant.onclick=()=>busy(grant,async()=>{await api('/api/question-versions/'+v.question_version_id+'/shares','POST',{username:name.value});message('指定版本已分享');});
          list.onclick=()=>busy(list,async()=>{const data=await api('/api/question-versions/'+v.question_version_id+'/shares');entries.replaceChildren();
            for(const share of data.items){const row=document.createElement('div'),revoke=document.createElement('button');row.textContent=(share.username||share.grantee_user_id)+' · '+(share.state==='ACTIVE'?'有效':'已撤销')+' ';revoke.type='button';revoke.textContent='撤销';revoke.disabled=share.state!=='ACTIVE';revoke.onclick=()=>busy(revoke,async()=>{await api('/api/question-versions/'+v.question_version_id+'/shares/'+share.grantee_user_id,'DELETE');row.textContent=(share.username||share.grantee_user_id)+' · 已撤销';});row.append(revoke);entries.append(row);}});
          panel.append(name,grant,list,entries);section.append(panel);
        }
        history.append(section);}
      fill(versions[0]);find('#bank-status').textContent='已加载 '+versions.length+' 个版本';
    }
    async function loadList(){
      const status=find('#bank-status');status.textContent='正在加载题目…';
      try{const rows=await pages('/api/questions');const render=()=>{const body=find('#bank-list');body.replaceChildren();
        const selected=rows.filter(q=>q.title.toLowerCase().includes(find('#bank-search').value.toLowerCase()));
        for(const q of selected){const tr=document.createElement('tr');for(const [i,value] of [q.title,q.type,'v'+q.latest_version_no,q.version_count,q.updated_at].entries()){
          const td=document.createElement('td');if(i===0){const a=document.createElement('a');a.href='/question-bank/'+q.question_id;a.textContent=value;td.append(a);}else td.textContent=value;tr.append(td);}body.append(tr);}
        status.textContent=selected.length?'显示 '+selected.length+' 个本人题目':'没有匹配题目，可创建新题目族';};find('#bank-search').oninput=render;render();}
      catch(e){status.textContent='加载失败，可点击重新加载；'+e.message;message(e);}
    }
    form.onsubmit=e=>{e.preventDefault();busy(form.querySelector('button[type="submit"]'),async()=>{
      const definition=readDefinition(form),submit=form.querySelector('button[type="submit"]');
      await pageIntent(submit,family?'/api/questions/'+family.question_id+'/versions':'/api/questions','POST',family?{definition,parent_version_id:versions[0].question_version_id,expected_revision:family.revision}:{definition},async result=>{
        if(!family)return{path:'/question-bank/'+result.family.question_id,kind:'family',id:result.family.question_id};
        else{await loadFamily();submit.dataset.keepDisabled='false';message('新版本已保存');}
      });});};
    if(family&&find('#question-stats-load'))find('#question-stats-load').onclick=()=>busy(find('#question-stats-load'),async()=>{
      const result=await api('/api/questions/'+family.question_id+'/stats');find('#question-stats-result').textContent=renderCrossStats(result);});
    if(family)loadFamily().catch(e=>{find('#bank-status').textContent='加载失败：'+e.message;form.querySelector('button[type="submit"]').disabled=true;});
    else{find('#bank-refresh').onclick=loadList;loadList();
      if(find('#shared-questions'))pages('/api/shared-question-versions').then(items=>{const list=find('#shared-questions');list.replaceChildren();
        for(const v of items){const li=document.createElement('li');li.textContent=v.definition.title+' · v'+v.version_no+' · 来自 '+v.owner_username;
          if(find('#shared-stats')){const button=document.createElement('button');button.type='button';button.textContent='查看本人问卷统计';
            button.onclick=()=>busy(button,async()=>{const result=await api('/api/questions/'+v.question_id+'/stats?version_id='+v.question_version_id);find('#shared-stats').textContent=renderCrossStats(result);});li.append(button);}list.append(li);}
        find('#shared-status').textContent=items.length?'仅可使用已授权版本':'暂无共享题目';}).catch(e=>{find('#shared-status').textContent='加载失败：'+e.message;});
    }
  }
  const organizer=find('#bank-organizer');
  if(organizer){
    let banks=[],available=[];const select=find('#bank-select'),status=find('#bank-organizer-status');
    async function loadBanks(selected=''){
      banks=await pages('/api/question-banks');select.replaceChildren(new Option('请选择题库',''));
      for(const bank of banks)select.add(new Option(bank.name,bank.bank_id));
      select.value=selected;await loadItems();
    }
    async function loadAvailable(){
      const mine=await pages('/api/questions'),shared=await pages('/api/shared-question-versions');available=[];
      for(const q of mine)available.push(...await pages('/api/questions/'+q.question_id+'/versions'));
      available.push(...shared);const list=find('#bank-add-version');list.replaceChildren(new Option('请选择版本',''));
      for(const v of available)list.add(new Option(v.definition.title+' · v'+v.version_no,v.question_version_id));
    }
    async function loadItems(){
      const list=find('#bank-items');list.replaceChildren();if(!select.value){status.textContent='请选择题库';return;}
      const bankId=select.value,items=await pages('/api/question-banks/'+bankId+'/items');if(select.value!==bankId)return;
      for(const item of items){
        const row=document.createElement('li'),label=document.createElement('span'),versions=document.createElement('select'),save=document.createElement('button'),remove=document.createElement('button');
        label.textContent=item.available?item.version.definition.title+' · 默认 v'+item.version.version_no:'共享授权已失效 · '+item.question_id;
        for(const v of available.filter(v=>v.question_id===item.question_id))versions.add(new Option(v.definition.title+' · v'+v.version_no,v.question_version_id));
        versions.value=item.default_version_id;save.type=remove.type='button';save.textContent='更新默认版本';remove.textContent='移除';
        save.disabled=!versions.value;versions.onchange=()=>{save.disabled=!versions.value;};
        save.onclick=()=>busy(save,async()=>{if(!versions.value)throw new Error('请选择可用版本');await api('/api/question-banks/'+bankId+'/items/'+item.question_id,'PUT',{question_version_id:versions.value,expected_revision:item.revision});await loadItems();});
        remove.onclick=()=>busy(remove,async()=>{await api('/api/question-banks/'+bankId+'/items/'+item.question_id+'?expected_revision='+item.revision,'DELETE');await loadItems();});
        row.append(label,versions,save,remove);list.append(row);
      }
      status.textContent=items.length?'成员 '+items.length+' 项':'题库暂无成员';
    }
    find('#bank-create').onsubmit=e=>{e.preventDefault();const form=e.currentTarget,button=form.querySelector('button');busy(button,async()=>{
      const data={name:form.elements.name.value,description:form.elements.description.value},created=await intentApi('/api/question-banks','POST',data);
      form.reset();await loadBanks(created.bank_id);message('题库已创建');});};
    select.onchange=()=>loadItems().catch(message);
    find('#bank-add').onclick=()=>busy(find('#bank-add'),async()=>{if(!select.value||!find('#bank-add-version').value)throw new Error('请选择题库和版本');await api('/api/question-banks/'+select.value+'/items','POST',{question_version_id:find('#bank-add-version').value});await loadItems();});
    find('#bank-rename').onclick=()=>busy(find('#bank-rename'),async()=>{const bank=banks.find(b=>b.bank_id===select.value);if(!bank)throw new Error('请选择题库');const name=prompt('新的题库名称',bank.name);if(name===null)return;await api('/api/question-banks/'+bank.bank_id,'PUT',{name,description:bank.description,expected_revision:bank.revision});await loadBanks(bank.bank_id);});
    find('#bank-delete').onclick=()=>busy(find('#bank-delete'),async()=>{const bank=banks.find(b=>b.bank_id===select.value);if(!bank)throw new Error('请选择题库');if(!confirm('删除题库不会删除题目和问卷，继续？'))return;await api('/api/question-banks/'+bank.bank_id+'?expected_revision='+bank.revision,'DELETE');await loadBanks();});
    (async()=>{await loadAvailable();await loadBanks();})().catch(e=>{status.textContent='加载失败：'+e.message;});
  }
  const picker=find('#bank-picker');
  if(picker){
    let families=[],versions=[],shared=[],bankItems=null;const f=picker.elements,status=find('#picker-status'),bankSelect=find('#picker-bank');
    const render=()=>{f.family.replaceChildren(new Option('请选择题目',''));const term=find('#picker-search').value.toLowerCase();
      if(bankItems!==null){for(const item of bankItems.filter(i=>i.available&&i.version.definition.title.toLowerCase().includes(term)))f.family.add(new Option('题库 · '+item.version.definition.title+' · v'+item.version.version_no,'bankitem:'+item.question_id));}
      else{for(const q of families.filter(q=>q.title.toLowerCase().includes(term)))f.family.add(new Option('我的 · '+q.title+' · '+q.type+' · v'+q.latest_version_no,q.question_id));
      for(const v of shared.filter(v=>v.definition.title.toLowerCase().includes(term)))f.family.add(new Option('共享 · '+v.definition.title+' · v'+v.version_no+' · '+v.owner_username,'shared:'+v.question_version_id));}f.version.replaceChildren(new Option('请选择确定版本',''));};
    async function load(){try{families=await pages('/api/questions');shared=find('#picker-shared-enabled')?await pages('/api/shared-question-versions'):[];
      if(bankSelect){const banks=await pages('/api/question-banks');bankSelect.replaceChildren(new Option('全部可用题目',''));for(const bank of banks)bankSelect.add(new Option(bank.name,bank.bank_id));bankItems=null;}
      render();status.textContent=families.length||shared.length?'请明确选择题目及版本':'题库为空，请先创建题目';}catch(e){status.textContent='加载失败：'+e.message;}}
    if(bankSelect)bankSelect.onchange=async()=>{try{const id=bankSelect.value,items=id?await pages('/api/question-banks/'+id+'/items'):null;if(bankSelect.value!==id)return;bankItems=items;render();status.textContent=bankItems?'请选择可用成员及其固定版本':'请明确选择题目及版本';}catch(e){status.textContent=e.message;}};
    find('#picker-refresh').onclick=load;find('#picker-search').oninput=render;
    f.family.onchange=async()=>{f.version.replaceChildren(new Option('请选择确定版本',''));try{if(!f.family.value)return;const qid=f.family.value;
      const sourceItems=bankItems,item=qid.startsWith('bankitem:')&&bankItems?bankItems.find(i=>i.question_id===qid.slice(9)&&i.available):null;
      if(item){versions=families.some(q=>q.question_id===item.question_id)?await pages('/api/questions/'+item.question_id+'/versions'):shared.filter(v=>v.question_id===item.question_id);
        if(!versions.some(v=>v.question_version_id===item.default_version_id))versions.push(item.version);}
      else versions=qid.startsWith('shared:')?shared.filter(v=>v.question_version_id===qid.slice(7)):await pages('/api/questions/'+qid+'/versions');
      if(f.family.value!==qid||(item&&bankItems!==sourceItems))return;
      for(const v of versions)f.version.add(new Option('v'+v.version_no+' · '+v.question_version_id,v.question_version_id));if(item){f.version.value=item.default_version_id;f.version.onchange();}}catch(e){status.textContent=e.message;}};
    f.version.onchange=()=>{const v=versions.find(v=>v.question_version_id===f.version.value);find('#picker-preview').textContent=v?JSON.stringify(v.definition,null,2):'';};
    picker.onsubmit=e=>{e.preventDefault();busy(picker.querySelector('button[type="submit"]'),async()=>{
      const body={question_version_id:f.version.value,required_override:f.required_override.value==='inherit'?null:f.required_override.value==='true',expected_schema_version:survey.schema_version};
      if(!body.question_version_id)throw new Error('请选择一个确定版本');
      await pageIntent(picker.querySelector('button[type="submit"]'),'/api/surveys/'+survey.id+(f.local_id.value?'/questions/'+f.local_id.value+'/binding':'/question-references'),f.local_id.value?'PUT':'POST',body,result=>({path:'/surveys/'+survey.id+'/edit',kind:'survey',id:survey.id,schema:result.schema_version,reload:true}));});};load();
  }
  for(const button of document.querySelectorAll('[data-revision-source]'))button.onclick=()=>{
    if(!confirm('创建独立修订草稿？将生成新问卷和新公开链接，原问卷及答卷不变。'))return;
    busy(button,()=>pageIntent(button,'/api/surveys/'+button.dataset.revisionSource+'/revisions','POST',{source_schema_version:Number(button.dataset.schemaVersion),expected_schema_version:Number(button.dataset.schemaVersion)},result=>({path:'/surveys/'+result.id+'/edit',kind:'survey',id:result.id,schema:result.schema_version})));};
})();
