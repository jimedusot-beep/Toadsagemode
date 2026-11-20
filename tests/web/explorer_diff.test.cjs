'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {compareSource, diffLines} = require('../../free-studio/explorer-adapter.js');

const kinds = result => result.lines.map(item => item.kind);

test('disjoint changes retain unchanged middle lines and count two exact hunks', () => {
  const before = 'start\nold first\nmiddle untouched\nold second\nend';
  const after = 'start\nnew first\nmiddle untouched\nnew second\nend';
  const result = compareSource(before, after);
  assert.equal(result.mode, 'exact');
  assert.equal(result.added, 2);
  assert.equal(result.removed, 2);
  assert.equal(result.hunks, 2);
  assert.deepEqual(kinds(result),
    ['same','removed','added','same','removed','added','same']);
  assert.equal(result.lines[3].text, 'middle untouched');
  assert.deepEqual(diffLines(before, after), result.lines);
});

test('independently reconstructs original and proposed source from tagged lines', () => {
  const specimens = [
    ['', 'hello'],
    ['hello', ''],
    ['same', 'same'],
    ['a\nb\nc', 'a\nnew\nb\nc'],
    ['a\nb\nc', 'a\nc'],
    ['a\nb\na\nb', 'b\na\nb\nb'],
    ['end\n', 'end'],
    ['line\n\nline', 'line\nnew\nline']
  ];
  for (const [before, after] of specimens) {
    const result = compareSource(before, after);
    const original = result.lines.filter(x => x.kind !== 'added').map(x => x.text).join('\n');
    const revised = result.lines.filter(x => x.kind !== 'removed').map(x => x.text).join('\n');
    assert.equal(original, before);
    assert.equal(revised, after);
    assert.equal(result.mode, 'exact');
  }
});

test('single-sided insertions and deletions remain exact with no matrix', () => {
  const insertion = compareSource('start\nend', 'start\nnew\nend');
  assert.deepEqual(kinds(insertion), ['same','added','same']);
  assert.equal(insertion.mode,'exact');
  const deletion = compareSource('start\nremove\nend', 'start\nend');
  assert.deepEqual(kinds(deletion), ['same','removed','same']);
  assert.equal(deletion.mode,'exact');
});

test('large internal edit is explicitly coarse, never falsely called an exact line diff', () => {
  const before = 'start\n' + Array.from({length:500},(_,i)=>'old'+i).join('\n') + '\nend';
  const after = 'start\n' + Array.from({length:500},(_,i)=>'new'+i).join('\n') + '\nend';
  const result = compareSource(before, after);
  assert.equal(result.mode, 'coarse');
  assert.equal(result.lines[0].text,'start');
  assert.equal(result.lines.at(-1).text,'end');
  assert.equal(result.added,500);
  assert.equal(result.removed,500);
  assert.equal(result.hunks,1);
  assert.equal(result.lines.filter(x=>x.kind==='removed').map(x=>x.text).length,500);
  assert.equal(result.lines.filter(x=>x.kind==='added').map(x=>x.text).length,500);
});

test('long repeated common source creates no unbounded LCS matrix', () => {
  const content = 'x\n'.repeat(5800);
  const result = compareSource(content, content);
  assert.equal(result.mode,'exact');
  assert.equal(result.added,0);
  assert.equal(result.removed,0);
  assert.equal(result.hunks,0);
  assert.equal(result.lines.length,5801);
});

test('comparison rejects unbounded or malformed source', () => {
  assert.throws(()=>compareSource(null, 'ok'),/bounded source text/);
  assert.throws(()=>compareSource('ok', {}),/bounded source text/);
  assert.throws(()=>compareSource('x'.repeat(12001),'ok'),/bounded source text/);
});
