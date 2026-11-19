/* iPhone-sized WebKit isolation check: interactive reviewed templates only.
   This does NOT execute AI-generated candidates or deploy applications.
*/
'use strict';
const assert=require('node:assert/strict');
const {webkit,devices}=require('playwright');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const http=require('node:http');
const {spawnSync}=require('node:child_process');

const repo=path.resolve(__dirname,'../..');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'toad-interactive-preview-'));
const dist=path.join(tmp,'dist');
const python=process.env.PYTHON||'python';
const build=spawnSync(python,['tools/build_free_studio_bundles.py','--output',dist],{
  cwd:repo,encoding:'utf8',timeout:25000
});
assert.equal(build.status,0,build.stderr||build.stdout);
const output=JSON.parse(build.stdout);
assert.equal(output.interactive_previews.count,6);
assert.equal(output.interactive_previews.reviewed_templates_only,true);
const root=path.join(dist,'browser-studio');

const roots=new Set([
  '/index.html','/app.js','/styles.css','/templates.json',
  '/v2.js','/v2.css','/v3.js','/v3.css'
]);
const iframeRoutes=new Set(
  ['tasks','notes','flashcards'].flatMap(k=>
    ['forest','midnight'].map(t=>'/previews/'+k+'-'+t+'/index.html'))
);
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
  '.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8'};
const server=http.createServer((req,res)=>{
  const route=new URL(req.url,'http://localhost').pathname;
  const target=route==='/'?'/index.html':route;
  if(!roots.has(target)&&!iframeRoutes.has(target)){res.writeHead(404).end();return;}
  fs.readFile(path.join(root,target.slice(1)),(err,body)=>{
    if(err){res.writeHead(404).end();return;}
    res.writeHead(200,{
      'Content-Type':mime[path.extname(target)],
      'Cache-Control':'no-store',
      'X-Content-Type-Options':'nosniff'
    });
    res.end(body);
  });
});

(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser;
  try{
    browser=await webkit.launch({headless:true});
    const url='http://127.0.0.1:'+server.address().port;
    const context=await browser.newContext({...devices['iPhone 13']});
    const page=await context.newPage();
    const errors=[];
    const offsite=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',req=>{if(!req.url().startsWith(url))offsite.push(req.url());});
    await page.goto(url);
    await page.locator('#interactive-frame').scrollIntoViewIfNeeded();
    assert.equal(await page.locator('#interactive-frame').getAttribute('sandbox'),'allow-scripts');
    assert.equal(await page.locator('#interactive-frame').getAttribute('referrerpolicy'),'no-referrer');
    assert.equal(await page.locator('#interactive-frame').getAttribute('src'),'./previews/flashcards-forest/index.html');
    const frame=page.frameLocator('#interactive-frame');
    await frame.locator('#card-form').waitFor({state:'visible',timeout:15000});
    assert.match(await frame.locator('.toad-preview-warning').innerText(),/Temporary in-memory data/);
    assert.match(await frame.locator('#message').innerText(),/browser|Stored|local/i);
    assert.equal(await page.evaluate(()=>{
      try{return document.querySelector('#interactive-frame').contentWindow.document.body.innerText}
      catch(_){return 'blocked'}
    }),'blocked','Parent must not read opaque-origin iframe DOM');
    assert.equal(await frame.locator('body').getAttribute('data-preview-sandbox'),'reviewed-template-v1');
    assert.equal(await frame.locator('body').evaluate(()=>{
      try{window.localStorage.getItem('anything');return 'allowed'}
      catch(e){return e.name}
    }),'SecurityError','Iframe must not have persistent browser localStorage access');

    await frame.locator('#front-input').fill('What is a template?');
    await frame.locator('#back-input').fill('A reviewed starting point');
    await frame.getByRole('button',{name:'Add flashcard'}).click();
    assert.equal(await frame.locator('#card-list .card-row').count(),1);
    assert.match(await frame.locator('#message').innerText(),/Preview only/);
    await frame.getByRole('button',{name:'Flip card to see its answer'}).click();
    assert.equal(await frame.locator('#face-text').innerText(),'A reviewed starting point');
    await frame.getByRole('button',{name:'Mark learned'}).click();
    assert.equal(await frame.locator('#progress').innerText(),'1 of 1 learned');

    await page.fill('#title','Study <Safe> & Learn');
    assert.equal(await frame.locator('h1').innerText(),'Study <Safe> & Learn');
    assert.equal(await frame.locator('h1 img').count(),0);

    // A fresh iframe has no data, and cannot read anything from the host page.
    await page.getByRole('button',{name:'Reset preview data'}).click();
    await frame.locator('#card-form').waitFor({state:'visible'});
    assert.equal(await frame.locator('#card-list .card-row').count(),0);
    assert.equal(await frame.locator('#progress').innerText(),'0 of 0 learned');
    await page.selectOption('#theme','midnight');
    await frame.locator('#card-form').waitFor({state:'visible'});
    assert.equal(await frame.locator('body').getAttribute('data-theme'),'midnight');

    // Other actual reviewed app types must respond to clicks, too.
    await page.check('input[value="tasks"]');
    await frame.locator('#task-form').waitFor({state:'visible'});
    await frame.locator('#task-input').fill('Finish schoolwork');
    await frame.getByRole('button',{name:'Add task'}).click();
    assert.equal(await frame.locator('#task-list .task').count(),1);
    await frame.locator('#task-list input[type=checkbox]').check();
    assert.equal(await frame.locator('#clear-done').isEnabled(),true);

    await page.check('input[value="notes"]');
    await frame.locator('#note-form').waitFor({state:'visible'});
    await frame.locator('#note-title').fill('Study plan');
    await frame.locator('#note-body').fill('Practice speech sounds');
    await frame.getByRole('button',{name:'Save note'}).click();
    assert.equal(await frame.locator('.note').count(),1);

    // Permanent Studio local project settings stay outside frame and unaffected.
    await page.fill('#title','A separate saved project');
    await page.fill('#slug','safe-project');
    await page.getByRole('button',{name:'Save current project'}).click();
    assert.equal(await page.locator('#project-count').innerText(),'1 of 20');
    assert.equal(await frame.locator('.note').count(),1);
    await page.getByRole('button',{name:'Reset preview data'}).click();
    await frame.locator('#note-form').waitFor({state:'visible'});
    assert.equal(await frame.locator('.note').count(),0);
    assert.equal(await page.locator('#project-count').innerText(),'1 of 20');

    assert.deepEqual(offsite,[],'Preview may not fetch third-party resources');
    assert.deepEqual(errors,[],'No parent or child page errors');
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
    await context.close();
    console.log('PASS: Studio V3 sandboxed opaque-origin interactive flashcards/tasks/notes, no persistent storage, reset and title update, no external network');
  }finally{
    if(browser)await browser.close();
    await new Promise(resolve=>server.close(resolve));
    fs.rmSync(tmp,{recursive:true,force:true});
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
