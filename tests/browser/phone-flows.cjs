/* Real browser regressions: drafts are data; multiple tabs share only the inbox. */
'use strict';
const assert=require('node:assert/strict');
const {devices}=require('playwright');
const fs=require('node:fs');
const KEY='toad-ability-library-v2', DRAFT='toad-feed-draft-v1';
const feed=page=>page.getByRole('button',{name:'Feed Toad',exact:true}).click();
const draftSaved=page=>page.waitForFunction(()=>/draft.*saved.*tab/i.test(document.querySelector('#draftstatus')?.textContent || ''));

async function reloadDraft(browser,base){
  const context=await browser.newContext({...devices['iPhone 13'],acceptDownloads:true});
  try{
    const page=await context.newPage();await page.goto(base);
    await page.locator('.feed summary').click();
    await page.fill('#abilityname','my-calculator');await page.fill('#abilitydescription','Add two numbers');await page.fill('#abilitysource','My phone');
    await page.fill('#feedinput','Create a calculator with a large display.');
    // A reload must recover the input even before the user presses Feed Toad.
    await page.waitForTimeout(350);await page.reload();
    assert.equal(await page.inputValue('#feedinput'),'Create a calculator with a large display.');
    assert.equal(await page.inputValue('#abilityname'),'my-calculator');
    assert.equal(await page.inputValue('#abilitydescription'),'Add two numbers');
    assert.equal(await page.inputValue('#abilitysource'),'My phone');
    assert.equal(await page.locator('[data-ability-id]').count(),0);
    assert.match(await page.locator('#draftstatus').innerText(),/restored.*not.*inbox/i);
    if(process.env.TOAD_DRAFT_SCREENSHOT)await page.screenshot({path:process.env.TOAD_DRAFT_SCREENSHOT,fullPage:true});
    const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Download draft',exact:true}).click();
    const saved=JSON.parse(fs.readFileSync(await (await downloaded).path(),'utf8'));
    assert.equal(saved.content,'Create a calculator with a large display.');
    await feed(page);assert.match(await page.locator('#abilitymessage').innerText(),/saved.*locally/i);
    await page.reload();assert.equal(await page.inputValue('#feedinput'),'');
    assert.equal(await page.inputValue('#abilityname'),'');
    assert.equal(await page.locator('[data-ability-id]').count(),1);
    assert.equal(await page.evaluate(key=>sessionStorage.getItem(key),DRAFT),null);
  }finally{await context.close();}
}

async function staleTab(browser,base,withoutLocks=false){
  const context=await browser.newContext({...devices['iPhone 13']});
  try{
    const first=await context.newPage();await first.goto(base);
    const second=await context.newPage();
    await second.addInitScript(noLocks=>{
      // Force a stale view even if a storage event would normally synchronize it.
      window.addEventListener('storage',e=>e.stopImmediatePropagation(),true);
      if(noLocks)Object.defineProperty(navigator,'locks',{value:undefined});
    },withoutLocks);
    await second.goto(base);
    await first.fill('#feedinput','First tab idea');await feed(first);
    await second.fill('#feedinput','Second tab idea');await feed(second);
    let items=await second.evaluate(key=>JSON.parse(localStorage.getItem(key)).abilities,KEY);
    assert.equal(items.length,1,'an old tab must not erase a feed saved by another tab');
    assert.equal(items[0].content,'First tab idea');
    assert.equal(await second.inputValue('#feedinput'),'Second tab idea');
    assert.match(await second.locator('#abilitymessage').innerText(),/changed.*another tab|another tab.*changed/i);
    await feed(second);
    items=await second.evaluate(key=>JSON.parse(localStorage.getItem(key)).abilities,KEY);
    assert.equal(items.length,2);
    await first.waitForFunction(()=>document.querySelectorAll('[data-ability-id]').length===2);
  }finally{await context.close();}
}

