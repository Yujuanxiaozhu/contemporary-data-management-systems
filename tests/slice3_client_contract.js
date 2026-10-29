const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const state=new Map(),calls=[];let fail=true,sequence=0;
const context=vm.createContext({document:{querySelector:()=>null,querySelectorAll:()=>[]},
  sessionStorage:{getItem:k=>state.get(k),setItem:(k,v)=>state.set(k,v),removeItem:k=>state.delete(k)},
  crypto:{randomUUID:()=>`intent-${++sequence}`},
  fetch:async(path,options)=>{calls.push({path,...options});if(fail)throw new Error('uncertain network result');return{ok:true,status:201,json:async()=>({saved:true})};}});
vm.runInContext(fs.readFileSync('app/static/management.js','utf8'),context);
vm.runInContext(fs.readFileSync('app/static/question-bank.js','utf8'),context);
(async()=>{
  await assert.rejects(vm.runInContext("intentApi('/api/questions','POST',{definition:{type:'text',title:'keep form content'}})",context));
  assert.equal(state.size,1);const first=calls[0].headers['Idempotency-Key'];
  fail=false;
  await vm.runInContext("intentApi('/api/questions','POST',{definition:{type:'text',title:'keep form content'}})",context);
  assert.equal(calls[1].headers['Idempotency-Key'],first);assert.equal(state.size,0);
  assert.equal(calls[1].headers['Content-Type'],'application/json');
  await vm.runInContext("intentApi('/api/questions','POST',{definition:{type:'text',title:'keep form content'}})",context);
  assert.notEqual(calls[2].headers['Idempotency-Key'],first);
  assert.equal(JSON.parse(calls[0].body).definition.title,'keep form content');
  console.log('SLICE3_CLIENT_INTENT_RETRY_AND_NEW_INTENT=PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
