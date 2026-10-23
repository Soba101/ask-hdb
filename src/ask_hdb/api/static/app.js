// Plain JS, no build step. The chat history lives only in this page's memory and is sent with each question.
// The map is the main view: click a block, school, station or BTO site to select it; the chat then knows what
// "this block" means. Map highlights come from the server, built by code from tool results, never from model text.
import { initBuildings, initLayers } from "./buildings.js";
import { initCard } from "./card.js";
const $ = (id) => document.getElementById(id);
initLayers();
const log = $("log"), form = $("form"), box = $("question"), send = $("send");
const tools = $("tools"), sources = $("sources"), empty = $("empty");
const history = [];
const MAX_TURNS = 12;
let selected = null; // {kind, id, label, lat, lng}

// ---------- chat ----------
function add(kind, text) {
  const div = document.createElement("div");
  div.className = "msg " + kind;
  // Text nodes only, never HTML: model output and tool results are untrusted. **bold** becomes <strong>.
  text.split("**").forEach((part, i) => {
    if (i % 2) { const strong = document.createElement("strong"); strong.textContent = part; div.appendChild(strong); }
    else div.append(part);
  });
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

function summary(args) {
  return Object.entries(args).filter(([, v]) => v !== null && v !== "").map(([k, v]) => k + ": " + v).join(", ");
}

function addTool(event) {
  empty.hidden = true;
  const card = document.createElement("div");
  card.className = "tool";
  const name = document.createElement("b");
  name.textContent = event.name;
  const args = document.createElement("div");
  args.className = "args";
  args.textContent = summary(event.args || {});
  card.append(name, args);
  tools.appendChild(card);
  $("evidence-count").textContent = "(" + tools.children.length + ")";
  return card;
}

function addResult(card, event) {
  const details = document.createElement("details");
  const label = document.createElement("summary");
  label.textContent = "Result";
  const pre = document.createElement("pre");
  const text = JSON.stringify(event.result, null, 2);
  pre.textContent = text.length > 4000 ? text.slice(0, 4000) + "\n… (cut)" : text;
  details.append(label, pre);
  card.appendChild(details);
  collectSources(event.result);
}

const seen = new Set();
function collectSources(node) {
  if (Array.isArray(node)) return node.forEach(collectSources);
  if (node && typeof node === "object") {
    if (typeof node.source === "string" && /^https:\/\//.test(node.source)) addSource(node.source, node.as_of);
    Object.values(node).forEach(collectSources);
  }
}

function addSource(url, asOf) {
  if (seen.has(url)) return;
  seen.add(url);
  if (!sources.firstChild) {
    const title = document.createElement("h2");
    title.className = "section";
    title.textContent = "Sources";
    sources.append(title, document.createElement("ul"));
  }
  const li = document.createElement("li");
  const a = document.createElement("a");
  a.href = url;
  a.textContent = url.replace(/^https:\/\//, "");
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  li.appendChild(a);
  if (asOf) li.append(" (as of " + asOf + ")");
  sources.querySelector("ul").appendChild(li);
}

function clearEvidence() {
  tools.replaceChildren();
  sources.replaceChildren();
  $("points").replaceChildren();
  $("evidence-count").textContent = "";
  seen.clear();
  empty.hidden = false;
  mapLayer.highlight([]);
}

async function* events(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      if (block.startsWith("data: ")) yield JSON.parse(block.slice(6));
    }
  }
}

async function ask(question) {
  if (send.disabled) return; // one question at a time
  document.querySelectorAll(".choices.confirm").forEach((c) => c.remove()); // an old "Yes" must not answer a newer turn
  add("user", question);
  clearEvidence();
  send.disabled = true;
  const status = document.createElement("div"); // outside the live region: a ticking timer must not be read out every second
  status.className = "msg status";
  status.textContent = "Working on it… 0s";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "off");
  log.after(status);
  const started = Date.now();
  const timer = setInterval(() => { status.textContent = "Working on it… " + Math.round((Date.now() - started) / 1000) + "s"; }, 1000);
  const cards = [];
  let answered = false;
  pendingChoices = null;
  try {
    const context = selected ? { selected: { kind: selected.kind, id: selected.id } } : {};
    const response = await fetch("/chat", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ question, history: history.slice(-MAX_TURNS), context }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === "string" ? body.detail : "The request was refused (" + response.status + ").");
    }
    for await (const event of events(response)) {
      if (event.type === "tool_call") cards.push(addTool(event));
      else if (event.type === "tool_result") addResult(cards[cards.length - 1] || addTool(event), event);
      else if (event.type === "map") runMapActions(event.actions);
      else if (event.type === "choices") pendingChoices = event.candidates;
      else if (event.type === "error") throw new Error(event.message);
      else if (event.type === "answer") { answered = true; show(question, event); }
    }
    if (!answered) throw new Error("The answer was cut off. Please try again.");
  } catch (error) {
    add("error", error.message);
  } finally {
    clearInterval(timer);
    status.remove();
    send.disabled = false;
    box.focus();
  }
}

