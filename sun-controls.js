// Keep playback and Singapore's clock independent of the browser's time zone.
import { refreshFacade } from "./building-card.js";
const $ = (id) => document.getElementById(id);
export function singaporeNow(now = new Date()) {
  const local = new Date(now.getTime() + 8 * 60 * 60 * 1000);
  const rawMinute = local.getUTCHours() * 60 + local.getUTCMinutes();
  const minute = Math.floor(rawMinute / 15) * 15;
  return { date: local.toISOString().slice(0, 10), minute: Math.max(360, Math.min(1170, minute)),
    down: rawMinute < 360 || rawMinute > 1170 };
}

export function initSunControls(render, clear) {
  const date = $("sun-date"), slider = $("sun-time"), play = $("sun-play");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  let samples = [], dayRequest = 0, frame = null, playing = false, lastTick = null, nowRequest = 0;
  function stop() {
    playing = false; lastTick = null;
    play.textContent = "Play"; play.setAttribute("aria-pressed", "false");
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
  }
  function updateTime() {
    const minute = Number(slider.value);
    const time = String(Math.floor(minute / 60)).padStart(2, "0") + ":" + String(minute % 60).padStart(2, "0");
    $("sun-time-label").textContent = time + " (+08:00)";
    slider.setAttribute("aria-valuetext", time + " Singapore time");
    const sun = samples[minute / 15];
    if (!sun) return;
    $("sun-position").textContent = "Sun " + Math.round(sun.altitude) + "° above the horizon, bearing " + Math.round(sun.azimuth) + "°";
    render(sun);
  }
  async function loadDay(minute = null, down = false) {
    const mine = ++dayRequest;
    samples = []; stop(); clear();
    $("sun-position").textContent = "Loading sun geometry…";
    slider.disabled = play.disabled = true;
    try {
      const response = await fetch("/sun" + (date.value ? "?date=" + encodeURIComponent(date.value) : ""));
      if (!response.ok) throw new Error("Use a valid date; sun geometry could not be loaded.");
      const data = await response.json();
      if (mine !== dayRequest) return false;
      date.value = data.date; samples = data.positions;
      slider.disabled = false; play.disabled = reduced.matches;
      if (minute !== null) slider.value = String(minute);
      updateTime();
      if (down) $("sun-position").textContent = "The sun is down.";
      return true;
    } catch (error) {
      if (mine === dayRequest) $("sun-position").textContent = error.message;
      return false;
    }
  }
  function manual() { nowRequest++; stop(); }
  function tick(time) {
    frame = null;
    if (!playing) return;
    if (lastTick === null) lastTick = time;
    // Advance only once per tick, even after a slow frame; never race through missed steps.
    if (time - lastTick >= 150) {
      lastTick = time;
      slider.value = String(Math.min(1170, Number(slider.value) + 15));
      updateTime();
      if (Number(slider.value) >= 1170) { stop(); return; }
    }
    frame = requestAnimationFrame(tick);
  }
  play.disabled = reduced.matches;
  play.onclick = () => {
    nowRequest++;
    if (playing) { stop(); return; }
    if (reduced.matches || slider.disabled || document.hidden || Number(slider.value) >= 1170) return;
    playing = true; play.textContent = "Pause"; play.setAttribute("aria-pressed", "true");
    frame = requestAnimationFrame(tick);
  };
  $("sun-now").onclick = async () => {
    manual(); const mine = nowRequest, now = singaporeNow();
    if (date.value !== now.date || !samples.length) {
      date.value = now.date;
      await loadDay(now.minute, now.down);
    } else {
      slider.value = String(now.minute); updateTime();
      if (now.down) $("sun-position").textContent = "The sun is down.";
    }
    if (mine === nowRequest) refreshFacade();
  };
  date.onchange = () => { manual(); loadDay(); refreshFacade(); };
  slider.oninput = () => {
    manual();
    frame = requestAnimationFrame(() => { frame = null; updateTime(); });
  };
  document.addEventListener("visibilitychange", () => { if (document.hidden) manual(); });
  reduced.addEventListener("change", () => { if (reduced.matches) stop(); play.disabled = reduced.matches || slider.disabled; });
  return { loadDay, updateTime, stop: manual };
}
