// Execute actual event handlers against a small DOM test double; not browser E2E.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(){this.children=[];this.dataset={};this.disabled=false;this.value='';this.checked=false;this.textContent='';this.hidden=false;this.fields={};}
  append(...nodes){this.children.push(...nodes);} replaceChildren(...nodes){this.children=[...nodes];}
  add(node){this.children.push(node);} querySelector(selector){return this.fields[selector]||null;}
  querySelectorAll(selector){return selector==='[data-for]'?this.blocks||[]:[];}
  reset(){this.resets=(this.resets||0)+1;}
}
const tick=async()=>{for(let i=0;i<12;i++)await new Promise(resolve=>setImmediate(resolve));};
const scenario=process.argv[2];
function fixture(mode,options={}){
  const nodes={},calls=[],storage=options.storage||new Map();let confirmValue=true,navFail=false,refreshFail=false,failPost=false,posts=0;
  const family={question_id:'family',revision:1,latest_committed_version_id:'v1'},version={question_version_id:'v1',version_no:1,created_at:'now',definition:{type:'number',title:'original',required:true,options:[],validation:{min:0}}};
  const node=id=>nodes[id]||(nodes[id]=new Element());node('#message');
  const button=new Element();
  if(mode==='family'||mode==='new_family'){
    node('#family-data').textContent=JSON.stringify(mode==='new_family'?null:family);
    const form=node('#bank-question-form');form.elements={};
    for(const name of ['type','title','required','options','integer_only','min','max'])form.elements[name]=new Element();
    form.elements.type.value='number';form.fields['button[type="submit"]']=button;
    form.blocks=[new Element(),new Element()];form.blocks[0].dataset.for='number';form.blocks[1].dataset.for='text';
    for(const id of ['#bank-form-title','#version-history','#bank-status','#bank-refresh','#bank-search','#bank-list'])node(id);
  }
  if(mode==='picker'){
    node('#survey-data').textContent=JSON.stringify({id:'survey',schema_version:7});
    const form=node('#bank-picker');form.elements={};
    for(const name of ['family','version','required_override','local_id'])form.elements[name]=new Element();
    form.elements.required_override.value='inherit';form.fields['button[type="submit"]']=button;
    for(const id of ['#picker-status','#picker-search','#picker-refresh','#picker-preview'])node(id);
  }
  if(mode==='revision'){button.dataset={revisionSource:'source',schemaVersion:'8'};}
  const loc={pathname:mode==='picker'?'/surveys/survey/edit':mode==='family'?'/question-bank/family':'/dashboard',reload(){if(navFail)throw new Error('reload unavailable');loc.reloads=(loc.reloads||0)+1;if(options.autoAck!==false)setImmediate(()=>acknowledge(loc.pathname));}};
  Object.defineProperty(loc,'href',{set(v){if(navFail)throw new Error('navigation unavailable');loc.destination=v;if(options.autoAck!==false)setImmediate(()=>acknowledge(v));}});
  const storageAPI={get length(){return storage.size;},key:i=>[...storage.keys()][i],getItem:k=>storage.has(k)?storage.get(k):null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)};
  function acknowledge(path,overrides={}){
    // A separate new-document VM and pageshow, not completion of href assignment.
    const handlers={};const data=new Element();
    data.textContent=JSON.stringify(overrides.data||{id:path.split('/')[2],schema_version:mode==='picker'?8:1});
    const target=vm.createContext({sessionStorage:storageAPI,location:{pathname:path},
      addEventListener:(name,handler)=>{handlers[name]=handler;},
      document:{querySelector:s=>!overrides.omitData&&s===(overrides.kind==='family'?'#family-data':'#survey-data')?data:null,querySelectorAll:()=>[]}});
    vm.runInContext(fs.readFileSync('app/static/question-bank.js','utf8').split('(function(){')[0],target);
    handlers.pageshow({persisted:!!overrides.persisted});
  }
  const sourceHandlers={};
  const context=vm.createContext({addEventListener:(name,handler)=>(sourceHandlers[name]||(sourceHandlers[name]=[])).push(handler),document:{querySelector:s=>nodes[s]||null,querySelectorAll:s=>s==='[data-revision-source]'&&mode==='revision'?[button]:[],createElement:()=>new Element()},
    Option:function(text,value){this.textContent=text;this.value=value;},
    sessionStorage:storageAPI,
    crypto:{randomUUID:()=>`key-${++fixture.sequence}`},confirm:()=>confirmValue,location:loc,
    fetch:async(path,options)=>{
      calls.push({path,...options});
      if(options.method!=='GET'){
        posts++;
        if(failPost)throw new Error('unknown write result');
        return {ok:true,status:201,json:async()=>({id:mode==='picker'?'survey':'child',schema_version:mode==='picker'?8:1,family:{question_id:'family'}})};
      }
      if(refreshFail&&posts)throw new Error('refresh unavailable');
      let result;
      if(path==='/api/questions/family')result=family;
      else if(path.startsWith('/api/questions/family/versions'))result={items:[version],next_cursor:null};
      else if(path.startsWith('/api/questions?'))result={items:[{...family,title:'Original',type:'number',latest_version_no:1}],next_cursor:null};
      else throw new Error('unexpected route '+path);
      return{ok:true,status:200,json:async()=>result};
    }});
  vm.runInContext(fs.readFileSync('app/static/management.js','utf8'),context);
  vm.runInContext(fs.readFileSync('app/static/question-bank.js','utf8'),context);
  return {nodes,calls,storage,button,loc,context,acknowledge,showSource:persisted=>{for(const handler of sourceHandlers.pageshow||[])handler({persisted});},change:o=>{if('confirm'in o)confirmValue=o.confirm;if('navFail'in o)navFail=o.navFail;if('refreshFail'in o)refreshFail=o.refreshFail;if('failPost'in o)failPost=o.failPost;},writes:()=>calls.filter(c=>c.method!=='GET')};
}
fixture.sequence=0;
const event={preventDefault(){}};
(async()=>{
  if(scenario.startsWith('restore')){
    const f=fixture('family');await tick();
    const restore=f.nodes['#version-history'].children[0].children[1];assert.equal(typeof restore.onclick,'function');
    if(scenario==='restore_cancel'){f.change({confirm:false});restore.onclick();await tick();assert.equal(f.writes().length,0);}
    else{
      if(scenario==='restore_refresh_failure')f.change({refreshFail:true});
      if(scenario==='restore_unknown_retry')f.change({failPost:true});
      restore.onclick();restore.onclick();await tick();assert.equal(f.writes().length,1);
      const first=f.writes()[0];assert.equal(first.path,'/api/questions/family/restore');
      assert.deepEqual(JSON.parse(first.body),{source_version_id:'v1',expected_revision:1});
      if(scenario==='restore_unknown_retry'){
        assert.equal(restore.disabled,false);assert.equal(f.storage.size,1);
        f.change({failPost:false});restore.onclick();await tick();assert.equal(f.writes().length,2);
        assert.equal(f.writes()[1].headers['Idempotency-Key'],first.headers['Idempotency-Key']);assert.equal(f.storage.size,0);
      }else if(scenario==='restore_refresh_failure'){
        assert.equal(restore.disabled,true);assert.equal(f.storage.size,1);
        assert.equal(f.nodes['#bank-question-form'].elements.title.value,'original');
        restore.onclick();await tick();assert.equal(f.writes().length,1);
      }else assert.equal(f.storage.size,0);
    }
  }else if(scenario.startsWith('picker')){
    const f=fixture('picker');await tick();const form=f.nodes['#bank-picker'],fields=form.elements;
    assert.equal(fields.family.children[1].value,'family');fields.family.value='family';await fields.family.onchange();
    fields.version.value='v1';fields.version.onchange();assert.match(f.nodes['#picker-preview'].textContent,/original/);
    fields.required_override.value=scenario==='picker_update'?'false':'inherit';
    fields.local_id.value=scenario==='picker_update'?'local':'';
    if(scenario==='picker_reload_failure')f.change({navFail:true});
    form.onsubmit(event);form.onsubmit(event);await tick();assert.equal(f.writes().length,1);
    const call=f.writes()[0];assert.equal(call.path,fields.local_id.value?'/api/surveys/survey/questions/local/binding':'/api/surveys/survey/question-references');
    assert.equal(call.method,fields.local_id.value?'PUT':'POST');assert.deepEqual(JSON.parse(call.body),{question_version_id:'v1',required_override:fields.local_id.value?false:null,expected_schema_version:7});
    if(scenario==='picker_reload_failure'){
      assert.equal(f.button.disabled,true);assert.equal(f.storage.size,1);assert.equal(fields.version.value,'v1');
      form.onsubmit(event);await tick();assert.equal(f.writes().length,1);
    }else{assert.equal(f.storage.size,0);assert.equal(f.loc.reloads,1);}
  }else if(scenario.startsWith('revision')){
    const f=fixture('revision');
    if(scenario==='revision_navigation_failure')f.change({navFail:true});else f.change({failPost:true});
    f.button.onclick();f.button.onclick();await tick();assert.equal(f.writes().length,1);
    const first=f.writes()[0];assert.equal(first.path,'/api/surveys/source/revisions');
    assert.deepEqual(JSON.parse(first.body),{source_schema_version:8,expected_schema_version:8});assert.equal(f.storage.size,1);
    if(scenario==='revision_navigation_failure'){assert.equal(f.button.disabled,true);f.button.onclick();await tick();assert.equal(f.writes().length,1);}
    else{assert.equal(f.button.disabled,false);f.change({failPost:false});f.button.onclick();await tick();assert.equal(f.writes().length,2);assert.equal(f.writes()[1].headers['Idempotency-Key'],first.headers['Idempotency-Key']);assert.equal(f.loc.destination,'/surveys/child/edit');assert.equal(f.storage.size,0);}
  }else if(scenario==='form_refresh_failure'){
    const f=fixture('family');await tick();const form=f.nodes['#bank-question-form'];form.elements.title.value='unsaved input';f.change({refreshFail:true});
    form.onsubmit(event);form.onsubmit(event);await tick();assert.equal(f.writes().length,1);assert.equal(f.button.disabled,true);assert.equal(f.storage.size,1);assert.equal(form.elements.title.value,'unsaved input');
  }else throw new Error('unknown scenario');
  console.log('SLICE3_DOM_'+scenario+'=PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
