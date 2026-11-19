'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const catalog=require('../../free-studio/templates.json');
const {
  validateCatalog,validateInput,makeSources,makePackage,makeZip,
  readBuildOptions,verifyDownloadedZip,suggestedSlug,crc32
}=require('../../free-studio/app.js');

test('trusted browser catalog is strictly limited to three exact kinds',()=>{
  assert.equal(validateCatalog(catalog).schema,'toad-free-studio-templates-v1');
  assert.throws(()=>validateCatalog({...catalog,templates:{tasks:catalog.templates.tasks}}));
  assert.throws(()=>validateInput({name:'../bad',kind:'flashcards',theme:'forest',title:'safe'}));
  assert.equal(suggestedSlug('Physics & <Space>'),'physics-space');
});

test('stored ZIP accepts only the five exact reviewed files, including README.md',()=>{
  const source={
    'index.html':'<html></html>',
    'styles.css':'body{}',
    'app.js':'console.log("trusted")',
    'README.md':'# Test',
    'build_report.json':'{}',
  };
  const zip=makeZip(source);
  const view=new DataView(zip.buffer);
  assert.equal(view.getUint32(0,true),0x04034b50);
  assert.equal(view.getUint32(zip.length-22,true),0x06054b50);
  assert.equal(view.getUint16(zip.length-12,true),5);
  assert.equal(crc32(new TextEncoder().encode('abc')),0x352441c2);
  assert.throws(()=>makeZip({...source,'malicious.js':'alert(1)'}));
  assert.throws(()=>makeZip({'README.md':'only'}));
});

test('all three reviewed app bundles generate bounded no-cost ZIPs',async()=>{
  for(const kind of ['tasks','notes','flashcards']){
    const name=kind+'-demo';
    const result=await makePackage(catalog,{kind,name,title:'A & <B>',theme:'midnight'});
    assert.equal(result.report.kind,kind);
    assert.equal(result.report.status,'generated_unverified');
    assert.equal(result.report.paid_requests,0);
    assert.equal(result.report.deployed,false);
    assert(result.files['README.md'].includes('standalone'));
    assert(result.files['index.html'].includes('A &amp; &lt;B&gt;'));
    assert(result.files['app.js'].includes('toad-sage-'+kind+'-v1:'+name));
    assert(result.zip.length > 5000);
    assert.equal(Object.keys(result.report.files_sha256).length,4);
  }
});

test('the exact downloaded ZIP matches reviewed template bytes without execution',async()=>{
  for(const kind of ['tasks','notes','flashcards']){
    const options={kind,name:kind+'-student',title:'Study & <Verify>',theme:'forest'};
    const built=await makePackage(catalog,options);
    assert.deepEqual(readBuildOptions(built.zip),options);
    const review=await verifyDownloadedZip(catalog,built.zip);
    assert.equal(review.status,'source_matches_current_reviewed_catalog');
    assert.equal(review.kind,kind);
    assert.match(review.zip_sha256,/^[0-9a-f]{64}$/);
    assert.equal(review.source_executed,false);
    assert.equal(review.individual_app_browser_tested,false);
    assert.equal(review.deployed,false);
    assert.equal(review.owner_review_required,true);
  }
});

test('corrupted, oversized, incompatible and self-consistent modified ZIPs fail closed',async()=>{
  const options={kind:'tasks',name:'study-tasks',title:'My Tasks',theme:'midnight'};
  const built=await makePackage(catalog,options);
  const corrupted=built.zip.slice();
  corrupted[50]^=1;
  await assert.rejects(verifyDownloadedZip(catalog,corrupted),/checksum|match|format/i);
  await assert.rejects(verifyDownloadedZip(catalog,new Uint8Array(400001)),/supported small/);
  await assert.rejects(verifyDownloadedZip(catalog,new Uint8Array(5)),/supported small/);
  const modified={...built.files,'app.js':built.files['app.js']+'\\nalert(1);'};
  const forgedZip=makeZip(modified); // Valid ZIP CRCs, but source differs from trusted catalog.
  await assert.rejects(verifyDownloadedZip(catalog,forgedZip),/does not match/);
  assert.throws(()=>makeZip({...built.files,'secret.env':'not allowed'}),/manifest/);
});
