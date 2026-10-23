// A small DOM for controller tests, built from the real page by Python's HTML parser.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
export const folder = process.argv[2];
class Element {
  constructor(tag, attrs = {}) {
    this.tagName = tag; this.attrs = { ...attrs }; this.childNodes = []; this.parentNode = null;
    this.hidden = "hidden" in attrs; this.open = "open" in attrs; this.value = attrs.value || "";
    this.dataset = Object.fromEntries(Object.entries(attrs).filter(([k]) => k.startsWith("data-")).map(([k, v]) => [k.slice(5), v]));
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
  get children() { return this.childNodes.filter((n) => typeof n !== "string"); }
  get textContent() { return this.childNodes.map((n) => typeof n === "string" ? n : n.textContent).join(""); }
  set textContent(text) { this.replaceChildren(String(text)); }
  setAttribute(key, value) { this.attrs[key] = String(value); }
  getAttribute(key) { return this.attrs[key]; }
  append(...nodes) {
    for (const node of nodes) {
      if (typeof node !== "string") { node.remove(); node.parentNode = this; }
      this.childNodes.push(node);
    }
  }
  appendChild(node) { this.append(node); return node; }
  replaceChildren(...nodes) {
    this.children.forEach((node) => { node.parentNode = null; });
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
  querySelectorAll: (selector) => {
    assert.equal(selector, ".radius button");
    return radiusButtons();
  },
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
