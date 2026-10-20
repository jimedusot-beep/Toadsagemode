/* Trusted app interaction tests. Never executes submitted source. */
'use strict';
const {webkit,chromium,devices}=require('playwright');
const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=process.env.TOAD_SITE_ROOT?path.resolve(process.env.TOAD_SITE_ROOT):path.resolve(__dirname,'../..');
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css'};
const server=http.createServer((req,res)=>{
  const relative=decodeURIComponent(new URL(req.url,'http://localhost').pathname).replace(/^\//,'')||'index.html';
  const file=path.resolve(root,relative);
  if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}
  fs.readFile(file,(e,body)=>{if(e){res.writeHead(404).end();return;}res.setHeader('Content-Type',mime[path.extname(file)]||'text/plain');res.end(body);});
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base=process.env.TOAD_BASE_URL || 'http://127.0.0.1:'+server.address().port;
  let browser;
  try{
    const type=process.env.TOAD_BROWSER==='chromium'?chromium:webkit;
    browser=await type.launch({headless:true,...(process.env.TOAD_BROWSER_EXECUTABLE?{executablePath:process.env.TOAD_BROWSER_EXECUTABLE}:{})});
    await require('./phone-flows.cjs')(browser,base);
    const context=await browser.newContext({...devices['iPhone 13'],acceptDownloads:true});
    const page=await context.newPage(), errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base);
    await page.fill('#feedinput','```python\nprint("hello")\n```');
    await page.getByRole('button',{name:'Feed Toad',exact:true}).click({timeout:3000});
    await page.waitForFunction(()=>!document.querySelector('#captureability').disabled);
    assert.match(await page.locator('#abilitymessage').innerText(),/saved.*locally/i);
    assert.equal(await page.locator('[data-ability-id]').count(),1);
    await page.reload();
    assert.equal(await page.locator('[data-ability-id]').count(),1);
    await page.fill('#feedinput','```python\nprint("hello")\n```');
    await page.getByRole('button',{name:'Feed Toad',exact:true}).click();
    await page.waitForFunction(()=>!document.querySelector('#captureability').disabled);
    assert.match(await page.locator('#abilitymessage').innerText(),/already|duplicate/i);
    assert.equal(await page.locator('[data-ability-id]').count(),1);
    await page.fill('#feedinput','<img src=x onerror="window.feedExecuted=true">');
    await page.getByRole('button',{name:'Feed Toad',exact:true}).click();
    await page.waitForFunction(()=>!document.querySelector('#captureability').disabled);
    assert.equal(await page.evaluate(()=>Boolean(window.feedExecuted)),false);
    await page.fill('#searchabilities','hello');
    assert.equal(await page.locator('[data-ability-id]').count(),1);
    await page.fill('#searchabilities','');
    await page.locator('[data-ability-id]').first().getByRole('button',{name:'Archive',exact:true}).click();
    assert.equal(await page.locator('[data-ability-id]').count(),1);
    await page.selectOption('#statusfilter','archived');
    assert.equal(await page.locator('[data-ability-id]').count(),1);
    await page.selectOption('#statusfilter','');
    const downloadWait=page.waitForEvent('download');
    await page.getByRole('button',{name:'Export backup',exact:true}).click();
    const download=await downloadWait;
    const raw=fs.readFileSync(await download.path(),'utf8');
    assert.equal(JSON.parse(raw).abilities.length,2);
    const exported=process.env.TOAD_BROWSER_EXPORT;
    if(exported)fs.writeFileSync(exported,raw);
    // Quota failures preserve the feed and do not claim success.
    await page.evaluate(()=>{Storage.prototype.setItem=function(){throw new DOMException('full','QuotaExceededError');};});
    await page.fill('#feedinput','Keep me after a failed save');
    await page.getByRole('button',{name:'Feed Toad',exact:true}).click();
    await page.waitForFunction(()=>!document.querySelector('#captureability').disabled);
    assert.match(await page.locator('#abilitymessage').innerText(),/could not save|storage|full/i);
    assert.equal(await page.inputValue('#feedinput'),'Keep me after a failed save');
    const corrupt=await context.newPage();
    await corrupt.goto(base);
    await corrupt.evaluate(()=>localStorage.setItem('toad-ability-library-v2','{broken'));
    await corrupt.reload();
    assert.match(await corrupt.locator('#storagebanner').innerText(),/repair|recover|unreadable/i);
    assert.equal(await corrupt.locator('#recoverstorage').isVisible(),true);
    // Storage denied at startup is a distinct, visible, nonfatal state.
    const blocked=await browser.newContext({...devices['iPhone 13']});
    await blocked.addInitScript(()=>{Object.defineProperty(window,'localStorage',{get(){throw new DOMException('denied','SecurityError');}});});
    const bp=await blocked.newPage();await bp.goto(base);
    assert.match(await bp.locator('#storagebanner').innerText(),/storage|unavailable/i);
    await bp.fill('#feedinput','still editable');
    // A full origin remains readable: exporting and a smaller delete can recover space.
    const full=await browser.newContext({...devices['iPhone 13'],acceptDownloads:true});
    await full.addInitScript(data=>{
      const key='toad-ability-library-v2';
      localStorage.setItem(key,JSON.stringify(data));
      const original=Storage.prototype.setItem;
      Storage.prototype.setItem=function(k,v){const old=this.getItem(k);if(k===key && old && v.length<old.length)return original.call(this,k,v);throw new DOMException('full','QuotaExceededError');};
    },JSON.parse(raw));
    const fp=await full.newPage();await fp.goto(base);
    assert.match(await fp.locator('#storagebanner').innerText(),/readable|storage/i);
    const recoveredDownload=fp.waitForEvent('download');
    await fp.getByRole('button',{name:'Export backup',exact:true}).click();
    const recovered=await recoveredDownload;
    assert.equal(JSON.parse(fs.readFileSync(await recovered.path(),'utf8')).abilities.length,2);
    fp.on('dialog',dialog=>dialog.accept());
    await fp.locator('[data-ability-id]').first().getByRole('button',{name:'Delete',exact:true}).click();
    assert.match(await fp.locator('#abilitymessage').innerText(),/deleted/i);
    assert.equal(await fp.locator('[data-ability-id]').count(),0);
    await full.close();
    // Backup import is additive and a malformed backup cannot erase existing entries.
    const imported=await browser.newContext({...devices['iPhone 13']});
    const ip=await imported.newPage();await ip.goto(base);
    const backupFile={name:'backup.json',mimeType:'application/json',buffer:Buffer.from(raw)};
    await ip.setInputFiles('#importabilities',backupFile);
    await ip.waitForFunction(()=>document.querySelector('#abilitymessage').textContent.includes('Imported 2'));
    await ip.selectOption('#statusfilter','all');
    assert.equal(await ip.locator('[data-ability-id]').count(),2);
    await ip.setInputFiles('#importabilities',backupFile);
    await ip.waitForFunction(()=>document.querySelector('#abilitymessage').textContent.includes('2 duplicates'));
    assert.equal(await ip.locator('[data-ability-id]').count(),2);
    await ip.setInputFiles('#importabilities',{name:'invalid.json',mimeType:'application/json',buffer:Buffer.from('{"schema":"toad-library-v2","abilities":[{"name":"broken","content":42}]}')});
    await ip.waitForFunction(()=>document.querySelector('#abilitymessage').textContent.includes('Import refused'));
    assert.equal(await ip.locator('[data-ability-id]').count(),2);
    await imported.close();
    assert.deepEqual(errors,[]);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),'mobile layout must not overflow');
    if(process.env.TOAD_SCREENSHOT)await page.screenshot({path:process.env.TOAD_SCREENSHOT,fullPage:true});
    console.log('PASS: mobile save/reload/dedupe/XSS/search/archive/export/quota/corruption/denied-storage/full-storage-recovery/additive-import');
    await blocked.close();await context.close();
  } finally {if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1;});
