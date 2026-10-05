// Choosing positions on the map. Without this script the forms work with typed coordinates.
(async () => {
  const holder = document.getElementById("tour-data");
  const mapElement = document.getElementById("map");
  if (!holder || !mapElement || !window.maplibregl) return;
  const data = JSON.parse(holder.textContent);
  const texts = JSON.parse(document.getElementById("map-texts").textContent);
  const hint = document.getElementById("pick-hint");

  let line = [];
  if (data.trackUrl) {
    try {
      const response = await fetch(data.trackUrl, { credentials: "same-origin" });
      const series = response.ok ? (await response.json()).series : null;
      if (series) line = series.lat.map((lat, index) => [series.lon[index], lat]);
    } catch (_error) {
      line = [];
    }
  }

  maplibregl.setWorkerUrl(data.workerUrl);
  const tileUrl = data.tileUrl.startsWith("/") ? window.location.origin + data.tileUrl : data.tileUrl;
  const place = (point) => point && point.lat != null && point.lon != null;
  const positions = [...line];
  for (const point of [data.start, data.end, ...data.photos, ...data.waypoints]) {
    if (place(point)) positions.push([point.lon, point.lat]);
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
    // Without anything to show yet: the Alps.
    center: positions[0] || [9.5, 46.8],
    zoom: positions.length ? 12 : 6,
  });
  map.addControl(new maplibregl.NavigationControl(), "top-right");
  map.getCanvas().style.cursor = "crosshair";
  if (positions.length > 1) {
    const bounds = positions.reduce(
      (box, position) => box.extend(position),
      new maplibregl.LngLatBounds(positions[0], positions[0]),
    );
    map.fitBounds(bounds, { padding: 40, animate: false, maxZoom: 15 });
  }

  const dot = (text, color) => {
    const element = document.createElement("div");
    element.className = "dot-marker";
    element.style.background = color;
    element.textContent = text;
    return element;
  };
  const show = (element, point, title) => {
    const marker = new maplibregl.Marker({ element }).setLngLat([point.lon, point.lat]).addTo(map);
    if (title) marker.setPopup(new maplibregl.Popup({ offset: 14 }).setText(title));
  };
  if (place(data.start)) show(dot("S", "#2e7d32"), data.start, data.start.name || data.texts.start);
  if (place(data.end)) show(dot("Z", "#c62828"), data.end, data.end.name || data.texts.end);
  for (const point of data.waypoints) if (place(point)) show(dot("•", "#5d4037"), point, point.name);
  for (const photo of data.photos) {
    if (!place(photo)) continue;
    const image = document.createElement("img");
    image.className = "photo-marker";
    image.src = photo.thumb;
    image.alt = photo.caption || "";
    show(image, photo, photo.caption);
  }

  const lineData = (coordinates) => ({
    type: "Feature",
    properties: {},
    geometry: { type: "LineString", coordinates },
  });
  await new Promise((resolve) => (map.loaded() ? resolve() : map.once("load", resolve)));
  const addLine = (id, coordinates, color, dashed) => {
    map.addSource(id, { type: "geojson", data: lineData(coordinates) });
    map.addLayer({
      id,
      type: "line",
      source: id,
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": color, "line-width": 4, ...(dashed ? { "line-dasharray": [1, 2] } : {}) },
    });
  };
  if (line.length > 1) addLine("track", line, "#c62828", false);
  addLine("drawn", [], "#1565c0", true);

  // --- Picking a position for one of the forms ---
  const chosen = new maplibregl.Marker({ element: dot("", "#1565c0") });
  let target = null; // { lat, lon } inputs, or "draw"
  const setHint = (text) => {
    hint.hidden = !text;
    hint.textContent = text || "";
  };
  for (const group of document.querySelectorAll(".position")) {
    const button = group.querySelector("button.pick");
    if (!button) continue;
    const prefix = group.dataset.position;
    const inputs = {
      lat: group.querySelector(`input[name="${prefix}lat"]`),
      lon: group.querySelector(`input[name="${prefix}lon"]`),
    };
    button.hidden = false;
    button.addEventListener("click", () => {
      target = inputs;
      setHint(texts.pick);
      mapElement.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  // --- Drawing a track ---
  const drawArea = document.getElementById("draw-points");
  const drawn = [];
  const syncDrawn = () => {
    drawArea.value = drawn.map(([lon, lat]) => `${lat.toFixed(5)}, ${lon.toFixed(5)}`).join("\n");
    map.getSource("drawn").setData(lineData(drawn));
  };
  if (drawArea) {
    const start = document.getElementById("draw-start");
    const undo = document.getElementById("draw-undo");
    start.hidden = false;
    undo.hidden = false;
    start.addEventListener("click", () => {
      target = "draw";
      setHint(texts.draw);
      mapElement.scrollIntoView({ behavior: "smooth", block: "center" });
    });
    undo.addEventListener("click", () => {
      drawn.pop();
      syncDrawn();
    });
  }

  map.on("click", (event) => {
    const { lng, lat } = event.lngLat;
    if (target === "draw") {
      drawn.push([lng, lat]);
      syncDrawn();
    } else if (target) {
      target.lat.value = lat.toFixed(6);
      target.lon.value = lng.toFixed(6);
      chosen.setLngLat([lng, lat]).addTo(map);
      setHint("");
      target.lat.scrollIntoView({ behavior: "smooth", block: "center" });
      target = null;
    }
  });
})();