let pendingChoices = null;

function showChoices(question, candidates) {
  const div = add("bot", "Which one do you mean?");
  const choices = document.createElement("div");
  choices.className = "choices";
  for (const c of candidates) {
    const button = document.createElement("button");
    button.className = "secondary";
    button.textContent = c.label;
    button.onclick = () => {
      if (send.disabled) return; // a question is running; keep the chips so the choice is not lost
      choices.remove();
      setSelected({ kind: c.kind, id: c.id, label: c.label, lat: c.lat, lng: c.lng });
      mapLayer.fly([c.lng, c.lat, c.lng, c.lat]);
      ask(question); // ask the same question again, now about the chosen place
    };
    choices.appendChild(button);
  }
  div.appendChild(choices);
}

function show(question, event) {
  const div = add("bot", event.answer);
  if (pendingChoices) { showChoices(question, pendingChoices); pendingChoices = null; }
  // The server accepts at most 2000 characters per earlier turn; cut here so a long answer cannot block later questions.
  history.push({ role: "user", content: question.slice(0, 1000) }, { role: "assistant", content: event.answer.slice(0, 2000) });
  if (event.needs_confirmation) {
    const choices = document.createElement("div");
    choices.className = "choices confirm";
    const yes = document.createElement("button");
    yes.textContent = "Yes, that's right";
    yes.onclick = () => { choices.remove(); ask("yes"); };
    const change = document.createElement("button");
    change.textContent = "Change something";
    change.className = "secondary";
    change.onclick = () => { choices.remove(); box.placeholder = "Tell me what to change"; box.focus(); };
    choices.append(yes, change);
    div.appendChild(choices);
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const question = box.value.trim();
  if (!question || send.disabled) return;
  box.value = "";
  box.placeholder = "Ask about a flat, a grant or a place";
  ask(question);
});
box.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
});

// ---------- tabs ----------
function tab(which) {
  const chat = which === "chat";
  $("chat").hidden = !chat;
  $("evidence").hidden = chat;
  $("tab-chat").classList.toggle("on", chat);
  $("tab-evidence").classList.toggle("on", !chat);
  $("tab-chat").setAttribute("aria-pressed", String(chat));
  $("tab-evidence").setAttribute("aria-pressed", String(!chat));
}
$("tab-chat").onclick = () => tab("chat");
$("tab-evidence").onclick = () => tab("evidence");

// ---------- selection and info card ----------
function setSelected(point) {
  selected = point;
  $("selected").hidden = !point;
  if (point) $("selected-label").textContent = point.label;
  mapLayer.select(point);
  card.select(point);
}
$("selected-clear").onclick = () => setSelected(null);

// ---------- price and lease layers ----------
let layerMode = "type";
const metricsCache = {};
let layerRequest = 0;

function fmtMoney(n) { return "$" + Math.round(n).toLocaleString("en-SG"); }

