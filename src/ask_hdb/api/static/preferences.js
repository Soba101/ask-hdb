const KEY = "ask-hdb.areaUnit", THEME = "ask-hdb.theme", MOTION = "ask-hdb.motion";
const $ = (id) => document.getElementById(id);
// null follows the device; a value forces that media feature for both CSS and script checks.
const forced = { "prefers-color-scheme": null, "prefers-reduced-motion": null };
const original = new WeakMap();

const read = (key) => { try { return localStorage.getItem(key); } catch { return null; } };
const write = (key, value) => { try { localStorage.setItem(key, value); } catch {} };

// matchMedia for "(feature: value)" that honours a forced theme or motion choice.
export function matches(query) {
  const [, feature, value] = query.match(/\(([\w-]+):\s*([\w-]+)\)/);
  return forced[feature] ? forced[feature] === value : window.matchMedia(query).matches;
}

// A forced choice rewrites the matching @media conditions, so the existing dark and motion CSS stays the only copy.
function rewriteMedia() {
  for (const sheet of document.styleSheets) {
    let rules;
    try { rules = sheet.cssRules; } catch { continue; } // a cross-origin sheet cannot be read
    for (const rule of rules) {
      if (!rule.media) continue;
      if (!original.has(rule)) original.set(rule, rule.media.mediaText);
      rule.media.mediaText = original.get(rule).replace(/\((prefers-color-scheme|prefers-reduced-motion):\s*([\w-]+)\)/g,
        (text, feature, value) => !forced[feature] ? text : forced[feature] === value ? "(min-width: 0px)" : "(max-width: 0px) and (min-width: 1px)");
    }
  }
}

export function initPreferences(onChange) {
  const button = $("preferences-button"), dialog = $("preferences"), select = $("area-unit");
  const theme = $("theme"), motion = $("motion");
  let unit = read(KEY) === "sqft" ? "sqft" : "sqm";
  select.value = unit;
  theme.value = ["light", "dark"].includes(read(THEME)) ? read(THEME) : "system";
  motion.value = read(MOTION) === "reduce" ? "reduce" : "system";
  // shortcut: this runs after first paint, so a forced theme can flash the device theme on load; move it into an inline head script if that bothers anyone.
  const apply = () => {
    forced["prefers-color-scheme"] = theme.value === "system" ? null : theme.value;
    forced["prefers-reduced-motion"] = motion.value === "system" ? null : motion.value;
    rewriteMedia();
    window.dispatchEvent(new Event("preferences"));
  };
  apply();
  button.onclick = () => dialog.showModal();
  $("preferences-close").onclick = () => dialog.close();
  dialog.addEventListener("cancel", (event) => { event.preventDefault(); dialog.close(); });
  dialog.addEventListener("close", () => button.focus());
  select.addEventListener("change", () => {
    unit = select.value === "sqft" ? "sqft" : "sqm";
    write(KEY, unit);
    onChange(unit);
  });
  theme.addEventListener("change", () => { write(THEME, theme.value); apply(); });
  motion.addEventListener("change", () => { write(MOTION, motion.value); apply(); });
  return { areaUnit: () => unit };
}
