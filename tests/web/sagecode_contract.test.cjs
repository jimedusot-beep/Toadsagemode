'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {webcrypto}=require('node:crypto');
const api=require('../../free-studio/sagecode-contract-adapter.js');
const input=JSON.parse(fs.readFileSync(path.resolve(__dirname,
  '../../free-studio/sagecode-contract-fixture.json'),'utf8'));
const copy=()=>JSON.parse(JSON.stringify(input));

test('validates the exact SageCode source-only draft shapes with unverified statuses',async()=>{
  const view=api.validateFixture(copy());
  assert.equal(view.origin,'local-fixture-only');
  assert.equal(view.status.verification,'unverified');
  assert.equal(view.status.executed,false);
  assert.equal(view.status.approved,false);
  assert.equal(view.status.release_allowed,false);
  assert.equal(view.status.test_evidence,null);
  assert.equal(view.tree.entries.filter(x=>x.kind==='file').length,2);
  assert.equal(view.sources.length,2);
  const checked=await api.validateHashes(view,webcrypto.subtle);
  assert(checked.results.every(x=>x.check==='fixture_hash_matches'));
  assert.equal(checked.fixture_consistency_only,true);
});

test('rejects forged verification/approval, injected fields or untrusted evidence',()=>{
  const changes=[
    x=>x.status.verification='verified',
    x=>x.status.approved=true,
    x=>x.status.executed=true,
    x=>x.status.release_allowed=true,
    x=>x.status.test_evidence={passed:true},
    x=>x.status.review_status='approved',
    x=>x.proposal.verification='verified',
    x=>x.proposal.release_allowed=true,
    x=>x.proposal.review_status='approved',
    x=>x.proposal.execute=true,
    x=>x.tree.entries[0].local_path='/tmp/secret',
    x=>x.search.matches[0].verified=true,
    x=>x.fixture_schema='sagecode-live-api-v1'
  ];
  for(const mutate of changes){
    const item=copy();mutate(item);
    assert.throws(()=>api.validateFixture(item),/SageCode sample rejected/,mutate.toString());
  }
});

test('cross-revision and cross-project data or false parent ancestry fail closed',()=>{
  const changes=[
    x=>x.tree.revision='c'.repeat(64),
    x=>x.tree.project_id='another-project',
    x=>x.sources[0].revision='c'.repeat(64),
    x=>x.sources[0].project_id='another-project',
    x=>x.search.revision='c'.repeat(64),
    x=>x.search.project_id='another-project',
    x=>x.proposal.parent_revision='c'.repeat(64),
    x=>x.proposal.revision=x.status.revision,
    x=>x.status.revision='not-a-sha',
    x=>x.status.project_id='../host',
    x=>x.tree.entries[2].path='../secrets',
    x=>x.tree.entries[2].path='src\\app.js',
    x=>x.tree.entries[1].path='wrong-directory',
    x=>x.tree.entries.push({...x.tree.entries[2]}),
    x=>x.sources[0].sha256='f'.repeat(64),
    x=>x.sources[0].path='missing.js',
    x=>x.search.matches[0].path='unknown.js',
    x=>x.search.matches[0].line=0,
    x=>x.search.matches[0].line=999,
  ];
  for(const mutate of changes){
    const item=copy();mutate(item);
    assert.throws(()=>api.validateFixture(item),/SageCode sample rejected/,mutate.toString());
  }
});

test('complete source mismatch against actual SHA-256 fails even if metadata matches',async()=>{
  const item=copy();
  item.sources[1].content='print("Hello, SageStudio!")\n'; // same byte count
  // even if byte count happens to differ, ensure the adapter never accepts it.
  const source=item.sources[1];
  item.tree.entries[2].bytes=new TextEncoder().encode(source.content).length;
  const view=api.validateFixture(item);
  await assert.rejects(api.validateHashes(view,webcrypto.subtle),/SHA-256 mismatch/);
});

test('partial source is labeled uncheckable, not falsely verified',async()=>{
  const item=copy();
  const s=item.sources[1];
  s.start_line=2;s.total_lines=15;s.content='print("partial")\n';s.truncated=true;
  const checked=await api.validateHashes(api.validateFixture(item),webcrypto.subtle);
  assert.equal(checked.results[1].check,'partial_view_not_hash_verified');
  assert.equal(checked.results[0].check,'fixture_hash_matches');
});

