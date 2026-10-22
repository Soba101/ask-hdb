// Plain JS, no build step. The chat history lives only in this page's memory and is sent with each question.
// The map is the main view: click a block, school, station or BTO site to select it; the chat then knows what
// "this block" means. Map highlights come from the server, built by code from tool results, never from model text.
const $ = (id) => document.getElementById(id);
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
const QUESTIONS = {
  block: ["What are the 3 nearest primary schools to this block?", "What were the recent resale prices here?"],
  bto: ["What are the 3 nearest MRT stations to this project?", "What are the launch prices of this project?"],
  mrt: [], lrt: [], primary_school: [],
};

function setSelected(point) {
  selected = point;
  $("selected").hidden = !point;
  if (point) $("selected-label").textContent = point.label;
  mapLayer.select(point);
  if (point) showCard(point); else $("card").hidden = true;
}
$("selected-clear").onclick = () => setSelected(null);
$("card-close").onclick = () => { $("card").hidden = true; };

async function showCard(point) {
  const card = $("card");
  $("card-title").textContent = point.label;
  $("card-facts").replaceChildren();
  $("card-actions").replaceChildren();
  $("card-limits").textContent = "";
  card.hidden = false;
  try {
    const response = await fetch("/card/" + encodeURIComponent(point.kind) + "/" + encodeURIComponent(point.id));
    if (!response.ok) throw new Error("no card");
    const data = await response.json();
    if (!selected || selected.id !== point.id) return; // the visitor clicked something else meanwhile
    for (const fact of data.facts) {
      const li = document.createElement("li");
      li.textContent = fact;
      $("card-facts").appendChild(li);
    }
    $("card-limits").textContent = data.limits.join(" ");
  } catch (error) {
    $("card-limits").textContent = "No details could be loaded for this place.";
  }
  for (const question of QUESTIONS[point.kind] || []) {
    const button = document.createElement("button");
    button.className = "secondary";
    button.textContent = question.replace(/^What (are|were) (the )?/, "").replace(/\?$/, "");
    button.onclick = () => { tab("chat"); ask(question); };
    $("card-actions").appendChild(button);
  }
}

// ---------- map ----------
const mapLayer = { highlight() {}, select() {}, fly() {} };
let maplibregl = null;
const COLORS = ["match", ["get", "kind"], "block", "#1d5fd6", "mrt", "#d62d2d", "lrt", "#d62d2d",
  "primary_school", "#1f9d55", "bto", "#e08a00", "#888888"];
const EMPTY = { type: "FeatureCollection", features: [] };

function runMapActions(actions) {
  for (const action of actions) {
    if (action.op === "highlight") {
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
    properties: { kind: p.kind, id: p.id, role: p.role, label: p.label, note: p.note || "" } })) };
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
      const data = await (await fetch("/map/features")).json();
      const blocks = { type: "FeatureCollection", features: data.features.filter((f) => f.properties.kind === "block") };
      const places = { type: "FeatureCollection", features: data.features.filter((f) => f.properties.kind !== "block") };
      map.addSource("blocks", { type: "geojson", data: blocks });
      map.addSource("places", { type: "geojson", data: places });
      map.addSource("highlight", { type: "geojson", data: EMPTY });
      map.addSource("selected", { type: "geojson", data: EMPTY });
      map.addLayer({ id: "blocks", type: "circle", source: "blocks", paint: { "circle-color": COLORS, "circle-opacity": 0.6,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 1.5, 14, 4, 17, 8] } });
      map.addLayer({ id: "places", type: "circle", source: "places", paint: { "circle-color": COLORS,
        "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.5,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 3.5, 14, 6, 17, 9] } });
      map.addLayer({ id: "highlight", type: "circle", source: "highlight", paint: { "circle-color": COLORS,
        "circle-stroke-color": "#ffb000", "circle-stroke-width": 3,
        "circle-radius": ["case", ["==", ["get", "role"], "origin"], 11, 8] } });
      map.addLayer({ id: "selected", type: "circle", source: "selected", paint: { "circle-color": "rgba(0,0,0,0)",
        "circle-stroke-color": "#111111", "circle-stroke-width": 3, "circle-radius": 13 } });
      for (const layer of ["places", "blocks", "highlight"]) {
        map.on("mouseenter", layer, () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", layer, () => { map.getCanvas().style.cursor = ""; });
      }
      map.on("click", (e) => {
        const box = [[e.point.x - 7, e.point.y - 7], [e.point.x + 7, e.point.y + 7]];
        const hits = map.queryRenderedFeatures(box, { layers: ["places", "highlight", "blocks"] });
        if (!hits.length) return;
        const f = hits[0]; // places are drawn above blocks, so they come first
        const [lng, lat] = f.geometry.coordinates;
        setSelected({ kind: f.properties.kind, id: f.properties.id, label: f.properties.label, lat, lng });
      });
      mapLayer.highlight = (points) => map.getSource("highlight").setData(asFeatures(points));
      mapLayer.select = (p) => map.getSource("selected").setData(p ? asFeatures([p]) : EMPTY);
      mapLayer.fly = (bbox) => {
        if (bbox[0] === bbox[2] && bbox[1] === bbox[3]) map.flyTo({ center: [bbox[0], bbox[1]], zoom: 15 });
        else map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], { padding: 60, maxZoom: 16, duration: 600 });
      };
    });
  } catch (error) {
    note.hidden = false;
    note.textContent = "The map could not load in this browser. You can still use the chat.";
  }
}

add("bot", "Hi! Click a block, school or station on the map, or just ask me about HDB resale prices, BTO launches, grants or eligibility. I'll show the tool results behind every number.");
startMap();
