// Slice 4 shared-version UI on the existing DOM double; no browser E2E claim.
const fs=require('node:fs'),assert=require('node:assert/strict');
let prefix=fs.readFileSync('tests/slice3_dom_contract.js','utf8').split('fixture.sequence=0;')[0];
prefix=prefix.replace("  if(mode==='picker'){", "  if(mode==='picker'){node('#picker-shared-enabled');");
prefix=prefix.replace("    node('#family-data').textContent", `    if(mode==='family')node('#share-controls-enabled');
    node('#family-data').textContent`);
prefix=prefix.replace("      if(path==='/api/questions/family')result=family;", `      if(path.startsWith('/api/shared-question-versions?'))result={items:[{...version,owner_username:'owner'}],next_cursor:null};
      else if(path==='/api/questions/family/versions/v1/shares')result={items:[]};
      else if(path==='/api/question-versions/v1/shares')result={items:[{username:'bob',grantee_user_id:'user',state:'ACTIVE'}]};
      else if(path==='/api/questions/family')result=family;`);
const moduleData={exports:{}};new Function('require','module',prefix+'\nfixture.sequence=0;module.exports=fixture;')(require,moduleData);
const fixture=moduleData.exports,tick=async()=>{for(let i=0;i<12;i++)await new Promise(r=>setImmediate(r));};
(async()=>{
 const picker=fixture('picker');await tick();const f=picker.nodes['#bank-picker'];
 assert.equal(f.elements.family.children[2].value,'shared:v1');assert.match(f.elements.family.children[2].textContent,/共享.*owner/);
 f.elements.family.value='shared:v1';await f.elements.family.onchange();assert.equal(f.elements.version.children[1].value,'v1');
 f.elements.version.value='v1';f.onsubmit({preventDefault(){}});await tick();assert.equal(picker.writes().length,1);
 assert.equal(JSON.parse(picker.writes()[0].body).question_version_id,'v1');
 const owner=fixture('family');await tick();const panel=owner.nodes['#version-history'].children[0].children[2];
 assert.ok(panel);const [name,grant,list,entries]=panel.children;name.value='bob';grant.onclick();await tick();
 assert.equal(owner.writes()[0].path,'/api/question-versions/v1/shares');assert.equal(JSON.parse(owner.writes()[0].body).username,'bob');
 list.onclick();await tick();assert.equal(entries.children.length,1);const revoke=entries.children[0].children[0];revoke.onclick();await tick();
 assert.equal(owner.writes()[1].method,'DELETE');assert.equal(owner.writes()[1].path,'/api/question-versions/v1/shares/user');
 console.log('SLICE4_SHARED_DOM=PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
