'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {
  KEY,SCHEMA,MAX_PROJECTS,validProject,parseProjects,makeRecord,
  upsertProject,serializeProjects,describeKind
}=require('../../free-studio/v2.js');

const when='2026-11-18T12:30:10.000Z';
const record=(name,kind='flashcards')=>makeRecord({
  name,title:'Useful & <Study>',kind,theme:'forest'
},when);

test('only bounded, strictly shaped settings can be stored',()=>{
  const good=record('study-cards');
  assert.equal(validProject(good),true);
  assert.equal(good.savedAt,when);
  assert.equal(KEY,'toad-sage-free-studio-projects-v1');
  assert.equal(MAX_PROJECTS,20);
  assert.equal(describeKind('notes'),'Notes');
  assert.equal(validProject({...good,secret:'accidental-secret'}),false);
  assert.equal(validProject({...good,name:'../bad'}),false);
  assert.equal(validProject({...good,title:'bad\nline'}),false);
  assert.equal(validProject({...good,kind:'chatbot'}),false);
  assert.throws(()=>makeRecord({name:'x',title:'A',kind:'tasks',theme:'forest'},when));
});

test('save/load round trips and preserves explicit app kind per slug',()=>{
  const initial=[record('study-cards')];
  const saved=serializeProjects(initial);
  assert.deepEqual(parseProjects(saved),initial);
  assert.deepEqual(parseProjects(null),[]);
  assert.equal(JSON.parse(saved).schema,SCHEMA);
  const revised=makeRecord({name:'study-cards',title:'Renamed',kind:'flashcards',theme:'midnight'},when);
  const updated=upsertProject(initial,revised);
  assert.equal(updated.length,1);
  assert.equal(updated[0].theme,'midnight');
  assert.throws(()=>upsertProject(initial,record('study-cards','tasks')),/different app type/);
  assert.equal(upsertProject(updated,record('my-tasks','tasks')).length,2);
});

test('invalid or corrupt project storage never becomes a valid empty library',()=>{
  const item=record('study-cards');
  const malformed=[
    '{bad','[]','{}',
    JSON.stringify({schema:'bad',projects:[item]}),
    JSON.stringify({schema:SCHEMA,projects:[item,item]}),
    JSON.stringify({schema:SCHEMA,projects:[{...item,title:''}]}),
    JSON.stringify({schema:SCHEMA,projects:[{...item,apiKey:'leak'}]}),
    'x'.repeat(12001)
  ];
  for(const example of malformed){
    assert.throws(()=>parseProjects(example));
  }
  assert.throws(()=>serializeProjects([item,item]));
});

test('project capacity is fixed at twenty and no code files are stored',()=>{
  let projects=[];
  for(let i=0;i<MAX_PROJECTS;i++) projects=upsertProject(projects,record('app-'+i));
  assert.equal(projects.length,20);
  assert.throws(()=>upsertProject(projects,record('app-extra')),/at most 20/);
  const snapshot=serializeProjects(projects);
  assert(snapshot.length<12000);
  assert.deepEqual(Object.keys(JSON.parse(snapshot)),['schema','projects']);
  assert.equal(snapshot.includes('app.js'),false);
  assert.equal(snapshot.includes('OPENAI_API_KEY'),false);
});
