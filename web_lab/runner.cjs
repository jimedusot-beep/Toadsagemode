/* Trusted in-container harness. NEVER execute on host or in GitHub Actions.
   The browser executes submitted JavaScript only INSIDE the isolated
   network-disabled Docker container; no host paths are mounted.
*/
'use strict';
const {webkit} = require('/opt/toad-web/node_modules/playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');

const FILES = new Set(['index.html', 'styles.css', 'app.js']);
const MIME = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8'};
const HEADERS = {
  'Cache-Control': 'no-store',
  'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'none'; img-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'",
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer'
};

async function receive() {
  const chunks = [];
  let length = 0;
  for await (const chunk of process.stdin) {
    length += chunk.length;
    if (length > 220000) throw Error('input_limit');
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}
function sameKeys(object, keys) {
  return object && typeof object === 'object' && !Array.isArray(object) &&
    Object.keys(object).length === keys.length && keys.every(key => Object.hasOwn(object, key));
}
function assertPackage(payload) {
  if (!sameKeys(payload, ['schema','files','checks']) || payload.schema !== 'toad-web-run-v1' ||
      !Array.isArray(payload.files) || payload.files.length !== 3 ||
      !Array.isArray(payload.checks) || payload.checks.length < 1 || payload.checks.length > 8) {
    throw Error('invalid_package');
  }
  const names = new Set();
  for (const file of payload.files) {
    if (!sameKeys(file,['path','content']) || !FILES.has(file.path) || names.has(file.path) ||
        typeof file.content !== 'string' || !file.content.trim() ||
        Buffer.byteLength(file.content,'utf8') > 64000) throw Error('invalid_file');
    names.add(file.path);
  }
  if (names.size !== FILES.size) throw Error('invalid_file_set');
  for (const check of payload.checks) {
    const fields = check.kind === 'title' ? ['kind','expected'] :
      check.kind === 'text' ? ['kind','selector','contains'] :
      check.kind === 'click_text' ? ['kind','selector','target','contains'] :
      check.kind === 'fill_click_text' ? ['kind','input','value','button','target','contains'] : null;
    if (!fields || !sameKeys(check,fields)) throw Error('invalid_check');
    for (const [key,value] of Object.entries(check)) {
      if (typeof value !== 'string' || value.length > 250 || (key !== 'value' && !value.trim())) {
        throw Error('invalid_check_field');
      }
    }
  }
}
async function openServer(root) {
  const server = http.createServer((req,res) => {
    let route;
    try {route = new URL(req.url,'http://localhost').pathname;} catch (_) {res.writeHead(400).end();return;}
    route = route === '/' ? '/index.html' : route;
    if (!FILES.has(route.slice(1)) || route.includes('%')) {res.writeHead(404).end();return;}
    const name = route.slice(1);
    fs.readFile(path.join(root,name)).then(body => {
      res.writeHead(200, {...HEADERS,'Content-Type':MIME[path.extname(name)]});
      res.end(body);
    }).catch(() => res.writeHead(404).end());
  });
  await new Promise((resolve,reject) => {server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  return server;
}
async function perform(page,check) {
  const option = {timeout:2500};
  if (check.kind === 'title') {
    const actual = await page.title();
    return actual === check.expected;
  }
  if (check.kind === 'text') {
    const text = await page.locator(check.selector).first().innerText(option);
    return text.includes(check.contains);
  }
  if (check.kind === 'click_text') {
    await page.locator(check.selector).first().click(option);
    const text = await page.locator(check.target).first().innerText(option);
    return text.includes(check.contains);
  }
  await page.locator(check.input).first().fill(check.value,option);
  await page.locator(check.button).first().click(option);
  const text = await page.locator(check.target).first().innerText(option);
  return text.includes(check.contains);
}
async function run() {
  let browser;
  let server;
  const outcome = {schema:'toad-web-browser-receipt-v1',browser:'webkit',
    executed:false,passed:false,checks:[],page_errors:0,blocked_requests:0};
  try {
    const payload = await receive();
    assertPackage(payload);
    const root = '/work/candidate';
    await fs.mkdir(root,{recursive:false,mode:0o700});
    for (const file of payload.files) {
      await fs.writeFile(path.join(root,file.path),file.content,{flag:'wx',mode:0o600});
    }
    server = await openServer(root);
    const origin = 'http://127.0.0.1:' + server.address().port;
    browser = await webkit.launch({headless:true, timeout:5000});
    const context = await browser.newContext({
      viewport:{width:390,height:844},serviceWorkers:'block',acceptDownloads:false,
      javaScriptEnabled:true
    });
    const page = await context.newPage();
    page.on('pageerror', () => {outcome.page_errors += 1;});
    await page.route('**/*', route => {
      let allowed = false;
      try {allowed = new URL(route.request().url()).origin === origin;} catch (_) {}
      if (allowed) return route.continue();
      outcome.blocked_requests += 1;
      return route.abort();
    });
    await page.goto(origin,{waitUntil:'load',timeout:5000});
    outcome.executed = true;
    for (let i=0;i<payload.checks.length;i++) {
      let passed = false;
      try {passed = await perform(page,payload.checks[i]);} catch (_) {}
      outcome.checks.push({index:i,kind:payload.checks[i].kind,passed:!!passed});
      if (!passed) break;
    }
    outcome.passed = outcome.page_errors === 0 && outcome.checks.length === payload.checks.length &&
      outcome.checks.every(result => result.passed);
    await context.close();
  } catch (error) {
    outcome.error_code = typeof error?.message === 'string' &&
      /^(input_limit|invalid_package|invalid_file|invalid_file_set|invalid_check|invalid_check_field)$/.test(error.message)
      ? error.message : 'browser_harness_failure';
  } finally {
    if (browser) await browser.close().catch(()=>{});
    if (server) await new Promise(resolve => server.close(resolve));
  }
  process.stdout.write(JSON.stringify(outcome) + '\n');
  if (!outcome.passed) process.exitCode = 1;
}
run().catch(() => {process.stdout.write(JSON.stringify({
  schema:'toad-web-browser-receipt-v1',executed:false,passed:false,error_code:'fatal_harness_failure',
  checks:[],page_errors:0,blocked_requests:0
})+'\n');process.exitCode=1;});
