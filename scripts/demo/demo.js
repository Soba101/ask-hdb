// Static demo shim: answers the app's own requests from the files in data/, so the page runs with no server.
// Chat and sun hours per block are switched off; everything else comes from files built by scripts/build_static_demo.py.
(() => {
  const base = new URL("./", document.currentScript.src).href;
  const real = window.fetch.bind(window);
  const bundles = new Map();
  const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
  const bundle = (kind, id) => {
    const key = kind + "__" + id;
    if (!bundles.has(key)) bundles.set(key, real(base + "data/place/" + encodeURIComponent(key) + ".json").then((r) => (r.ok ? r.json() : null)));
    return bundles.get(key);
  };
  window.DEMO = true;
  window.fetch = async (input, init) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    const path = url.pathname.replace(/^\/ask-hdb(?=\/)/, ""), parts = path.split("/").filter(Boolean).map(decodeURIComponent);
    const [head, kind, id] = parts;
    if (path === "/chat") {
      return json({ detail: "Chat is paused in this demo: the free model limit has been reached. Run Ask HDB yourself to chat (see the README)." }, 429);
    }
    if (path === "/map/features") return real(base + "data/features.json");
    if (path === "/map/buildings") return real(base + "data/buildings.json");
    if (path === "/map/metrics") return real(base + "data/metrics/" + encodeURIComponent(url.searchParams.get("flat_type")) + ".json");
    if (path === "/sun") {
      const date = url.searchParams.get("date") || new Date().toISOString().slice(0, 10);
      const day = date.slice(5) === "02-29" ? "02-28" : date.slice(5); // the sun's path barely changes between years
      const data = await real(base + "data/sun/" + day + ".json").then((r) => r.json());
      return json({ ...data, date });
    }
    if (head === "sun" && kind === "block") {
      const date = url.searchParams.get("date") || new Date().toISOString().slice(0, 10);
      return json({ date, facades: [], limits: "Direct-sun hours for each block are not in the demo; the 3D sun and shadows are." });
    }
    if (["card", "schools", "around", "nearby", "route"].includes(head)) {
      const data = await bundle(kind, id);
      if (!data) return json({ detail: "Unknown place." }, 404);
      if (head === "card") return json(data.card);
      if (head === "schools") return json(data.schools);
      if (head === "around") return json(data.around[String(Number(url.searchParams.get("km")))] || { counts: {}, limits: [] });
      if (head === "nearby") return json(data.nearby[url.searchParams.get("type")] || { items: [], limits: [], source: "", as_of: "" });
      const route = data.routes[url.searchParams.get("to")];
      return route ? json(route) : json({ error: "no_route", message: "No walking route was found for this pair in the demo." }, 404);
    }
    return real(input, init);
  };
  addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("form"), note = document.createElement("p");
    note.className = "notice"; note.textContent = "Demo: the map, layers, cards, nearby places, walking routes and 3D work from saved data. " +
      "Chat is paused because the free model limit is reached.";
    if (form) form.before(note);
    const question = document.getElementById("question");
    if (question) question.placeholder = "Chat is paused in this demo";
  });
})();
