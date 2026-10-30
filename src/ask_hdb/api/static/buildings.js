// Building geometry and sunlight are illustrative; all figures come from local data or geometry.
import { refreshFacade } from "./building-card.js";
import { initSunControls } from "./sun-controls.js";
import { initShadows } from "./shadows.js";
const $ = (id) => document.getElementById(id);
const SUN_COLOR = ["interpolate", ["linear"], ["coalesce", ["feature-state", "exposure"], 0],
  0, "#39465c", 0.5, "#dba247", 1, "#fff0a6"];

export function wallExposure(az, alt, bearing) {
  // Same cosine incidence as ask_hdb/sun.py; night is excluded by the caller there.
  const value = Math.max(0, Math.min(1, Math.cos(alt * Math.PI / 180) * Math.cos((az - bearing) * Math.PI / 180)));
  return alt > 0 && value > 1e-12 ? value : 0;
}

export function initBuildings(map) {
  const toggle = $("toggle-3d"), panel = $("sun-panel");
  let enabled = false, outlines = null, loading = false, failed = false, shadows = null, wanted = false;
  let mode = "type", written = null, rows = {}, color = SUN_COLOR, oldLight = null, oldPitch = 0;

  function paint() {
    if (!outlines) return;
    map.setPaintProperty("buildings", "fill-extrusion-color", mode === "type" ? SUN_COLOR : color);
  }

  function renderSun(sun) {
    if (!enabled) return;
    // MapLibre's spherical conversion adds 90 degrees, with tile Y pointing south.
    // Offset the compass bearing by 180; polar angle is measured down from the zenith.
    map.setLight({ anchor: "map", position: [1.15, (sun.azimuth + 180) % 360, 90 - sun.altitude], color: "#ffffff", intensity: sun.altitude > 0 ? 0.85 : 0 });
    if (outlines && mode === "type") for (const f of outlines.features) {
      const exposure = Math.max(...f.properties.facing.map((b) => wallExposure(sun.azimuth, sun.altitude, b)));
      map.setFeatureState({ source: "buildings", id: f.id }, { exposure });
    }
    paint();
    shadows?.update(sun);
  }

  const clock = initSunControls(renderSun, () => {
    if (enabled) map.setLight({ intensity: 0 });
    shadows?.update(null);
    // Clear old sunlight so a failed date request cannot show yesterday's geometry under a new date.
    if (outlines) for (const f of outlines.features) map.setFeatureState({ source: "buildings", id: f.id }, { exposure: 0 });
  });

  function setMetrics(nextMode, nextRows, expression) {
    mode = nextMode; rows = nextRows;
    // Reuse the exact price/lease ramp and budget filtering from the existing point layer.
    const stateExpression = (node) => Array.isArray(node)
      ? node[0] === "get" && ["price", "lease", "mop"].includes(node[1])
        ? ["coalesce", ["feature-state", node[1]], node[1] === "price" ? 0 : -1]
        : node.map(stateExpression) : node;
    color = stateExpression(expression);
    if (outlines && rows !== written) for (const f of outlines.features) {
      const row = rows[f.id];
      map.setFeatureState({ source: "buildings", id: f.id }, { price: row && row[0] ? row[0] : 0, lease: row ? row[2] : -1, mop: row?.[3] ?? -1 });
    }
    if (outlines) written = rows;
    if (nextMode === "type" && enabled) clock.updateTime();
    paint();
  }

  toggle.disabled = false;
  async function setEnabled(on, { ease = true } = {}) {
    // Remember a levelling gesture while outlines load, without starting another request.
    if (loading) { wanted = on; return; }
    if (on === enabled) return;
    wanted = on; loading = true; toggle.disabled = true;
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
        shadows = initShadows(map, outlines);
        map.on("mouseenter", "buildings", () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", "buildings", () => { map.getCanvas().style.cursor = ""; });
        setMetrics(mode, rows, color);
      }
      if (on && !wanted) return;
      // Sun requests have their own stale guard; they must not lock out switching back to flat.
      loading = false; toggle.disabled = false;
      enabled = on;
      panel.hidden = !enabled;
      shadows.setEnabled(enabled);
      toggle.classList.toggle("on", enabled);
      toggle.setAttribute("aria-pressed", String(enabled));
      map.setLayoutProperty("buildings", "visibility", enabled ? "visible" : "none");
      // Blocks without an outline stay as points, so nothing disappears from the budget view.
      map.setFilter("blocks", enabled ? ["!", ["in", ["get", "id"], ["literal", outlines.features.map((f) => f.id)]]] : null);
      if (enabled) {
        // getLight can omit defaults; setLight({}) would leave our sun light in place.
        oldLight = { anchor: "viewport", position: [1.15, 210, 30], color: "#ffffff", intensity: 0.5, ...map.getLight() };
        if (ease) { oldPitch = map.getPitch(); map.easeTo({ pitch: 60, essential: false }); }
        await clock.loadDay();
        refreshFacade();
      } else {
        if (ease) map.easeTo({ pitch: oldPitch, essential: false });
        map.setLight(oldLight);
      }
      $("building-error").textContent = "";
    } catch (error) {
      failed = true;
      $("building-error").textContent = error.message;
    } finally { loading = false; toggle.disabled = false; }
  }
  toggle.onclick = () => { clock.stop(); return setEnabled(!enabled); };
  map.on("pitchend", (event) => {
    // Programmatic easing has no originalEvent, including a manual off back to a high oldPitch.
    if (!event.originalEvent) return;
    if (map.getPitch() > 10 && !(failed && !outlines)) return setEnabled(true, { ease: false });
    if (map.getPitch() < 3) { clock.stop(); return setEnabled(false, { ease: false }); }
  });
  return { setMetrics };
}