async function applyLayer() {
  const mine = ++layerRequest;
  card.refreshMetrics(); // A different flat type must not retain the previous type's headline.
  document.querySelectorAll("#layers [data-mode]").forEach((b) => {
    const on = b.dataset.mode === layerMode;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", String(on));
  });
  $("price-controls").hidden = layerMode !== "price";
  $("lease-controls").hidden = layerMode !== "lease";
  $("layer-note").textContent = "";
  if (layerMode === "type") { mapLayer.layer("type", null, 0); return; }
  const flat = layerMode === "price" ? $("flat-type").value : "4 ROOM"; // lease does not depend on the flat type
  try {
    if (!metricsCache[flat]) {
      const response = await fetch("/map/metrics?flat_type=" + encodeURIComponent(flat));
      if (!response.ok) throw new Error("no metrics");
      metricsCache[flat] = await response.json();
    }
  } catch (error) {
    if (mine !== layerRequest) return;
    $("layer-note").textContent = "Price and lease data could not be loaded.";
    return;
  }
  if (mine !== layerRequest) return; // an older response must not overwrite the current colour mode
  card.refreshMetrics();
  const data = metricsCache[flat];
  const prices = Object.values(data.blocks).map((r) => r[0]).filter(Boolean).sort((a, b) => a - b);
  const slider = $("budget");
  if (layerMode === "price" && prices.length) {
    if (slider.dataset.flat !== flat) { // a new flat type resets the budget to the top of its range
      slider.min = String(Math.floor(prices[0] / 10000) * 10000);
      slider.max = String(Math.ceil(prices[prices.length - 1] / 10000) * 10000);
      slider.value = slider.max;
      slider.dataset.flat = flat;
    }
    $("budget-label").textContent = fmtMoney(Number(slider.value));
    slider.setAttribute("aria-valuetext", fmtMoney(Number(slider.value)));
    const at = (q) => prices[Math.min(prices.length - 1, Math.floor(prices.length * q))];
    $("ramp-low").textContent = fmtMoney(at(0.1));
    $("ramp-high").textContent = fmtMoney(at(0.9));
  }
  mapLayer.layer(layerMode, data, Number(slider.value || 0));
  $("layer-note").textContent = layerMode === "price"
    ? "Grey: fewer than " + data.min_sales + " sales, or above your budget. " + data.limits.join(" ")
    : data.limits[2] + " Based on the lease start year of each block.";
}
document.querySelectorAll("#layers [data-mode]").forEach((b) => { b.onclick = () => { layerMode = b.dataset.mode; applyLayer(); }; });
$("flat-type").onchange = applyLayer;
$("budget").oninput = () => { $("budget-label").textContent = fmtMoney(Number($("budget").value)); $("budget").setAttribute("aria-valuetext", fmtMoney(Number($("budget").value))); if (metricsCache[$("flat-type").value]) applyLayer(); };

// ---------- map ----------
// Until the map has loaded, calls are remembered and applied when it is ready, so an early answer is not lost.
const todo = { highlight: [], select: null, fly: null, ring: null, layer: null };
const mapLayer = {
  ring(rings, fit) { todo.ring = rings.length ? { rings, fit } : null; },
  layer(mode, data, budget) { todo.layer = { mode, data, budget }; },
  highlight(points) { todo.highlight = points; },
  select(point) { todo.select = point; },
  fly(bbox) { todo.fly = bbox; },
};
const card = initCard({
  mapLayer,
  metrics: () => ({ flat: $("flat-type").value, data: metricsCache[$("flat-type").value] }),
  ask: (question) => { tab("chat"); ask(question); },
});
let maplibregl = null;
const COLORS = ["match", ["get", "kind"], "block", "#1d5fd6", "mrt", "#d62d2d", "lrt", "#d62d2d",
  "primary_school", "#1f9d55", "bto", "#e08a00", "#888888"];
const EMPTY = { type: "FeatureCollection", features: [] };

function runMapActions(actions) {
  for (const action of actions) {
    if (action.op === "highlight") {
      card.chatHighlight();
      mapLayer.highlight(action.points);
      const list = $("points");
      list.replaceChildren();
      for (const p of action.points) {
        const li = document.createElement("li");
        li.textContent = (p.role === "origin" ? "Asked about: " : "") + p.label + (p.note ? " (" + p.note + ")" : "");
        list.appendChild(li);
      }
    } else if (action.op === "fly_to") mapLayer.fly(action.bbox);
  }
}

function asFeatures(points) {
  return { type: "FeatureCollection", features: points.map((p) => ({
    type: "Feature", geometry: { type: "Point", coordinates: [p.lng, p.lat] },
    properties: { kind: p.kind, id: p.id, role: p.role, label: p.label, note: p.note || "", band: p.band || "" } })) };
}

