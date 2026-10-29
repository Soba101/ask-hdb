// Nearest supermarkets, MRT/LRT and bus stops for the selected place, and a walking route to one of them.
// Distances and routes come from the server (code and OneMap); this file only draws them.
const $ = (id) => document.getElementById(id);
const TYPES = { supermarket: "Supermarkets", mrt: "MRT/LRT", bus: "Bus stops" };

function km(value) { return value < 1 ? Math.round(value * 1000) + " m" : value.toFixed(2) + " km"; }
// OneMap writes "Make A Slight Right"; read it as a sentence, keeping the street names.
function sentence(text) { return text.replace(/(?<=\s)(A|An|The|To|On|Onto|Into|At|And|Of)(?=\s)/g, (w) => w.toLowerCase()); }
function minutes(seconds) { return Math.max(1, Math.round(seconds / 60)) + " min"; }

export function initAmenityCard({ mapLayer, onRoute }) {
  let point = null, type = null, listRequest = 0, routeRequest = 0;
  const buttons = document.querySelectorAll("#amenity-pills button");
  function say(text) { $("route-status").textContent = text; } // route messages never replace the data attribution
  function clearRoute() {
    routeRequest++;
    $("route-block").hidden = true;
    $("route-steps").replaceChildren(); $("route-summary").textContent = "";
    mapLayer.route(null);
  }
  function clear() {
    listRequest++; type = null; point = null;
    buttons.forEach((b) => { b.setAttribute("aria-pressed", "false"); b.classList.toggle("on", false); });
    $("amenity-list").replaceChildren(); say(""); $("amenity-note").textContent = "";
    mapLayer.amenities([]); clearRoute();
  }
  async function walk(item, button) {
    const mine = ++routeRequest, from = point;
    button.disabled = true; say("Finding the walking route…");
    try {
      const response = await fetch("/route/" + encodeURIComponent(from.kind) + "/" + encodeURIComponent(from.id) +
        "?to=" + encodeURIComponent(item.id));
      const data = await response.json().catch(() => ({}));
      if (mine !== routeRequest || from !== point) return; // a newer choice or selection replaced this one
      if (!response.ok || data.error) { say(data.message || "Walking directions could not be loaded."); return; }
      say("");
      $("route-summary").textContent = "To " + data.to + ": about " + minutes(data.duration_s) + ", " +
        km(data.distance_m / 1000) + " walking (estimate from OneMap).";
      $("route-steps").replaceChildren(...data.steps.map((s) => {
        const li = document.createElement("li");
        li.textContent = sentence(s.text) + (s.distance_m ? " (" + s.distance_m + " m)" : "");
        return li;
      }));
      $("route-limits").textContent = data.limits.join(" ") + " " + data.source + ".";
      $("route-block").hidden = false;
      mapLayer.route(data.line);
      onRoute();
    } catch (error) {
      if (mine === routeRequest) say("Walking directions could not be loaded.");
    } finally {
      button.disabled = false;
    }
  }
  async function show(next) {
    clearRoute();
    const mine = ++listRequest, from = point;
    type = next;
    buttons.forEach((b) => {
      const on = b.dataset.type === type;
      b.setAttribute("aria-pressed", String(on)); b.classList.toggle("on", on);
    });
    $("amenity-list").replaceChildren(); mapLayer.amenities([]); $("amenity-note").textContent = "Loading…"; say("");
    try {
      const response = await fetch("/nearby/" + encodeURIComponent(from.kind) + "/" + encodeURIComponent(from.id) +
        "?type=" + encodeURIComponent(next) + "&n=3");
      if (!response.ok) throw new Error("no list");
      const data = await response.json();
      if (mine !== listRequest || from !== point) return;
      $("amenity-note").textContent = data.limits.join(" ") + " " + data.source + ", as of " + data.as_of + ".";
      mapLayer.amenities(data.items);
      $("amenity-list").replaceChildren(...data.items.map((item, i) => {
        const li = document.createElement("li"), button = document.createElement("button");
        li.append((i + 1) + ". " + item.name + (item.ref ? " (stop " + item.ref + ")" : "") + " — " + km(item.km) + " ");
        button.className = "secondary"; button.textContent = "Walk";
        button.setAttribute("aria-label", "Walking directions to " + item.name);
        button.onclick = () => walk(item, button);
        li.append(button);
        return li;
      }));
    } catch (error) {
      if (mine === listRequest) $("amenity-note").textContent = "Nearby places could not be loaded.";
    }
  }
  buttons.forEach((b) => {
    b.onclick = () => {
      if (!point) return;
      if (type === b.dataset.type) { const keep = point; clear(); point = keep; return; } // pressing again turns it off
      return show(b.dataset.type);
    };
  });
  $("route-clear").onclick = () => clearRoute();
  return { select(next) { clear(); point = next; }, clear, TYPES };
}
