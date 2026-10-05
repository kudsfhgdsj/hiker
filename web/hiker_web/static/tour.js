// Map, elevation profile and photos of a tour. The page stays readable without this script.
(async () => {
  const holder = document.getElementById("tour-data");
  const mapElement = document.getElementById("map");
  if (!holder || !mapElement || !window.maplibregl) return;
  const data = JSON.parse(holder.textContent);
  const number = (value, digits = 0) =>
    value.toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });

  // --- Photos: open the large image in a dialog instead of leaving the page ---
  const dialog = document.getElementById("photo-dialog");
  const showPhoto = (url, caption) => {
    if (!dialog || !dialog.showModal) return window.open(url, "_blank", "noopener");
    dialog.querySelector("img").src = url;
    dialog.querySelector("p").textContent = caption || "";
    dialog.showModal();
  };
  for (const link of document.querySelectorAll("a.photo-link")) {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      showPhoto(link.href, link.dataset.caption);
    });
  }

  // --- Track ---
  let series = null;
  if (data.trackUrl) {
    try {
      const response = await fetch(data.trackUrl, { credentials: "same-origin" });
      if (response.ok) series = (await response.json()).series;
    } catch (_error) {
      series = null;
    }
  }
  const line = series ? series.lat.map((lat, index) => [series.lon[index], lat]) : [];

  // --- Map ---
  maplibregl.setWorkerUrl(data.workerUrl);
  // Tiles from the own server are configured as a path; the map needs a full address.
  const tileUrl = data.tileUrl.startsWith("/") ? window.location.origin + data.tileUrl : data.tileUrl;
  const positions = [...line];
  const place = (point) => point && point.lat != null && point.lon != null;
  for (const point of [data.start, data.end, ...data.photos, ...data.waypoints]) {
    if (place(point)) positions.push([point.lon, point.lat]);
  }
  if (positions.length === 0) {
    mapElement.hidden = true;
    return;
  }
  const map = new maplibregl.Map({
    container: mapElement,
    style: {
      version: 8,
      sources: {
        base: { type: "raster", tiles: [tileUrl], tileSize: 256, attribution: data.attribution },
      },
      layers: [{ id: "base", type: "raster", source: "base" }],
    },
    center: positions[0],
    zoom: 12,
  });
  map.addControl(new maplibregl.NavigationControl(), "top-right");
  const bounds = positions.reduce(
    (box, position) => box.extend(position),
    new maplibregl.LngLatBounds(positions[0], positions[0]),
  );
  if (positions.length > 1) map.fitBounds(bounds, { padding: 40, animate: false, maxZoom: 15 });

  const dot = (text, color) => {
    const element = document.createElement("div");
    element.className = "dot-marker";
    element.style.background = color;
    element.textContent = text;
    return element;
  };
  const addMarker = (element, point, title) => {
    const marker = new maplibregl.Marker({ element }).setLngLat([point.lon, point.lat]).addTo(map);
    if (title) marker.setPopup(new maplibregl.Popup({ offset: 14 }).setText(title));
    return marker;
  };
  if (place(data.start)) addMarker(dot("S", "#2e7d32"), data.start, data.start.name || data.texts.start);
  if (place(data.end)) addMarker(dot("Z", "#c62828"), data.end, data.end.name || data.texts.end);
  for (const point of data.waypoints) {
    if (!place(point)) continue;
    const symbol = point.kind === "peak" ? "▲" : point.kind === "saddle" ? "⌣" : "•";
    const height = point.elevation_m != null ? ` (${number(point.elevation_m)} m)` : "";
    addMarker(dot(symbol, "#5d4037"), point, `${point.name || ""}${height}`);
  }
  for (const photo of data.photos) {
    if (!place(photo)) continue;
    const image = document.createElement("img");
    image.className = "photo-marker";
    image.src = photo.thumb;
    image.alt = photo.caption || "";
    image.addEventListener("click", () => showPhoto(photo.full, photo.caption));
    addMarker(image, photo);
  }
  let walkedUntil = -1;
  const walkedPart = (index) => ({
    type: "Feature",
    properties: {},
    geometry: { type: "LineString", coordinates: index > 0 ? line.slice(0, index + 1) : [] },
  });
  map.on("load", () => {
    if (line.length < 2) return;
    map.addSource("track", {
      type: "geojson",
      data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: line } },
    });
    map.addLayer({
      id: "track",
      type: "line",
      source: "track",
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#c62828", "line-width": 4 },
    });
    // The part of the track up to the position chosen in the elevation profile.
    map.addSource("walked", { type: "geojson", data: walkedPart(walkedUntil) });
    map.addLayer({
      id: "walked",
      type: "line",
      source: "walked",
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#1b5e20", "line-width": 6 },
    });
  });

  // --- Elevation profile, linked with the map ---
  // Pointing at the profile (mouse, finger or arrow keys) walks along the track on the map.
  const box = document.getElementById("profile-box");
  const profile = document.getElementById("profile");
  const tip = document.getElementById("profile-tip");
  const elevations = series && series.elevation_m;
  const known = elevations ? elevations.filter((value) => value != null) : [];
  if (!box || !profile || !tip || known.length < 2) {
    if (box) box.remove();
    return;
  }
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
    for (const photo of data.photos) {
      if (photo.distance == null) continue;
      const tick = svg("circle", {
        class: "photo-tick",
        cx: x(photo.distance),
        cy: y(filled[indexAt(photo.distance)]),
        r: 5,
      });
      tick.addEventListener("click", () => showPhoto(photo.full, photo.caption));
    }
    cursor = svg("line", { class: "cursor", x1: 0, x2: 0, y1: margin.top, y2: bottom });
    focus = svg("circle", { class: "focus", cx: 0, cy: 0, r: 6 });
    if (shown >= 0) show(shown, false);
  };

  const walker = document.createElement("div");
  walker.className = "walk-marker";
  const position = new maplibregl.Marker({ element: walker });
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

    position.setLngLat(line[index]).addTo(map);
    walkedUntil = index;
    const walked = map.getSource("walked");
    if (walked) walked.setData(walkedPart(index));
    // Walking out of the visible part of the map moves the map along.
    if (follow && !map.getBounds().contains(line[index])) map.panTo(line[index], { duration: 300 });

    const rows = [row(data.texts.distance, `${number(meters / 1000, 1)} km`)];
    if (elevations[index] != null) rows.push(row(data.texts.elevation, `${number(elevations[index])} m`));
    const slope = slopeAt(index);
    if (slope != null) {
      const percent = Math.round(slope) || 0;
      rows.push(row(data.texts.slope, `${percent > 0 ? "+" : ""}${number(percent)} %`));
    }
    if (series.time && series.time[index]) {
      const time = new Date(series.time[index]).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
      rows.push(row(data.texts.time, time));
    }
    if (series.heart_rate && series.heart_rate[index] != null) {
      rows.push(row(data.texts.heartRate, String(series.heart_rate[index])));
    }
    tip.replaceChildren(...rows);
    // The box stands beside the cursor, on the side with more room.
    const before = left > profile.clientWidth / 2;
    tip.style.left = before ? "" : `${left + 12}px`;
    tip.style.right = before ? `${profile.clientWidth - left + 12}px` : "";
  };
  const hide = () => {
    shown = -1;
    walkedUntil = -1;
    box.classList.remove("active");
    position.remove();
    const walked = map.getSource("walked");
    if (walked) walked.setData(walkedPart(-1));
  };

  draw();
  if (window.ResizeObserver) new ResizeObserver(draw).observe(profile);

  let waiting = null;
  const point = (event) => {
    const area = profile.getBoundingClientRect();
    const inner = area.width - margin.left - margin.right;
    const share = Math.min(1, Math.max(0, (event.clientX - area.left - margin.left) / inner));
    // At most one update per frame, however fast the pointer moves.
    if (waiting == null) requestAnimationFrame(() => {
      show(indexAt(waiting * total), true);
      waiting = null;
    });
    waiting = share;
  };
  profile.addEventListener("pointermove", point);
  profile.addEventListener("pointerdown", point);
  // A finger leaves the profile when it lifts: the position stays until the next touch.
  profile.addEventListener("pointerleave", (event) => {
    if (event.pointerType === "mouse") hide();
  });
  profile.addEventListener("keydown", (event) => {
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
  profile.addEventListener("blur", hide);

  let fromMap = false;
  map.on("mousemove", (event) => {
    // The point of the track closest to the pointer, if it is close enough.
    let best = -1;
    let bestDistance = 20 * 20;
    line.forEach((coordinates, index) => {
      const pixel = map.project(coordinates);
      const distance = (pixel.x - event.point.x) ** 2 + (pixel.y - event.point.y) ** 2;
      if (distance < bestDistance) {
        best = index;
        bestDistance = distance;
      }
    });
    if (best >= 0) show(best, false);
    else if (fromMap) hide();
    fromMap = best >= 0;
  });
  map.on("mouseout", () => {
    if (fromMap) hide();
    fromMap = false;
  });
})();
