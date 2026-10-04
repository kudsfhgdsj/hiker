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
    // The own vector map if the server has one, else the cached raster tiles.
    style: data.styleUrl || {
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
  if (!box || !series || !window.hikerProfile) {
    if (box) box.remove();
    return;
  }
  const walker = document.createElement("div");
  walker.className = "walk-marker";
  const position = new maplibregl.Marker({ element: walker });
  const chart = window.hikerProfile({
    box,
    series,
    texts: data.texts,
    photos: data.photos,
    onPhoto: (photo) => showPhoto(photo.full, photo.caption),
    onShow: (index, follow) => {
      position.setLngLat(line[index]).addTo(map);
      walkedUntil = index;
      const walked = map.getSource("walked");
      if (walked) walked.setData(walkedPart(index));
      // Walking out of the visible part of the map moves the map along.
      if (follow && !map.getBounds().contains(line[index])) map.panTo(line[index], { duration: 300 });
    },
    onHide: () => {
      walkedUntil = -1;
      position.remove();
      const walked = map.getSource("walked");
      if (walked) walked.setData(walkedPart(-1));
    },
  });
  if (!chart) return;

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
    if (best >= 0) chart.show(best, false);
    else if (fromMap) chart.hide();
    fromMap = best >= 0;
  });
  map.on("mouseout", () => {
    if (fromMap) chart.hide();
    fromMap = false;
  });
})();
