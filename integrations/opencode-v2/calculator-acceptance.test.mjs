// Frozen before the first real OpenCode build. The agent must not modify this file.
// Run: node --test calculator-acceptance.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { calculate } from './calculator.mjs';

test('addition', () => assert.equal(calculate('add', 7, 5), 12));
test('subtraction', () => assert.equal(calculate('subtract', 7, 5), 2));
test('multiplication', () => assert.equal(calculate('multiply', 7, 5), 35));
test('division', () => assert.equal(calculate('divide', 7, 2), 3.5));
test('division by zero throws RangeError', () => {
  assert.throws(() => calculate('divide', 7, 0), RangeError);
});
test('web assets exist', () => {
  for (const file of ['index.html', 'styles.css', 'app.mjs', 'calculator.mjs']) {
    assert.ok(existsSync(new URL(file, import.meta.url)), `${file} missing`);
  }
  const html = readFileSync(new URL('index.html', import.meta.url), 'utf8');
  assert.match(html, /styles\.css/);
  assert.match(html, /app\.mjs/);
});
