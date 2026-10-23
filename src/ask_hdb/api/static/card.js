// The summary and every disclosure reuse server facts. No prices or leases are inferred here.
import { clearBuildingCard, showBuildingFacts, openBuildingSun } from "./building-card.js";
import { initCardMap } from "./card-map.js";
const $ = (id) => document.getElementById(id);
const SECTIONS = [["Prices", "card-prices"], ["Lease", "card-lease"], ["Sun and facing", "card-facing"],
  ["Schools", "schools"], ["Nearby", "card-nearby"]];
const QUESTIONS = {
  block: [["Ask about schools", "What are the 3 nearest primary schools to this block?"],
    ["Ask about prices", "What were the recent resale prices here?"]],
  bto: [["Ask about MRT", "What are the 3 nearest MRT stations to this project?"],
    ["Ask about prices", "What are the launch prices of this project?"]],
};
function line(id, text, tag = "p") {
  const node = document.createElement(tag); node.textContent = text; $(id).appendChild(node);
  return node;
}
function headline(text, source) {
  const li = line("card-facts", text, "li"), note = document.createElement("small");
  note.textContent = source; li.appendChild(note);
}
function metadata(id, data) {
  // Keep provenance supplied by an endpoint, including any future nested sources.
  if (!data || typeof data !== "object") return;
  if (typeof data.source === "string") line(id, "Source: " + data.source);
  if (data.as_of) line(id, "As of " + data.as_of);
  Object.values(data).forEach((value) => { if (typeof value === "object") metadata(id, value); });
}
async function get(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error("Details could not be loaded.");
  return response.json();
}

