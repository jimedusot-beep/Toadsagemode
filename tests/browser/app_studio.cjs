/* Real WebKit interaction coverage for the trusted generated task app only.
   Nothing here executes downloaded or model-submitted source. */
'use strict';
const assert = require('node:assert/strict');
const {webkit, devices} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const {spawnSync} = require('node:child_process');

const repo = path.resolve(__dirname, '../..');
const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'toad-app-test-'));
const target = path.join(workspace, 'app-previews', 'browser-proof');
const python = process.env.PYTHON || 'python';
const build = spawnSync(python, [
  '-m', 'toad_core', '--workspace', workspace, 'app', 'create',
  'browser-proof', '--title', 'Browser Proof', '--theme', 'forest'
], {cwd:repo, encoding:'utf8', timeout:15000});
assert.equal(build.status, 0, build.stderr);
assert.equal(JSON.parse(build.stdout).status, 'generated_unverified');

const allowed = new Set(['/index.html','/styles.css','/app.js']);
const mime = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8'};
const server = http.createServer((req,res) => {
  const requestPath = new URL(req.url,'http://localhost').pathname;
  const pathname = requestPath === '/' ? '/index.html' : requestPath;
  if (!allowed.has(pathname)) {res.writeHead(404).end();return;}
  const file = path.join(target, pathname.slice(1));
  fs.readFile(file,(error,body) => {
    if (error) {res.writeHead(404).end();return;}
    res.writeHead(200, {'Content-Type':mime[path.extname(file)],'Cache-Control':'no-store'});
    res.end(body);
  });
});
(async () => {
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  let browser;
  try {
    browser = await webkit.launch({headless:true});
    const url = 'http://127.0.0.1:' + server.address().port;
    const context = await browser.newContext({...devices['iPhone 13']});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(url);
    assert.equal(await page.title(), 'Browser Proof');
    assert.equal(await page.locator('.task').count(), 0);
    assert.equal(await page.locator('#clear-done').isDisabled(),true);

    await page.fill('#task-input','Finish the outline');
    await page.getByRole('button',{name:'Add task'}).click();
    assert.equal(await page.locator('.task').count(),1);
    assert.equal(await page.locator('#count').innerText(),'1 remaining');

    const evil = '<img src=x onerror="window.injectionRan=true">';
    await page.fill('#task-input',evil);
    await page.getByRole('button',{name:'Add task'}).click();
    assert.equal(await page.locator('.task').count(),2);
    assert.equal(await page.locator('.task img').count(),0);
    assert.equal(await page.evaluate(() => Boolean(window.injectionRan)),false);
    assert.equal(await page.locator('.task-text').last().innerText(),evil);

    await page.reload();
    assert.equal(await page.locator('.task').count(),2);
    await page.getByRole('checkbox',{name:'Mark completed: Finish the outline'}).click();
    assert.equal(await page.getByRole('checkbox',{name:'Mark active: Finish the outline'}).isChecked(), true);
    assert.equal(await page.locator('#count').innerText(),'1 remaining');
    await page.getByRole('button',{name:'Active'}).click();
    assert.equal(await page.locator('.task').count(),1);
    await page.getByRole('button',{name:'Completed'}).click();
    assert.equal(await page.locator('.task').count(),1);
    assert.equal(await page.locator('.task-text').innerText(),'Finish the outline');
    await page.getByRole('button',{name:'Clear completed'}).click();
    assert.equal(await page.locator('.task').count(),0);
    await page.getByRole('button',{name:'All',exact:true}).click();
    assert.equal(await page.locator('.task').count(),1);
    await page.getByRole('button',{name:'Delete: '+evil}).click();
    assert.equal(await page.locator('.task').count(),0);
    await page.reload();
    assert.equal(await page.locator('.task').count(),0);
    assert.deepEqual(errors,[]);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1),true);
    await context.close();

    // Corrupt saved state is preserved, never overwritten by new edits.
    const corruptContext = await browser.newContext({...devices['iPhone 13']});
    const corrupt = await corruptContext.newPage();
    await corrupt.goto(url);
    await corrupt.evaluate(() => localStorage.setItem('toad-sage-task-list-v1','{bad'));
    await corrupt.reload();
    assert.match(await corrupt.locator('#message').innerText(), /not be overwritten/i);
    await corrupt.fill('#task-input','Keep unsaved');
    await corrupt.getByRole('button',{name:'Add task'}).click();
    assert.equal(await corrupt.locator('.task').count(),1);
    assert.equal(await corrupt.evaluate(() => localStorage.getItem('toad-sage-task-list-v1')),'{bad');
    await corruptContext.close();

    // Browser storage failure does not lose changes already shown on screen.
    const limited = await browser.newContext({...devices['iPhone 13']});
    await limited.addInitScript(() => {
      Storage.prototype.setItem = function() {throw new DOMException('full','QuotaExceededError');};
    });
    const badSave = await limited.newPage();
    await badSave.goto(url);
    await badSave.fill('#task-input','Visible unsaved task');
    await badSave.getByRole('button',{name:'Add task'}).click();
    assert.equal(await badSave.locator('.task').count(),1);
    assert.match(await badSave.locator('#message').innerText(),/not saved/i);
    await limited.close();
    console.log('PASS: trusted task-app mobile WebKit add/reload/check/filter/delete/clear/XSS/corruption/quota/width');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
    fs.rmSync(workspace,{recursive:true,force:true});
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
