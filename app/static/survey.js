const $ = selector => document.querySelector(selector);
const token=$('#public-survey').dataset.token;
const base='/api/public/surveys/'+encodeURIComponent(token);
let survey,current=null; const answers=new Map(), visited=new Set();
async function api(path, data) {
  const response=await fetch(base+path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify(data):undefined});
  const body=await response.json();
  if(!response.ok) throw new Error(typeof body.detail==='string'?body.detail:JSON.stringify(body.detail));
  return body;
}
function showQuestion(id){
  current=survey.questions.find(q=>q.id===id);
  if(!current || visited.has(id) || visited.size>=200) throw new Error('问卷路径异常，请重新加载');
  $('#question-title').textContent=current.title+(current.required?'（必答）':'（选答）');
  $('#progress').textContent='正在填写第 '+current.order+' 题 · 版本 '+survey.schema_version;
  const fields=$('#answer-fields'); fields.replaceChildren();
  if(current.type==='single_choice'||current.type==='multiple_choice'){
    for(const option of current.options){
      const label=document.createElement('label'), input=document.createElement('input');
      input.type=current.type==='single_choice'?'radio':'checkbox'; input.name='answer'; input.value=option.id;
      label.append(input,document.createTextNode(option.label)); fields.append(label);
    }
  }else{
    const input=document.createElement(current.type==='text'?'textarea':'input');
    if(current.type==='number'){input.type='number';input.step='any';}
    input.name='answer'; fields.append(input);
  }
}
function answerValue(){
  if(current.type==='multiple_choice') return Array.from(document.querySelectorAll('[name=answer]:checked'),e=>e.value);
  if(current.type==='single_choice') return document.querySelector('[name=answer]:checked')?.value??null;
  const raw=document.querySelector('[name=answer]').value;
  return current.type==='number'?(raw===''?null:Number(raw)):raw;
}
$('#answer-form').onsubmit=async event=>{
  event.preventDefault(); $('#next').disabled=true; $('#message').textContent='';
  try{
    const value=answerValue();
    const next=await api('/next',{schema_version:survey.schema_version,current_question_id:current.id,answer:value});
    answers.set(current.id,value); visited.add(current.id);
    if(next.completed){$('#answer-form').hidden=true;$('#submit-response').hidden=false;$('#progress').textContent='填写完成，请提交';}
    else showQuestion(next.next_question_id);
  }catch(error){$('#message').textContent=error.message;}finally{$('#next').disabled=false;}
};
$('#submit-response').onclick=async()=>{
  $('#submit-response').disabled=true;
  try{
    const result=await api('/responses',{schema_version:survey.schema_version,answers:Array.from(answers,([question_id,value])=>({question_id,value}))});
    $('#message').textContent='提交成功，答卷编号：'+result.id; $('#submit-response').hidden=true;
  }catch(error){$('#message').textContent=error.message;$('#submit-response').disabled=false;}
};
(async()=>{try{
  survey=await api('');$('#title').textContent=survey.title;$('#description').textContent=survey.description;
  survey.questions.sort((a,b)=>a.order-b.order);
  if(survey.questions.length) showQuestion(survey.questions[0].id);
  else{$('#answer-form').hidden=true;$('#submit-response').hidden=false;}
}catch(error){$('#answer-form').hidden=true;$('#message').textContent=error.message;}})();
