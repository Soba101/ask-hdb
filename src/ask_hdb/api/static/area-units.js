const SQFT_PER_SQM = 10.7639;
const number = String.raw`\d+(?:,\d{3})*(?:\.\d+)?`;
const sqm = String.raw`(?:sqm|sq\s+m|m²|square\s+met(?:re|er)s?)(?![\w²])`;
const span = `${number}(?:\\s*[-–—‑]\\s*${number}|\\s+to\\s+${number})?`;
const metric = new RegExp(String.raw`(?<![\w.,$])(?:\$(${number})\s*(?:per\s+${sqm}|/\s*${sqm}|psm\b)|(${span})\s*${sqm})`, "gi");
const imperial = new RegExp(String.raw`(?:\$?${span}\s*(?:per\s+|/\s*)?(?:sq\s*ft|sqft|psf)\b)(?:\s*(?:\([^)]*${sqm}\)|\/\s*\$?${span}\s*(?:per\s+)?${sqm}))?`, "gi");
const areaPattern = () => new RegExp(`${imperial.source}|${metric.source}`, "gi");
const value = (text) => Number(text.replaceAll(",", ""));
const whole = (n) => Math.round(n).toLocaleString("en-SG");

// No-break spaces keep "1,001 sq ft" and "93 sqm" whole on a narrow screen; the line may break at the slash.
export function convertAreaText(text, unit) {
  if (unit !== "sqft") return text;
  // Leave existing imperial values and their metric brackets alone.
  return text.replace(areaPattern(), (match, price, area) => {
    if (price) return "$" + whole(value(price) / SQFT_PER_SQM) + "\u00a0per\u00a0sq\u00a0ft / $" + price + "\u00a0per\u00a0sqm";
    if (!area) return match;
    const values = area.match(new RegExp(number, "g"));
    const converted = values.map((n) => whole(value(n) * SQFT_PER_SQM)).join("-");
    return converted + "\u00a0sq\u00a0ft / " + values.join("-") + "\u00a0sqm";
  });
}

const originals = new WeakMap();
// A link is a boundary: a number before it must not pull its label out (that left an empty link).
const inline = new Set(["strong", "em", "b", "i", "span", "code"]);
export function displayAreaUnits(root, unit) {
  // Only edit rendered text. Link destinations and the server's chat history stay intact.
  let nodes = [];
  function flush() {
    let offset = 0;
    const entries = nodes.map((node) => {
      if (!originals.has(node)) originals.set(node, node.textContent);
      const text = originals.get(node), start = offset;
      offset += text.length;
      return { node, text, start, end: offset, value: text };
    });
    const text = entries.map((entry) => entry.text).join("");
    // Match across inline tags, but keep the nodes so metric text and formatting can be restored.
    // Work backwards so earlier source offsets stay valid after a replacement grows.
    if (unit === "sqft") for (const match of [...text.matchAll(areaPattern())].reverse()) {
      const converted = convertAreaText(match[0], unit), end = match.index + match[0].length;
      if (converted === match[0]) continue;
      let inserted = false;
      for (const entry of entries) {
        if (entry.start >= end || entry.end <= match.index) continue;
        const from = Math.max(0, match.index - entry.start), to = Math.min(entry.text.length, end - entry.start);
        entry.value = entry.value.slice(0, from) + (inserted ? "" : converted) + entry.value.slice(to);
        inserted = true;
      }
    }
    for (const entry of entries) entry.node.textContent = entry.value;
    nodes = [];
  }
  function visit(node) {
    if (node.nodeType === 3) { nodes.push(node); return; }
    const tag = node.tagName?.toLowerCase();
    if (tag === "button" || tag === "a" && node.textContent === node.href) { flush(); return; }
    // A number in one paragraph or table cell must not borrow a unit from the next.
    if (!inline.has(tag)) flush();
    for (const child of node.childNodes) visit(child);
    if (!inline.has(tag)) flush();
  }
  visit(root); flush();
}
