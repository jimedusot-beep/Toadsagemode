'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {previewRoute,previewTitle}=require('../../free-studio/v3.js');

test('allowlisted interactive preview routes are exact and static',()=>{
  const all=[];
  for(const kind of ['tasks','notes','flashcards']){
    for(const theme of ['forest','midnight']){
      all.push(previewRoute(kind,theme));
    }
  }
  assert.equal(new Set(all).size,6);
  assert.deepEqual(all,[
    './previews/tasks-forest/index.html',
    './previews/tasks-midnight/index.html',
    './previews/notes-forest/index.html',
    './previews/notes-midnight/index.html',
    './previews/flashcards-forest/index.html',
    './previews/flashcards-midnight/index.html',
  ]);
  for(const input of [
    ['../../secrets','forest'],['tasks','../../secrets'],['chatbot','forest'],
    ['Tasks','midnight'],['tasks','Forest'],['tasks','https://evil.example']
  ]){
    assert.throws(()=>previewRoute(...input),/Only reviewed app previews/);
  }
});

test('only bounded plain title text may enter the opaque iframe',()=>{
  assert.equal(previewTitle('  My Study Cards  '),'My Study Cards');
  assert.equal(previewTitle('<img src=x onerror=alert(1)>'),'<img src=x onerror=alert(1)>');
  for(const title of [null,undefined,'',' ','A'.repeat(81),'bad\nline',123]){
    assert.equal(previewTitle(title),null);
  }
});
