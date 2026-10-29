// Node DOM contract: the owner can request statistics and sees the correct unit.
const fs=require('node:fs'),assert=require('node:assert/strict');
let prefix=fs.readFileSync('tests/slice3_dom_contract.js','utf8').split('fixture.sequence=0;')[0];
prefix=prefix.replace("  if(mode==='family'||mode==='new_family'){", "  if(mode==='family') { node('#question-stats-load'); node('#question-stats-result'); }\n  if(mode==='family'||mode==='new_family'){");
prefix=prefix.replace("      if(path==='/api/questions/family')result=family;", `      if(path==='/api/questions/family/stats')result={versions:[{version_no:1,statistics:{type:'number',answered_count:2,min:10,max:20,average:15}}]};
      else if(path==='/api/questions/family')result=family;`);
const box={exports:{}};new Function('require','module',prefix+'\nfixture.sequence=0;module.exports=fixture;')(require,box);
const tick=async()=>{for(let i=0;i<12;i++)await new Promise(r=>setImmediate(r));};
(async()=>{const f=box.exports('family');await tick();const button=f.nodes['#question-stats-load'];button.onclick();await tick();
 assert.ok(f.calls.some(c=>c.path==='/api/questions/family/stats'&&c.method==='GET'));
 assert.match(f.nodes['#question-stats-result'].textContent,/有效回答次数：2/);
 assert.match(f.nodes['#question-stats-result'].textContent,/平均值：15/);
 console.log('SLICE7_STATS_DOM=PASS');})().catch(e=>{console.error(e);process.exitCode=1;});
