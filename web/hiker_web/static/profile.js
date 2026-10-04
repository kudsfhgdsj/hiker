// Elevation profile as a chart: axes, grid and a box that names the place under the pointer.
// Used by the tour page and the route planner; both link it with their map through
// `onShow(index, follow)` and `onHide()`.
window.hikerProfile = ({ box, series, texts, photos = [], onPhoto, onShow, onHide }) => {
  const number = (value, digits = 0) =>
    value.toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const profile = box.querySelector("#profile");
  const tip = box.querySelector("#profile-tip");
  const elevations = series && series.elevation_m;
  const known = elevations ? elevations.filter((value) => value != null) : [];
  if (!profile || !tip || known.length < 2) {
    box.hidden = true;
    return null;
  }
  box.hidden = false;
  const distances = series.distance_m;
  const count = distances.length;
  const total = distances[count - 1] || 1;
  // Points without elevation take the one of their neighbour, so that the curve has no holes.
  const filled = [...elevations];
  for (let index = 1; index < count; index++) if (filled[index] == null) filled[index] = filled[index - 1];
  for (let index = count - 2; index >= 0; index--) if (filled[index] == null) filled[index] = filled[index + 1];

  // A step of 1, 2 or 5 times a power of ten that gives about `wanted` steps.
  const niceStep = (span, wanted) => {
    const rough = span / wanted;
    const power = 10 ** Math.floor(Math.log10(rough));
    const share = rough / power;
    return (share <= 1 ? 1 : share <= 2 ? 2 : share <= 5 ? 5 : 10) * power;
  };
  const indexAt = (meters) => {
    let lower = 0;
    let upper = count - 1;
    while (lower < upper) {
      const middle = (lower + upper) >> 1;
      if (distances[middle] < meters) lower = middle + 1;
      else upper = middle;
    }
    return lower;
  };
  // Slope in percent over about 100 m around the point; single points are too noisy.
  const slopeAt = (index) => {
    const from = indexAt(Math.max(0, distances[index] - 50));
    const to = indexAt(Math.min(total, distances[index] + 50));
    const run = distances[to] - distances[from];
    return run > 0 ? ((filled[to] - filled[from]) / run) * 100 : null;
  };

  const margin = { top: 12, right: 14, bottom: 26, left: 58 };
  const lowest = Math.min(...known);
  const highest = Math.max(...known);
  const stepY = niceStep(Math.max(highest - lowest, 10), 4);
  const low = Math.floor(lowest / stepY) * stepY;
  const high = Math.max(Math.ceil(highest / stepY) * stepY, low + stepY);
  let x = () => 0;
  let y = () => 0;
  let cursor = null;
  let focus = null;
  let shown = -1;

  const svg = (name, attributes, text) => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (text != null) element.textContent = text;
    profile.append(element);
    return element;
  };
  const draw = () => {
    const width = profile.clientWidth || 600;
    const height = profile.clientHeight || 200;
    const right = width - margin.right;
    const bottom = height - margin.bottom;
    profile.replaceChildren();
    profile.setAttribute("viewBox", `0 0 ${width} ${height}`);
    x = (meters) => margin.left + (meters / total) * (right - margin.left);
    y = (elevation) => bottom - ((elevation - low) / (high - low)) * (bottom - margin.top);

    const gradient = svg("linearGradient", { id: "profile-fill", x1: 0, y1: 0, x2: 0, y2: 1 });
    for (const [offset, opacity] of [[0, 0.5], [1, 0.05]]) {
      const stop = document.createElementNS("http://www.w3.org/2000/svg", "stop");
      stop.setAttribute("offset", offset);
      stop.setAttribute("class", "fill-stop");
      stop.setAttribute("stop-opacity", opacity);
      gradient.append(stop);
    }
    for (let value = low; value <= high + stepY / 2; value += stepY) {
      svg("line", { class: "grid", x1: margin.left, x2: right, y1: y(value), y2: y(value) });
      svg("text", { class: "tick", x: margin.left - 8, y: y(value) + 4, "text-anchor": "end" }, `${number(value)} m`);
    }
    const stepX = niceStep(total / 1000, width < 500 ? 4 : 8);
    const digits = stepX < 1 ? (stepX < 0.1 ? 2 : 1) : 0;
    for (let km = 0; km * 1000 <= total + 1; km += stepX) {
      const at = x(km * 1000);
      svg("line", { class: "grid upright", x1: at, x2: at, y1: margin.top, y2: bottom });
      svg("text", { class: "tick", x: at, y: bottom + 18, "text-anchor": "middle" }, `${number(km, digits)} km`);
    }
    const path = distances.map((meters, index) => `${x(meters).toFixed(1)},${y(filled[index]).toFixed(1)}`);
    svg("polygon", { class: "area", points: `${margin.left},${bottom} ${path.join(" ")} ${right},${bottom}` });
    svg("polyline", { class: "line", points: path.join(" ") });
    for (const photo of photos) {
      if (photo.distance == null) continue;
      const tick = svg("circle", {
        class: "photo-tick",
        cx: x(photo.distance),
        cy: y(filled[indexAt(photo.distance)]),
        r: 5,
      });
      if (onPhoto) tick.addEventListener("click", () => onPhoto(photo));
    }
    cursor = svg("line", { class: "cursor", x1: 0, x2: 0, y1: margin.top, y2: bottom });
    focus = svg("circle", { class: "focus", cx: 0, cy: 0, r: 6 });
    if (shown >= 0) show(shown, false);
  };

  const row = (label, value) => {
    const entry = document.createElement("div");
    const name = document.createElement("span");
    name.textContent = label;
    const content = document.createElement("strong");
    content.textContent = value;
    entry.append(name, content);
    return entry;
  };

  const show = (index, follow) => {
    shown = index;
    const meters = distances[index];
    const left = x(meters);
    cursor.setAttribute("x1", left);
    cursor.setAttribute("x2", left);
    focus.setAttribute("cx", left);
    focus.setAttribute("cy", y(filled[index]));
    box.classList.add("active");
    if (onShow) onShow(index, follow);

    const rows = [row(texts.distance, `${number(meters / 1000, 1)} km`)];
    if (elevations[index] != null) rows.push(row(texts.elevation, `${number(elevations[index])} m`));
    const slope = slopeAt(index);
    if (slope != null) {
      const percent = Math.round(slope) || 0;
      rows.push(row(texts.slope, `${percent > 0 ? "+" : ""}${number(percent)} %`));
    }
    if (series.time && series.time[index]) {
      const time = new Date(series.time[index]).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
      rows.push(row(texts.time, time));
    }
    if (series.time_s && series.time_s[index] != null && texts.walked) {
      const minutes = Math.round(series.time_s[index] / 60);
      rows.push(row(texts.walked, `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, "0")} min`));
    }
    if (series.heart_rate && series.heart_rate[index] != null) {
      rows.push(row(texts.heartRate, String(series.heart_rate[index])));
    }
    tip.replaceChildren(...rows);
    // The box stands beside the cursor, on the side with more room.
    const before = left > profile.clientWidth / 2;
    tip.style.left = before ? "" : `${left + 12}px`;
    tip.style.right = before ? `${profile.clientWidth - left + 12}px` : "";
  };
  const hide = () => {
    shown = -1;
    box.classList.remove("active");
    if (onHide) onHide();
  };

  // One chart can replace another on the same element: its listeners go with it.
  const life = new AbortController();
  const listen = (name, handler) => profile.addEventListener(name, handler, { signal: life.signal });
  draw();
  const observer = window.ResizeObserver ? new ResizeObserver(draw) : null;
  if (observer) observer.observe(profile);

  let waiting = null;
  const point = (event) => {
    const area = profile.getBoundingClientRect();
    const inner = area.width - margin.left - margin.right;
    const share = Math.min(1, Math.max(0, (event.clientX - area.left - margin.left) / inner));
    // At most one update per frame, however fast the pointer moves.
    if (waiting == null) requestAnimationFrame(() => {
      if (!life.signal.aborted) show(indexAt(waiting * total), true);
      waiting = null;
    });
    waiting = share;
  };
  listen("pointermove", point);
  listen("pointerdown", point);
  // A finger leaves the profile when it lifts: the position stays until the next touch.
  listen("pointerleave", (event) => {
    if (event.pointerType === "mouse") hide();
  });
  listen("keydown", (event) => {
    const stride = Math.max(1, Math.round(count / 100));
    const current = shown < 0 ? 0 : shown;
    const target = {
      ArrowRight: Math.min(count - 1, shown < 0 ? 0 : current + stride),
      ArrowLeft: Math.max(0, current - stride),
      Home: 0,
      End: count - 1,
    }[event.key];
    if (event.key === "Escape") hide();
    if (target == null) return;
    event.preventDefault();
    show(target, true);
  });
  listen("blur", hide);

  return {
    show,
    hide,
    destroy() {
      life.abort();
      if (observer) observer.disconnect();
      hide();
    },
  };
};
