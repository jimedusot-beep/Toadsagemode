'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const Catalog = require('../../web/catalog.js');

test('paste creates a named unverified Python candidate without running it', () => {
  const r = Catalog.createCandidate('```python\nprint("hello")\n```');
  assert.equal(r.language, 'Python');
  assert.ok(r.name.length > 1);
  assert.equal(r.installed, false);
  assert.equal(r.verification, 'unverified');
  assert.equal(r.manifest.files[0].content, 'print("hello")\n');
  assert.ok(r.history.some(x => x.event === 'received'));
  assert.ok(r.history.some(x => x.event === 'inspected'));
});

test('invalid JSON and HTML are saved as text with honest syntax information', () => {
  const bad = Catalog.createCandidate('{"broken":');
  assert.equal(bad.status, 'needs_review');
  assert.ok(bad.validation_results.errors.length);
  const html = Catalog.createCandidate('<img src=x onerror="window.evil=1">');
  assert.equal(html.language, 'HTML');
  assert.equal(html.content, '<img src=x onerror="window.evil=1">');
});

test('legacy backups migrate without discarding unknown data or trusting status', () => {
  const lib = Catalog.normalizeLibrary({schema:'toad-library-v1', extra:'keep', abilities:[{
    name:'old-demo', version:'0.1.0', content:'print(1)', kind:'Python', status:'unverified', installed:false,
    source:'Gemini', custom:{a:1}
  }]});
  assert.equal(lib.schema, 'toad-library-v2');
  assert.equal(lib.abilities[0].source, 'Gemini');
  assert.equal(lib.abilities[0].extensions.original.custom.a, 1);
  assert.equal(lib.extensions.original.extra, 'keep');
  const modified = JSON.parse(JSON.stringify(lib));
  modified.abilities[0].status='installed'; modified.abilities[0].installed=true;
  modified.abilities[0].test_results=[{passed:true}];
  const again=Catalog.normalizeLibrary(modified);
  assert.notEqual(again.abilities[0].status, 'installed');
  assert.equal(again.abilities[0].installed, false);
  assert.equal(again.abilities[0].test_results.length, 0);
  assert.equal(again.abilities[0].extensions.original.test_results[0].passed, true);
});

test('duplicate imports merge additively and cannot erase existing entries', () => {
  const a=Catalog.createCandidate('Remember to build a calculator.');
  const b=Catalog.createCandidate('Review sensor readings.');
  const initial={schema:'toad-library-v2',abilities:[a]};
  const merged=Catalog.mergeLibraries(initial,{schema:'toad-library-v2',abilities:[a,b]});
  assert.equal(merged.library.abilities.length,2);
  assert.equal(merged.added,1);
  assert.equal(merged.duplicates,1);
});

test('portable path aliases, duplicate names and oversized packages are rejected', () => {
  const base={schema:'toad-ability-v2',name:'demo',version:'0.1.0',files:[{path:'main.py',content:'print(1)'}],entrypoint:'main.py',tests:[],permissions:[],dependencies:[]};
  for(const p of ['../evil.py','/abs.py','C:/drive.py','a\\evil.py','toad_core/hack.py','CON.py','a/../b.py','a//b.py','a./b.py']){
    assert.throws(()=>Catalog.normalizeManifest({...base,files:[{path:p,content:'x'}],entrypoint:p}),/path|protected|portable/i);
  }
  assert.throws(()=>Catalog.normalizeManifest({...base,files:[{path:'main.py',content:'a'},{path:'MAIN.py',content:'b'}]}),/duplicate/i);
  assert.throws(()=>Catalog.createCandidate('x'.repeat(250001)),/limit|large|250/i);
  assert.throws(()=>Catalog.normalizeManifest({...base,permissions:[{admin:true}]}),/permission/i);
});

test('multiple named code blocks become separate files and preserve the source', () => {
  const raw='```python main.py\nprint(1)\n```\n```python tests/test_demo.py\nimport unittest\n```';
  const r=Catalog.createCandidate(raw);
  assert.deepEqual(r.manifest.files.map(f=>f.path),['main.py','tests/test_demo.py']);
  assert.equal(r.content,raw);
  assert.equal(r.verification,'unverified');
});

test('malformed backup refuses all entries rather than partially importing', () => {
  assert.throws(()=>Catalog.normalizeLibrary({schema:'toad-library-v2',abilities:[{name:'bad',content:43}]}),/record|content|ability/i);
  assert.throws(()=>Catalog.normalizeLibrary({schema:'made-up',abilities:[]}),/schema|format/i);
});

test('invalid structured manifest cannot silently become a different input', () => {
  const p={schema:'toad-ability-v2',name:'demo',version:'0.1.0',files:[{path:'main.py',content:'print(1)'}],entrypoint:'main.py',permissions:[],dependencies:[],tests:[{kind:'python',path:'main.py'}]};
  assert.throws(()=>Catalog.createCandidate(JSON.stringify(p)),/expected_stdout|test/i);
});

test('browser and Python use the same permission and dependency contract', () => {
  const p={schema:'toad-ability-v2',name:'demo',version:'0.1.0',files:[{path:'main.py',content:'print(1)'}],entrypoint:'main.py',permissions:[],dependencies:[],tests:[]};
  assert.throws(()=>Catalog.normalizeManifest({...p,dependencies:['--index-url=https://example.com']}),/dependenc/i);
  assert.throws(()=>Catalog.normalizeManifest({...p,permissions:['../core']}),/permission/i);
});

test('v2 backup can retain a large structured-package original within package limits', () => {
  const content=JSON.stringify({padding:'x'.repeat(260000)});
  const a=Catalog.createCandidate('placeholder');
  a.content=content;
  a.manifest=Catalog.normalizeManifest({schema:'toad-ability-v2',name:'demo',version:'0.1.0',files:[{path:'a.py',content:'#'+ 'a'.repeat(130000)},{path:'b.py',content:'#'+'b'.repeat(130000)}],entrypoint:'a.py',permissions:[],dependencies:[],tests:[]});
  const lib=Catalog.normalizeLibrary({schema:'toad-library-v2',abilities:[a]});
  assert.equal(lib.abilities[0].content,content);
});
