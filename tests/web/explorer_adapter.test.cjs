'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const adapter = require('../../free-studio/explorer-adapter.js');

const file = path.resolve(__dirname, '../../free-studio/explorer-fixtures.json');
const original = JSON.parse(fs.readFileSync(file, 'utf8'));
const copy = () => JSON.parse(JSON.stringify(original));

test('fixture adapter validates a real multi-file catalog and defensive copy', () => {
  const data = adapter.validateCatalog(copy());
  assert.equal(data.schema, 'toad-sage-explorer-fixture-v1');
  assert.equal(data.source, 'local-fixture-only');
  assert(data.projects.length >= 4);
  assert.deepEqual(data.projects.map(p => p.state), ['draft','failed','verified','testing','untested']);
  assert(data.projects[0].files.some(f => f.path === 'src/app.js'));
  assert.equal(data.projects.at(-1).files.length, 0);
  assert.equal(data.projects.at(-1).revision, null);
  original.projects[0].title = 'Still fixture';
  assert.notEqual(data.projects[0].title, 'Still fixture');
});

test('before/after text diff marks additions, removals and identical lines', () => {
  const entries = adapter.diffLines('keep\nold\nend', 'keep\nnew\nend');
  assert.deepEqual(entries.map(x => x.kind), ['same','removed','added','same']);
  assert.equal(entries[1].text, 'old');
  assert.equal(entries[2].text, 'new');
  assert.equal(adapter.diffLines('same', 'same')[0].kind, 'same');
});

test('adapter rejects path escapes, duplicates and phantom revision targets', () => {
  const bad = [
    x => x.projects[0].files[0].path = '../secrets',
    x => x.projects[0].files[0].path = '/absolute.js',
    x => x.projects[0].files[0].path = 'dir//app.js',
    x => x.projects[0].files[0].path = 'dir/./app.js',
    x => x.projects[0].files[0].path = 'dir\\app.js',
    x => x.projects[0].files[1].path = x.projects[0].files[0].path,
    x => x.projects[0].revision.path = 'fake.js',
    x => x.projects[0].revision.before = 'mismatched file content',
  ];
  for (const mutate of bad) {
    const specimen = copy();
    mutate(specimen);
    assert.throws(() => adapter.validateCatalog(specimen), /Fixture invalid/, mutate.toString());
  }
});

test('unsupported states, hidden fields and forged/missing data are refused', () => {
  const bad = [
    x => x.schema = 'toad-sage-live-backend-v1',
    x => x.projects[0].state = 'shipped',
    x => x.projects[0].test.status = 'passed',
    x => x.projects[0].revision.test.output = 3,
    x => x.projects[0].revision.status = 'released',
    x => x.projects[1].id = x.projects[0].id,
    x => x.projects[0].source_url = 'https://bad.example',
    x => x.projects[0].files[0].execute = true,
    x => x.projects[0].files = null,
    x => x.projects[0].files[0].content = 'x'.repeat(12001),
    x => x.projects[0].summary = '<'.repeat(241),
    x => x.projects = [...x.projects, ...Array.from({length: 20}, (_, i) => ({
      ...x.projects[0], id:'extra-' + i
    }))],
  ];
  for (const mutate of bad) {
    const specimen = copy();
    mutate(specimen);
    assert.throws(() => adapter.validateCatalog(specimen), /Fixture invalid/, mutate.toString());
  }
});

test('model-looking HTML or JavaScript is returned as inert strings, never interpreted', () => {
  const specimen = copy();
  const attack = '<img src=x onerror="window.explorerXss=true">';
  specimen.projects[0].files[0].content = attack;
  const normal = adapter.validateCatalog(specimen);
  assert.equal(normal.projects[0].files[0].content, attack);
  assert.equal(normal.source, 'local-fixture-only');
});

test('empty catalog is allowed and can be shown without false verification', () => {
  const value = adapter.validateCatalog({schema: adapter.SCHEMA, projects: []});
  assert.deepEqual(value.projects, []);
});

test('source loader fetches exact relative fixture route and never invents a backend', async () => {
  let calls = 0;
  const result = await adapter.loadFixtures(async (url, opts) => {
    calls++;
    assert.equal(url, './explorer-fixtures.json');
    assert.deepEqual(opts, {cache:'no-store'});
    return {ok:true, headers:{get:()=>null}, text:async()=>JSON.stringify(copy())};
  });
  assert.equal(calls,1);
  assert.equal(result.projects.length, 5);
  await assert.rejects(adapter.loadFixtures(async()=>({ok:false})), /unavailable/);
  await assert.rejects(adapter.loadFixtures(async()=>({
    ok:true,headers:{get:()=>null},text:async()=>'{not-json'
  })), /valid JSON/);
  await assert.rejects(adapter.loadFixtures(async()=>({
    ok:true,headers:{get:()=>String(99999999)},text:async()=>{throw Error('read should not happen');}
  })), /too large/);
});