async function attachments(browser,base){
  const context=await browser.newContext({...devices['iPhone 13']});
  try{
    const page=await context.newPage();await page.goto(base);await page.locator('.feed summary').click();
    await page.fill('#feedinput','Review the attached sensor code.');
    await page.setInputFiles('#sourcefiles',{name:'sensor.py',mimeType:'text/plain',buffer:Buffer.from('print(1)\n')});
    await draftSaved(page);await page.reload();
    assert.equal(await page.inputValue('#feedinput'),'Review the attached sensor code.');
    assert.equal(await page.locator('#draftfilewarning').isVisible(),true);
    await feed(page);assert.match(await page.locator('#abilitymessage').innerText(),/select.*files|attachments/i);
    assert.equal(await page.locator('[data-ability-id]').count(),0);
    await page.getByRole('button',{name:'Continue without attachments',exact:true}).click();
    await feed(page);assert.equal(await page.locator('[data-ability-id]').count(),1);
  }finally{await context.close();}
}

async function deniedDraft(browser,base){
  const context=await browser.newContext({...devices['iPhone 13']});
  try{
    await context.addInitScript(()=>{
      const original=Storage.prototype.setItem;
      Storage.prototype.setItem=function(k,v){if(this===sessionStorage)throw new DOMException('full','QuotaExceededError');return original.call(this,k,v);};
    });
    const page=await context.newPage();await page.goto(base);await page.fill('#feedinput','Still save this feed');
    await page.waitForFunction(()=>/could not|unavailable/i.test(document.querySelector('#draftstatus')?.textContent || ''));
    await feed(page);assert.match(await page.locator('#abilitymessage').innerText(),/saved.*locally/i);
    await page.reload();assert.equal(await page.locator('[data-ability-id]').count(),1);
  }finally{await context.close();}
}

async function unreadableDraft(browser,base){
  const context=await browser.newContext({...devices['iPhone 13'],acceptDownloads:true});
  try{
    const page=await context.newPage();await page.goto(base);
    await page.evaluate(key=>sessionStorage.setItem(key,'{bad-draft'),DRAFT);await page.reload();
    assert.match(await page.locator('#draftstatus').innerText(),/unreadable|recover/i);
    await page.fill('#feedinput','A new thought');await page.waitForTimeout(350);
    assert.equal(await page.evaluate(key=>sessionStorage.getItem(key),DRAFT),'{bad-draft');
    await feed(page);
    assert.equal(await page.evaluate(key=>sessionStorage.getItem(key),DRAFT),'{bad-draft','feeding new text must not discard an unreadable draft');
    const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Download draft',exact:true}).click();
    assert.equal(fs.readFileSync(await (await downloaded).path(),'utf8'),'{bad-draft');
    await page.getByRole('button',{name:'Clear input',exact:true}).click();
    assert.equal(await page.evaluate(key=>sessionStorage.getItem(key),DRAFT),null);
    await page.fill('#feedinput','Fresh draft');await draftSaved(page);await page.reload();
    assert.equal(await page.inputValue('#feedinput'),'Fresh draft');
  }finally{await context.close();}
}


async function pendingMetadata(browser,base){
  const context=await browser.newContext({...devices['iPhone 13']});
  try{
    const first=await context.newPage();await first.goto(base);await first.fill('#feedinput','Keep my edited name');await feed(first);
    const second=await context.newPage();await second.goto(base);
    await second.getByText('Edit name and description',{exact:true}).click();
    const editor=second.locator('[data-ability-id]').first().getByLabel('Name',{exact:true});
    await editor.fill('Do not lose this edit');
    await first.fill('#feedinput','An independent feed');await feed(first);
    await second.waitForTimeout(100);
    assert.equal(await editor.inputValue(),'Do not lose this edit','storage events must not discard unsaved metadata edits');
    await second.getByRole('button',{name:'Save changes',exact:true}).click();
    assert.match(await second.locator('#abilitymessage').innerText(),/another tab/i);
    assert.equal(await editor.inputValue(),'Do not lose this edit');
  }finally{await context.close();}
}

