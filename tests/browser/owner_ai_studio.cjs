/* iPhone-sized WebKit test for owner AI draft controls.
 * Serves a FAKE API. No model API, Python worker, or untrusted JS execution.
 */
'use strict';
const assert=require('node:assert/strict');
const {webkit,devices}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');

const root=path.resolve(__dirname,'../../owner-ai-studio');
const ownerToken='unshared-verified-owner-token-32-characters';
const id='f'.repeat(32);
const calls=[];
const sources={
  'index.html':'<img src=x onerror="window.generatedRan=true"> <h1>Original Proposal</h1>',
  'styles.css':'body{color:lime}',
  'app.js':'window.generatedRan = true;'
};
const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://localhost');
  calls.push({method:req.method,path:url.pathname,authorization:req.headers['x-toad-owner-token'],origin:req.headers.origin});
  const send=(code,body,contentType='application/json; charset=utf-8')=>{
    res.writeHead(code,{
      'Content-Type':contentType,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
      'Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'none'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    });res.end(body);
  };
  if(req.method==='GET' && ['/', '/index.html','/app.js','/styles.css'].includes(url.pathname)){
    const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
    const type=name.endsWith('.js')?'application/javascript':name.endsWith('.css')?'text/css':'text/html';
    send(200,fs.readFileSync(path.join(root,name)),type+'; charset=utf-8');
    return;
  }
  if(req.headers['x-toad-owner-token']!==ownerToken){send(401,JSON.stringify({error:'Private owner token required'}));return;}
  if(req.method==='GET' && url.pathname==='/api/status'){
    send(200,JSON.stringify({provider_selection:'ollama',calls_remaining:1,source_execution:false,deploy_enabled:false}));
    return;
  }
  if(req.method==='POST' && url.pathname==='/api/drafts'){
    let body='';
    req.on('data',part=>body+=part);
    req.on('end',()=>{
      assert.equal(JSON.parse(body).goal,'Build an offline spelling game');
      send(201,JSON.stringify({id,status:'quarantined_unverified',draft_sha256:'0'.repeat(64),
        risk_flags:['html_injection_or_dynamic_markup'],executed:false,tested:false,deployed:false}));
    });
    return;
  }
  if(req.method==='GET' && url.pathname==='/api/drafts/'+id){
    send(200,JSON.stringify({id,status:'quarantined_unverified',executed:false,release_allowed:false,
      draft:{files:Object.entries(sources).map(([path,content])=>({path,content}))}}));
    return;
  }
  send(404,JSON.stringify({error:'Not found'}));
});

(async()=>{
  await new Promise(done=>server.listen(0,'127.0.0.1',done));
  let browser;
  try{
    browser=await webkit.launch({headless:true});
    const origin='http://127.0.0.1:'+server.address().port;
    const context=await browser.newContext({...devices['iPhone 13']});
    const page=await context.newPage();
    const pageErrors=[];
    const external=[];
    page.on('pageerror',e=>pageErrors.push(e.message));
    page.on('request',r=>{if(!r.url().startsWith(origin))external.push(r.url());});
    await page.goto(origin);
    assert.equal(await page.locator('h1').innerText(),'AI Code Draft Lab');
    assert.equal(await page.locator('#token').getAttribute('type'),'password');
    await page.fill('#token',ownerToken);
    await page.getByRole('button',{name:'Check connection metadata'}).click();
    await page.getByRole('status').filter({hasText:'calls left 1'}).waitFor();
    assert.equal(calls.some(c=>c.method==='POST'),false,'Metadata must not invoke a model');
    await page.fill('#goal','Build an offline spelling game');
    await page.getByRole('button',{name:'Generate quarantined source'}).click();
    await page.getByRole('status').filter({hasText:'Quarantined source created'}).waitFor();
    assert.match(await page.locator('#draft-summary').innerText(),/quarantined_unverified/);
    await page.getByRole('button',{name:'View source as text only'}).click();
    await page.waitForFunction(()=>!document.querySelector('#source-file').disabled);
    assert.match(await page.locator('#source-text').innerText(),/<img src=x onerror=/);
    assert.equal(await page.locator('#source-text img').count(),0);
    assert.equal(await page.evaluate(()=>Boolean(window.generatedRan)),false);
    await page.selectOption('#source-file','app.js');
    assert.equal(await page.locator('#source-text').innerText(),'window.generatedRan = true;');
    assert.equal(await page.evaluate(()=>Boolean(window.generatedRan)),false);
    assert.equal(calls.filter(x=>x.method==='POST'&&x.path==='/api/drafts').length,1);
    assert.equal(calls.every(x=>!x.path.includes(ownerToken)),true);
    assert.equal(calls.filter(x=>x.path.startsWith('/api/')).every(x=>x.authorization===ownerToken),true);
    assert.equal(await page.evaluate(()=>localStorage.length),0);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
    assert.deepEqual(pageErrors,[]);
    assert.deepEqual(external,[]);
    await context.close();
    console.log('PASS: iPhone WebKit owner AI Draft Lab UI, fake API, no model calls, text-only code, no script execution or token storage');
  }finally{
    if(browser)await browser.close();
    await new Promise(done=>server.close(done));
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