export function initCard({ mapLayer, metrics, ask }) {
  const map = initCardMap(mapLayer);
  let cardRequest = 0, current = null, facts = null;
  let sectionRequest = 0;
  function refreshMetrics() {
    if (!current || !facts) return;
    $("card-facts").replaceChildren();
    $("metrics-limits").replaceChildren();
    $("metric-prices").replaceChildren(); $("metric-lease").replaceChildren();
    if (current.kind !== "block") {
      const source = current.kind === "bto" ? "BTO project data · approximate site" : "Place data · straight-line counts";
      facts.facts.slice(0, 2).forEach((fact) => headline(fact, source));
      return;
    }
    const { flat, data } = metrics(), row = data?.blocks[current.id];
    if (row) {
      if (row[0] != null) {
        const price = flat + " median, last " + data.window_months + " months: $" + Math.round(row[0]).toLocaleString("en-SG") + " from " + row[1] + " sales";
        headline(price, "HDB resale data (data.gov.sg) · not a valuation");
        line("metric-prices", price);
      } else line("metric-prices", flat + ": " + row[1] + " sale(s) in " + data.window_months + " months, too few for a median");
      if (row[2] != null && row[2] >= 0) {
        const lease = "Remaining lease: about " + row[2] + " years";
        headline(lease, "HDB resale data (data.gov.sg) · whole years"); line("metric-lease", lease);
      }
      data.limits.forEach((text) => line("metrics-limits", text)); metadata("metrics-limits", data);
    }
    if (row?.[2] == null || row[2] < 0) {
      const lease = facts.facts.find((fact) => fact.startsWith("Lease started:"));
      if (lease) headline(lease, "HDB resale data (data.gov.sg)"); // Keep the server's wording, not an estimated lease.
    }
    if (facts.facing_label) headline(facts.facing_label, "Building footprint · approximate, per block; not per unit");
  }
  function render(data, point) {
    facts = data;
    const town = point.kind === "block" && data.facts.find((fact) => fact.startsWith("Town:"));
    $("card-subtitle").textContent = town || { block: "HDB block", bto: "BTO · approximate site", mrt: "MRT station",
      lrt: "LRT station", primary_school: "Primary school" }[point.kind];
    for (const [index, fact] of data.facts.entries()) {
      if (point.kind !== "block" && index < 2 || fact === town) continue;
      const target = point.kind !== "block" ? "nearby-facts" : fact.startsWith("Lease started:") ? "lease-facts"
        : fact.startsWith("Nearest") ? "nearby-facts" : "price-facts";
      line(target, fact, "li");
    }
    data.limits.forEach((text) => line("card-limits", text)); metadata("card-limits", data);
    if (point.kind === "block") facts.facing_label = showBuildingFacts(data, point);
    refreshMetrics();
  }
  function renderSchools(data) {
    $("schools-list").replaceChildren();
    for (const school of data.schools) {
      const li = line("schools-list", "", "li"), button = document.createElement("button");
      button.textContent = school.label;
      button.onclick = () => mapLayer.fly([school.lng, school.lat, school.lng, school.lat]);
      const distance = document.createElement("span");
      distance.textContent = " – " + school.km.toFixed(2) + " km (" + school.band + "; approximate)";
      li.append(button, distance);
    }
    const inside = data.schools.filter((s) => s.band !== "borderline").length;
    $("schools-summary").textContent = "Primary schools within 2 km: " + inside +
      (data.schools.length > inside ? " (+" + (data.schools.length - inside) + " borderline)" : "");
  }
  function reset() {
    cardRequest++; sectionRequest++; clearBuildingCard(); current = null; facts = null;
    for (const id of ["card-facts", "card-actions", "card-limits", "card-sections", "price-facts", "lease-facts",
      "nearby-facts", "metric-prices", "metric-lease", "metrics-limits", "schools-list", "schools-limits"]) $(id).replaceChildren();
    SECTIONS.forEach(([, id]) => { $(id).hidden = true; });
    $("schools-summary").textContent = "Primary schools within 2 km";
    $("card-about").open = false;
  }
  async function select(point) {
    reset(); const mine = cardRequest, stamp = map.select(point), sectionMine = sectionRequest;
    $("card").hidden = !point;
    if (!point) return;
    current = point;
    $("card-title").textContent = point.label; $("card-subtitle").textContent = "Loading details…";
    const path = encodeURIComponent(point.kind) + "/" + encodeURIComponent(point.id);
    let schoolData;
    const schools = () => schoolData ||= get("/schools/" + path).then((data) => {
      if (mine !== cardRequest) return;
      $("schools-limits").textContent = data.limits.join(" ");
      metadata("schools-limits", data);
      return data;
    });
    // Blocks need the same school response immediately for their default map rings.
    if (point.kind === "block") schools().then((data) => {
      if (mine === cardRequest && data) map.schools(point, data.schools, stamp);
    }).catch(() => {}); // The list is an extra; the card still works without it.
    const ready = get("/card/" + path).then((data) => {
      if (mine !== cardRequest) return; // the visitor clicked something else meanwhile
      render(data, point);
    }).catch(() => {
      if (mine === cardRequest) {
        $("card-subtitle").textContent = "Details unavailable";
        $("card-limits").textContent = "No details could be loaded for this place.";
      }
    });
    const chips = [];
    for (const [label, id] of SECTIONS) {
      if (point.kind !== "block" && !["schools", "card-nearby"].includes(id)) continue;
      const button = line("card-sections", label, "button"); button.className = "secondary";
      button.setAttribute("aria-controls", id); button.setAttribute("aria-expanded", "false");
      let loaded = false;
      chips.push({ button, id });
      button.onclick = async () => {
        if (sectionMine !== sectionRequest) return;
        const opening = $(id).hidden;
        chips.forEach((chip) => {
          const open = opening && chip.id === id;
          $(chip.id).hidden = !open; chip.button.setAttribute("aria-expanded", String(open));
          chip.button.classList.toggle("on", open);
        });
        if (!opening || loaded) return;
        loaded = true; // Also deduplicates opens while a request is still pending.
        await ready;
        if (sectionMine !== sectionRequest || mine !== cardRequest) return;
        if (id === "card-facing") await openBuildingSun(point);
        if (id === "card-nearby") await map.nearby();
        if (id === "schools") {
          try {
            const data = await schools();
            if (sectionMine !== sectionRequest || mine !== cardRequest) return;
            renderSchools(data);
          } catch (error) {
            if (sectionMine === sectionRequest) $("schools-summary").textContent = "Schools could not be loaded.";
          }
        }
      };
    }
    for (const [label, question] of QUESTIONS[point.kind] || []) {
      const button = line("card-actions", label, "button"); button.className = "secondary";
      button.onclick = () => ask(question);
    }
    return ready;
  }
  $("card-close").onclick = () => { cardRequest++; sectionRequest++; clearBuildingCard(); $("card").hidden = true; };
  return { select, refreshMetrics, chatHighlight: map.chatHighlight };
}
