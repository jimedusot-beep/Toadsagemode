'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const adapter = require('../../free-studio/explorer-adapter.js');

const fixturePath = path.resolve(__dirname, '../../free-studio/explorer-fixtures.json');
const catalog = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));
const original = () => adapter.validateCatalog(JSON.parse(JSON.stringify(catalog))).projects[0];

test('SageCode-shaped fixture filename search uses line zero, never a backend revision', () => {
  const result = adapter.searchFixtureProject(original(), 'SRC', 50);
  assert.equal(result.project_id, 'study-planner');
  assert.equal(result.revision, null);
  assert.equal(result.source, 'local-fixture-only');
  assert.equal(result.term, 'SRC');
  assert.equal(result.limited, false);
  assert.deepEqual(result.matches, [{
    path:'src/app.js', line:0, snippet:'src/app.js', kind:'filename'
  }]);
});

test('content matches preserve one-based source lines, snippets and sorted paths', () => {
  const project = original();
  const matched = adapter.searchFixtureProject(project, 'START', 50);
  assert(matched.matches.length >= 1);
  assert(matched.matches.some(m =>
    m.path === 'src/app.js' && m.kind === 'content' &&
    m.line === 2 && m.snippet.includes('Start with one task.')));
  assert(matched.matches.every(x => Number.isInteger(x.line) && x.line >= 0));
  const no = adapter.searchFixtureProject(project, 'not-found-111-xyz', 50);
  assert.deepEqual(no.matches, []);
  assert.equal(no.limited, false);
});

test('50 hit cap is explicit and may hide more hits', () => {
  const project = original();
  project.files[0].content = Array.from({length:85},(_,i)=>'needle '+i).join('\n');
  const result = adapter.searchFixtureProject(project, 'needle');
  assert.equal(result.matches.length,50);
  assert.equal(result.limited,true);
  assert.deepEqual(result.matches.map(m=>m.line), Array.from({length:50},(_,i)=>i+1));
  const one = adapter.searchFixtureProject(project, 'needle', 1);
  assert.equal(one.matches.length,1);
  assert.equal(one.limited,true);
});

test('search refuses whitespace-only, control characters, 100-byte overflow and bad limits', () => {
  for(const term of ['', ' ', '\t', 'contains\nnewline', '\u007f', '🦉'.repeat(26)]) {
    assert.throws(()=>adapter.searchFixtureProject(original(),term),/Fixture invalid/);
  }
  for (const limit of [0, 101, NaN, 1.1, true, '50', null]) {
    assert.throws(()=>adapter.searchFixtureProject(original(),'tip',limit),/Fixture invalid/);
  }
  const hundred = 'x'.repeat(100);
  assert.doesNotThrow(()=>adapter.searchFixtureProject(original(),hundred));
});

test('invalid project and unbounded file content cannot bypass search controls', () => {
  assert.throws(()=>adapter.searchFixtureProject(null,'tip'),/Fixture invalid/);
  const project = original();
  project.files[0].content = 'x'.repeat(12001);
  assert.throws(()=>adapter.searchFixtureProject(project,'tip'),/Fixture invalid/);
  const tooMany = original();
  tooMany.files = Array.from({length:25},(_,i)=>({path:'file'+i+'.js',content:''}));
  assert.throws(()=>adapter.searchFixtureProject(tooMany,'test'),/Fixture invalid/);
});

test('inert malicious-looking source search only returns text', () => {
  const project = original();
  const injection = '<img src=x onerror="window.explorerXss=true">';
  project.files[0].content = injection + '\n' + injection;
  const result = adapter.searchFixtureProject(project,'onerror');
  assert.equal(result.matches.length,2);
  assert.equal(result.matches[0].snippet,injection);
  assert.equal(result.matches[1].line,2);
  assert.equal(result.source,'local-fixture-only');
});
