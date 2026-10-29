// Verify an unavailable shared member can switch to another currently authorized version.
const fs=require('node:fs'),assert=require('node:assert/strict');
let source=fs.readFileSync('tests/slice3_dom_contract.js','utf8').split('fixture.sequence=0;')[0];
source=source.replace("version={question_version_id:'v1'", "version={question_id:'family',question_version_id:'v1'");
source=source.replace("  if(mode==='picker'){", `  if(mode==='organizer'){
    for(const id of ['#bank-organizer','#bank-select','#bank-organizer-status','#bank-items','#bank-add-version','#bank-add','#bank-rename','#bank-delete'])node(id);
    const form=node('#bank-create');form.elements={name:new Element(),description:new Element()};form.fields.button=new Element();
  }
  if(mode==='picker'){`);
source=source.replace("createElement:()=>new Element()", `createElement:tag=>{const element=new Element();if(tag==='select'){let value='';Object.defineProperty(element,'value',{get:()=>value,set:v=>{value=element.children.some(c=>c.value===v)?v:''}});}return element;}`);
source=source.replace("      if(path==='/api/questions/family')result=family;", `      if(path.startsWith('/api/question-banks/bank/items?'))result={items:[{question_id:'family',default_version_id:'revoked',revision:1,available:false,version:null}],next_cursor:null};
      else if(path.startsWith('/api/question-banks?'))result={items:[{bank_id:'bank',name:'My bank',revision:1,description:''}],next_cursor:null};
      else if(path.startsWith('/api/shared-question-versions?'))result={items:[],next_cursor:null};
      else if(path==='/api/questions/family')result=family;`);
const box={exports:{}};new Function('require','module',source+'\nfixture.sequence=0;module.exports=fixture;')(require,box);
const tick=async()=>{for(let i=0;i<12;i++)await new Promise(r=>setImmediate(r));};
(async()=>{
 const f=box.exports('organizer');await tick();const bank=f.nodes['#bank-select'];bank.value='bank';bank.onchange();await tick();
 const row=f.nodes['#bank-items'].children[0],versions=row.children[1],save=row.children[2];
 assert.equal(save.disabled,true);versions.value='v1';versions.onchange();assert.equal(save.disabled,false);
 save.onclick();await tick();assert.equal(f.writes().length,1);
 assert.equal(f.writes()[0].path,'/api/question-banks/bank/items/family');assert.equal(JSON.parse(f.writes()[0].body).question_version_id,'v1');
 console.log('SLICE5_UNAVAILABLE_SWITCH=PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
