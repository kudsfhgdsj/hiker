// Plan and walked track of a tour on one map: the plan in red, the track in blue.
(() => {
  const holder = document.getElementById("compare-data");
  const mapElement = document.getElementById("map");
  if (!holder || !mapElement || !window.maplibregl) return;
  const data = JSON.parse(holder.textContent);
  const coordinates = (series) => (series ? series.lat.map((lat, index) => [series.lon[index], lat]) : []);
  const plan = coordinates(data.plan);
  const track = coordinates(data.track);
  const all = [...plan, ...track];
  if (!all.length) return;

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
    center: all[0],
    zoom: 12,
  });
  map.addControl(new maplibregl.NavigationControl(), "top-right");
  if (window.hikerMapLayers) window.hikerMapLayers(map, data.layerTexts);
  const bounds = all.reduce((area, point) => area.extend(point), new maplibregl.LngLatBounds(all[0], all[0]));
  map.fitBounds(bounds, { padding: 50, animate: false, maxZoom: 15 });

  map.on("load", () => {
    const line = (id, points, color, width) => {
      if (points.length < 2) return;
      map.addSource(id, {
        type: "geojson",
        data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: points } },
      });
      map.addLayer({
        id: `${id}-casing`,
        type: "line",
        source: id,
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": "#ffffff", "line-width": width + 3 },
      });
      map.addLayer({
        id,
        type: "line",
        source: id,
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": color, "line-width": width },
      });
    };
    line("plan", plan, "#c62828", 4);
    // The walked track lies on top, a little thinner, so that the plan shows beneath it.
    line("track", track, "#1565c0", 3);
  });
})();
