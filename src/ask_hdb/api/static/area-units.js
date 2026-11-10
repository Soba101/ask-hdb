const SQFT_PER_SQM = 10.7639;
const number = String.raw`\d+(?:,\d{3})*(?:\.\d+)?`;
const sqm = String.raw`(?:sqm|sq\s+m|m²|square\s+met(?:re|er)s?)(?![\w²])`;
const span = `${number}(?:\\s*[-–—‑]\\s*${number}|\\s+to\\s+${number})?`;
const metric = new RegExp(String.raw`(?<![\w.,$])(?:\$(${number})\s*(?:per\s+${sqm}|/\s*${sqm}|psm\b)|(${span})\s*${sqm})`, "gi");
const imperial = new RegExp(String.raw`(?:\$?${span}\s*(?:per\s+|/\s*)?(?:sq\s*ft|sqft|psf)\b)(?:\s*(?:\([^)]*${sqm}\)|\/\s*\$?${span}\s*(?:per\s+)?${sqm}))?`, "gi");
const value = (text) => Number(text.replaceAll(",", ""));
const whole = (n) => Math.round(n).toLocaleString("en-SG");

// No-break spaces keep "1,001 sq ft" and "93 sqm" whole on a narrow screen; the line may break at the slash.
export function convertAreaText(text, unit) {
  if (unit !== "sqft") return text;
  // Leave existing imperial values and their metric brackets alone.
  const pattern = new RegExp(`${imperial.source}|${metric.source}`, "gi");
  return text.replace(pattern, (match, price, area) => {
    if (price) return "$" + whole(value(price) / SQFT_PER_SQM) + "\u00a0per\u00a0sq\u00a0ft / $" + price + "\u00a0per\u00a0sqm";
    if (!area) return match;
    const values = area.match(new RegExp(number, "g"));
    const converted = values.map((n) => whole(value(n) * SQFT_PER_SQM)).join("-");
    return converted + "\u00a0sq\u00a0ft / " + values.join("-") + "\u00a0sqm";
  });
}

const originals = new WeakMap();
export function displayAreaUnits(root, unit) {
  // Only edit rendered text. Link destinations and the server's chat history stay intact.
  if (root.nodeType === 3) {
    if (!originals.has(root)) originals.set(root, root.textContent);
    root.textContent = convertAreaText(originals.get(root), unit);
  } else {
    const tag = root.tagName?.toLowerCase();
    if (tag === "button" || tag === "a" && root.textContent === root.href) return;
    for (const child of root.childNodes) displayAreaUnits(child, unit);
  }
}
