import * as lib from "./vendor/maplibre/maplibre-gl.mjs";

// Plain JS, no build step. The chat history lives only in this page's memory and is sent with each question.
const log = document.getElementById("log");
const form = document.getElementById("form");
const box = document.getElementById("question");
const send = document.getElementById("send");
const tools = document.getElementById("tools");
const sources = document.getElementById("sources");
const empty = document.getElementById("empty");
const history = [];
const MAX_TURNS = 12;

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
  details.open = true;
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

// Map: points come from the server (found by code from ids in the tool calls), never from the model's text.
const maplibregl = lib.default || lib;
const features = new Map();
let map = null;
let mapReady = false;
const COLORS = ["match", ["get", "kind"], "block", "#1d5fd6", "mrt", "#d62d2d", "lrt", "#d62d2d",
  "primary_school", "#1f9d55", "bto", "#e08a00", "#888888"];

function startMap() {
  try {
    map = new maplibregl.Map({
      container: "map", center: [103.82, 1.35], zoom: 10.3, attributionControl: { compact: true },
      style: { version: 8, sources: { osm: { type: "raster", tileSize: 256, maxzoom: 19,
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], attribution: "© OpenStreetMap contributors" } },
        layers: [{ id: "osm", type: "raster", source: "osm" }] },
    });
  } catch (error) {
    document.getElementById("map").textContent = "The map could not start in this browser.";
    return;
  }
  map.on("load", () => {
    map.addSource("pts", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    map.addLayer({ id: "pts", type: "circle", source: "pts", paint: {
      "circle-color": COLORS, "circle-radius": ["case", ["==", ["get", "role"], "origin"], 9, 6],
      "circle-stroke-color": "#ffffff", "circle-stroke-width": 2 } });
    map.on("click", "pts", (e) => {
      const p = e.features[0].properties;
      const box = document.createElement("div");
      box.textContent = p.label + (p.note ? " (" + p.note + ")" : "");
      new maplibregl.Popup({ closeButton: false }).setLngLat(e.features[0].geometry.coordinates).setDOMContent(box).addTo(map);
    });
    map.on("mouseenter", "pts", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "pts", () => { map.getCanvas().style.cursor = ""; });
    mapReady = true;
    drawPoints();
  });
}

function drawPoints() {
  const list = document.getElementById("points");
  list.replaceChildren();
  for (const p of features.values()) {
    const li = document.createElement("li");
    li.textContent = p.label + (p.note ? " (" + p.note + ")" : "");
    list.appendChild(li);
  }
  if (!mapReady) return;
  map.getSource("pts").setData({ type: "FeatureCollection", features: [...features.values()].map((p) => ({
    type: "Feature", geometry: { type: "Point", coordinates: [p.lng, p.lat] },
    properties: { kind: p.kind, role: p.role, label: p.label, note: p.note || "" } })) });
  if (features.size) {
    const bounds = new maplibregl.LngLatBounds();
    features.forEach((p) => bounds.extend([p.lng, p.lat]));
    map.fitBounds(bounds, { padding: 40, maxZoom: 16, duration: 600 });
  }
}

function addPoints(points) {
  points.forEach((p) => { if (!features.has(p.id)) features.set(p.id, p); });
  drawPoints();
}

function clearEvidence() {
  features.clear();
  drawPoints();
  tools.replaceChildren();
  sources.replaceChildren();
  seen.clear();
  empty.hidden = false;
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
  document.querySelectorAll(".choices").forEach((c) => c.remove()); // an old "Yes" must not answer a newer turn
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
  try {
    const response = await fetch("/chat", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ question, history: history.slice(-MAX_TURNS) }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === "string" ? body.detail : "The request was refused (" + response.status + ").");
    }
    for await (const event of events(response)) {
      if (event.type === "tool_call") cards.push(addTool(event));
      else if (event.type === "tool_result") addResult(cards[cards.length - 1] || addTool(event), event);
      else if (event.type === "points") addPoints(event.points);
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

function show(question, event) {
  const div = add("bot", event.answer);
  // The server accepts at most 2000 characters per earlier turn; cut here so a long answer cannot block later questions.
  history.push({ role: "user", content: question.slice(0, 1000) }, { role: "assistant", content: event.answer.slice(0, 2000) });
  if (event.needs_confirmation) {
    const choices = document.createElement("div");
    choices.className = "choices";
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
  box.placeholder = "Ask about a flat, a grant or eligibility";
  ask(question);
});
box.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
});
startMap();
add("bot", "Hi! Ask me about HDB resale prices, BTO launches, grants or eligibility. I'll show the tool results behind every number.");
