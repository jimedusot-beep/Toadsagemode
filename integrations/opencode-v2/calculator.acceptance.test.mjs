/** Frozen independent tests: preserve this contract while agents generate/repair. */
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const root = process.env.TOAD_CALCULATOR_DIR;
if (!root || !isAbsolute(root)) {
  throw new Error("Set TOAD_CALCULATOR_DIR to an absolute disposable project path");
}
const app = resolve(root);
for (const file of ["index.html", "styles.css", "app.mjs", "calculator.mjs"]) {
  if (!existsSync(resolve(app, file))) {
    throw new Error("Missing required generated file: " + file);
  }
}
const html = readFileSync(resolve(app, "index.html"), "utf8");
const ui = readFileSync(resolve(app, "app.mjs"), "utf8");
const logic = readFileSync(resolve(app, "calculator.mjs"), "utf8");
const css = readFileSync(resolve(app, "styles.css"), "utf8");
const { calculate } = await import(pathToFileURL(resolve(app, "calculator.mjs")).href);

test("pure calculate(operation, first, second) API exists", () => {
  assert.equal(typeof calculate, "function");
});
test("addition", () => assert.equal(calculate("add", 7, 5), 12));
test("subtraction", () => assert.equal(calculate("subtract", 7, 5), 2));
test("multiplication", () => assert.equal(calculate("multiply", 7, 5), 35));
test("division", () => assert.equal(calculate("divide", 7, 2), 3.5));
test("negative and decimal operands", () => {
  assert.equal(calculate("multiply", -2, 0.5), -1);
  assert.ok(Math.abs(calculate("add", 0.1, 0.2) - 0.3) < 1e-12);
});
test("division by zero rejects", () => {
  assert.throws(() => calculate("divide", 1, 0), RangeError);
});
test("unknown operation rejects", () => {
  assert.throws(() => calculate("power", 2, 2), RangeError);
});
test("invalid operands reject with TypeError", () => {
  for (const invalid of [NaN, Infinity, -Infinity, "2", undefined, null]) {
    assert.throws(() => calculate("add", invalid, 2), TypeError);
    assert.throws(() => calculate("add", 2, invalid), TypeError);
  }
});
test("logic module has no browser-global dependency", () => {
  assert.doesNotMatch(logic, /\b(?:window|document)\s*\./);
});
test("UI links external CSS and app module", () => {
  assert.match(html, /styles\.css/i);
  assert.match(html, /app\.mjs/i);
  assert.match(html, /type\s*=\s*["']module["']/i);
  assert.match(html, /<input\b/i);
  assert.match(html, /<button\b/i);
  assert.match(ui, /(?:from\s*["']\.\/?calculator\.mjs["']|import\s*\(\s*["']\.\/?calculator\.mjs["'])/);
});
test("UI has input labels and focus styling", () => {
  assert.match(html, /(?:<label\b|aria-label\s*=)/i);
  assert.match(css, /:focus(?:-visible)?\b/i);
});
test("no remote dependencies, inline handlers or dynamic code execution", () => {
  assert.doesNotMatch(html, /\bon[a-z]+\s*=/i);
  assert.doesNotMatch(html + ui + logic, /\beval\s*\(|new\s+Function\s*\(/);
  assert.doesNotMatch(html + ui, /https?:\/\//i);
  assert.doesNotMatch(ui, /\binnerHTML\s*=/);
});
