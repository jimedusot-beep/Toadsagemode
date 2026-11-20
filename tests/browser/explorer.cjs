/* Real WebKit smoke tests for Sage Studio's FIXTURE-ONLY Project Explorer.
 * No AI generation, code execution, cloud provider, external network or deployment.
 */
'use strict';
const assert = require('node:assert/strict');
const {webkit, devices} = require('playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../../free-studio');
const routes = new Set([
  '/index.html', '/styles.css', '/v2.css',
  '/explorer.html', '/explorer.css', '/explorer.js',
  '/explorer-adapter.js', '/explorer-fixtures.json'
]);
const mime = {'.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8',
              '.js':'text/javascript; charset=utf-8', '.json':'application/json; charset=utf-8'};
const server = http.createServer((req, res) => {
  const target = new URL(req.url, 'http://localhost').pathname;
  const name = target === '/' ? '/index.html' : target;
  if (!routes.has(name)) {res.writeHead(404).end();return;}
  fs.readFile(path.join(root, name.slice(1)), (error, body) => {
    if (error) {res.writeHead(404).end();return;}
    res.writeHead(200, {'Content-Type':mime[path.extname(name)], 'Cache-Control':'no-store'});
    res.end(body);
  });
});

async function ready(page, url) {
  await page.goto(url + '/explorer.html');
  await page.waitForFunction(() => document.querySelector('#explorer-notice').textContent.includes('Loaded 5 fixture projects.'));
}
function fixture() {
  return JSON.parse(fs.readFileSync(path.join(root,'explorer-fixtures.json'),'utf8'));
}

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await webkit.launch({headless:true});
    const url = 'http://127.0.0.1:' + server.address().port;
    const phone = await browser.newContext({...devices['iPhone 13']});
    const page = await phone.newPage();
    const errors = [];
    const offsite = [];
    page.on('pageerror', err => errors.push(err.message));
    page.on('request', req => {if (!req.url().startsWith(url)) offsite.push(req.url());});
    await ready(page, url);

    assert.match(await page.title(), /Project Explorer V1/);
    assert.match(await page.locator('#fixture-heading').innerText(), /Local fixture demonstration/);
    assert.equal(await page.locator('#explorer-project-list button').count(), 5);
    assert.match(await page.locator('#explorer-project-state').innerText(), /Fixture: draft.*sample only/);
    assert.equal(await page.locator('#explorer-file-list button').count(), 4);
    assert.equal(await page.locator('#explorer-selected-path').innerText(), 'index.html');
    assert.match(await page.locator('#explorer-source').innerText(), /Study Planner/);
    assert.match(await page.locator('#explorer-revision-state').innerText(), /Fixture: untested/);
    assert.match(await page.locator('#explorer-before').innerText(), /Start with one task/);
    assert.match(await page.locator('#explorer-after').innerText(), /Start with your most important task/);
    assert((await page.locator('#explorer-before .diff-removed').count()) > 0);
    assert((await page.locator('#explorer-after .diff-added').count()) > 0);
    assert.match(await page.locator('#explorer-revision-output').innerText(), /BLOCKED.*fixture/);

    // File selection works with a real keyboard and displays plain code.
    const sourceButton = page.getByRole('button', {name:'Read source: src/app.js'});
    await sourceButton.focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#explorer-selected-path').innerText(), 'src/app.js');
    assert.match(await page.locator('#explorer-source').innerText(), /Start with one task/);
    assert.equal(await sourceButton.getAttribute('aria-current'), 'true');
    await sourceButton.focus();
    const outline = await sourceButton.evaluate(el => getComputedStyle(el).outlineStyle);
    assert.notEqual(outline, 'none', 'Keyboard focus must remain visible');

    // An explicit confirmation is necessary for DEMO approval.
    page.once('dialog', dialog => dialog.dismiss());
    await page.getByRole('button', {name:'Approve demo revision'}).click();
    assert.match(await page.locator('#explorer-decision').innerText(), /No demo decision/);
    page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button', {name:'Approve demo revision'}).click();
    assert.match(await page.locator('#explorer-decision').innerText(), /Demo approved.*page only/);
    assert.equal(await page.getByRole('button', {name:'Approve demo revision'}).isDisabled(), true);
    assert.match(await page.locator('#explorer-revision-state').innerText(), /Fixture: untested/);
    assert.equal(await page.evaluate(() => localStorage.length), 0, 'Explorer must not persist approval');

    // A failed status must remain failed and rejection must be explicit too.
    await page.getByRole('button', {name:'Open fixture project: Notes Debugging · example'}).click();
    assert.match(await page.locator('#explorer-project-state').innerText(), /Fixture: failed/);
    assert.match(await page.locator('#explorer-revision-output').innerText(), /TypeError/);
    page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button', {name:'Reject demo revision'}).click();
    assert.match(await page.locator('#explorer-decision').innerText(), /Demo rejected/);
    assert.match(await page.locator('#explorer-test-state').innerText(), /Fixture: failed/);

    // A verified status remains explicitly labeled as a SAMPLE with no evidence.
    await page.getByRole('button', {name:'Open fixture project: Flashcards · status example'}).click();
    assert.match(await page.locator('#explorer-test-state').innerText(), /Fixture: verified.*sample only/);
    assert.match(await page.locator('#explorer-test-output').innerText(), /VERIFIED SAMPLE.*fixture data only/);
    assert.equal(await page.getByRole('button', {name:'Approve demo revision'}).isDisabled(), true);
    await page.getByRole('button', {name:'Open fixture project: Testing · status example'}).click();
    assert.match(await page.locator('#explorer-test-state').innerText(), /Fixture: testing.*sample only/);
    await page.getByRole('button', {name:'Open fixture project: Empty Project · example'}).click();
    assert.match(await page.locator('#explorer-empty').innerText(), /Empty project/);
    assert.equal(await page.locator('#explorer-file-list button').count(), 0);
    assert.equal(await page.getByRole('button', {name:'Reject demo revision'}).isDisabled(), true);

    // Session-only state disappears on reload.
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#explorer-notice').textContent.includes('Loaded 5'));
    assert.match(await page.locator('#explorer-decision').innerText(), /No demo decision recorded/);

    // Real responsive bounds: no page-wide horizontal scrolling on phone.
    const phoneFits = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
    assert.equal(phoneFits, true, 'Phone layout must not horizontally overflow');

    // Tablet uses the same UI and retains readable source/test output.
    const tablet = await browser.newContext({viewport:{width:834,height:1112},hasTouch:true,isMobile:true});
    const tabletPage = await tablet.newPage();
    await ready(tabletPage, url);
    assert.equal(await tabletPage.locator('#explorer-file-list button').count(), 4);
    assert.equal(await tabletPage.evaluate(() =>
      document.documentElement.scrollWidth <= window.innerWidth + 1), true);
    assert.equal(await tabletPage.locator('#explorer-after').isVisible(),true);
    await tablet.close();

    // Browser storage is unavailable: Explorer still works, because it never accesses it.
    const storage = await browser.newContext({...devices['iPhone 13']});
    await storage.addInitScript(() => {
      Object.defineProperty(window, 'localStorage', {
        configurable:true,
        get() {throw new DOMException('Disabled', 'SecurityError');}
      });
    });
    const denied = await storage.newPage();
    await ready(denied, url);
    await denied.getByRole('button', {name:'Open fixture project: Notes Debugging · example'}).click();
    assert.match(await denied.locator('#explorer-source').innerText(), /Save note/);
    await storage.close();

    // Missing fixture, corrupt JSON, invalid path: fail closed with retry option.
    const failures = [
      route => route.fulfill({status:404,body:'not found'}),
      route => route.fulfill({contentType:'application/json',body:'{bad json'}),
      route => {
        const obj = fixture();
        obj.projects[0].files[0].path = '../private/secret.js';
        return route.fulfill({contentType:'application/json',body:JSON.stringify(obj)});
      }
    ];
    for (const failWith of failures) {
      const bad = await browser.newContext({...devices['iPhone 13']});
      const failed = await bad.newPage();
      await failed.route('**/explorer-fixtures.json',failWith);
      await failed.goto(url+'/explorer.html');
      await failed.getByRole('button',{name:'Retry loading example data'}).waitFor();
      assert.match(await failed.locator('#explorer-notice').innerText(), /Cannot load safe fixture/);
      assert.equal(await failed.locator('#explorer-project-list button').count(),0);
      assert.equal(await failed.getByRole('button',{name:'Approve demo revision'}).isDisabled(),true);
      await bad.close();
    }

    // A long filename, large source, and malicious-looking HTML are inert text.
    const hostile = fixture();
    const longName = 'src/' + 'a'.repeat(95) + '.js';
    const markup = '<img src=x onerror="window.explorerXss=true">';
    hostile.projects[4].files.push({path:longName,content:markup+'\n'+'x'.repeat(10000)});
    const injected = await browser.newContext({...devices['iPhone 13']});
    const injection = await injected.newPage();
    await injection.route('**/explorer-fixtures.json', route =>
      route.fulfill({contentType:'application/json',body:JSON.stringify(hostile)}));
    await ready(injection, url);
    await injection.getByRole('button',{name:'Open fixture project: Empty Project · example'}).click();
    await injection.getByRole('button',{name:'Read source: '+longName}).click();
    assert.match(await injection.locator('#explorer-source').innerText(), /<img src=x/);
    assert.equal(await injection.locator('#explorer-source img').count(),0);
    assert.equal(await injection.evaluate(()=>Boolean(window.explorerXss)),false);
    assert.equal(await injection.evaluate(() =>
      document.documentElement.scrollWidth <= window.innerWidth + 1), true);
    await injected.close();

    // Local import rejects invalid files atomically and requires confirmation.
    await page.setInputFiles('#explorer-import-file', {
      name:'corrupt.json',mimeType:'application/json',buffer:Buffer.from('{not-json')
    });
    await page.getByRole('button',{name:'Inspect selected fixture JSON'}).click();
    assert.match(await page.locator('#explorer-notice').innerText(), /Fixture import refused/);
    assert.equal(await page.locator('#explorer-project-list button').count(),5);
    await page.setInputFiles('#explorer-import-file', {
      name:'huge.json',mimeType:'application/json',buffer:Buffer.alloc(100001,65)
    });
    await page.getByRole('button',{name:'Inspect selected fixture JSON'}).click();
    assert.match(await page.locator('#explorer-notice').innerText(), /exceeds 100 KB/);
    assert.equal(await page.locator('#explorer-project-list button').count(),5);

    const imported = fixture();
    imported.projects = [imported.projects[4]]; // one empty demo
    await page.setInputFiles('#explorer-import-file', {
      name:'safe.json',mimeType:'application/json',
      buffer:Buffer.from(JSON.stringify(imported))
    });
    page.once('dialog',dialog=>dialog.dismiss());
    await page.getByRole('button',{name:'Inspect selected fixture JSON'}).click();
    assert.equal(await page.locator('#explorer-project-list button').count(),5);
    page.once('dialog',dialog=>dialog.accept());
    await page.getByRole('button',{name:'Inspect selected fixture JSON'}).click();
    assert.equal(await page.locator('#explorer-project-list button').count(),1);
    assert.match(await page.locator('#explorer-notice').innerText(), /local imported fixture projects/);
    await page.getByRole('button',{name:'Restore built-in examples'}).click();
    await page.waitForFunction(()=>document.querySelector('#explorer-project-list').querySelectorAll('button').length===5);
    assert.equal(await page.evaluate(()=>localStorage.length),0);

    // Two separate source changes must preserve an unchanged middle line.
    const twoHunks = fixture();
    const originalSource = 'start\nold first\nmiddle untouched\nold second\nend';
    const nextSource = 'start\nnew first\nmiddle untouched\nnew second\nend';
    const updatedFile = twoHunks.projects[0].files.find(x=>x.path==='src/app.js');
    updatedFile.content = originalSource;
    twoHunks.projects[0].revision.before = originalSource;
    twoHunks.projects[0].revision.after = nextSource;
    const multi = await browser.newContext({...devices['iPhone 13']});
    const multiple = await multi.newPage();
    await multiple.route('**/explorer-fixtures.json', route=>
      route.fulfill({contentType:'application/json',body:JSON.stringify(twoHunks)}));
    await ready(multiple,url);
    assert.match(await multiple.locator('#explorer-diff-status').innerText(),
      /Exact line comparison: 2 added, 2 removed, 2 change groups/);
    assert.match(await multiple.locator('#explorer-before .diff-same').allTextContents()
      .then(lines=>lines.join('\n')),/middle untouched/);
    assert.equal(await multiple.locator('#explorer-before .diff-removed')
      .filter({hasText:'middle untouched'}).count(),0);
    assert.equal(await multiple.locator('#explorer-after .diff-added')
      .filter({hasText:'middle untouched'}).count(),0);
    assert.match(await multiple.locator('#explorer-before .diff-removed').first().innerText(),
      /\d+\s+− old first/);
    await multi.close();

    // Large changes keep ALL source readable while explicitly disabling
    // granular highlighting, avoiding thousands of DOM spans on mobile.
    const large = fixture();
    const hugeBefore = Array.from({length:700},(_,i)=>'old'+i).join('\n');
    const hugeAfter = Array.from({length:700},(_,i)=>'new'+i).join('\n');
    large.projects[0].files.find(x=>x.path==='src/app.js').content = hugeBefore;
    large.projects[0].revision.before = hugeBefore;
    large.projects[0].revision.after = hugeAfter;
    const giant = await browser.newContext({...devices['iPhone 13']});
    const oversized = await giant.newPage();
    await oversized.route('**/explorer-fixtures.json', route=>
      route.fulfill({contentType:'application/json',body:JSON.stringify(large)}));
    await ready(oversized,url);
    assert.match(await oversized.locator('#explorer-diff-status').innerText(),
      /Large comparison: showing the COMPLETE original and proposed source as plain text/);
    assert.match(await oversized.locator('#explorer-diff-status').innerText(),
      /change counts are approximate/);
    assert.match(await oversized.locator('#explorer-before').innerText(),/old699/);
    assert.match(await oversized.locator('#explorer-after').innerText(),/new699/);
    assert.equal(await oversized.locator('#explorer-after .diff-line').count(),0);
    assert.equal(await oversized.evaluate(()=>
      document.documentElement.scrollWidth <= window.innerWidth + 1),true);
    await giant.close();

    assert.deepEqual(errors, [],'No WebKit page errors');
    assert.deepEqual(offsite, [],'No requests off the local Studio origin');
    await phone.close();
    console.log('Sage Explorer V1 WebKit: phone/tablet, keyboard, fixture diff, mock decisions, storage and failure paths PASS (no AI or generated-code execution).');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
})().catch(error=>{console.error(error);process.exitCode=1;server.close();});
