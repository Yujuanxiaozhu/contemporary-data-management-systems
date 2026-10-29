const fs=require('node:fs'),assert=require('node:assert/strict');
const prefix=fs.readFileSync('tests/slice3_dom_contract.js','utf8').split('fixture.sequence=0;')[0];
const moduleData={exports:{}};
new Function('require','module',prefix+'\nfixture.sequence=0;module.exports=fixture;')(require,moduleData);
const fixture=moduleData.exports;
const tick=async()=>{for(let i=0;i<12;i++)await new Promise(resolve=>setImmediate(resolve));};
const scenario=process.argv[2],event={preventDefault(){}};
(async()=>{
  const mode=scenario.startsWith('picker')?'picker':scenario.startsWith('family')?'new_family':'revision';
  let f=fixture(mode,{autoAck:false});await tick();
  async function submit(target){
    if(mode==='picker'){
      const form=target.nodes['#bank-picker'];form.elements.family.value='family';await form.elements.family.onchange();
      form.elements.version.value='v1';form.onsubmit(event);
    }else if(mode==='new_family'){
      const form=target.nodes['#bank-question-form'];form.elements.title.value='new family';form.onsubmit(event);
    }else target.button.onclick();
    await tick();
  }
  await submit(f);assert.equal(f.writes().length,1);
  const key=f.writes()[0].headers['Idempotency-Key'];
  assert.equal(f.storage.size,1);assert.equal(f.button.disabled,true);
  const record=JSON.parse([...f.storage.values()][0]);assert.equal(record.key,key);assert.ok(record.navigation);
  if(scenario.endsWith('_revisit_failure')||scenario.endsWith('_revisit_cancelled')){
    const path=mode==='picker'?'/surveys/survey/edit':'/surveys/child/edit';
    f.acknowledge(path);assert.equal(f.storage.size,0);f.showSource(true);assert.equal(f.button.disabled,false);
    if(scenario.endsWith('_revisit_failure'))f.change({navFail:true});
    // With autoAck disabled, the non-throwing navigation leaves the source active, as when cancelled.
    await submit(f);assert.equal(f.writes().length,1);assert.equal(f.storage.size,0);assert.equal(f.button.disabled,false);
    f.change({navFail:false});await submit(f);assert.equal(f.writes().length,1);assert.equal(f.storage.size,0);assert.equal(f.button.disabled,false);
  }else if(scenario==='picker_unconfirmed_changed_payload'){
    f.showSource(true);assert.equal(f.button.disabled,false);assert.equal(f.storage.size,1);
    const form=f.nodes['#bank-picker'];form.elements.required_override.value='true';form.onsubmit(event);await tick();
    assert.equal(f.writes().length,1);assert.equal(f.storage.size,1);assert.equal(f.button.disabled,false);
    assert.equal(JSON.parse([...f.storage.values()][0]).key,key);
    form.elements.required_override.value='inherit';await submit(f);
    assert.equal(f.writes().length,2);assert.equal(f.writes()[1].headers['Idempotency-Key'],key);assert.equal(f.storage.size,1);
  }else if(scenario.endsWith('_bfcache_confirmed')){
    // The target is a separate document. Return restores the original VM and DOM.
    const path=mode==='picker'?'/surveys/survey/edit':mode==='new_family'?'/question-bank/family':'/surveys/child/edit';
    f.acknowledge(path,mode==='new_family'?{kind:'family',data:{question_id:'family'}}:{});
    assert.equal(f.storage.size,0);assert.equal(f.button.disabled,true);
    f.showSource(false);assert.equal(f.button.disabled,true); // a normal pageshow is not restoration
    f.showSource(true);assert.equal(f.button.disabled,false);
    await submit(f);assert.equal(f.writes().length,1);assert.equal(f.storage.size,0);
    if(mode==='picker')assert.equal(f.loc.reloads,2);else assert.equal(f.loc.destination,path);
  }else if(scenario.endsWith('_bfcache_unconfirmed')){
    const path=mode==='picker'?'/surveys/survey/edit':mode==='new_family'?'/question-bank/family':'/surveys/child/edit';
    f.acknowledge('/wrong');assert.equal(f.storage.size,1);
    if(mode==='new_family')f.acknowledge(path,{kind:'family',data:{question_id:'wrong'}});
    else f.acknowledge(path,{data:{id:'wrong',schema_version:0}});
    assert.equal(f.storage.size,1);
    if(mode==='picker'){f.acknowledge(path,{data:{id:'survey',schema_version:7}});assert.equal(f.storage.size,1);}
    f.showSource(true);assert.equal(f.button.disabled,false);assert.equal(f.storage.size,1);
    if(mode==='new_family'){
      const form=f.nodes['#bank-question-form'];form.elements.title.value='changed';form.onsubmit(event);await tick();
      assert.equal(f.writes().length,1);assert.equal(f.storage.size,1);assert.equal(f.button.disabled,false);
    }
    await submit(f);assert.equal(f.writes().length,2);
    assert.equal(f.writes()[1].headers['Idempotency-Key'],key);assert.equal(f.storage.size,1);
    f.acknowledge(path,mode==='new_family'?{kind:'family',data:{question_id:'family'}}:{});
    assert.equal(f.storage.size,0);
  }else if(scenario==='revision_retry_same_key'){
    // New source document after unconfirmed navigation: same intent and key.
    const again=fixture('revision',{autoAck:false,storage:f.storage});await submit(again);
    assert.equal(again.writes()[0].headers['Idempotency-Key'],key);assert.equal(f.storage.size,1);
    again.acknowledge('/surveys/child/edit');assert.equal(f.storage.size,0);
  }else if(scenario==='revision_wrong_target'){
    f.acknowledge('/dashboard');assert.equal(f.storage.size,1);
    f.acknowledge('/surveys/child/edit',{data:{id:'other',schema_version:1}});assert.equal(f.storage.size,1);
    f.acknowledge('/surveys/child/edit',{omitData:true});assert.equal(f.storage.size,1);
    f.acknowledge('/surveys/child/edit');assert.equal(f.storage.size,0);
  }else if(scenario==='revision_back_forward_cache'){
    f.acknowledge('/surveys/child/edit',{persisted:true});assert.equal(f.storage.size,1);
    f.acknowledge('/surveys/child/edit');assert.equal(f.storage.size,0);
  }else if(scenario==='picker_stale_document'){
    f.acknowledge('/surveys/survey/edit',{data:{id:'survey',schema_version:7}});assert.equal(f.storage.size,1);
    f.acknowledge('/surveys/survey/edit',{data:{id:'survey',schema_version:8}});assert.equal(f.storage.size,0);
  }else if(scenario==='picker_retry_same_key'){
    const again=fixture('picker',{autoAck:false,storage:f.storage});await tick();await submit(again);
    assert.equal(again.writes()[0].headers['Idempotency-Key'],key);assert.equal(f.storage.size,1);
    again.acknowledge('/surveys/survey/edit');assert.equal(f.storage.size,0);
  }else if(scenario==='family_target_confirmation'){
    f.acknowledge('/question-bank/family',{kind:'family',data:{question_id:'wrong'}});assert.equal(f.storage.size,1);
    f.acknowledge('/question-bank/family',{kind:'family',data:{question_id:'family'}});assert.equal(f.storage.size,0);
  }else throw new Error('unknown scenario');
  console.log('NAVIGATION_ACK_'+scenario+'=PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
