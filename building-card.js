// Separate from map loading: the building card still works if WebGL is unavailable.
const $ = (id) => document.getElementById(id);
let current = null, request = 0, opened = false;
let loadedDate = null, pending = null;

export function line(parent, text, tag = "p") {
  const p = document.createElement(tag);
  p.textContent = text;
  parent.appendChild(p);
  return p;
}

export function clearBuildingCard() {
  current = null; request++; opened = false; loadedDate = null; pending = null;
  for (const id of ["card-buildings", "storey-prices", "card-sun", "building-limits", "sun-limits"]) $(id).replaceChildren();
}

export function showBuildingFacts(data, point) {
  current = point;
  const box = $("card-buildings"), prices = $("storey-prices"), limits = $("building-limits");
  const source = { property_info: "HDB property information", sales: "highest recorded resale band (estimate)", default: "default estimate" };
  line(box, data.floors ? data.floors + " floors · " + source[data.height_source] : "Building height is unavailable.");
  const facing = data.facing_label ? "Approximate block facing: " + data.facing_label + " (not per unit)." : null;
  if (facing) line(box, facing);
  line(prices, "Price by storey band · median, last 24 months · all flat types pooled");
  for (const band of data.storey_prices || []) {
    line(prices, "Storeys " + band.label + ": $" + band.median_price.toLocaleString("en-SG") + " median · " + band.sales + " sales");
  }
  if (!data.storey_prices?.length) line(prices, "No storey bands with enough recent sales for a median.");
  if (data.storey_prices_as_of) line(limits, "Price by storey band · data to " + data.storey_prices_as_of);
  if (data.storey_prices_limits) line(limits, data.storey_prices_limits);
  return facing; // the headline uses this same qualified facing, never a derived bearing
}

export function openBuildingSun(point) {
  current = point;
  return refreshFacade(true);
}

export async function refreshFacade(open = false) {
  opened ||= open;
  if (!current || !opened) return; // map controls must not eagerly load a closed card section
  const date = $("sun-date").value;
  if (loadedDate === date) return pending;
  loadedDate = date;
  const mine = ++request, point = current, box = $("card-sun"), limits = $("sun-limits");
  box.replaceChildren(); limits.replaceChildren();
  pending = (async () => {
    try {
      const response = await fetch("/sun/block/" + encodeURIComponent(point.id) + (date ? "?date=" + encodeURIComponent(date) : ""));
      if (!response.ok) throw new Error("Sun geometry is unavailable for this block or date.");
      const data = await response.json();
      if (mine !== request) return;
      line(box, "Illustrative direct sun · " + data.date + " (+08:00)");
      for (const facade of data.facades) {
        line(box, facade.label + " facade: " + facade.hours + " hours · peak " + (facade.peak_time || "none") + " · illustrative");
      }
      line(limits, data.limits);
    } catch (error) {
      if (mine === request) line(box, error.message);
    }
  })();
  return pending;
}
