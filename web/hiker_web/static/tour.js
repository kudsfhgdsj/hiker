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
  });

  // --- Elevation profile, linked with the map ---
  const profile = document.getElementById("profile");
  const readout = document.getElementById("profile-readout");
  const elevations = series && series.elevation_m;
  const known = elevations ? elevations.filter((value) => value != null) : [];
  if (!profile || known.length < 2) {
    if (profile) profile.remove();
    return;
  }
  const width = 1000;
  const height = 220;
  const total = series.distance_m[series.distance_m.length - 1] || 1;
  const low = Math.min(...known);
  const span = Math.max(...known) - low || 1;
  const x = (meters) => (meters / total) * width;
  const y = (elevation) => height - 10 - ((elevation - low) / span) * (height - 20);
  const svg = (name, attributes) => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    profile.append(element);
    return element;
  };
  const path = [];
  series.distance_m.forEach((meters, index) => {
    if (elevations[index] != null) path.push(`${x(meters).toFixed(1)},${y(elevations[index]).toFixed(1)}`);
  });
  svg("polygon", { class: "area", points: `0,${height} ${path.join(" ")} ${width},${height}` });
  svg("polyline", { class: "line", points: path.join(" ") });
  for (const photo of data.photos) {
    if (photo.distance != null) svg("circle", { class: "photo-tick", cx: x(photo.distance), cy: height - 5, r: 4 });
  }
  const cursor = svg("line", { class: "cursor", x1: 0, x2: 0, y1: 0, y2: height });
  const position = new maplibregl.Marker({ element: dot("", "#c62828") });

  const show = (index) => {
    const meters = series.distance_m[index];
    cursor.setAttribute("x1", x(meters));
    cursor.setAttribute("x2", x(meters));
    cursor.style.visibility = "visible";
    position.setLngLat(line[index]).addTo(map);
    const parts = [`${number(meters / 1000, 1)} km`];
    if (elevations[index] != null) parts.push(`${number(elevations[index])} m`);
    if (series.time && series.time[index]) {
      parts.push(new Date(series.time[index]).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }));
    }
    if (series.heart_rate && series.heart_rate[index] != null) {
      parts.push(`${data.texts.heartRate} ${series.heart_rate[index]}`);
    }
    readout.textContent = parts.join(" · ");
  };
  const indexAt = (meters) => {
    let lower = 0;
    let upper = series.distance_m.length - 1;
    while (lower < upper) {
      const middle = (lower + upper) >> 1;
      if (series.distance_m[middle] < meters) lower = middle + 1;
      else upper = middle;
    }
    return lower;
  };
  profile.addEventListener("pointermove", (event) => {
    const box = profile.getBoundingClientRect();
    const share = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width));
    show(indexAt(share * total));
  });
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
    if (best >= 0) show(best);
  });
})();
