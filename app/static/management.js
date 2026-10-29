const $=selector=>document.querySelector(selector);
function message(error){$('#message').textContent=typeof error==='string'?error:error.message;}
async function api(path,method='GET',data,headers={}){
  const response=await fetch(path,{method,headers:{...(data?{'Content-Type':'application/json'}:{}),...headers},body:data?JSON.stringify(data):undefined});
  if(response.status===204)return null;
  const body=await response.json();
  if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));
  return body;
}
async function run(action){try{await action();}catch(error){message(error);}}
if($('#logout'))$('#logout').onclick=()=>run(async()=>{await api('/api/auth/logout','POST');location.href='/login';});
const account=$('#account-form');
if(account)account.onsubmit=event=>{event.preventDefault();run(async()=>{
  const data=Object.fromEntries(new FormData(account));await api('/api/auth/'+account.dataset.mode,'POST',data);
  location.href=account.dataset.mode==='register'?'/login':'/dashboard';
});};
for(const button of document.querySelectorAll('[data-action]'))button.onclick=()=>run(async()=>{
  const card=button.closest('[data-survey-id]'),action=button.dataset.action;
  if(!confirm(action==='delete'?'确认删除草稿？':'确认'+(action==='publish'?'发布':'关闭')+'问卷？'))return;
  await api('/api/surveys/'+card.dataset.surveyId+(action==='delete'?'':'/'+action),action==='delete'?'DELETE':'POST');location.reload();
});
for(const button of document.querySelectorAll('[data-copy]'))button.onclick=()=>run(async()=>{
  const input=button.closest('[data-survey-id]').querySelector('[data-public-url]');input.select();
  if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(input.value);message('链接已复制');}
  else message('链接已选中，请按 Ctrl+C 复制');
});
const survey=$('#survey-data')?JSON.parse($('#survey-data').textContent):null;
const metadata=$('#metadata-form');
if(metadata){
  if(survey){for(const key of ['title','description'])metadata.elements[key].value=survey[key];
    for(const key of ['allow_anonymous','allow_multiple_submissions'])metadata.elements[key].checked=survey[key];
    if(survey.deadline){const date=new Date(survey.deadline);const local=new Date(date.getTime()-date.getTimezoneOffset()*60000);metadata.elements.deadline.value=local.toISOString().slice(0,19);}}
  metadata.onsubmit=event=>{event.preventDefault();run(async()=>{
    const fields=metadata.elements,data={title:fields.title.value,description:fields.description.value,allow_anonymous:fields.allow_anonymous.checked,allow_multiple_submissions:fields.allow_multiple_submissions.checked,deadline:fields.deadline.value?new Date(fields.deadline.value).toISOString():null};
    const saved=await api('/api/surveys'+(survey?'/'+survey.id:''),survey?'PUT':'POST',data);location.href='/surveys/'+saved.id+'/edit';
  });};
}
const qform=$('#question-form');let editingQuestion=null;
const rulesByType={single_choice:[],multiple_choice:['min_selections','max_selections','exact_selections'],text:['min_length','max_length'],number:['min','max']};
function showType(){for(const block of qform.querySelectorAll('[data-for]'))block.hidden=!block.dataset.for.split(' ').includes(qform.elements.type.value);}
if(qform){showType();qform.elements.type.onchange=showType;
  $('#new-question').onclick=()=>{qform.reset();editingQuestion=null;qform.elements.id.readOnly=false;$('#question-form-title').textContent='添加题目';showType();};
  for(const button of document.querySelectorAll('[data-edit-question]'))button.onclick=()=>{
    const q=survey.questions.find(q=>q.id===button.dataset.editQuestion);qform.reset();editingQuestion=q.id;
    for(const key of ['id','title','type','order'])qform.elements[key].value=q[key];qform.elements.id.readOnly=true;qform.elements.required.checked=q.required;
    qform.elements.options.value=q.options.map(o=>o.id+'|'+o.label).join('\n');
    for(const [key,value]of Object.entries(q.validation)){if(key==='integer_only')qform.elements[key].checked=value;else qform.elements[key].value=value;}
    $('#question-form-title').textContent='编辑题目 '+q.id;showType();qform.scrollIntoView({behavior:'smooth'});
  };
  qform.onsubmit=event=>{event.preventDefault();run(async()=>{
    const f=qform.elements,type=f.type.value,data={type,title:f.title.value,required:f.required.checked,options:[],validation:{}};
    if(f.id.value.trim())data.id=f.id.value.trim();if(f.order.value!=='')data.order=Number(f.order.value);
    if(type.includes('choice'))data.options=f.options.value.split('\n').filter(line=>line.trim()).map(line=>{const split=line.indexOf('|');if(split<0)throw new Error('每个选项请按 id|文字 填写');return{id:line.slice(0,split).trim(),label:line.slice(split+1).trim()};});
    for(const key of rulesByType[type])if(f[key].value!=='')data.validation[key]=Number(f[key].value);
    if(type==='number')data.validation.integer_only=f.integer_only.checked;
    if(editingQuestion && f.new_family?.checked)data.new_family=true;
    await intentApi('/api/surveys/'+survey.id+'/questions'+(editingQuestion?'/'+editingQuestion:''),editingQuestion?'PUT':'POST',data);location.reload();
  });};
}
for(const button of document.querySelectorAll('[data-delete-question]'))button.onclick=()=>run(async()=>{if(!confirm('确认删除该题？'))return;await api('/api/surveys/'+survey.id+'/questions/'+button.dataset.deleteQuestion,'DELETE');location.reload();});
const rform=$('#rule-form');let editingRule=null;
if(rform){$('#new-rule').onclick=()=>{rform.reset();editingRule=null;rform.elements.id.readOnly=false;$('#rule-form-title').textContent='添加规则';};
  for(const button of document.querySelectorAll('[data-edit-rule]'))button.onclick=()=>{
    const rule=survey.jump_rules.find(r=>r.id===button.dataset.editRule);editingRule=rule.id;
    for(const key of ['id','source_question_id','target_question_id','operator','value','priority'])rform.elements[key].value=rule[key];
    rform.elements.id.readOnly=true;$('#rule-form-title').textContent='编辑规则 '+rule.id;rform.scrollIntoView({behavior:'smooth'});
  };
  rform.onsubmit=event=>{event.preventDefault();run(async()=>{
    const f=rform.elements,source=survey.questions.find(q=>q.id===f.source_question_id.value);
    const data={source_question_id:f.source_question_id.value,target_question_id:f.target_question_id.value,operator:f.operator.value,value:source?.type==='number'?Number(f.value.value):f.value.value,priority:Number(f.priority.value)};
    if(f.id.value.trim())data.id=f.id.value.trim();await api('/api/surveys/'+survey.id+'/jump-rules'+(editingRule?'/'+editingRule:''),editingRule?'PUT':'POST',data);location.reload();
  });};
}
for(const button of document.querySelectorAll('[data-delete-rule]'))button.onclick=()=>run(async()=>{if(!confirm('确认删除该规则？'))return;await api('/api/surveys/'+survey.id+'/jump-rules/'+button.dataset.deleteRule,'DELETE');location.reload();});
