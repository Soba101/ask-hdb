// Only headers capture pointers. Scrolling content and the map keep their native gestures.
export function sheetGestures({ handles, button, active, height, points, snap, preview }) {
  let drag = null, suppressClick = false;
  const nearest = (value) => points().reduce((best, point, i, values) =>
    Math.abs(point - value) < Math.abs(values[best] - value) ? i : best, 0);
  handles.forEach((node) => {
    node.addEventListener("pointerdown", (event) => {
      if (!active() || event.button !== 0 || drag) return;
      suppressClick = false;
      // Capture immediately so a pointer leaving the header cannot strand a pending drag.
      // Other buttons keep their native click target, including the card close button.
      if (event.target.closest("button") && event.target !== button) return;
      const capture = event.target === button ? button : node;
      drag = { id: event.pointerId, y: event.clientY, height: height(), moved: false, node: capture };
      capture.setPointerCapture(event.pointerId);
    });
    node.addEventListener("pointermove", (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      const delta = drag.y - event.clientY;
      if (Math.abs(delta) >= 8 && !drag.moved) {
        drag.moved = true;
      }
      if (drag.moved) {
        event.preventDefault();
        preview(Math.max(points()[0], Math.min(points()[2], drag.height + delta)));
      }
    });
    const finish = (event) => {
      if (!drag || event.pointerId !== drag.id) return;
      const previous = drag; drag = null;
      if (previous.node.hasPointerCapture(event.pointerId)) previous.node.releasePointerCapture(event.pointerId);
      if (previous.moved) {
        suppressClick = true;
        snap(event.type === "pointercancel" ? nearest(previous.height) : nearest(height()));
      }
    };
    node.addEventListener("pointerup", finish);
    node.addEventListener("pointercancel", finish);
    node.addEventListener("click", (event) => {
      if (!suppressClick) return;
      suppressClick = false; event.preventDefault(); event.stopPropagation();
    }, true);
  });
  button.addEventListener("click", (event) => {
    if (active() && !event.defaultPrevented) snap((nearest(height()) + 1) % 3, true);
  });
  return () => { drag = null; suppressClick = false; };
}
