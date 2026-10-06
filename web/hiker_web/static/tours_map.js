// The map of the tour list: all tours of the choice at once, each as its own line. A
// click on a line or a point opens the tour.
(() => {
  const holder = document.getElementById("tours-map-data");
  const mapElement = document.getElementById("map");
  if (!holder || !mapElement || !window.maplibregl) return;
  const data = JSON.parse(holder.textContent);
  const note = document.getElementById("tours-map-note");

  maplibregl.setWorkerUrl(data.workerUrl);
  const tileUrl = data.tileUrl.startsWith("/") ? window.location.origin + data.tileUrl : data.tileUrl;
  const map = new maplibregl.Map({
    container: mapElement,
    style: data.styleUrl || {
      version: 8,
      sources: {
        base: { type: "raster", tiles: [tileUrl], tileSize: 256, attribution: data.attribution },
      },
      layers: [{ id: "base", type: "raster", source: "base" }],
    },
    center: [10.5, 46.8],
    zoom: 6,
  });
  map.addControl(new maplibregl.NavigationControl(), "top-right");
  if (window.hikerMapLayers) window.hikerMapLayers(map, data.layerTexts);

  map.on("load", async () => {
    let tours;
    try {
      tours = await (await fetch(data.tracksUrl, { credentials: "same-origin" })).json();
    } catch (_error) {
      return;
    }
    if (!tours.features || !tours.features.length) {
      note.textContent = data.texts.empty;
      note.hidden = false;
      return;
    }
    map.addSource("tours", { type: "geojson", data: tours });
    // Own tours in red, tours shared with the user in blue.
    const colour = ["case", ["get", "own"], "#c8201a", "#1f6fb5"];
    const lines = ["==", ["geometry-type"], "LineString"];
    map.addLayer({
      id: "tours-casing",
      type: "line",
      source: "tours",
      filter: lines,
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#ffffff", "line-width": 5.5, "line-opacity": 0.85 },
    });
    map.addLayer({
      id: "tours-line",
      type: "line",
      source: "tours",
      filter: lines,
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": colour, "line-width": 3 },
    });
    // Tours without a track show as a dot at their start.
    map.addLayer({
      id: "tours-point",
      type: "circle",
      source: "tours",
      filter: ["==", ["geometry-type"], "Point"],
      paint: {
        "circle-radius": 6,
        "circle-color": colour,
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 2,
      },
    });
    const bounds = new maplibregl.LngLatBounds();
    for (const feature of tours.features) {
      const points = feature.geometry.type === "Point" ? [feature.geometry.coordinates] : feature.geometry.coordinates;
      for (const point of points) bounds.extend(point);
    }
    map.fitBounds(bounds, { padding: 40, animate: false, maxZoom: 13 });

    const open = (event) => {
      const tour = event.features[0].properties;
      const box = document.createElement("div");
      const link = document.createElement("a");
      link.href = data.tourUrl.replace("00000000-0000-0000-0000-000000000000", tour.tour_id);
      link.textContent = tour.title;
      const strong = document.createElement("strong");
      strong.append(link);
      box.append(strong);
      const facts = [];
      if (tour.date) facts.push(tour.date.split("-").reverse().join("."));
      if (tour.distance_m) facts.push(`${(tour.distance_m / 1000).toFixed(1).replace(".", ",")} km`);
      if (tour.ascent_m) facts.push(`${Math.round(tour.ascent_m)} Hm`);
      if (!tour.own) facts.push(data.texts.shared);
      // Properties of a clicked feature arrive as text: the list of tags too.
      const tags = typeof tour.tags === "string" ? JSON.parse(tour.tags) : tour.tags || [];
      for (const line of [facts.join(" · "), tags.join(", ")]) {
        if (!line) continue;
        const row = document.createElement("div");
        row.className = "meta";
        row.textContent = line;
        box.append(row);
      }
      new maplibregl.Popup().setLngLat(event.lngLat).setDOMContent(box).addTo(map);
    };
    for (const layer of ["tours-casing", "tours-point"]) {
      map.on("click", layer, open);
      map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
    }
  });
})();
