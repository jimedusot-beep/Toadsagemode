/* iPhone-sized WebKit test of the zero-cost App Studio ZIP download.
   Uses only reviewed templates; no model/API/deploy is called.
*/
'use strict';
const assert = require('node:assert/strict');
const {webkit, devices} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {crc32} = require('../../free-studio/app.js');

const root = path.resolve(__dirname, '../../free-studio');
const allowed = new Set(['/index.html','/styles.css','/app.js','/templates.json','/v2.css','/v2.js','/v3.css','/v3.js']);
const mime = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8'};
const server = http.createServer((req,res) => {
  const pathname = new URL(req.url,'http://localhost').pathname;
  const route = pathname === '/' ? '/index.html' : pathname;
  if (!allowed.has(route)) {res.writeHead(404).end();return;}
  fs.readFile(path.join(root,route.slice(1)),(err,body) => {
    if (err) {res.writeHead(404).end();return;}
    res.writeHead(200,{'Content-Type':mime[path.extname(route)],'Cache-Control':'no-store'});
    res.end(body);
  });
});

function unzipStored(bytes) {
  const view = new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  const decoder = new TextDecoder();
  const files = new Map();
  let pos = 0;
  while (pos+4 <= bytes.length && view.getUint32(pos,true) === 0x04034b50) {
    assert.equal(view.getUint16(pos+8,true),0,'Expected no compression');
    const crc = view.getUint32(pos+14,true);
    const size = view.getUint32(pos+18,true);
    const nameSize = view.getUint16(pos+26,true);
    const extraSize = view.getUint16(pos+28,true);
    const filename = decoder.decode(bytes.subarray(pos+30,pos+30+nameSize));
    assert(!files.has(filename));
    const dataStart = pos+30+nameSize+extraSize;
    const raw = bytes.subarray(dataStart,dataStart+size);
    assert.equal(crc32(raw),crc,'Wrong ZIP CRC for '+filename);
    files.set(filename,decoder.decode(raw));
    pos = dataStart+size;
  }
  assert.equal(view.getUint32(pos,true),0x02014b50,'Expected ZIP central directory');
  return files;
}

(async () => {
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser;
  try {
    browser = await webkit.launch({headless:true});
    const url='http://127.0.0.1:'+server.address().port;
    const context=await browser.newContext({...devices['iPhone 13'],acceptDownloads:true});
    const page=await context.newPage();
    const errors=[];
    const remote=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',request=>{if(!request.url().startsWith(url))remote.push(request.url());});
    await page.goto(url);
    assert.equal(await page.title(),'Toad Sage — Free App Studio');
    await page.waitForFunction(()=>!document.querySelector('#download').disabled);
    assert.match(await page.locator('#status').innerText(),/No API calls or charges/);
    await page.fill('#title','Physics & <Space> Notes');
    assert.equal(await page.inputValue('#slug'),'physics-space-notes');
    await page.fill('#title','Physics & <Space>');
    await page.fill('#slug','physics-space');
    await page.check('input[value="flashcards"]');
    await page.getByRole('button',{name:'Prepare downloadable app ZIP'}).click();
    await page.waitForFunction(() => {
      const node=document.querySelector('#status');
      return node.textContent.includes('ZIP prepared') || node.classList.contains('error');
    },null,{timeout:7000});
    assert.match(await page.locator('#status').innerText(),/ZIP prepared/);
    await page.locator('#download-link').waitFor({state:'visible',timeout:3000});
    const event=page.waitForEvent('download');
    await page.getByRole('link',{name:'Download prepared ZIP'}).click();
    const download=await event;
    assert.equal(download.suggestedFilename(),'physics-space-toad-sage-app.zip');
    const files=unzipStored(fs.readFileSync(await download.path()));
    assert.deepEqual([...files.keys()].sort(),
      ['README.md','app.js','build_report.json','index.html','styles.css']);
    assert(files.get('index.html').includes('Physics &amp; &lt;Space&gt;'));
    assert(files.get('app.js').includes('toad-sage-flashcards-v1:physics-space'));
    assert(files.get('app.js').includes('learned'));
    const report=JSON.parse(files.get('build_report.json'));
    assert.equal(report.kind,'flashcards');
    assert.equal(report.status,'generated_unverified');
    assert.equal(report.paid_requests,0);
    assert.equal(report.deployed,false);
    assert.equal(Object.keys(report.files_sha256).length,4);
    assert.match(await page.locator('#status').innerText(),/ZIP prepared/);

    await page.check('input[value="tasks"]');
    await page.fill('#title','Daily Checklist');
    await page.fill('#slug','daily-checklist');
    await page.getByRole('button',{name:'Prepare downloadable app ZIP'}).click();
    await page.waitForFunction(() => {
      const node=document.querySelector('#status');
      return node.textContent.includes('ZIP prepared') || node.classList.contains('error');
    },null,{timeout:7000});
    assert.match(await page.locator('#status').innerText(),/ZIP prepared/);
    await page.locator('#download-link').waitFor({state:'visible',timeout:3000});
    const taskEvent=page.waitForEvent('download');
    await page.getByRole('link',{name:'Download prepared ZIP'}).click();
    const taskDownload=await taskEvent;
    const tasks=unzipStored(fs.readFileSync(await taskDownload.path()));
    assert(tasks.get('app.js').includes("const KEY = 'toad-sage-tasks-v1:daily-checklist';"));
    assert(tasks.get('index.html').includes('Daily Checklist'));
    assert.equal(JSON.parse(tasks.get('build_report.json')).kind,'tasks');

    await page.check('input[value="notes"]');
    await page.fill('#slug','notes-01');
    await page.getByRole('button',{name:'Prepare downloadable app ZIP'}).click();
    await page.waitForFunction(() => {
      const node=document.querySelector('#status');
      return node.textContent.includes('ZIP prepared') || node.classList.contains('error');
    },null,{timeout:7000});
    assert.match(await page.locator('#status').innerText(),/ZIP prepared/);
    await page.locator('#download-link').waitFor({state:'visible',timeout:3000});
    const notesEvent=page.waitForEvent('download');
    await page.getByRole('link',{name:'Download prepared ZIP'}).click();
    const notesDownload=await notesEvent;
    const notes=unzipStored(fs.readFileSync(await notesDownload.path()));
    assert(notes.get('app.js').includes('toad-sage-notes-v1:notes-01'));
    assert.equal(JSON.parse(notes.get('build_report.json')).kind,'notes');

    await page.fill('#slug','../../bad');
    await page.getByRole('button',{name:'Prepare downloadable app ZIP'}).click();
    await page.waitForFunction(() => document.querySelector('#status').classList.contains('error'),null,{timeout:7000});
    assert.match(await page.locator('#status').innerText(),/App name must use/);
    assert.equal(await page.locator('#download-link').isHidden(),true);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
    assert.deepEqual(errors,[]);
    assert.deepEqual(remote,[]);
    await context.close();

    const broken=await browser.newContext({...devices['iPhone 13']});
    const p=await broken.newPage();
    await p.route('**/templates.json',route=>route.abort());
    await p.goto(url);
    assert.match(await p.locator('#status').innerText(),/could not load/i);
    assert.equal(await p.locator('#download').isDisabled(),true);
    await broken.close();
    console.log('PASS: free browser App Studio WebKit ZIP downloads (tasks/notes/flashcards), CRC, hashes, input validation, network-free, mobile');
  } finally {
    if(browser) await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
