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
const files = ["index.html", "styles.css", "app.mjs", "calculator.mjs"];
for (const file of files) {
  if (!existsSync(resolve(app, file))) {
    throw new Error("Missing required generated file: " + file);
  }
}
const html = readFileSync(resolve(app, "index.html"), "utf8");
const calcJs = readFileSync(resolve(app, "calculator.mjs"), "utf8");
const uiJs = readFileSync(resolve(app, "app.mjs"), "utf8");
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
test("division by zero throws", () => {
  assert.throws(() => calculate("divide", 1, 0), RangeError);
});
test("unknown operation throws", () => {
  assert.throws(() => calculate("power", 2, 2), RangeError);
});
test("non-finite and non-number operands reject", () => {
  for (const bad of [NaN, Infinity, -Infinity, "2", undefined, null]) {
    assert.throws(() => calculate("add", bad, 2), TypeError);
    assert.throws(() => calculate("add", 2, bad), TypeError);
  }
});
test("browser UI references CSS and application module", () => {
  assert.match(html, /styles\.css/i);
  assert.match(html, /app\.mjs/i);
  assert.match(html, /type\s*=\s*["']module["']/i);
  assert.match(html, /<input\b/i);
  assert.match(html, /<button\b/i);
  assert.match(uiJs, /calculator\.mjs/i);
});
test("no inline JavaScript or obvious code evaluation", () => {
  for (const script of [uiJs, calcJs]) {
    assert.doesNotMatch(script, /\beval\s*\(/);
    assert.doesNotMatch(script, /new\s+Function\s*\(/);
  }
  assert.doesNotMatch(html, /\bon[a-z]+\s*=/i);
  assert.doesNotMatch(html, /https?:\/\//i);
});