async function startMap() {
  const note = $("mapnote");
  try {
    const lib = await import("./vendor/maplibre/maplibre-gl.mjs");
    maplibregl = lib.default || lib;
    const map = new maplibregl.Map({
      container: "map", center: [103.82, 1.35], zoom: 10.6, attributionControl: { compact: true },
      style: { version: 8, sources: { osm: { type: "raster", tileSize: 256, maxzoom: 19,
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], attribution: "© OpenStreetMap contributors" } },
        layers: [{ id: "osm", type: "raster", source: "osm" }] },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", async () => {
      let data;
      try {
        const response = await fetch("/map/features");
        if (!response.ok) throw new Error("no features");
        data = await response.json();
      } catch (error) {
        note.hidden = false;
        note.textContent = "The map data could not be loaded. You can still use the chat.";
        return;
      }
      const blocks = { type: "FeatureCollection", features: data.features.filter((f) => f.properties.kind === "block") };
      const places = { type: "FeatureCollection", features: data.features.filter((f) => f.properties.kind !== "block") };
      const blockFeatures = blocks.features;
      map.addSource("blocks", { type: "geojson", data: blocks });
      map.addSource("places", { type: "geojson", data: places });
      map.addSource("highlight", { type: "geojson", data: EMPTY });
      map.addSource("selected", { type: "geojson", data: EMPTY });
      map.addSource("radius", { type: "geojson", data: EMPTY });
      map.addLayer({ id: "radius-fill", type: "fill", source: "radius", paint: { "fill-color": "#1d5fd6", "fill-opacity": 0.1 } });
      map.addLayer({ id: "radius-line", type: "line", source: "radius", filter: ["==", ["get", "dash"], true],
        paint: { "line-color": "#1d5fd6", "line-width": 2, "line-dasharray": [2, 2] } });
      map.addLayer({ id: "radius-line-solid", type: "line", source: "radius", filter: ["==", ["get", "dash"], false],
        paint: { "line-color": "#1d5fd6", "line-width": 2.5 } });
      map.addLayer({ id: "blocks", type: "circle", source: "blocks", paint: { "circle-color": COLORS, "circle-opacity": 0.6,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 1.5, 14, 4, 17, 8] } });
      map.addLayer({ id: "places", type: "circle", source: "places", paint: { "circle-color": COLORS,
        "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 3.5, 14, 6, 17, 9] } });
      map.addLayer({ id: "highlight", type: "circle", source: "highlight", paint: { "circle-color": COLORS,
        "circle-stroke-color": ["match", ["get", "band"], "within 1 km", "#00a152", "1 to 2 km", "#ffb000", "borderline", "#9aa3b5", "#ffb000"],
        "circle-stroke-width": 3,
        "circle-radius": ["case", ["==", ["get", "role"], "origin"], 11, 8] } });
      map.addLayer({ id: "selected", type: "circle", source: "selected", paint: { "circle-color": "rgba(0,0,0,0)",
        "circle-stroke-color": "#111111", "circle-stroke-width": 3, "circle-radius": 13 } });
      const buildings = initBuildings(map);
      const blockIndex = new Map(blockFeatures.map((f) => [f.properties.id, f]));
      for (const layer of ["places", "blocks", "highlight"]) {
        map.on("mouseenter", layer, () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", layer, () => { map.getCanvas().style.cursor = ""; });
      }
      map.on("click", (e) => {
        const box = [[e.point.x - 7, e.point.y - 7], [e.point.x + 7, e.point.y + 7]];
        const layers = ["places", "highlight", "blocks"];
        if (map.getLayer("buildings")) layers.push("buildings");
        const hits = map.queryRenderedFeatures(box, { layers });
        if (!hits.length) return;
        const hit = hits[0]; // places are drawn above blocks, so they come first
        const f = hit.layer.id === "buildings" ? blockIndex.get(hit.properties.block_id) : hit;
        if (!f) return;
        const [lng, lat] = f.geometry.coordinates;
        setSelected({ kind: f.properties.kind, id: f.properties.id, label: f.properties.label, lat, lng });
      });
      mapLayer.ring = (rings, fit) => {
        map.getSource("radius").setData({ type: "FeatureCollection", features: rings.map((r) => ({
          type: "Feature", geometry: { type: "Polygon", coordinates: [r.ring] }, properties: { km: r.km, dash: r.dash } })) });
        if (rings.length && fit) {
          const bounds = new maplibregl.LngLatBounds();
          rings.forEach((r) => r.ring.forEach((c) => bounds.extend(c)));
          map.fitBounds(bounds, { padding: 60, duration: 500 });
        }
      };
      let lastMetrics = null, lastMode = null;
      mapLayer.layer = (mode, metricsData, budget) => {
        // Price and lease colouring of the blocks: values come from /map/metrics (computed by code from the sales data).
        const rows = metricsData ? metricsData.blocks : {};
        for (const f of blockFeatures) {
          const row = rows[f.properties.id];
          f.properties.price = row && row[0] ? row[0] : 0;
          f.properties.lease = row ? row[2] : -1; // -1: no lease known, drawn grey
        }
        if (lastMetrics !== metricsData || lastMode !== mode) { // a slider move only changes the colour expression
          map.getSource("blocks").setData({ type: "FeatureCollection", features: blockFeatures });
          lastMetrics = metricsData; lastMode = mode;
        }
        let color = COLORS, opacity = 0.6;
        if (mode === "price" && metricsData) {
          const prices = Object.values(rows).map((r) => r[0]).filter(Boolean).sort((a, b) => a - b);
          const at = (q) => prices[Math.min(prices.length - 1, Math.floor(prices.length * q))] || 1;
          color = ["case", ["==", ["get", "price"], 0], "#b8bdc9", [">", ["get", "price"], budget], "#b8bdc9",
            ["interpolate", ["linear"], ["get", "price"], at(0.1), "#fde725", at(0.5), "#21908d", at(0.9), "#440154"]];
          opacity = 0.9;
        } else if (mode === "lease" && metricsData) {
          color = ["case", ["<", ["get", "lease"], 0], "#b8bdc9", ["step", ["get", "lease"], "#440154", 60, "#3b528b", 75, "#21908d", 90, "#fde725"]];
          opacity = 0.9;
        }
        map.setPaintProperty("blocks", "circle-color", color);
        buildings.setMetrics(mode, rows, color);
        map.setPaintProperty("blocks", "circle-opacity", opacity);
        // In a price or lease view the blocks carry the meaning, so draw them larger and the places quieter.
        const coloured = mode !== "type";
        map.setPaintProperty("blocks", "circle-radius", ["interpolate", ["linear"], ["zoom"], 10, coloured ? 2.2 : 1.5,
          14, coloured ? 5 : 4, 17, coloured ? 9 : 8]);
        map.setPaintProperty("places", "circle-opacity", coloured ? 0.5 : 1);
        map.setPaintProperty("places", "circle-stroke-opacity", coloured ? 0.5 : 1);
        map.setPaintProperty("places", "circle-radius", ["interpolate", ["linear"], ["zoom"], 10, coloured ? 2.5 : 3.5,
          14, coloured ? 4 : 6, 17, coloured ? 7 : 9]);
      };
      mapLayer.highlight = (points) => map.getSource("highlight").setData(asFeatures(points));
      mapLayer.select = (p) => map.getSource("selected").setData(p ? asFeatures([p]) : EMPTY);
      mapLayer.fly = (bbox) => {
        if (bbox[0] === bbox[2] && bbox[1] === bbox[3]) map.flyTo({ center: [bbox[0], bbox[1]], zoom: 15 });
        else map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], { padding: 60, maxZoom: 16, duration: 600 });
      };
      if (todo.layer) mapLayer.layer(todo.layer.mode, todo.layer.data, todo.layer.budget);
      if (todo.ring) mapLayer.ring(todo.ring.rings, todo.ring.fit);
      mapLayer.highlight(todo.highlight);
      if (todo.select) mapLayer.select(todo.select);
      if (todo.fly) mapLayer.fly(todo.fly);
    });
  } catch (error) {
    note.hidden = false;
    note.textContent = "The map could not load in this browser. You can still use the chat.";
  }
}

add("bot", "Hi! Click a block, school or station on the map, or just ask me about HDB resale prices, BTO launches, grants or eligibility. I'll show the tool results behind every number.");
startMap();
