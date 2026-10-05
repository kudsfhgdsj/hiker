// The map of the statistics: all own tracks at once. The lines are translucent, so that
// ground walked often shows darker, like a heat map of where the user has been.
(() => {
  const holder = document.getElementById("stats-data");
  const mapElement = document.getElementById("map");
  if (!holder || !mapElement || !window.maplibregl) return;
  const data = JSON.parse(holder.textContent);

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
    let tracks;
    try {
      tracks = await (await fetch(data.tracksUrl, { credentials: "same-origin" })).json();
    } catch (_error) {
      return;
    }
    if (!tracks.features || !tracks.features.length) return;
    map.addSource("walked", { type: "geojson", data: tracks });
    // A wide soft band under a thin line: overlaps add up to darker ground.
    map.addLayer({
      id: "walked-glow",
      type: "line",
      source: "walked",
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#e8351a", "line-width": 9, "line-opacity": 0.18, "line-blur": 4 },
    });
    map.addLayer({
      id: "walked",
      type: "line",
      source: "walked",
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#b5120c", "line-width": 2.2, "line-opacity": 0.55 },
    });
    const bounds = new maplibregl.LngLatBounds();
    for (const feature of tracks.features) for (const point of feature.geometry.coordinates) bounds.extend(point);
    map.fitBounds(bounds, { padding: 40, animate: false, maxZoom: 13 });

    // A click on a line opens its tour.
    map.on("click", "walked-glow", (event) => {
      const tour = event.features[0].properties;
      const link = document.createElement("a");
      link.href = data.tourUrl.replace("00000000-0000-0000-0000-000000000000", tour.tour_id);
      link.textContent = tour.date ? `${tour.title} (${tour.date.split("-").reverse().join(".")})` : tour.title;
      new maplibregl.Popup().setLngLat(event.lngLat).setDOMContent(link).addTo(map);
    });
    map.on("mouseenter", "walked-glow", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "walked-glow", () => (map.getCanvas().style.cursor = ""));
  });
})();
