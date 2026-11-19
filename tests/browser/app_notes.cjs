/* Real mobile WebKit test of a trusted, template-built notes app.
   No model-generated JavaScript or arbitrary candidate is executed here. */
'use strict';
const assert = require('node:assert/strict');
const {webkit, devices} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const {spawnSync} = require('node:child_process');

const repo = path.resolve(__dirname, '../..');
const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'toad-notes-test-'));
const target = path.join(workspace, 'app-previews', 'research-notes');
const python = process.env.PYTHON || 'python';
const build = spawnSync(python, [
  '-m', 'toad_core', '--workspace', workspace, 'app', 'create',
  'research-notes', '--title', 'Research Notes', '--kind', 'notes'
], {cwd: repo, encoding: 'utf8', timeout: 15000});
assert.equal(build.status, 0, build.stderr);
assert.equal(JSON.parse(build.stdout).status, 'generated_unverified');

const files = new Set(['/index.html', '/styles.css', '/app.js']);
const mime = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8'};
const server = http.createServer((req,res) => {
  const name = new URL(req.url,'http://localhost').pathname;
  const route = name === '/' ? '/index.html' : name;
  if (!files.has(route)) {res.writeHead(404).end();return;}
  fs.readFile(path.join(target, route.slice(1)),(error,body) => {
    if (error) {res.writeHead(404).end();return;}
    res.writeHead(200, {'Content-Type':mime[path.extname(route)],'Cache-Control':'no-store'});
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
    page.on('pageerror',error => errors.push(error.message));
    await page.goto(url);
    assert.equal(await page.title(),'Research Notes');
    assert.equal(await page.locator('.note').count(),0);
    await page.fill('#note-title','Project idea');
    await page.fill('#note-body','Build a small expressive robot');
    await page.getByRole('button',{name:'Save note'}).click();
    assert.equal(await page.locator('.note').count(),1);
    assert.equal(await page.locator('#count').innerText(),'1 note');
    assert.equal(await page.locator('.note h3').innerText(),'Project idea');
    await page.reload();
    assert.equal(await page.locator('.note').count(),1);

    await page.getByRole('button',{name:'Edit: Project idea'}).click();
    assert.equal(await page.inputValue('#note-title'),'Project idea');
    await page.fill('#note-body','New note body');
    await page.getByRole('button',{name:'Update note'}).click();
    assert.equal(await page.locator('.note p').innerText(),'New note body');

    const payload = '<img src=x onerror="window.notesXss=true">';
    await page.fill('#note-title',payload);
    await page.fill('#note-body','A safe text record <script>alert(1)</script>');
    await page.getByRole('button',{name:'Save note'}).click();
    assert.equal(await page.locator('.note').count(),2);
    assert.equal(await page.locator('.note img').count(),0);
    assert.equal(await page.evaluate(() => Boolean(window.notesXss)),false);
    assert.equal(await page.locator('.note h3').last().innerText(),payload);

    await page.fill('#note-search','NEW NOTE BODY');
    assert.equal(await page.locator('.note').count(),1);
    await page.fill('#note-search','no-match');
    assert.equal(await page.locator('.note').count(),0);
    assert.match(await page.locator('#empty').innerText(),/No matching/i);
    await page.fill('#note-search','');
    assert.equal(await page.locator('.note').count(),2);
    await page.getByRole('button',{name:'Delete: Project idea'}).click();
    assert.equal(await page.locator('.note').count(),1);
    await page.reload();
    assert.equal(await page.locator('.note').count(),1);
    assert.deepEqual(errors,[]);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1),true);
    await context.close();

    const corruptContext = await browser.newContext({...devices['iPhone 13']});
    const corrupt = await corruptContext.newPage();
    await corrupt.goto(url);
    await corrupt.evaluate(() => localStorage.setItem('toad-sage-notes-v1:research-notes','{bad'));
    await corrupt.reload();
    assert.match(await corrupt.locator('#message').innerText(),/not be overwritten/i);
    await corrupt.fill('#note-title','Unsaved note');
    await corrupt.fill('#note-body','Data is visible in this session');
    await corrupt.getByRole('button',{name:'Save note'}).click();
    assert.equal(await corrupt.locator('.note').count(),1);
    assert.equal(await corrupt.evaluate(() => localStorage.getItem('toad-sage-notes-v1:research-notes')),'{bad');
    await corruptContext.close();

    const quota = await browser.newContext({...devices['iPhone 13']});
    await quota.addInitScript(() => {
      Storage.prototype.setItem = function () { throw new DOMException('storage full','QuotaExceededError'); };
    });
    const q = await quota.newPage();
    await q.goto(url);
    await q.fill('#note-title','Quota note');
    await q.fill('#note-body','This should stay on screen after the save fails');
    await q.getByRole('button',{name:'Save note'}).click();
    assert.equal(await q.locator('.note').count(),1);
    assert.match(await q.locator('#message').innerText(),/not saved/i);
    await quota.close();
    console.log('PASS: trusted notes WebKit create/reload/edit/search/delete/XSS/corrupt-storage/quota/mobile');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
    fs.rmSync(workspace,{recursive:true,force:true});
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
