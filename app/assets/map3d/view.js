// The 3D view of the app: the map of the web frontend's library in a WebView, lifted by
// the elevation data. Everything comes from the map server inside the app (same origin),
// so it also works without network for what the device has. View only: turn, tilt, zoom.
(async () => {
  const note = document.getElementById("note");
  const fail = (text) => {
    note.textContent = text;
    note.hidden = false;
  };
  let scene;
  try {
    scene = await (await fetch("scene.json")).json();
  } catch (_error) {
    fail("Die 3D-Ansicht konnte nicht geladen werden.");
    return;
  }
  const probe = document.createElement("canvas");
  if (!window.maplibregl || !(probe.getContext("webgl2") || probe.getContext("webgl"))) {
    fail(scene.texts.unsupported);
    return;
  }
  maplibregl.setWorkerUrl(new URL("maplibre-gl-csp-worker.js", window.location.href).href);
  const map = new maplibregl.Map({
    container: "map",
    style: scene.style,
    center: scene.center,
    zoom: scene.zoom,
    bearing: scene.bearing || 0,
    pitch: 60,
    maxPitch: 80,
    attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  map.on("error", (event) => {
    // A missing tile is no reason to give up; a map that cannot start is.
    if (!map.loaded() && event.error && /webgl/i.test(String(event.error.message))) fail(scene.texts.unsupported);
  });

  map.on("load", () => {
    // The layers as they were switched in the app.
    for (const [layer, visible] of Object.entries(scene.visible || {})) {
      if (map.getLayer(layer)) map.setLayoutProperty(layer, "visibility", visible ? "visible" : "none");
    }
    for (const [layer, opacity] of Object.entries(scene.opacity || {})) {
      if (map.getLayer(layer)) map.setPaintProperty(layer, "raster-opacity", opacity);
    }
    if (scene.terrain && map.getSource(scene.terrain.source)) map.setTerrain(scene.terrain);

    // Rain radar and clouds over the terrain, with a slider for their time. It starts
    // at the time that was chosen in the app.
    const radar = scene.radar;
    if (radar && radar.times.length) {
      const slider = document.getElementById("time");
      const clock = document.getElementById("clock");
      const play = document.getElementById("play");
      const show = (index) => {
        const time = radar.times[index];
        clock.textContent = new Date(time * 1000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
        for (const layer of radar.layers) {
          const id = `radar-${layer.kind}`;
          // The image of that kind closest before the chosen time.
          const known = layer.frames.filter((frame) => frame <= time);
          if (!known.length) {
            if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", "none");
            continue;
          }
          const tiles = [layer.tiles.replace("{time}", known[known.length - 1])];
          if (map.getSource(id)) {
            map.getSource(id).setTiles(tiles);
            map.setLayoutProperty(id, "visibility", "visible");
          } else {
            map.addSource(id, { type: "raster", tiles, tileSize: 256, maxzoom: layer.maxzoom });
            map.addLayer({
              id,
              type: "raster",
              source: id,
              paint: { "raster-opacity": layer.opacity, "raster-fade-duration": 0 },
            });
          }
        }
      };
      slider.max = radar.times.length - 1;
      slider.value = radar.index;
      slider.addEventListener("input", () => show(Number(slider.value)));
      let timer = null;
      play.addEventListener("click", () => {
        if (timer) {
          clearInterval(timer);
          timer = null;
          play.textContent = "▶";
          return;
        }
        play.textContent = "⏸";
        timer = setInterval(() => {
          slider.value = (Number(slider.value) + 1) % radar.times.length;
          show(Number(slider.value));
        }, 900);
      });
      show(radar.index);
      document.getElementById("radar").hidden = false;
    }

    const track = scene.track || [];
    if (track.length > 1) {
      map.addSource("track", {
        type: "geojson",
        data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: track } },
      });
      const layout = { "line-join": "round", "line-cap": "round" };
      map.addLayer({ id: "track-casing", type: "line", source: "track", layout, paint: { "line-color": "#ffffff", "line-width": 7 } });
      map.addLayer({ id: "track-line", type: "line", source: "track", layout, paint: { "line-color": "#E8731A", "line-width": 4 } });
    }
    const second = scene.secondTrack || [];
    if (second.length > 1) {
      // The line to compare with, e.g. what was walked over what was planned.
      map.addSource("second", {
        type: "geojson",
        data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: second } },
      });
      map.addLayer({
        id: "second-line",
        type: "line",
        source: "second",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": "#1565C0", "line-width": 3 },
      });
    }
    for (const point of scene.points || []) {
      const element = document.createElement("div");
      element.className = point.found ? "dot found" : "dot";
      new maplibregl.Marker({ element }).setLngLat([point.lon, point.lat]).addTo(map);
    }
  });
})();
