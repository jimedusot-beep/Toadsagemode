/* Real mobile WebKit exercise for Studio V2: safe preview and project memory.
 * Does not execute downloaded applications or call a model.
 */
'use strict';
const assert = require('node:assert/strict');
const {webkit,devices} = require('playwright');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');

const ROOT=path.resolve(__dirname,'../../free-studio');
const ALLOWED=new Set([
  '/index.html','/styles.css','/app.js','/templates.json','/v2.css','/v2.js','/v3.css','/v3.js'
]);
const MIME={
  '.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8',
  '.js':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8'
};
const server=http.createServer((req,res)=>{
  const raw=new URL(req.url,'http://localhost').pathname;
  const route=raw==='/'?'/index.html':raw;
  if(!ALLOWED.has(route)){res.writeHead(404).end();return;}
  fs.readFile(path.join(ROOT,route.slice(1)),(error,body)=>{
    if(error){res.writeHead(404).end();return;}
    res.writeHead(200,{'Content-Type':MIME[path.extname(route)],'Cache-Control':'no-store'});
    res.end(body);
  });
});
async function open(page,url) {
  await page.goto(url);
  await page.waitForFunction(()=>!document.querySelector('#download').disabled);
}
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser;
  try {
    browser=await webkit.launch({headless:true});
    const url='http://127.0.0.1:'+server.address().port;
    const context=await browser.newContext({...devices['iPhone 13'],acceptDownloads:true});
    const page=await context.newPage();
    const errors=[];
    const remote=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',req=>{if(!req.url().startsWith(url))remote.push(req.url());});

    await open(page,url);
    assert.equal(await page.locator('#preview-title').innerText(),'My Flashcards');
    assert.equal(await page.locator('#device-preview').getAttribute('data-theme'),'forest');
    assert.match(await page.locator('#preview-content').innerText(),/What is an app prototype/);
    assert.match(await page.locator('#preview-panel').innerText(),/Visual only/);

    const hostile='<img src=x onerror="window.studioXss=true">';
    await page.fill('#title',hostile);
    assert.equal(await page.locator('#preview-title').innerText(),hostile);
    assert.equal(await page.locator('#preview-title img').count(),0);
    assert.equal(await page.evaluate(()=>Boolean(window.studioXss)),false);

    await page.selectOption('#theme','midnight');
    assert.equal(await page.locator('#device-preview').getAttribute('data-theme'),'midnight');
    await page.selectOption('#preview-size','tablet');
    assert.equal(await page.locator('#device-preview').getAttribute('data-size'),'tablet');
    await page.check('input[value="notes"]');
    assert.equal(await page.locator('#device-preview').getAttribute('data-kind'),'notes');
    assert.match(await page.locator('#preview-content').innerText(),/Save note/);

    await page.fill('#title','College Notes');
    await page.fill('#slug','college-notes');
    await page.getByRole('button',{name:'Save current project'}).click();
    assert.match(await page.locator('#projects-status').innerText(),/Saved College Notes locally/);
    assert.equal(await page.locator('#project-count').innerText(),'1 of 20');
    assert.equal(await page.locator('.saved-project').count(),1);
    assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('toad-sage-free-studio-projects-v1')).projects.length),1);

    await page.reload();
    await page.waitForFunction(()=>!document.querySelector('#download').disabled);
    assert.equal(await page.locator('#project-count').innerText(),'1 of 20');
    await page.getByRole('button',{name:'Load: college-notes'}).click();
    assert.equal(await page.inputValue('#title'),'College Notes');
    assert.equal(await page.inputValue('#slug'),'college-notes');
    assert.equal(await page.inputValue('#theme'),'midnight');
    assert.equal(await page.locator('input[value="notes"]').isChecked(),true);
    assert.equal(await page.locator('#preview-title').innerText(),'College Notes');
    assert.equal(await page.locator('#device-preview').getAttribute('data-size'),'phone');

    await page.check('input[value="flashcards"]');
    await page.getByRole('button',{name:'Save current project'}).click();
    assert.match(await page.locator('#projects-status').innerText(),/different app type/);
    assert.equal(await page.locator('#project-count').innerText(),'1 of 20');
    await page.check('input[value="notes"]');

    // iPad backup must contain settings only, download locally, and restore additively.
    await page.getByRole('button',{name:'Prepare project backup'}).click();
    assert.match(await page.locator('#projects-status').innerText(),/Backup ready/);
    const backupEvent=page.waitForEvent('download');
    await page.getByRole('link',{name:'Download project backup'}).click();
    const backup=await backupEvent;
    assert.equal(backup.suggestedFilename(),'toad-sage-studio-projects-backup.json');
    const backupBytes=fs.readFileSync(await backup.path());
    const exported=JSON.parse(backupBytes.toString('utf8'));
    assert.equal(exported.schema,'toad-studio-projects-v1');
    assert.equal(exported.projects.length,1);
    assert.deepEqual(Object.keys(exported.projects[0]).sort(),
      ['kind','name','savedAt','theme','title']);
    assert.equal(backupBytes.includes(Buffer.from('app.js')),false);

    await page.getByRole('button',{name:'Delete: college-notes'}).click();
    assert.equal(await page.locator('.saved-project').count(),1);
    assert.equal(await page.locator('#project-count').innerText(),'1 of 20');
    await page.getByRole('button',{name:'Confirm delete: college-notes'}).click();
    assert.equal(await page.locator('#project-count').innerText(),'0 of 20');
    await page.setInputFiles('#backup-file',{
      name:'studio-backup.json',mimeType:'application/json',buffer:backupBytes
    });
    await page.getByRole('button',{name:'Restore settings without overwriting'}).click();
    assert.match(await page.locator('#projects-status').innerText(),/Restored 1 project/);
    assert.equal(await page.locator('#project-count').innerText(),'1 of 20');

    // A conflicting saved name cannot silently overwrite a newer local revision.
    await page.getByRole('button',{name:'Load: college-notes'}).click();
    await page.fill('#title','Updated Locally');
    await page.getByRole('button',{name:'Save current project'}).click();
    const beforeConflict=await page.evaluate(()=>
      localStorage.getItem('toad-sage-free-studio-projects-v1'));
    await page.setInputFiles('#backup-file',{
      name:'studio-backup.json',mimeType:'application/json',buffer:backupBytes
    });
    await page.getByRole('button',{name:'Restore settings without overwriting'}).click();
    assert.match(await page.locator('#projects-status').innerText(),/conflicts.*nothing was changed/);
    assert.equal(await page.evaluate(()=>
      localStorage.getItem('toad-sage-free-studio-projects-v1')),beforeConflict);
    await page.getByRole('button',{name:'Delete: college-notes'}).click();
    await page.getByRole('button',{name:'Confirm delete: college-notes'}).click();
    assert.equal(await page.locator('#project-count').innerText(),'0 of 20');
    await page.reload();
    assert.equal(await page.locator('.saved-project').count(),0);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1),true);
    assert.deepEqual(errors,[]);
    assert.deepEqual(remote,[]);
    await context.close();

    const corrupt=await browser.newContext({...devices['iPhone 13']});
    const broken=await corrupt.newPage();
    await broken.goto(url);
    await broken.evaluate(()=>localStorage.setItem('toad-sage-free-studio-projects-v1','{broken'));
    await broken.reload();
    assert.match(await broken.locator('#projects-status').innerText(),/not overwritten/);
    assert.equal(await broken.locator('#save-project').isDisabled(),true);
    assert.equal(await broken.locator('#backup-projects').isDisabled(),true);
    assert.equal(await broken.locator('#restore-projects').isDisabled(),true);
    assert.equal(await broken.evaluate(()=>localStorage.getItem('toad-sage-free-studio-projects-v1')),'{broken');
    await broken.fill('#title','Still able to preview');
    assert.equal(await broken.locator('#preview-title').innerText(),'Still able to preview');
    await corrupt.close();

    const denied=await browser.newContext({...devices['iPhone 13']});
    await denied.addInitScript(()=>{
      Storage.prototype.getItem=function(){throw new DOMException('denied','SecurityError');};
    });
    const block=await denied.newPage();
    await block.goto(url);
    assert.equal(await block.locator('#save-project').isDisabled(),true);
    assert.match(await block.locator('#projects-status').innerText(),/not|read/i);
    await denied.close();

    const quota=await browser.newContext({...devices['iPhone 13']});
    await quota.addInitScript(()=>{
      Storage.prototype.setItem=function(){throw new DOMException('full','QuotaExceededError');};
    });
    const noSpace=await quota.newPage();
    await noSpace.goto(url);
    await noSpace.getByRole('button',{name:'Save current project'}).click();
    assert.match(await noSpace.locator('#projects-status').innerText(),/unavailable or full/i);
    assert.equal(await noSpace.locator('#project-count').innerText(),'0 of 20');
    await quota.close();

    console.log('PASS: Studio V2 mobile WebKit live visual preview, theme, tablet, project save/reload/load/delete, XSS text safety, corruption/denial/quota');
  }finally{
    if(browser)await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
