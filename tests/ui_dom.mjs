// A small DOM for controller tests, built from the real page by Python's HTML parser.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
export const folder = process.argv[2];
class TextNode {
  constructor(text) { this.textContent = text; this.parentNode = null; this.nodeType = 3; }
  remove() {
    if (this.parentNode) this.parentNode.childNodes = this.parentNode.childNodes.filter((node) => node !== this);
    this.parentNode = null;
  }
}
class Element {
  constructor(tag, attrs = {}) {
    this.nodeType = 1; this.tagName = tag; this.attrs = { ...attrs }; this.childNodes = []; this.parentNode = null;
    this.hidden = "hidden" in attrs; this.open = "open" in attrs; this.value = attrs.value || "";
    this.dataset = Object.fromEntries(Object.entries(attrs).filter(([k]) => k.startsWith("data-")).map(([k, v]) => [k.slice(5), v]));
    this.listeners = {}; this.inert = false;
    this.style = { setProperty: (key, value) => { this.style[key] = value; },
      removeProperty: (key) => { delete this.style[key]; }, getPropertyValue: (key) => this.style[key] || "" };
    this.classList = { toggle: (name, on) => {
      const classes = new Set((this.className || "").split(" ").filter(Boolean));
      if (on) classes.add(name); else classes.delete(name);
      this.className = [...classes].join(" ");
    } };
  }
  get id() { return this.attrs.id; }
  set id(value) { this.attrs.id = value; }
  get className() { return this.attrs.class || ""; }
  set className(value) { this.attrs.class = value; }
  get children() { return this.childNodes.filter((n) => n.nodeType === 1); }
  get textContent() { return this.childNodes.map((n) => n.textContent).join(""); }
  set textContent(text) { this.replaceChildren(...(String(text) ? [String(text)] : [])); }
  addEventListener(type, listener, capture = false) { (this.listeners[type] ||= []).push({ listener, capture }); }
  removeAttribute(key) { delete this.attrs[key]; }
  querySelectorAll(selector) { return query(this, selector); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) { for (let n = this; n; n = n.parentNode) if (matches(n, selector)) return n; return null; }
  focus() {
    for (let n = this; n; n = n.parentNode) if (n.inert) return; // inert subtrees refuse focus
    const previous = document.activeElement; document.activeElement = this; fire(this, "focusin", { relatedTarget: previous }); }
  setPointerCapture(id) { this.capture = id; }
  hasPointerCapture(id) { return this.capture === id; }
  releasePointerCapture() { this.capture = null; }
  getBoundingClientRect() { return this.rect || { bottom: 72, height: 0 }; }
  setAttribute(key, value) { this.attrs[key] = String(value); }
  getAttribute(key) { return this.attrs[key]; }
  append(...nodes) {
    for (let node of nodes) {
      if (typeof node === "string") node = new TextNode(node);
      node.remove(); node.parentNode = this;
      this.childNodes.push(node);
    }
  }
  appendChild(node) { this.append(node); return node; }
  replaceChildren(...nodes) {
    this.childNodes.forEach((node) => { node.parentNode = null; });
    this.childNodes = []; this.append(...nodes);
  }
  remove() {
    if (this.parentNode) this.parentNode.childNodes = this.parentNode.childNodes.filter((n) => n !== this);
    this.parentNode = null;
  }
  contains(node) { return this === node || this.children.some((child) => child.contains(node)); }
}
function build(node) {
  if (typeof node === "string") return node;
  const element = new Element(node.tag, node.attrs);
  element.append(...node.children.map(build));
  return element;
}
function matches(node, selector) {
  if (selector.startsWith("#")) return node.id === selector.slice(1);
  if (selector.startsWith(".")) return node.className.split(" ").includes(selector.slice(1));
  if (selector.startsWith("[data-")) return node.dataset[selector.slice(6, -1)] !== undefined;
  return node.tagName === selector;
}
function query(node, selector) {
  const parts = selector.split(" "), last = parts.pop();
  return all(node).filter((item) => {
    if (!matches(item, last)) return false;
    let parent = item.parentNode;
    return [...parts].reverse().every((part) => {
      while (parent && !matches(parent, part)) parent = parent.parentNode;
      if (!parent) return false;
      parent = parent.parentNode; return true;
    });
  });
}
export function fire(target, type, fields = {}) {
  const event = { type, target, button: 0, pointerId: 1, defaultPrevented: false,
    preventDefault() { this.defaultPrevented = true; }, stopPropagation() { this.stopped = true; }, ...fields };
  const path = []; for (let node = target; node; node = node.parentNode) path.push(node);
  for (const node of [...path].reverse()) for (const item of node.listeners[type] || []) {
    if (item.capture) item.listener(event);
  }
  for (const node of path) {
    if (event.stopped) break;
    for (const item of node.listeners[type] || []) if (!item.capture) item.listener(event);
    if (!event.defaultPrevented) node["on" + type]?.(event);
  }
  return event;
}
export const root = build(JSON.parse(await readFile(folder + "/page.json", "utf8")));
export const all = (node = root) => [node, ...node.children.flatMap((child) => all(child))];
export const get = (id) => {
  const found = all().filter((e) => e.id === id);
  assert.equal(found.length, 1, "one real DOM element for " + id);
  return found[0];
};
export const radiusButtons = () => all().filter((e) => e.dataset.km !== undefined);
globalThis.document = {
  getElementById: get,
  createElement: (tag) => new Element(tag),
  querySelectorAll: (selector) => query(root, selector),
  querySelector: (selector) => query(root, selector)[0] || null,
};
export const response = (data, ok = true) => ({ ok, json: async () => data });
export const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};
export const tick = () => new Promise((done) => setImmediate(done));
export const point = { kind: "block", id: "blk_a", label: "Blk <img src=x>", lat: 1.3, lng: 103.8 };
export class MapStub {
  constructor() { this.rings = []; this.highlights = []; this.fits = []; this.flies = []; }
  ring(rings, fit) { this.rings = rings; this.fits.push(fit); }
  highlight(points) { this.highlights = points; }
  fly(bounds) { this.flies.push(bounds); }
}
