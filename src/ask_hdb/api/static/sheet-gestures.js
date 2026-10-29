// Only headers capture pointers. Scrolling content and the map keep their native gestures.
export function sheetGestures({ handles, button, content, active, height, points, snap, preview }) {
  let drag = null, suppressClick = false;
  const nearest = (value) => points().reduce((best, point, i, values) =>
    Math.abs(point - value) < Math.abs(values[best] - value) ? i : best, 0);
  const clamp = (value) => Math.max(points()[0], Math.min(points()[2], value));
  const FLICK = 0.4; // pixels per millisecond: a quick flick moves one snap even when the finger travels only a short way
  // Where the sheet settles: a flick goes one step in its direction, anything slower goes to the nearest snap.
  const target = (start, speed) => speed > FLICK ? Math.min(2, start + 1) : speed < -FLICK ? Math.max(0, start - 1) : nearest(height());
  // Finger speed over the last 100 ms, positive when moving up; events without a timestamp (tests) have none.
  const speedOf = (trail) => {
    const last = trail[trail.length - 1], first = trail.find((point) => last.t - point.t <= 100);
    return last.t && first && last.t > first.t ? (first.y - last.y) / (last.t - first.t) : 0;
  };
  handles.forEach((node) => {
    node.addEventListener("pointerdown", (event) => {
      if (!active() || event.button !== 0 || drag) return;
      suppressClick = false;
      // Capture immediately so a pointer leaving the header cannot strand a pending drag.
      // Other buttons keep their native click target, including the card close button.
      if (event.target.closest("button") && event.target !== button) return;
      const capture = event.target === button ? button : node;
      drag = { id: event.pointerId, y: event.clientY, height: height(), moved: false, node: capture,
        start: nearest(height()), trail: [{ t: event.timeStamp, y: event.clientY }] };
      capture.setPointerCapture(event.pointerId);
    });
    node.addEventListener("pointermove", (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      const delta = drag.y - event.clientY;
      drag.trail.push({ t: event.timeStamp, y: event.clientY });
      if (Math.abs(delta) >= 8 && !drag.moved) {
        drag.moved = true;
      }
      if (drag.moved) {
        event.preventDefault();
        preview(clamp(drag.height + delta));
      }
    });
    const finish = (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      const previous = drag; drag = null;
      if (previous.node.hasPointerCapture(event.pointerId)) previous.node.releasePointerCapture(event.pointerId);
      if (previous.moved) {
        suppressClick = true;
        snap(event.type === "pointercancel" ? previous.start : target(previous.start, speedOf(previous.trail)));
      }
    };
    node.addEventListener("pointerup", finish);
    node.addEventListener("pointercancel", finish);
    node.addEventListener("click", (event) => {
      if (!suppressClick) return;
      suppressClick = false; event.preventDefault(); event.stopPropagation();
    }, true);
  });
  // Touch on the scrolling content hands over to the sheet, as in Apple Maps: dragging up grows a sheet that is not full,
  // and dragging down at the top of the content shrinks it. Everything else scrolls natively.
  if (content) {
    let touch = null;
    content.addEventListener("touchstart", (event) => {
      touch = active() && event.touches.length === 1 ? { y: event.touches[0].clientY, height: height(), start: nearest(height()),
        sheet: false, trail: [{ t: event.timeStamp, y: event.touches[0].clientY }] } : null;
    }, { passive: true });
    content.addEventListener("touchmove", (event) => {
      if (!touch) return;
      const y = event.touches[0].clientY, delta = touch.y - y;
      touch.trail.push({ t: event.timeStamp, y });
      if (!touch.sheet) {
        if (Math.abs(delta) < 8) return;
        const index = nearest(height());
        if ((delta > 0 && index < 2) || (delta < 0 && content.scrollTop <= 0 && index > 0)) {
          touch.sheet = true; touch.start = index; // from here the finger moves the sheet, counted from where it first touched
        } else { touch = null; return; }
      }
      event.preventDefault();
      preview(clamp(touch.height + (touch.y - y)));
    }, { passive: false });
    const end = () => {
      if (touch?.sheet) { suppressClick = true; snap(target(touch.start, speedOf(touch.trail))); }
      touch = null;
    };
    content.addEventListener("touchend", end);
    content.addEventListener("touchcancel", () => { if (touch?.sheet) snap(touch.start); touch = null; });
  }
  button.addEventListener("click", (event) => {
    if (active() && !event.defaultPrevented) snap((nearest(height()) + 1) % 3, true);
  });
  return () => { drag = null; suppressClick = false; };
}
