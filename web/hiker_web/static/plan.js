// Route planner: waypoints are set on the map; the server connects them along paths or as
// straight lines and returns the line with its key figures.
(() => {
  const holder = document.getElementById("plan-data");
  const mapElement = document.getElementById("map");
  if (!holder || !mapElement || !window.maplibregl) return;
  const data = JSON.parse(holder.textContent);
  const texts = data.texts;
  const form = document.getElementById("plan-form");
  const field = document.getElementById("plan-waypoints");
  const profile = document.getElementById("plan-profile");
  const difficulty = document.getElementById("plan-difficulty");
  const ferrata = document.getElementById("plan-ferrata");
  const list = document.getElementById("plan-list");
  const empty = document.getElementById("plan-empty");
  const message = document.getElementById("plan-message");
  const stats = document.getElementById("plan-stats");
  const note = document.getElementById("plan-duration-note");
  const save = document.getElementById("plan-save");
  const box = document.getElementById("profile-box");
  const number = (value, digits = 0) =>
    value.toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });

  let waypoints = (data.route.waypoints || []).map((point) => ({
    lat: point.lat,
    lon: point.lon,
    name: point.name || "",
    direct: Boolean(point.direct),
  }));
  let line = [];
  let chart = null;
  let request = 0;

  // --- Map ---
  maplibregl.setWorkerUrl(data.workerUrl);
  const tileUrl = data.tileUrl.startsWith("/") ? window.location.origin + data.tileUrl : data.tileUrl;
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
    // Without a route yet: the Alps.
    center: waypoints.length ? [waypoints[0].lon, waypoints[0].lat] : [9.5, 46.8],
    zoom: waypoints.length ? 12 : 6,
  });
  map.addControl(new maplibregl.NavigationControl(), "top-right");
  map.getCanvas().style.cursor = "crosshair";
  const lineData = () => ({
    type: "Feature",
    properties: {},
    geometry: { type: "LineString", coordinates: line },
  });
  const loaded = new Promise((resolve) => map.on("load", resolve));
  loaded.then(() => {
    map.addSource("route", { type: "geojson", data: lineData() });
    map.addLayer({
      id: "route-casing",
      type: "line",
      source: "route",
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#ffffff", "line-width": 7 },
    });
    map.addLayer({
      id: "route",
      type: "line",
      source: "route",
      layout: { "line-join": "round", "line-cap": "round" },
      paint: { "line-color": "#c62828", "line-width": 4 },
    });
  });
  const drawLine = () => loaded.then(() => map.getSource("route").setData(lineData()));

  const walker = document.createElement("div");
  walker.className = "walk-marker";
  const position = new maplibregl.Marker({ element: walker });

  // --- Line and key figures from the server ---
  const duration = (seconds) => {
    const minutes = Math.round(seconds / 60);
    const hours = Math.floor(minutes / 60);
    return hours ? `${hours} h ${String(minutes % 60).padStart(2, "0")} min` : `${minutes} min`;
  };
  const say = (text, isError) => {
    message.hidden = !text;
    message.textContent = text || "";
    message.classList.toggle("error", Boolean(isError));
  };
  const showResult = (result) => {
    const series = result && result.series;
    line = series ? series.lat.map((lat, index) => [series.lon[index], lat]) : [];
    drawLine();
    if (chart) chart.destroy();
    chart = null;
    position.remove();
    stats.hidden = !series;
    note.hidden = !series;
    box.hidden = true;
    if (!series) return;
    const set = (name, text) => {
      stats.querySelector(`[data-stat="${name}"]`).textContent = text;
    };
    const meters = (value) => (value == null ? "–" : `${number(value)} m`);
    set("distance", `${number(result.distance_m / 1000, 1)} km`);
    set("ascent", meters(result.ascent_m));
    set("descent", meters(result.descent_m));
    set("duration", duration(result.duration_s));
    chart = window.hikerProfile({
      box,
      series,
      texts,
      onShow: (index, follow) => {
        position.setLngLat(line[index]).addTo(map);
        if (follow && !map.getBounds().contains(line[index])) map.panTo(line[index], { duration: 300 });
      },
      onHide: () => position.remove(),
    });
  };

  const compute = async () => {
    const current = ++request;
    save.disabled = waypoints.length < 2;
    if (waypoints.length < 2) {
      say("");
      showResult(null);
      return;
    }
    say(texts.computing);
    let response;
    try {
      response = await fetch(data.previewUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": form.elements.csrf_token.value },
        body: JSON.stringify({
          profile: profile.value,
          max_difficulty: Number(difficulty.value),
          via_ferrata: ferrata.checked,
          waypoints: waypoints.map((point) => ({
            lat: point.lat,
            lon: point.lon,
            name: point.name || null,
            direct: point.direct,
          })),
        }),
      });
    } catch (_error) {
      response = null;
    }
    // A newer change is already on its way: this answer is outdated.
    if (current !== request) return;
    if (!response || !response.ok) {
      let code = "";
      try {
        code = (await response.json()).error;
      } catch (_error) {
        code = "";
      }
      say(texts[code] || texts.failed, true);
      showResult(null);
      return;
    }
    say("");
    showResult(await response.json());
  };

  // --- Waypoints: markers on the map and rows in the list ---
  let markers = [];
  const changed = (recompute = true) => {
    field.value = JSON.stringify(waypoints);
    render();
    if (recompute) compute();
  };
  const label = (index) => (index === 0 ? "S" : String(index + 1));

  const render = () => {
    for (const marker of markers) marker.remove();
    markers = waypoints.map((point, index) => {
      const element = document.createElement("div");
      element.className = "dot-marker plan-point";
      element.textContent = label(index);
      const marker = new maplibregl.Marker({ element, draggable: true })
        .setLngLat([point.lon, point.lat])
        .addTo(map);
      marker.on("dragend", () => {
        const moved = marker.getLngLat();
        point.lat = Number(moved.lat.toFixed(6));
        point.lon = Number(moved.lng.toFixed(6));
        changed();
      });
      // A click on a point must not set a new one beneath it.
      element.addEventListener("click", (event) => event.stopPropagation());
      return marker;
    });

    empty.hidden = waypoints.length > 0;
    list.replaceChildren(
      ...waypoints.map((point, index) => {
        const row = document.createElement("li");
        const badge = document.createElement("span");
        badge.className = "chip";
        badge.textContent = index === 0 ? texts.start : label(index);
        const name = document.createElement("input");
        name.value = point.name;
        name.maxLength = 200;
        name.placeholder = texts.name;
        name.setAttribute("aria-label", `${texts.name} ${label(index)}`);
        name.className = "grow";
        // A name does not change the course: no new computation.
        name.addEventListener("change", () => {
          point.name = name.value.trim();
          field.value = JSON.stringify(waypoints);
        });
        row.append(badge, name);
        if (index > 0) {
          const direct = document.createElement("label");
          const box = document.createElement("input");
          box.type = "checkbox";
          box.checked = point.direct;
          box.addEventListener("change", () => {
            point.direct = box.checked;
            changed();
          });
          direct.append(box, ` ${texts.direct}`);
          row.append(direct);
        }
        const remove = document.createElement("button");
        remove.type = "button";
        remove.textContent = texts.remove;
        remove.addEventListener("click", () => {
          waypoints.splice(index, 1);
          changed();
        });
        row.append(remove);
        return row;
      }),
    );
  };

  map.on("click", (event) => {
    if (waypoints.length >= data.maxWaypoints) {
      say(texts.too_many, true);
      return;
    }
    waypoints.push({
      lat: Number(event.lngLat.lat.toFixed(6)),
      lon: Number(event.lngLat.lng.toFixed(6)),
      name: "",
      direct: false,
    });
    changed();
  });
  document.getElementById("plan-undo").addEventListener("click", () => {
    waypoints.pop();
    changed();
  });
  document.getElementById("plan-reverse").addEventListener("click", () => {
    // The mark for a straight leg belongs to the leg, so it moves to its other end.
    const marks = waypoints.map((point) => point.direct);
    waypoints.reverse();
    waypoints.forEach((point, index) => {
      point.direct = index > 0 && marks[waypoints.length - index];
    });
    changed();
  });
  document.getElementById("plan-clear").addEventListener("click", () => {
    waypoints = [];
    changed();
  });
  for (const control of [profile, difficulty, ferrata]) control.addEventListener("change", () => compute());
  // Enter in a name field must not send the whole form by accident.
  list.addEventListener("keydown", (event) => {
    if (event.key === "Enter") event.preventDefault();
  });

  // --- Start: a stored route shows its line without asking the server again ---
  save.disabled = waypoints.length < 2;
  render();
  if (data.route.series) {
    showResult(data.route);
    const bounds = line.reduce(
      (area, coordinates) => area.extend(coordinates),
      new maplibregl.LngLatBounds(line[0], line[0]),
    );
    map.fitBounds(bounds, { padding: 50, animate: false, maxZoom: 15 });
  } else if (waypoints.length >= 2) {
    compute();
  }
})();
