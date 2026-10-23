// Separate from map loading: the building card still works if WebGL is unavailable.
const $ = (id) => document.getElementById(id);
let current = null, request = 0;

function line(parent, text) {
  const p = document.createElement("p");
  p.textContent = text;
  parent.appendChild(p);
}

export function clearBuildingCard() {
  current = null; request++;
  $("card-buildings").replaceChildren();
  $("card-sun").replaceChildren();
}

export function showBuildingFacts(data, point) {
  current = point;
  const box = $("card-buildings");
  const source = { property_info: "HDB property information", sales: "highest recorded resale band (estimate)", default: "default estimate" };
  line(box, data.floors ? data.floors + " floors · " + source[data.height_source] : "Building height is unavailable.");
  if (data.facing_label) line(box, "Approximate block facing: " + data.facing_label + " (not per unit).");
  line(box, "Price by storey band" + (data.storey_prices_as_of ? " · data to " + data.storey_prices_as_of : ""));
  for (const band of data.storey_prices) {
    line(box, "Storeys " + band.label + ": $" + band.median_price.toLocaleString("en-SG") + " median · " + band.sales + " sales");
  }
  if (!data.storey_prices.length) line(box, "No storey bands with enough recent sales for a median.");
  line(box, data.storey_prices_limits);
  refreshFacade();
}

export async function refreshFacade() {
  const mine = ++request, point = current, box = $("card-sun");
  box.replaceChildren();
  if (!point) return;
  const date = $("sun-date").value;
  try {
    const response = await fetch("/sun/block/" + encodeURIComponent(point.id) + (date ? "?date=" + encodeURIComponent(date) : ""));
    if (!response.ok) throw new Error("Sun geometry is unavailable for this block or date.");
    const data = await response.json();
    if (mine !== request) return;
    line(box, "Illustrative direct sun · " + data.date + " (+08:00)");
    for (const facade of data.facades) {
      line(box, facade.label + " facade: " + facade.hours + " hours · peak " + (facade.peak_time || "none"));
    }
    line(box, data.limits);
  } catch (error) {
    if (mine === request) line(box, error.message);
  }
}