async function delayedImport(browser,base){
  const context=await browser.newContext({...devices['iPhone 13']});
  try{
    const first=await context.newPage();await first.goto(base);
    const second=await context.newPage();await second.goto(base);
    const backup=await first.evaluate(()=>({schema:'toad-library-v2',abilities:[ToadCatalog.createCandidate('Incoming backup entry')]}));
    await first.evaluate(()=>{const original=File.prototype.text;File.prototype.text=function(){return new Promise(resolve=>{window.releaseFile=()=>resolve(original.call(this));});};});
    await first.setInputFiles('#importabilities',{name:'backup.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(backup))});
    await first.waitForFunction(()=>typeof window.releaseFile==='function');
    await second.fill('#feedinput','Saved while import was reading');await feed(second);
    await first.waitForFunction(()=>document.querySelectorAll('[data-ability-id]').length===1);
    await first.evaluate(()=>window.releaseFile());
    await first.waitForFunction(()=>document.querySelector('#abilitymessage').textContent.includes('Imported 1'));
    const items=await first.evaluate(key=>JSON.parse(localStorage.getItem(key)).abilities,KEY);
    assert.equal(items.length,2,'reading an import must not capture a stale library before await');
    assert.deepEqual(items.map(a=>a.content).sort(),['Incoming backup entry','Saved while import was reading'].sort());
  }finally{await context.close();}
}

async function newerDraft(browser,base){
  const context=await browser.newContext({...devices['iPhone 13']});
  try{
    const page=await context.newPage();await page.goto(base);await page.locator('.feed summary').click();
    await page.fill('#feedinput','Original upload notes');
    await page.setInputFiles('#sourcefiles',{name:'sensor.py',mimeType:'text/plain',buffer:Buffer.from('print(1)\n')});
    await page.evaluate(()=>{const original=File.prototype.text;File.prototype.text=function(){return new Promise(resolve=>{window.releaseFile=()=>resolve(original.call(this));});};});
    await feed(page);await page.waitForFunction(()=>typeof window.releaseFile==='function');
    await page.fill('#feedinput','New thought typed during save');await page.fill('#abilityname','next-draft');
    await page.evaluate(()=>window.releaseFile());
    await page.waitForFunction(()=>document.querySelector('#abilitymessage').textContent.includes('Newer edits'));
    assert.equal(await page.inputValue('#feedinput'),'New thought typed during save');
    const item=await page.evaluate(key=>JSON.parse(localStorage.getItem(key)).abilities[0],KEY);
    assert.equal(item.content,'Original upload notes');
    await page.reload();assert.equal(await page.inputValue('#feedinput'),'New thought typed during save');
    assert.equal(await page.inputValue('#abilityname'),'next-draft');
  }finally{await context.close();}
}


async function queuedWriter(browser,base){
  const context=await browser.newContext({...devices['iPhone 13']});
  try{
    const holder=await context.newPage();await holder.goto(base);
    const writer=await context.newPage();await writer.goto(base);
    if(!await holder.evaluate(()=>Boolean(navigator.locks))){console.log('SKIP: Web Locks unavailable; fallback has separate coverage');return;}
    await holder.evaluate(()=>{navigator.locks.request('toad-inbox-write-v2',()=>new Promise(resolve=>{window.releaseLock=resolve;}));});
    await holder.waitForFunction(()=>typeof window.releaseLock==='function');
    await writer.fill('#feedinput','Waiting writer draft');await feed(writer);
    await holder.evaluate(key=>localStorage.setItem(key,JSON.stringify({schema:'toad-library-v2',abilities:[ToadCatalog.createCandidate('Independent stored entry')]})),KEY);
    await writer.waitForFunction(()=>document.querySelectorAll('[data-ability-id]').length===1);
    await holder.evaluate(()=>window.releaseLock());
    await writer.waitForFunction(()=>document.querySelector('#abilitymessage').textContent.includes('changed in another tab'));
    const items=await writer.evaluate(key=>JSON.parse(localStorage.getItem(key)).abilities,KEY);
    assert.equal(items.length,1);assert.equal(items[0].content,'Independent stored entry');
    assert.equal(await writer.inputValue('#feedinput'),'Waiting writer draft');
    await feed(writer);assert.equal(await writer.locator('[data-ability-id]').count(),2);
  }finally{await context.close();}
}

async function importDraft(browser,base){
  const context=await browser.newContext({...devices['iPhone 13']});
  try{
    const page=await context.newPage();await page.goto(base);await page.locator('.feed summary').click();
    const draft={schema:'toad-feed-draft-v1',content:'<img src=x onerror="window.feedExecuted=true">',name:'Recovered idea',description:'A saved draft',source:'Files',has_files:false,saved_at:'2026-10-20T17:00:00.000Z'};
    const file=data=>({name:'toad-feed-draft.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(data))});
    await page.setInputFiles('#importdraft',file(draft));
    await page.waitForFunction(()=>document.querySelector('#abilitymessage').textContent.includes('Draft restored'));
    assert.equal(await page.inputValue('#feedinput'),draft.content);
    assert.equal(await page.evaluate(()=>Boolean(window.feedExecuted)),false);
    page.once('dialog',dialog=>dialog.dismiss());
    await page.setInputFiles('#importdraft',file({...draft,name:'Replacement draft'}));
    await page.waitForFunction(()=>document.querySelector('#importdraft').value==='');
    assert.equal(await page.inputValue('#abilityname'),'Recovered idea');
    page.once('dialog',dialog=>dialog.accept());
    await page.setInputFiles('#importdraft',file({...draft,name:'Replacement draft'}));
    await page.waitForFunction(()=>document.querySelector('#abilityname').value==='Replacement draft');
    await page.setInputFiles('#importdraft',file({...draft,schema:'unknown-future-draft'}));
    await page.waitForFunction(()=>document.querySelector('#abilitymessage').textContent.includes('Draft import refused'));
    assert.equal(await page.inputValue('#feedinput'),draft.content);
    await page.reload();assert.equal(await page.inputValue('#feedinput'),draft.content);
    assert.equal(await page.locator('[data-ability-id]').count(),0);
  }finally{await context.close();}
}


async function escapedDraft(browser,base){
  const context=await browser.newContext({...devices['iPhone 13'],acceptDownloads:true});
  try{
    const page=await context.newPage();await page.goto(base);await page.locator('.feed summary').click();
    // Small paste interactions are covered above; inject this large byte-boundary fixture.
    await page.evaluate(()=>{const input=document.querySelector('#feedinput');input.value='\u0001'.repeat(90000);input.dispatchEvent(new Event('input',{bubbles:true}));});
    await draftSaved(page);
    const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Download draft',exact:true}).click();
    const buffer=fs.readFileSync(await (await downloaded).path());
    assert.ok(buffer.length>512000,'JSON escaping can exceed source-package bytes for a valid draft');
    await page.getByRole('button',{name:'Clear input',exact:true}).click();
    await page.setInputFiles('#importdraft',{name:'toad-feed-draft.json',mimeType:'application/json',buffer});
    await page.waitForFunction(()=>document.querySelector('#importdraft').value==='');
    assert.equal((await page.inputValue('#feedinput')).length,90000,'a valid downloaded draft must restore at its encoded size');
  }finally{await context.close();}
}


async function manualRecovery(browser,base){
  const context=await browser.newContext({...devices['iPhone 13'],acceptDownloads:true});
  try{
    const page=await context.newPage();await page.goto(base);
    await page.evaluate(()=>{const input=document.querySelector('#feedinput');input.value='x'.repeat(250001);input.dispatchEvent(new Event('input',{bubbles:true}));});
    await page.waitForFunction(()=>document.querySelector('#draftstatus').textContent.includes('Could not update'));
    const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Download draft',exact:true}).click();
    const file=await downloaded,raw=JSON.parse(fs.readFileSync(await file.path(),'utf8'));
    assert.equal(file.suggestedFilename(),'toad-draft-manual-recovery.json');
    assert.equal(raw.schema,'toad-feed-draft-recovery-v1');
    assert.equal(raw.draft.content.length,250001);
    assert.match(await page.locator('#abilitymessage').innerText(),/manual recovery.*cannot.*restore/i);
    assert.equal((await page.inputValue('#feedinput')).length,250001);
  }finally{await context.close();}
}

module.exports=async(browser,base)=>{
  const cases={reload:reloadDraft,stale:staleTab,fallback:(b,u)=>staleTab(b,u,true),attachments,denied:deniedDraft,unreadable:unreadableDraft,metadata:pendingMetadata,import:delayedImport,newer:newerDraft,queued:queuedWriter,recover:importDraft,escaped:escapedDraft,manual:manualRecovery};
  for(const [name,run] of Object.entries(cases))if(!process.env.TOAD_PHONE_CASE || process.env.TOAD_PHONE_CASE===name){await run(browser,base);console.log('PASS: phone '+name);}
};
