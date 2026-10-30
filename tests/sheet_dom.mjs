// Reuse the real page with just the viewport and geometry APIs the sheet needs.
import { all, get } from "./ui_dom.mjs";
export function viewport(width) {
  const listeners = {}, viewportListeners = {};
  // The sheet system runs at every width; `wide` says whether the sheet is the docked left panel.
  const mobile = { matches: true, addEventListener: (_, fn) => { mobile.change = fn; } };
  const wide = { matches: width > 800, addEventListener: (_, fn) => { wide.change = fn; } };
  globalThis.window = { innerHeight: 800, matchMedia: (query) => query === "(min-width: 0px)" ? mobile
    : query === "(min-width: 801px)" ? wide : { matches: false, addEventListener() {} },
    addEventListener: (type, fn) => { listeners[type] = fn; },
    visualViewport: { height: 800, offsetTop: 0,
      addEventListener: (type, fn) => { viewportListeners[type] = fn; } } };
  globalThis.ResizeObserver = class {
    constructor(fn) { this.fn = fn; }
    observe() { this.fn(); }
    disconnect() {}
  };
  globalThis.fetch = () => { throw Error("Unexpected network request"); };
  return { mobile, wide, resize: () => listeners.resize(), keyboard: () => viewportListeners.resize() };
}
export const snapshot = () => new Map(all().map((node) => [node, [...node.childNodes]]));
export const sheetHeight = () => parseFloat(get("app").style.getPropertyValue("--sheet-h"));
