// Building geometry and sunlight are illustrative; all figures come from local data or geometry.
import { refreshFacade } from "./building-card.js";
const $ = (id) => document.getElementById(id);
const SUN_COLOR = ["interpolate", ["linear"], ["coalesce", ["feature-state", "exposure"], 0],
  0, "#596579", 0.5, "#e4b466", 1, "#fff0a6"];

export function initLayers() {
  const toggle = $("layers-toggle"), controls = $("map-controls"), panel = $("layers");
  const mobile = window.matchMedia("(max-width: 800px)");
  function close(focus = false) {
    toggle.setAttribute("aria-expanded", "false");
    if (focus) toggle.focus();
  }
  toggle.onclick = () => {
    toggle.setAttribute("aria-expanded", String(toggle.getAttribute("aria-expanded") !== "true"));
  };
  document.addEventListener("pointerdown", (event) => {
    if (mobile.matches && !controls.contains(event.target)) close();
  });
  document.addEventListener("keydown", (event) => {
    if (mobile.matches && event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") close(true);
  });
  // Each phone layout starts compact, even after rotating or resizing from desktop.
  mobile.addEventListener("change", () => {
    const focused = panel.contains(document.activeElement);
    close(mobile.matches && focused);
    if (!mobile.matches && document.activeElement === toggle) panel.querySelector("button").focus();
  });
  close();
}

export function wallExposure(az, alt, bearing) {
  // Same cosine incidence as ask_hdb/sun.py; night is excluded by the caller there.
  const value = Math.max(0, Math.min(1, Math.cos(alt * Math.PI / 180) * Math.cos((az - bearing) * Math.PI / 180)));
  return alt > 0 && value > 1e-12 ? value : 0;
}

export function initBuildings(map) {
  const toggle = $("toggle-3d"), panel = $("sun-panel"), date = $("sun-date"), slider = $("sun-time");
  let enabled = false, outlines = null, samples = [], dayRequest = 0;
  let mode = "type", written = null, rows = {}, color = SUN_COLOR, oldLight = null, oldPitch = 0;
  let frame = null;

  function paint() {
    if (!outlines) return;
    map.setPaintProperty("buildings", "fill-extrusion-color", mode === "type" ? SUN_COLOR : color);
  }

  function updateTime() {
    const minute = Number(slider.value);
    const time = String(Math.floor(minute / 60)).padStart(2, "0") + ":" + String(minute % 60).padStart(2, "0");
    $("sun-time-label").textContent = time + " (+08:00)";
    slider.setAttribute("aria-valuetext", time + " Singapore time");
    const sun = samples[minute / 15];
    if (!sun) return;
    $("sun-position").textContent = "Azimuth " + sun.azimuth.toFixed(1) + "° · altitude " + sun.altitude.toFixed(1) + "°";
    if (!enabled) return;
    // MapLibre's spherical conversion adds 90 degrees, with tile Y pointing south.
    // Offset the compass bearing by 180; polar angle is measured down from the zenith.
    map.setLight({ anchor: "map", position: [1.15, (sun.azimuth + 180) % 360, 90 - sun.altitude], intensity: sun.altitude > 0 ? 0.5 : 0 });
    if (outlines && mode === "type") for (const f of outlines.features) {
      const exposure = Math.max(...f.properties.facing.map((b) => wallExposure(sun.azimuth, sun.altitude, b)));
      map.setFeatureState({ source: "buildings", id: f.id }, { exposure });
    }
    paint();
  }

  async function loadDay() {
    const mine = ++dayRequest;
    samples = [];
    $("sun-position").textContent = "Loading sun geometry…";
    slider.disabled = true;
    if (enabled) map.setLight({ intensity: 0 });
    // Clear old sunlight so a failed date request cannot show yesterday's geometry under a new date.
    if (outlines) for (const f of outlines.features) map.setFeatureState({ source: "buildings", id: f.id }, { exposure: 0 });
    try {
      const response = await fetch("/sun" + (date.value ? "?date=" + encodeURIComponent(date.value) : ""));
      if (!response.ok) throw new Error("Use a valid date; sun geometry could not be loaded.");
      const data = await response.json();
      if (mine !== dayRequest) return;
      date.value = data.date;
      samples = data.positions;
      slider.disabled = false;
      updateTime();
    } catch (error) {
      if (mine === dayRequest) $("sun-position").textContent = error.message;
    }
  }

  function setMetrics(nextMode, nextRows, expression) {
    mode = nextMode; rows = nextRows;
    // Reuse the exact price/lease ramp and budget filtering from the existing point layer.
    const stateExpression = (node) => Array.isArray(node)
      ? node[0] === "get" && ["price", "lease"].includes(node[1])
        ? ["coalesce", ["feature-state", node[1]], node[1] === "price" ? 0 : -1]
        : node.map(stateExpression) : node;
    color = stateExpression(expression);
    if (outlines && rows !== written) for (const f of outlines.features) {
      const row = rows[f.id];
      map.setFeatureState({ source: "buildings", id: f.id }, { price: row && row[0] ? row[0] : 0, lease: row ? row[2] : -1 });
    }
    if (outlines) written = rows;
    if (nextMode === "type" && enabled) updateTime();
    paint();
  }

  toggle.disabled = false;
  toggle.onclick = async () => {
    toggle.disabled = true;
    try {
      if (!enabled && !outlines) {
        const response = await fetch("/map/buildings");
        if (!response.ok) throw new Error("Building outlines are unavailable. The flat map is still available.");
        const data = await response.json();
        for (const f of data.features) f.id = f.properties.block_id;
        map.addSource("buildings", { type: "geojson", data, promoteId: "block_id" });
        map.addLayer({ id: "buildings", type: "fill-extrusion", source: "buildings",
          paint: { "fill-extrusion-height": ["get", "height_m"], "fill-extrusion-color": SUN_COLOR,
            "fill-extrusion-opacity": 0.9 }, layout: { visibility: "none" } }, "places");
        outlines = data;
        map.on("mouseenter", "buildings", () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", "buildings", () => { map.getCanvas().style.cursor = ""; });
        setMetrics(mode, rows, color);
      }
      enabled = !enabled;
      panel.hidden = !enabled;
      toggle.classList.toggle("on", enabled);
      toggle.setAttribute("aria-pressed", String(enabled));
      map.setLayoutProperty("buildings", "visibility", enabled ? "visible" : "none");
      // Blocks without an outline stay as points, so nothing disappears from the budget view.
      map.setFilter("blocks", enabled ? ["!", ["in", ["get", "id"], ["literal", outlines.features.map((f) => f.id)]]] : null);
      if (enabled) {
        // getLight can omit defaults; setLight({}) would leave our sun light in place.
        oldLight = { anchor: "viewport", position: [1.15, 210, 30], color: "#ffffff", intensity: 0.5, ...map.getLight() };
        oldPitch = map.getPitch();
        map.easeTo({ pitch: 60 });
        await loadDay();
        refreshFacade();
      } else {
        map.easeTo({ pitch: oldPitch });
        map.setLight(oldLight);
      }
      $("building-error").textContent = "";
    } catch (error) {
      $("building-error").textContent = error.message;
    } finally { toggle.disabled = false; }
  };
  date.onchange = () => { loadDay(); refreshFacade(); };
  slider.oninput = () => {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => { frame = null; updateTime(); });
  };
  return { setMetrics };
}
