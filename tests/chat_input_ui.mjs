// Exercise the real input handlers without a browser or chat request.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../src/ask_hdb/api/static/app.js", import.meta.url), "utf8");
const code = source.slice(source.indexOf('box.addEventListener("input", grow)'), source.indexOf("// ---------- tabs"));
const box = { value: "我想买", listeners: {}, addEventListener(type, handler) { this.listeners[type] = handler; } };
const form = {
  listeners: {}, addEventListener(type, handler) { this.listeners[type] = handler; },
  requestSubmit() { this.listeners.submit({ preventDefault() {} }); },
};
const questions = [];
new Function("box", "form", "send", "ask", "grow", code)(box, form, { disabled: false }, (q) => questions.push(q), () => {});
const enter = (fields) => {
  const event = { key: "Enter", shiftKey: false, isComposing: false, defaultPrevented: false,
    preventDefault() { this.defaultPrevented = true; }, ...fields };
  box.listeners.keydown(event);
  return event;
};
assert.equal(enter({ isComposing: true }).defaultPrevented, false, "IME keeps Enter to confirm its candidate");
assert.equal(box.value, "我想买", "the unfinished draft stays in the field");
assert.deepEqual(questions, []);
assert.equal(enter({ shiftKey: true }).defaultPrevented, false, "Shift+Enter keeps its newline");
assert.deepEqual(questions, []);
assert.equal(enter({}).defaultPrevented, true, "ordinary Enter still submits");
assert.deepEqual(questions, ["我想买"]);
assert.equal(box.value, "");
