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

    // Revision-section navigation is review-only: keyboard-accessible links,
    // no fake revision-history, apply, restore, approval or execution controls.
    const narrow=await browser.newContext({viewport:{width:320,height:650},
      hasTouch:true,isMobile:true});
    const narrowPage=await narrow.newPage();
    await open(narrowPage,url);
    const sections=narrowPage.getByRole('navigation',{name:'Inspector sections'});
    assert.equal(await sections.getByRole('link').count(),3);
    const diffLink=sections.getByRole('link',{name:'Proposed revision diff'});
    await diffLink.focus();
    assert.notEqual(await diffLink.evaluate(el=>getComputedStyle(el).outlineStyle),'none');
    await narrowPage.keyboard.press('Enter');
    assert.equal(await narrowPage.evaluate(()=>location.hash),'#sage-proposal-heading');
    for(const name of ['Current sample source','Sample search','Proposed revision diff']){
      const link=sections.getByRole('link',{name});
      assert((await link.boundingBox()).height>=44,'Section link touch height: '+name);
    }
    assert.equal(await narrowPage.evaluate(()=>
      document.documentElement.scrollWidth<=window.innerWidth+1),true);
    await narrow.close();

    // A response can report truncated:false on the FINAL page while still
    // missing preceding lines. Never call it whole-file SHA-256 checked.
    const finalPage=fixture();
    finalPage.sources[1].start_line=5;
    finalPage.sources[1].total_lines=20;
    finalPage.sources[1].content='print("tail")\n';
    finalPage.sources[1].truncated=false;
    finalPage.search.matches[0].line=1; // Valid result, absent from this excerpt
    const pagingCtx=await browser.newContext({...devices['iPhone 13']});
    const paging=await pagingCtx.newPage();
    await paging.route('**/sagecode-contract-fixture.json',route=>
      route.fulfill({contentType:'application/json',body:JSON.stringify(finalPage)}));
    await open(paging,url);
    await paging.getByRole('button',{name:'Read SageCode fixture source: src/main.py'}).click();
    assert.match(await paging.locator('#sage-source-state').innerText(),
      /Partial read.*Whole-file hash cannot be checked/);
    assert.match(await paging.locator('#sage-source-limits').innerText(),
      /PARTIAL SAMPLE.*later-page read.*truncated=false/);
    await paging.getByRole('button',{
      name:'Open contract example hit: src/main.py, line 1'
    }).click();
    assert.match(await paging.locator('#sage-navigation-note').innerText(),
      /OUTSIDE the loaded excerpt.*matching line is not displayed/);
    assert.match(await paging.locator('#sage-source').innerText(),/tail/);
    assert.equal(await paging.locator('#sage-source').evaluate(el=>document.activeElement===el),true);
    await pagingCtx.close();

    // An empty source manifest must give an explicit, non-misleading message.
    const empty=fixture();
    empty.tree.entries=[];empty.sources=[];empty.search.matches=[];empty.proposal=null;
    const emptyCtx=await browser.newContext({...devices['iPhone 13']});
    const noFiles=await emptyCtx.newPage();
    await noFiles.route('**/sagecode-contract-fixture.json',route=>
      route.fulfill({contentType:'application/json',body:JSON.stringify(empty)}));
    await open(noFiles,url);
    assert.equal(await noFiles.locator('#sage-empty-tree').isVisible(),true);
    assert.equal(await noFiles.locator('#sage-tree button').count(),0);
    assert.match(await noFiles.locator('#sage-search-state').innerText(),/No sample matches/);
    assert.match(await noFiles.locator('#sage-proposal-summary').innerText(),/No sample revision/);
    assert.match(await noFiles.locator('#sage-state').innerText(),/UNVERIFIED/);
    await emptyCtx.close();

    // Even very long declared paths stay readable without horizontal page overflow.
    const lengthy=fixture();
    const name='a'.repeat(115)+'.md';
    lengthy.tree.entries[0].path=name;
    lengthy.sources[0].path=name;
    const longCtx=await browser.newContext({...devices['iPhone 13']});
    const longPage=await longCtx.newPage();
    await longPage.route('**/sagecode-contract-fixture.json',route=>
      route.fulfill({contentType:'application/json',body:JSON.stringify(lengthy)}));
    await open(longPage,url);
    await longPage.getByRole('button',{name:'Read SageCode fixture source: '+name}).click();
    assert.equal(await longPage.locator('#sage-source-name').innerText(),name);
    assert.equal(await longPage.evaluate(()=>
      document.documentElement.scrollWidth<=window.innerWidth+1),true);
    await longCtx.close();

    // The inspector has no dependency on localStorage or other browser persistence.
    const blockedStorage=await browser.newContext({...devices['iPhone 13']});
    await blockedStorage.addInitScript(()=>{
      Object.defineProperty(window,'localStorage',{configurable:true,
        get(){throw new DOMException('Unavailable','SecurityError');}});
    });
    const readOnly=await blockedStorage.newPage();
    await open(readOnly,url);
    await readOnly.getByRole('button',{name:'Read SageCode fixture source: src/main.py'}).click();
    await readOnly.getByRole('button',{name:'Read SageCode fixture source: README.md'}).click();
    await readOnly.getByRole('button',{name:'Read SageCode fixture source: src/main.py'}).click();
    assert.match(await readOnly.locator('#sage-source').innerText(),/Hello, SageCode!/);
    await blockedStorage.close();

    // Invalid fixture data must fail closed without ever showing proposal diff.
    for(const variant of ['invalid-json','blank-changed-diff','unknown-status-field']){
      const ctx=await browser.newContext({...devices['iPhone 13']});
      const screen=await ctx.newPage();
      await screen.route('**/sagecode-contract-fixture.json',route=>{
        if(variant==='invalid-json')return route.fulfill({
          contentType:'application/json',body:'{"unfinished":'});
        const value=fixture();
        if(variant==='blank-changed-diff')value.proposal.diff='';
        else value.status.unexpected='verified';
        return route.fulfill({contentType:'application/json',body:JSON.stringify(value)});
      });
      await screen.goto(url+'/sagecode-contract.html');
      await screen.getByRole('button',{name:'Retry loading local example'}).waitFor();
      assert.match(await screen.locator('#sage-notice').innerText(),/Blocked/);
      assert.equal(await screen.locator('#sage-tree button').count(),0);
      assert.equal(await screen.locator('#sage-diff').innerText(),'No source diff available.');
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
