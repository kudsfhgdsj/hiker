// Map mode: look at the map and look things up, without planning anything. A click names
// what lies there (summit, hut, path with its difficulty) and when the sun rises and sets.
(() => {
  const holder = document.getElementById("map-data");
  const mapElement = document.getElementById("map");
  if (!holder || !mapElement || !window.maplibregl) return;
  const data = JSON.parse(holder.textContent);
  const texts = data.texts;

  // Where the map was looked at last; the address of the page carries it too.
  const remembered = () => {
    const fromHash = window.location.hash.match(/^#(\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)$/);
    if (fromHash) return { zoom: Number(fromHash[1]), center: [Number(fromHash[3]), Number(fromHash[2])] };
    try {
      const view = JSON.parse(window.localStorage.getItem("hiker-map-view"));
      if (view && view.center) return view;
    } catch (_error) {
      // Nothing stored or private mode: the Alps.
    }
    return { zoom: 7, center: [10.5, 46.8] };
  };

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
    ...remembered(),
  });
  map.addControl(new maplibregl.NavigationControl(), "top-right");
  map.addControl(new maplibregl.ScaleControl(), "bottom-left");
  if (window.hikerMapLayers) window.hikerMapLayers(map, data.layerTexts);
  new ResizeObserver(() => map.resize()).observe(mapElement);
  window.hikerMap = map;

  map.on("moveend", () => {
    const center = map.getCenter();
    const view = { zoom: Number(map.getZoom().toFixed(2)), center: [Number(center.lng.toFixed(5)), Number(center.lat.toFixed(5))] };
    window.history.replaceState(null, "", `#${view.zoom}/${view.center[1]}/${view.center[0]}`);
    try {
      window.localStorage.setItem("hiker-map-view", JSON.stringify(view));
    } catch (_error) {
      // Private mode: the address still carries the view.
    }
  });

  const number = (value, digits = 0) =>
    value.toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  const clock = (moment) =>
    new Date(moment).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  const line = (text, className) => {
    const node = document.createElement("div");
    if (className) node.className = className;
    node.textContent = text;
    return node;
  };

  // What the map draws at the clicked place, named once each.
  const thingsAt = (point) => {
    const box = [
      [point.x - 6, point.y - 6],
      [point.x + 6, point.y + 6],
    ];
    const seen = new Set();
    const things = [];
    let summit = null;
    for (const feature of map.queryRenderedFeatures(box)) {
      const properties = feature.properties || {};
      const layer = feature.sourceLayer;
      let text = null;
      if (layer === "mountain_peak" && properties.name) {
        text = properties.ele ? `${properties.name}, ${number(Number(properties.ele))} m` : properties.name;
        if (properties.ele && !summit) summit = Number(properties.ele);
      } else if (layer === "hiking") {
        const grade = properties.highway === "via_ferrata" ? texts.via_ferrata : texts.sac[properties.sac_scale];
        if (grade) text = properties.name ? `${properties.name}: ${grade}` : grade;
      } else if (layer === "poi" && properties.name) {
        text = properties.name;
      } else if ((layer === "place" || layer === "water_name") && properties.name) {
        text = properties.name;
      }
      if (text && !seen.has(text)) {
        seen.add(text);
        things.push(text);
      }
    }
    return { things: things.slice(0, 6), summit };
  };

  let popup = null;
  let asked = 0;
  map.on("click", async (event) => {
    const current = ++asked;
    const { lat, lng } = event.lngLat;
    const { things, summit } = thingsAt(event.point);
    const content = document.createElement("div");
    content.className = "map-info";
    for (const [index, thing] of things.entries()) content.append(line(thing, index === 0 ? "name" : ""));
    content.append(line(`${number(lat, 5)}° N, ${number(lng, 5)}° O`, "meta"));
    const sun = line(texts.sun_loading, "meta");
    content.append(sun);
    const plan = document.createElement("a");
    plan.href = `${data.planUrl}?lat=${lat.toFixed(5)}&lon=${lng.toFixed(5)}&zoom=${Math.max(12, Math.round(map.getZoom()))}`;
    plan.textContent = texts.plan_here;
    if (data.planUrl) content.append(plan);
    if (popup) popup.remove();
    popup = new maplibregl.Popup({ maxWidth: "20rem" }).setLngLat(event.lngLat).setDOMContent(content).addTo(map);

    // Sunrise and sunset there today; for a summit also with its free view.
    const ask = async (elevation) => {
      const query = `lat=${lat.toFixed(5)}&lon=${lng.toFixed(5)}${elevation ? `&elevation_m=${elevation}` : ""}`;
      const response = await fetch(`${data.sunUrl}?${query}`);
      if (!response.ok) throw new Error("sun");
      return response.json();
    };
    try {
      const day = await ask(0);
      const free = summit ? await ask(summit) : null;
      if (current !== asked) return;
      const rows = [];
      if (!day.sunrise || !day.sunset) {
        rows.push(line(texts.sun_none));
      } else {
        rows.push(line(`${texts.sunrise}: ${clock(day.sunrise)} · ${texts.sunset}: ${clock(day.sunset)}`));
        if (free && free.sunrise && free.sunset) {
          rows.push(line(texts.sun_summit.replace("{rise}", clock(free.sunrise)).replace("{set}", clock(free.sunset)), "meta"));
        }
        if (day.dawn && day.dusk) {
          rows.push(line(texts.sun_light.replace("{dawn}", clock(day.dawn)).replace("{dusk}", clock(day.dusk)), "meta"));
        }
      }
      sun.replaceWith(...rows);
    } catch (_error) {
      if (current === asked) sun.remove();
    }
  });
})();
