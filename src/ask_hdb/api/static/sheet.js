// A phone layout of the same nodes: remember every slot before moving anything.
import { sheetGestures } from "./sheet-gestures.js";
const $ = (id) => document.getElementById(id);
export function initSheet({ chat = () => {} } = {}) {
  const mobile = window.matchMedia("(max-width: 800px)");
  const side = $("side"), app = $("app"), header = side.querySelector("header");
  let enabled = false, state = 0, pixels = 0, map = null, selected = !$("card").hidden;
  let slots = [], content, peek, handle, observer, cancelDrag = () => {};
  const points = () => {
    const available = Math.max(0, window.innerHeight - keyboard());
    return [Math.min(112, available), Math.min(window.innerHeight * .5, available),
      Math.min(window.innerHeight * .92, available)];
  };
  function keyboard() {
    const viewport = window.visualViewport;
    return viewport ? Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop) : 0;
  }
  function preview(value) {
    pixels = value;
    app.style.setProperty("--sheet-h", value + "px");
    side.dataset.dragging = "true";
  }
  function snap(next, focus = false) {
    if (!enabled) return;
    state = Math.max(0, Math.min(2, next));
    preview(points()[state]);
    delete side.dataset.dragging;
    side.dataset.snap = ["peek", "half", "full"][state];
    content.inert = state === 0;
    side.scrollTop = 0;
    if (state === 0) content.scrollTop = 0; // a place opens at its summary, not wherever the last scroll left the sheet
    handle.setAttribute("aria-label", "Results, " + ["peek", "half height", "full height"][state] +
      (state === 2 ? ". Press to collapse." : ". Press to expand."));
    map?.setPadding({ top: 0, left: 0, right: 0, bottom: pixels });
    if (focus && state > 0) $("tab-chat").focus();
  }
  function move(node, parent) { parent.append(node); }
  function select(point) {
    const closing = selected && !point;
    selected = !!point;
    if (!enabled) return;
    if (closing) chat();
    header.hidden = selected;
    $("peek-hint").hidden = selected;
    $("card-summary").hidden = !selected;
    $("card-close").hidden = !selected;
    snap(0); // A map selection never moves focus or fits the map.
  }
  function enter() {
    enabled = true; header.id = "sheet-header";
    const legend = document.querySelector(".legend"), seg = document.querySelector(".seg");
    const note = $("layer-note").parentNode;
    // Snapshot whole child lists, including whitespace, so adjacent moved siblings restore exactly.
    const nodes = [$("form"), $("selected"), $("card"), seg, $("toggle-3d"), $("price-controls"),
      $("lease-controls"), $("mop-controls"), $("sun-panel"), legend, note, $("building-error"), $("sun-panel-limits"),
      header, $("card-summary"), $("card-close"), ...side.children];
    slots = [...new Set(nodes.map((node) => node.parentNode))].map((parent) => [parent, [...parent.childNodes]]);
    peek = document.createElement("div"); peek.id = "sheet-peek";
    content = document.createElement("div"); content.id = "sheet-content";
    handle = document.createElement("button"); handle.id = "sheet-handle"; handle.type = "button";
    handle.setAttribute("aria-controls", "sheet-content");
    side.setAttribute("role", "region"); side.setAttribute("aria-label", "Results");
    // The summary stays above the inert fold; all disclosures share one scrolling content area.
    move(handle, peek); move(header, peek); move($("card-close"), peek);
    move($("card-summary"), peek); move(legend, peek);
    move($("card"), content); move($("sheet-notes"), content);
    for (const node of [...side.children]) if (node !== content) move(node, content);
    side.append(peek, content);
    $("peek-hint").textContent = "Ask about a flat, a grant or a place";
    move($("form"), $("topbar")); move($("selected"), $("topbar"));
    move(seg, $("chips")); move($("toggle-3d"), $("chips"));
    move($("price-controls"), $("chip-detail")); move($("lease-controls"), $("chip-detail")); move($("mop-controls"), $("chip-detail"));
    move($("sun-panel"), $("sun-bar"));
    for (const node of [note, $("building-error"), $("sun-panel-limits")]) move(node, $("sheet-notes"));
    cancelDrag = sheetGestures({ handles: [peek], button: handle, active: () => enabled,
      height: () => pixels, points, snap, preview });
    // Selection chips and layer details change height without a window resize.
    observer = new ResizeObserver(() => {
      app.style.setProperty("--topbar-bottom", $("topbar").getBoundingClientRect().bottom + "px");
      app.style.setProperty("--chip-detail-h", $("chip-detail").getBoundingClientRect().height + "px");
    });
    observer.observe($("topbar")); observer.observe($("chip-detail"));
    app.style.setProperty("--kb", keyboard() + "px");
    select(selected);
  }
  function leave() {
    enabled = false; cancelDrag(); observer.disconnect();
    // append moves existing nodes back; no clone, rebuild or listener replacement.
    for (const [parent, children] of slots) parent.append(...children);
    peek.remove(); content.remove();
    for (const id of ["card-summary", "card-close", "sheet-header", "peek-hint"]) $(id).hidden = false;
    $("peek-hint").textContent = "";
    header.removeAttribute("id");
    side.removeAttribute("role"); side.removeAttribute("aria-label");
    delete side.dataset.snap; delete side.dataset.dragging;
    for (const name of ["--sheet-h", "--kb", "--topbar-bottom", "--chip-detail-h"]) app.style.removeProperty(name);
    map?.setPadding({ top: 0, right: 0, bottom: 0, left: 0 });
  }
  function layout() { if (mobile.matches && !enabled) enter(); else if (!mobile.matches && enabled) leave(); }
  mobile.addEventListener("change", layout);
  window.addEventListener("resize", () => { if (enabled) snap(state); });
  window.visualViewport?.addEventListener("resize", () => {
    if (!enabled) return;
    app.style.setProperty("--kb", keyboard() + "px"); snap(state);
  });
  $("topbar").addEventListener("click", (event) => {
    if (!enabled || !$("form").contains(event.target)) return;
    chat(); snap(2); $("question").focus();
  });
  side.addEventListener("keydown", (event) => {
    if (!enabled) return;
    const fromHandle = event.target === handle;
    if (event.key === "Escape" && state > 0) { event.preventDefault(); snap(state - 1); }
    else if (fromHandle && ["ArrowUp", "ArrowDown", "Enter", " "].includes(event.key)) {
      event.preventDefault();
      snap(event.key === "ArrowDown" ? state - 1 : event.key === "ArrowUp" ? state + 1 : (state + 1) % 3);
    }
  });
  // Content is inert at peek, so only the peek area can take focus; keyboard entry from outside raises it.
  // A mouse or touch press also focuses the handle, so skip that and let the click step the sheet.
  let pressing = false;
  side.addEventListener("pointerdown", () => { pressing = true; }, true);
  for (const type of ["pointerup", "pointercancel"]) side.addEventListener(type, () => { pressing = false; }, true);
  side.addEventListener("focusin", (event) => {
    if (enabled && state === 0 && !pressing && peek.contains(event.target) && !side.contains(event.relatedTarget)) snap(1);
  });
  // Escape in the search bar steps the sheet down too.
  $("topbar").addEventListener("keydown", (event) => {
    if (enabled && event.key === "Escape" && state > 0) { event.preventDefault(); snap(state - 1); }
  });
  layout();
  return {
    select,
    section: () => { if (enabled && state < 1) snap(1); },
    answer: () => { if (enabled) { chat(); snap(1); } },
    setMap(value) { map = value; if (enabled) snap(state); },
    // setPadding in snap() already clears the sheet, so fitBounds needs only the plain gap.
    padding: (gap) => gap,
  };
}
