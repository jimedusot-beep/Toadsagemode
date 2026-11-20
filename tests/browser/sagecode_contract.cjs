/* Real WebKit checks for source-only Agent A contract SHAPES shown as fixtures.
 * No backend, executed source, secret loading, model, authorization or deployment.
 */
'use strict';
const assert=require('node:assert/strict');
const {webkit,devices}=require('playwright');
const fs=require('node:fs');
const http=require('node:http');
const path=require('node:path');
const root=path.resolve(__dirname,'../../free-studio');
const allow=new Set(['/sagecode-contract.html','/sagecode-contract.css',
  '/sagecode-contract.js','/sagecode-contract-adapter.js',
  '/sagecode-contract-fixture.json','/styles.css','/v2.css','/explorer.css']);
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
  '.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8'};
const fixture=()=>JSON.parse(fs.readFileSync(
  path.join(root,'sagecode-contract-fixture.json'),'utf8'));
const server=http.createServer((req,res)=>{
  const target=new URL(req.url,'http://localhost').pathname;
  if(!allow.has(target)){res.writeHead(404).end();return;}
  fs.readFile(path.join(root,target.slice(1)),(err,bytes)=>{
    if(err){res.writeHead(404).end();return;}
    res.writeHead(200,{'Content-Type':mime[path.extname(target)],'Cache-Control':'no-store'});
    res.end(bytes);
  });
});
async function open(page,url) {
  await page.goto(url+'/sagecode-contract.html');
  await page.waitForFunction(()=>document.querySelector('#sage-notice')
    .textContent.includes('Loaded SageCode contract fixture'));
}
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser;
  try {
    browser=await webkit.launch({headless:true});
    const url='http://127.0.0.1:'+server.address().port;
    const context=await browser.newContext({...devices['iPhone 13']});
    const page=await context.newPage();
    const errors=[],offsite=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(!r.url().startsWith(url))offsite.push(r.url());});
    await open(page,url);
    assert.match(await page.title(),/Contract Inspector/);
    assert.match(await page.locator('#sage-warning-title').innerText(),/Fixture only/);
    assert.match(await page.locator('#sage-state').innerText(),/UNVERIFIED example/);
    assert.match(await page.locator('#sage-evidence').innerText(),/no execution/);
    assert.match(await page.locator('#sage-approval').innerText(),/no owner approval or release/);
    assert.equal(await page.locator('#sage-tree button').count(),2);
    assert.match(await page.locator('#sage-source-state').innerText(),
      /Full sample read.*SHA-256 matches sample metadata.*no authenticity/);
    assert.match(await page.locator('#sage-source').innerText(),/fixture source/);
    assert.equal(await page.locator('button').filter({hasText:/approve|apply|deploy/i}).count(),0);

    const source=page.getByRole('button',{name:'Read SageCode fixture source: src/main.py'});
    await source.focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#sage-source-name').innerText(),'src/main.py');
    assert.match(await page.locator('#sage-source').innerText(),/Hello, SageCode!/);
    assert.equal(await source.getAttribute('aria-current'),'true');
    assert.equal(await page.locator('#sage-source').evaluate(el=>document.activeElement===el),true);
    // Enter intentionally moves focus to source; refocus the file button
    // before asserting its :focus-visible outline.
    await source.focus();
    const outline=await source.evaluate(el=>getComputedStyle(el).outlineStyle);
    assert.notEqual(outline,'none');
    assert.match(await page.locator('#sage-search-state').innerText(),/Example term.*Hello/);
    await page.getByRole('button',{
      name:'Open contract example hit: src/main.py, line 1'
    }).click();
    assert.equal(await page.locator('#sage-source-name').innerText(),'src/main.py');
    assert.match(await page.locator('#sage-proposal-state').innerText(),/Unverified/);
    assert.match(await page.locator('#sage-diff').innerText(),/Hello, Sage Studio!/);
    assert.match(await page.locator('#sage-proposal-warning').innerText(),/No independent tests/);
    assert.equal(await page.evaluate(()=>localStorage.length),0);
    assert.equal(await page.evaluate(()=>
      document.documentElement.scrollWidth <= window.innerWidth + 1),true);
    await context.close();

    const tablet=await browser.newContext({viewport:{width:834,height:1112},
      hasTouch:true,isMobile:true});
    const ipad=await tablet.newPage();
    await open(ipad,url);
    assert.equal(await ipad.evaluate(()=>
      document.documentElement.scrollWidth <= window.innerWidth + 1),true);
    assert.equal(await ipad.locator('#sage-source').isVisible(),true);
    await tablet.close();

    // Server-like source drift with the same revision and stale source hash
    // must fail closed before the UI offers any source or proposal content.
    const forged=fixture();
    forged.sources[0].content=forged.sources[0].content.replace('fixture','unsafe!'); 
    // Metadata changes are not authorized: validation or SHA-256 must reject.
    const tampered=await browser.newContext({...devices['iPhone 13']});
    const bad=await tampered.newPage();
    await bad.route('**/sagecode-contract-fixture.json',route=>
      route.fulfill({contentType:'application/json',body:JSON.stringify(forged)}));
    await bad.goto(url+'/sagecode-contract.html');
    await bad.getByRole('button',{name:'Retry loading local example'}).waitFor();
    assert.match(await bad.locator('#sage-notice').innerText(),/Blocked/);
    assert.equal(await bad.locator('#sage-tree button').count(),0);
    assert.equal(await bad.locator('#sage-diff').innerText(),'No source diff available.');
    await tampered.close();

    // A truncated backend-shaped source view must never be presented as
    // complete or cryptographically checked from the partial bytes.
    const partial=fixture();
    partial.sources[1].start_line=2;
    partial.sources[1].total_lines=20;
    partial.sources[1].truncated=true;
    partial.sources[1].content='print("partial")\n';
    const limited=await browser.newContext({...devices['iPhone 13']});
    const truncated=await limited.newPage();
    await truncated.route('**/sagecode-contract-fixture.json',route=>
      route.fulfill({contentType:'application/json',body:JSON.stringify(partial)}));
    await open(truncated,url);
    await truncated.getByRole('button',{
      name:'Read SageCode fixture source: src/main.py'
    }).click();
    assert.match(await truncated.locator('#sage-source-state').innerText(),
      /Partial read.*Whole-file hash cannot be checked/);
    assert.match(await truncated.locator('#sage-source-limits').innerText(),
      /TRUNCATED SAMPLE.*No additional read endpoint/);
    assert.match(await truncated.locator('#sage-source').innerText(),/partial/);
    await limited.close();

    // A malicious-looking proposal remains text, never an HTML node/script.
    const hostile=fixture();
    const marker='<img src=x onerror="window.sageContractXss=true">';
    hostile.proposal.diff=marker;
    const inert=await browser.newContext({...devices['iPhone 13']});
    const textOnly=await inert.newPage();
    await textOnly.route('**/sagecode-contract-fixture.json',route=>
      route.fulfill({contentType:'application/json',body:JSON.stringify(hostile)}));
    await open(textOnly,url);
    assert.match(await textOnly.locator('#sage-diff').innerText(),/onerror/);
    assert.equal(await textOnly.locator('#sage-diff img').count(),0);
    assert.equal(await textOnly.evaluate(()=>Boolean(window.sageContractXss)),false);
    await inert.close();

    // Invalid/missing fixtures never leave stale project information exposed.
    for(const variant of ['missing','wrong-revision']){
      const ctx=await browser.newContext({...devices['iPhone 13']});
      const p=await ctx.newPage();
      await p.route('**/sagecode-contract-fixture.json',route=>{
        if(variant==='missing')return route.fulfill({status:404,body:''});
        const value=fixture();value.tree.revision='c'.repeat(64);
        return route.fulfill({contentType:'application/json',body:JSON.stringify(value)});
      });
      await p.goto(url+'/sagecode-contract.html');
      await p.getByRole('button',{name:'Retry loading local example'}).waitFor();
      assert.match(await p.locator('#sage-notice').innerText(),/Blocked/);
      assert.equal(await p.locator('#sage-tree button').count(),0);
      await ctx.close();
    }
    assert.deepEqual(errors,[]);
    assert.deepEqual(offsite,[]);
    console.log('SageCode Contract Inspector Mobile WebKit PASS: iPhone/tablet, exact source hash, stale revision, partial source, inert diff, blocked states; fixture-only.');
  }finally{
    if(browser)await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
