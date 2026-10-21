'use strict';
const assert=require('node:assert/strict'),{devices}=require('playwright'),fs=require('node:fs');
module.exports=async(browser,base)=>{
  const context=await browser.newContext({...devices['iPhone 13'],acceptDownloads:true});
  try{
    const page=await context.newPage();await page.goto(base);
    await page.fill('#feedinput','<script>window.lessonExecuted=true</script> A patient explanation');
    await page.getByRole('button',{name:'Make empathy lesson from text',exact:true}).click();
    await page.waitForURL('**/empathy.html');
    assert.match(await page.inputValue('#ematerial'),/patient explanation/);
    await page.getByRole('button',{name:'Save unreviewed lesson',exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll('[data-lesson-id]').length===1);
    assert.equal(await page.evaluate(()=>Boolean(window.lessonExecuted)),false);
    await page.reload();assert.equal(await page.locator('[data-lesson-id]').count(),1);
    const card=page.locator('[data-lesson-id]').first();
    await card.getByText('Review this version',{exact:true}).click();
    await card.locator('select').selectOption('helpful');await card.locator('textarea').fill('Reviewed my original note');
    await card.getByRole('button',{name:'Record human review',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#emessage').textContent.includes('Human review saved'));
    await page.locator('[data-lesson-id]').first().getByRole('button',{name:'Correct this lesson',exact:true}).click();
    await page.fill('#etechnique','Ask permission before explaining');
    await page.getByRole('button',{name:'Save correction · require review',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#emessage').textContent.includes('Lesson saved'));
    const stored=await page.evaluate(()=>JSON.parse(localStorage.getItem('toad-empathy-library-v2')));
    assert.equal(stored.lessons[0].version,2);assert.equal(stored.lessons[0].review_status,'needs_review');
    assert.equal(stored.lessons[0].previous_versions.length,1);
    await page.getByRole('button',{name:'Add original starter examples',exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll('[data-lesson-id]').length===12);
    await page.fill('#esearch','Listen before fixing');
    const starter=page.locator('[data-lesson-id]');await starter.getByText('Review this version',{exact:true}).click();
    await starter.locator('select').selectOption('helpful');await starter.locator('textarea').fill('Reviewed fictional adult example');
    await starter.getByRole('button',{name:'Record human review',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#emessage').textContent.includes('Human review saved'));
    await page.selectOption('#escenario','practice-02');await page.selectOption('#escenario','practice-01');
    assert.match(await page.locator('#ematches').innerText(),/Listen before fixing/);
    await page.fill('#ebaseline','What is broken?');await page.fill('#eretrievalresponse','Would listening or troubleshooting help right now?');
    await page.locator('#erubric select').evaluateAll(nodes=>nodes.forEach(e=>{e.value='1';}));
    await page.getByRole('button',{name:'Save my paired assessment',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#emessage').textContent.includes('assessment saved'));
    const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Export empathy backup',exact:true}).click();
    const buffer=fs.readFileSync(await (await downloaded).path());
    assert.equal(JSON.parse(buffer).assessments.length,1);
    const other=await browser.newContext({...devices['iPhone 13']});
    try{
      const restored=await other.newPage();await restored.goto(new URL('empathy.html',base.endsWith('/')?base:base+'/').href);
      await restored.setInputFiles('#elessonfile',{name:'backup.json',mimeType:'application/json',buffer});
      await restored.waitForFunction(()=>document.querySelectorAll('[data-lesson-id]').length===12);
      assert.equal(await restored.evaluate(()=>JSON.parse(localStorage.getItem('toad-empathy-library-v2')).lessons.filter(x=>x.review_status==='helpful').length),0);
    }finally{await other.close();}
    await page.evaluate(()=>{Storage.prototype.setItem=function(){throw new DOMException('full','QuotaExceededError');};});
    await page.fill('#ematerial','Keep this lesson after quota failure');await page.getByRole('button',{name:'Save unreviewed lesson',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#emessage').textContent.includes('Your input has been kept'));
    assert.equal(await page.inputValue('#ematerial'),'Keep this lesson after quota failure');
    console.log('PASS: empathy mobile ingestion/review/correction/retrieval/assessment/backup/inert-text/quota');
  }finally{await context.close();}
};
