// Radius choices survive selections. Chat and explicit choices always beat automatic school rings.
const $ = (id) => document.getElementById(id);

function circle(lat, lng, km) {
  // A display-only ring (flat-earth approximation, fine at this size); the counts come from the server.
  const ring = [], dLat = km / 110.574, dLng = km / (111.32 * Math.cos(lat * Math.PI / 180));
  for (let i = 0; i <= 64; i++) {
    const t = i / 64 * 2 * Math.PI;
    ring.push([lng + dLng * Math.cos(t), lat + dLat * Math.sin(t)]);
  }
  return ring;
}

export function initCardMap(mapLayer) {
  let selected = null, radiusKm = 0, radiusChosen = false, schoolRings = false;
  let revision = 0, radiusRequest = 0, counts = null;
  const buttons = document.querySelectorAll(".radius button");
  function drawRadius(fit) {
    buttons.forEach((b) => {
      const on = !schoolRings && Number(b.dataset.km) === radiusKm;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", String(on));
    });
    const rings = [];
    if (selected && schoolRings) rings.push({ km: 2, dash: true }, { km: 1, dash: false });
    else if (selected && radiusKm) rings.push({ km: radiusKm, dash: true });
    mapLayer.ring(selected ? rings.map((r) => ({ ...r, ring: circle(selected.lat, selected.lng, r.km) })) : [], fit);
  }
  function clearCounts() {
    radiusRequest++; counts = null;
    $("radius-counts").textContent = "";
    $("radius-limits").textContent = "";
  }
  async function nearby() {
    if (!selected || !radiusKm || schoolRings) return;
    if (counts) return counts;
    const mine = ++radiusRequest, km = radiusKm, point = selected;
    counts = (async () => {
      try {
        const response = await fetch("/around/" + encodeURIComponent(point.kind) + "/" + encodeURIComponent(point.id) + "?km=" + km);
        if (!response.ok) throw new Error("no counts");
        const data = await response.json();
        if (mine !== radiusRequest) return; // the radius or the place changed meanwhile
        const c = data.counts;
        $("radius-counts").textContent = "Within " + (km < 1 ? km * 1000 + " m" : km + " km") + " (straight-line): " +
          c.blocks + " blocks, " + c.mrt_lrt + " MRT/LRT, " + c.primary_schools + " primary schools, " + c.bto_sites + " BTO sites.";
        $("radius-limits").textContent = data.limits.join(" ");
      } catch (error) {
        if (mine === radiusRequest) $("radius-counts").textContent = "Counts could not be loaded.";
      }
    })();
    return counts;
  }
  buttons.forEach((b) => {
    b.onclick = () => {
      revision++; clearCounts();
      if (schoolRings) mapLayer.highlight([]);
      schoolRings = false; radiusChosen = true; radiusKm = Number(b.dataset.km);
      drawRadius(true);
      return nearby();
    };
  });
  $("radius-fit").onclick = () => drawRadius(true);
  return {
    nearby,
    select(point) {
      revision++; clearCounts();
      if (schoolRings) mapLayer.highlight([]); // the school highlights belong to the old place
      selected = point; schoolRings = false;
      drawRadius(false);
      return revision;
    },
    schools(point, schools, stamp) {
      if (stamp !== revision || selected !== point || radiusChosen) return;
      schoolRings = true; // 1 km solid ring, 2 km dashed ring; schools are ringed by band.
      mapLayer.highlight([{ ...point, role: "origin" }, ...schools.map((s) => ({ ...s, role: "result" }))]);
      drawRadius(false); // Selection never changes the viewport.
    },
    chatHighlight() {
      revision++; clearCounts(); schoolRings = false;
      mapLayer.ring([], false); // A late school response cannot overwrite a chat answer.
    },
  };
}
