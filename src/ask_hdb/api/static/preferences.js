const KEY = "ask-hdb.areaUnit";
const $ = (id) => document.getElementById(id);

export function initPreferences(onChange) {
  const button = $("preferences-button"), dialog = $("preferences"), select = $("area-unit");
  let unit = "sqm";
  try { if (localStorage.getItem(KEY) === "sqft") unit = "sqft"; } catch {}
  select.value = unit;
  button.onclick = () => dialog.showModal();
  $("preferences-close").onclick = () => dialog.close();
  dialog.addEventListener("cancel", (event) => { event.preventDefault(); dialog.close(); });
  dialog.addEventListener("close", () => button.focus());
  select.addEventListener("change", () => {
    unit = select.value === "sqft" ? "sqft" : "sqm";
    try { localStorage.setItem(KEY, unit); } catch {}
    onChange(unit);
  });
  return { areaUnit: () => unit };
}
