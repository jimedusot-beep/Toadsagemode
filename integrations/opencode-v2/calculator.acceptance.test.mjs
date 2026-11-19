import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";

const root = process.env.TOAD_CALCULATOR_DIR;
if (!root || !root.startsWith("/")) {
  throw new Error("Set TOAD_CALCULATOR_DIR to an absolute disposable project path");
}
const app = resolve(root);
const files = ["index.html", "styles.css", "calculator.mjs"];
for (const file of files) {
  if (!existsSync(resolve(app, file))) {
    throw new Error("Missing required generated file: " + file);
  }
}
const html = readFileSync(resolve(app, "index.html"), "utf8");
const js = readFileSync(resolve(app, "calculator.mjs"), "utf8");
const { calculate } = await import(pathToFileURL(resolve(app, "calculator.mjs")).href);

test("pure calculate(a, b, op) API exists", () => {
  assert.equal(typeof calculate, "function");
});
test("addition", () => assert.equal(calculate(2, 3, "+"), 5));
test("subtraction", () => assert.equal(calculate(8, 3, "-"), 5));
test("multiplication", () => assert.equal(calculate(7, 6, "*"), 42));
test("division", () => assert.equal(calculate(12, 4, "/"), 3));
test("negative and decimal operands", () => {
  assert.equal(calculate(-2, 0.5, "*"), -1);
  assert.ok(Math.abs(calculate(0.1, 0.2, "+") - 0.3) < 1e-12);
});
test("division by zero rejects", () => {
  assert.throws(() => calculate(1, 0, "/"), RangeError);
});
test("unknown operation rejects", () => {
  assert.throws(() => calculate(2, 2, "^"), RangeError);
});
test("invalid operands reject", () => {
  for (const invalid of [NaN, Infinity, -Infinity, "2", undefined, null]) {
    assert.throws(() => calculate(invalid, 2, "+"), TypeError);
    assert.throws(() => calculate(2, invalid, "+"), TypeError);
  }
});
test("simple browser UI is linked", () => {
  assert.match(html, /styles\.css/i);
  assert.match(html, /calculator\.mjs/i);
  assert.match(html, /type\s*=\s*["']module["']/i);
  assert.match(html, /<input\b/i);
  assert.match(html, /<button\b/i);
});
test("no code evaluation or inline scripts", () => {
  assert.doesNotMatch(js, /\beval\s*\(/);
  assert.doesNotMatch(js, /new\s+Function\s*\(/);
  assert.doesNotMatch(html, /\bon[a-z]+\s*=/i);
  assert.doesNotMatch(html, /https?:\/\//i);
});
