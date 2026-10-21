'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const E=require('../../web/empathy.js');
const legacy=require('../../empathy/examples.json');
test('legacy empathy examples migrate as unreviewed data with unknown metadata',()=>{
  const source=structuredClone(legacy);source.owner='Jimmy';source.examples[0].custom={keep:true};
  const result=E.merge(E.empty(),source);
  assert.equal(result.lessons.length,7);assert.equal(result.lessons[0].review_status,'needs_review');
  assert.deepEqual(result.lessons[0].custom,{keep:true});assert.equal(result.imports[0].owner,'Jimmy');
});
test('review is local, edits invalidate it, and import cannot authorize retrieval',()=>{
  const data=E.merge(E.empty(),require('../../empathy/lessons.json'));
  const adult=data.lessons[0],child=data.lessons[1];
  E.review(adult,'helpful','Human checked');E.review(child,'helpful','Human checked');
  assert.equal(E.retrieve(data,'project', 'adult').length,1);
  assert.equal(E.retrieve(data,'turn', 'adult').some(x=>x.id===child.id),false);
  const restored=E.merge(E.empty(),data);
  assert.equal(E.retrieve(restored,'project','adult').length,0);
  const edited=E.edit(adult,{technique:'Ask first'});
  assert.equal(edited.review_status,'needs_review');assert.equal(edited.version,2);
  assert.equal(edited.previous_versions[0].technique,adult.technique);
});
test('bad imports are refused atomically and oversized or malformed fields fail',()=>{
  const data=E.empty();
  assert.throws(()=>E.merge(data,{schema:E.SCHEMA,lessons:[{material:'valid'},{material:7}]}));
  assert.equal(data.lessons.length,0);
  assert.throws(()=>E.note('x'.repeat(250001),'adult'));
  assert.throws(()=>E.note('test','robot'));
});
test('paired human assessment requires both responses and complete rubric ratings',()=>{
  const scenario=require('../../empathy/practice.json').scenarios[0];
  assert.throws(()=>E.assessment(scenario,'baseline','',{},[]));
  const scores=Object.fromEntries(E.RUBRIC.map(k=>[k,{baseline:1,retrieved:2}]));
  const result=E.assessment(scenario,'baseline','retrieved',scores,[]);
  assert.equal(result.origin,'human_self_report');assert.equal(result.improvement,null);
  assert.deepEqual(result.model_ratings,[]);assert.equal(result.split,'practice');
});
test('large corrected lessons restore and source corrections preserve unknown metadata',()=>{
  const data=E.empty();data.lessons.push(E.note('x'.repeat(160000),'adult',{kind:'user_notes',custom:{keep:true}}));
  data.lessons[0]=E.edit(data.lessons[0],{title:'First',source:{label:'New label'}});
  data.lessons[0]=E.edit(data.lessons[0],{title:'Second'});
  assert.equal(E.validate(data).lessons[0].source.custom.keep,true);
  const restored=E.merge(E.empty(),data);
  assert.equal(restored.lessons[0].material.length,160000);
  assert.equal(restored.lessons[0].imported_claims.previous_versions.length,2);
});