test('invalid full source lengths, bytes, limits and unsafe paths fail closed',()=>{
  const bad=[
    x=>x.sources[0].start_line=2,
    x=>x.sources[0].total_lines=400,
    x=>x.sources[0].content='oversized '.repeat(2000),
    x=>x.sources[0].truncated='false',
    x=>x.tree.entries[0].bytes=10000000,
    x=>x.tree.entries[2].sha256='bad-sha',
    x=>x.search.matches[0].kind='executable',
    x=>x.search.matches[0].snippet='<'.repeat(201),
    x=>x.search.limited='false',
    x=>x.proposal.truncated='false',
    x=>x.proposal.diff='x'.repeat(30001)
  ];
  for(const mutate of bad){
    const item=copy();mutate(item);
    assert.throws(()=>api.validateFixture(item),/SageCode sample rejected/,mutate.toString());
  }
  assert.equal(api.countLines('a\nb\n'),2);
  assert.equal(api.countLines('a'),1);
  assert.equal(api.countLines(''),0);
});

test('only exact fixture path is fetched, and missing/bad data is blocked',async()=>{
  const result=await api.loadFixture(async(url,opts)=>{
    assert.equal(url,'./sagecode-contract-fixture.json');
    assert.deepEqual(opts,{cache:'no-store'});
    return {ok:true,headers:{get:()=>null},text:async()=>JSON.stringify(copy())};
  },webcrypto.subtle);
  assert.equal(result.results.length,2);
  await assert.rejects(api.loadFixture(async()=>({ok:false}),webcrypto.subtle),/unavailable/);
  await assert.rejects(api.loadFixture(async()=>({
    ok:true,headers:{get:()=>null},text:async()=>'{broken'
  }),webcrypto.subtle),/fixture JSON not valid/);
  await assert.rejects(api.loadFixture(async()=>({
    ok:true,headers:{get:()=>null},text:async()=>JSON.stringify(copy())
  }),null),/SHA-256 unavailable/);
});

test('empty SageCode project stays unverified and contains no invented source',async()=>{
  const item=copy();
  item.tree.entries=[];item.sources=[];item.search.matches=[];item.proposal=null;
  const checked=await api.validateHashes(api.validateFixture(item),webcrypto.subtle);
  assert.equal(checked.results.length,0);
  assert.equal(checked.view.status.test_evidence,null);
});


test('a final paginated source window is partial even when truncated=false',async()=>{
  const item=copy();
  const source=item.sources[1];
  source.start_line=5;
  source.total_lines=10;
  source.content='last line\n';
  source.truncated=false; // Agent A: no later page, but earlier pages omitted
  const value=api.validateFixture(item);
  const checked=await api.validateHashes(value,webcrypto.subtle);
  assert.equal(checked.results[1].check,'partial_view_not_hash_verified');
  assert.equal(value.sources[1].start_line,5);
  assert.equal(value.sources[1].truncated,false);
});

test('a changed proposal must contain an inspectable diff, even when truncated',()=>{
  for (const diff of ['', '   ', '\n']) {
    const item=copy();
    item.proposal.diff=diff;
    assert.throws(()=>api.validateFixture(item),/changed proposal without a readable diff/);
    item.proposal.truncated=true;
    assert.throws(()=>api.validateFixture(item),/changed proposal without a readable diff/);
  }
});

test('partial source windows cannot claim bytes outside manifest or lines beyond total',()=>{
  for (const change of [
    source=>{source.start_line=999;},
    source=>{source.content='x'.repeat(200);},
    source=>{source.start_line=3;source.total_lines=3;source.content='a\nb\n';}
  ]) {
    const item=copy();
    const source=item.sources[1];
    source.start_line=2;source.total_lines=10;source.truncated=false;
    source.content='x\n';
    change(source);
    assert.throws(()=>api.validateFixture(item),/SageCode sample rejected/);
  }
});

test('empty project and empty source are accepted without claiming verification',async()=>{
  const value=copy();
  value.tree.entries=[];
  value.sources=[];
  value.search.matches=[];
  value.proposal=null;
  const checked=await api.validateHashes(api.validateFixture(value),webcrypto.subtle);
  assert.equal(checked.results.length,0);
  assert.equal(checked.view.status.approved,false);
  assert.equal(checked.view.status.verification,'unverified');
});

test('repeated read-only fixture inspections cannot create executed or approved state',async()=>{
  for(let i=0;i<5;i++){
    const checked=await api.validateHashes(api.validateFixture(copy()),webcrypto.subtle);
    assert.equal(checked.view.status.executed,false);
    assert.equal(checked.view.status.approved,false);
    assert.equal(checked.view.status.test_evidence,null);
  }
});
