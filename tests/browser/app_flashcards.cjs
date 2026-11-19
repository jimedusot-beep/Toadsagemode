/* iPhone-sized WebKit: reviewed flashcards only, no AI-generated JS. */
'use strict';
const assert = require('node:assert/strict');
const {webkit, devices} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const {spawnSync} = require('node:child_process');

const repo = path.resolve(__dirname, '../..');
const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'toad-flashcards-'));
const target = path.join(workspace, 'app-previews', 'college-cards');
const python = process.env.PYTHON || 'python';
const build = spawnSync(python, [
  '-m', 'toad_core', '--workspace', workspace, 'app', 'free-build',
  'Make an offline flashcard app for college',
  '--name', 'college-cards', '--title', 'College Flashcards', '--theme', 'forest'
], {cwd:repo, encoding:'utf8', timeout:15000});
assert.equal(build.status, 0, build.stderr);
assert.equal(JSON.parse(build.stdout).paid_requests,0);
assert.equal(JSON.parse(build.stdout).app.status,'generated_unverified');

const allowed = new Set(['/index.html','/styles.css','/app.js']);
const mime = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8'};
const server = http.createServer((req,res) => {
  const pathName = new URL(req.url,'http://localhost').pathname;
  const route = pathName === '/' ? '/index.html' : pathName;
  if (!allowed.has(route)) {res.writeHead(404).end();return;}
  fs.readFile(path.join(target,route.slice(1)),(error,body) => {
    if (error) {res.writeHead(404).end();return;}
    res.writeHead(200, {'Content-Type':mime[path.extname(route)],'Cache-Control':'no-store'});
    res.end(body);
  });
});

async function addCard(page, question, answer) {
  await page.fill('#front-input',question);
  await page.fill('#back-input',answer);
  await page.getByRole('button',{name:'Add flashcard'}).click();
}

(async () => {
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  let browser;
  try {
    browser = await webkit.launch({headless:true});
    const url = 'http://127.0.0.1:' + server.address().port;
    const context = await browser.newContext({...devices['iPhone 13']});
    const page = await context.newPage();
    const errors = [];
    const remote = [];
    page.on('pageerror',error => errors.push(error.message));
    page.on('request', req => {
      if (!req.url().startsWith(url)) remote.push(req.url());
    });
    await page.goto(url);
    assert.equal(await page.title(),'College Flashcards');
    assert.equal(await page.locator('#card-list .card-row').count(),0);
    assert.equal(await page.locator('#study-controls').isHidden(),true);
    await addCard(page,'What is algebra?','The study of quantities using variables');
    await addCard(page,'What is phonology?','A language sound system');
    assert.equal(await page.locator('#card-list .card-row').count(),2);
    assert.equal(await page.locator('#card-count').innerText(),'2 cards');
    assert.equal(await page.locator('#progress').innerText(),'0 of 2 learned');
    assert.equal(await page.locator('#face-text').innerText(),'What is algebra?');

    await page.getByRole('button',{name:'Flip card to see its answer'}).click();
    assert.equal(await page.locator('#face-label').innerText(),'ANSWER');
    assert.equal(await page.locator('#face-text').innerText(),'The study of quantities using variables');
    await page.getByRole('button',{name:'Next'}).click();
    assert.equal(await page.locator('#face-label').innerText(),'QUESTION');
    assert.equal(await page.locator('#face-text').innerText(),'What is phonology?');
    await page.getByRole('button',{name:'Mark learned'}).click();
    assert.equal(await page.locator('#progress').innerText(),'1 of 2 learned');
    assert.equal(await page.locator('#learned-card').getAttribute('aria-pressed'),'true');
    await page.reload();
    assert.equal(await page.locator('#progress').innerText(),'1 of 2 learned');
    assert.equal(await page.locator('#card-list .card-row').count(),2);

    await page.fill('#search-cards','LANGUAGE SOUND');
    assert.equal(await page.locator('#card-list .card-row').count(),1);
    await page.fill('#search-cards','no-match');
    assert.equal(await page.locator('#card-list .card-row').count(),0);
    assert.match(await page.locator('#empty-cards').innerText(),/No matching/);
    await page.fill('#search-cards','');

    await page.getByRole('button',{name:'Edit: What is algebra?'}).click();
    await page.fill('#back-input','Variables, expressions and equations.');
    await page.getByRole('button',{name:'Update flashcard'}).click();
    await page.getByRole('button',{name:'Flip card to see its answer'}).click();
    assert.equal(await page.locator('#face-text').innerText(),'Variables, expressions and equations.');

    const malicious = '<img src=x onerror="window.flashXss=true">';
    await addCard(page,malicious,'<script>alert(1)</script>');
    assert.equal(await page.locator('#card-list .card-row').count(),3);
    assert.equal(await page.locator('.card-row img').count(),0);
    assert.equal(await page.evaluate(() => Boolean(window.flashXss)),false);
    assert.equal(await page.locator('.card-row h3').last().innerText(),malicious);

    await page.getByRole('button',{name:'Delete: What is phonology?'}).click();
    assert.equal(await page.locator('#progress').innerText(),'0 of 2 learned');
    assert.equal(await page.locator('#card-count').innerText(),'2 cards');
    await page.reload();
    assert.equal(await page.locator('#card-list .card-row').count(),2);
    assert.equal(await page.locator('#progress').innerText(),'0 of 2 learned');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1),true);
    assert.deepEqual(errors,[]);
    assert.deepEqual(remote,[]);
    await context.close();

    const corrupt = await browser.newContext({...devices['iPhone 13']});
    const broken = await corrupt.newPage();
    await broken.goto(url);
    await broken.evaluate(() => localStorage.setItem('toad-sage-flashcards-v1:college-cards','{bad'));
    await broken.reload();
    assert.match(await broken.locator('#message').innerText(),/not be overwritten/i);
    await addCard(broken,'Recoverable question','This is temporary');
    assert.equal(await broken.locator('.card-row').count(),1);
    assert.equal(await broken.evaluate(() => localStorage.getItem('toad-sage-flashcards-v1:college-cards')),'{bad');
    await corrupt.close();

    const quota = await browser.newContext({...devices['iPhone 13']});
    await quota.addInitScript(() => {
      Storage.prototype.setItem = function () { throw new DOMException('No space','QuotaExceededError'); };
    });
    const noSpace = await quota.newPage();
    await noSpace.goto(url);
    await addCard(noSpace,'No storage','But still visible');
    assert.equal(await noSpace.locator('.card-row').count(),1);
    assert.match(await noSpace.locator('#message').innerText(),/not saved/i);
    await quota.close();
    console.log('PASS: free flashcards WebKit create/reload/flip/next/learned/edit/search/delete/XSS/corrupt-storage/quota/mobile');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
    fs.rmSync(workspace,{recursive:true,force:true});
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
