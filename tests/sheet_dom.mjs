// Reuse the real page with just the viewport and geometry APIs the sheet needs.
import { all, get } from "./ui_dom.mjs";
export function viewport(width) {
  const listeners = {}, viewportListeners = {};
  const mobile = { matches: width <= 800, addEventListener: (_, fn) => { mobile.change = fn; } };
  globalThis.window = { innerHeight: 800, matchMedia: (query) => query === "(max-width: 800px)" ? mobile
    : { matches: false, addEventListener() {} },
    addEventListener: (type, fn) => { listeners[type] = fn; },
    visualViewport: { height: 800, offsetTop: 0,
      addEventListener: (type, fn) => { viewportListeners[type] = fn; } } };
  globalThis.ResizeObserver = class {
    constructor(fn) { this.fn = fn; }
    observe() { this.fn(); }
    disconnect() {}
  };
  globalThis.fetch = () => { throw Error("Unexpected network request"); };
  return { mobile, resize: () => listeners.resize(), keyboard: () => viewportListeners.resize() };
}
export const snapshot = () => new Map(all().map((node) => [node, [...node.childNodes]]));
export const sheetHeight = () => parseFloat(get("app").style.getPropertyValue("--sheet-h"));
