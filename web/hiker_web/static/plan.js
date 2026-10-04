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
  // The fields for paths and pace live in a drop-down on the map; they are taken out of
  // their template now, so that the form has them even before the map has loaded.
  const fields = document.getElementById("plan-difficulty-fields").content.firstElementChild;
  // Until the map shows them they wait unseen in the form, so that saving never loses them.
  const parked = document.createElement("div");
  parked.hidden = true;
  parked.append(fields);
  form.append(parked);
  const inFields = (id) => fields.querySelector(`#${id}`);
  const profile = inFields("plan-profile");
  const difficulty = inFields("plan-difficulty");
  const ferrata = inFields("plan-ferrata");
  const pace = inFields("plan-pace");
  const paceValues = {
    ascent: inFields("plan-pace-ascent"),
    descent: inFields("plan-pace-descent"),
    distance: inFields("plan-pace-distance"),
  };
  const paceName = inFields("plan-pace-name");
  const paceNew = inFields("plan-pace-new");
  const paceStore = inFields("plan-pace-store");
  const paceDelete = inFields("plan-pace-delete");
  const start = document.getElementById("plan-start");
  const startUtc = document.getElementById("plan-start-utc");
  const sun = document.getElementById("plan-sun");
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
    center: waypoints.length ? [waypoints[0].lon, waypoints[0].lat] : (data.view || {}).center || [9.5, 46.8],
    zoom: waypoints.length ? 12 : (data.view || {}).zoom || 6,
  });
  map.addControl(new maplibregl.NavigationControl(), "top-right");
  const ownGroup = { title: texts.difficulty, build: (panel) => panel.append(fields) };
  if (window.hikerMapLayers) window.hikerMapLayers(map, data.layerTexts, { groups: [ownGroup] });
  // The map fills what the window leaves; it follows when that changes.
  new ResizeObserver(() => map.resize()).observe(mapElement);
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
  const clock = (moment) =>
    new Date(moment).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  const fill = (text, values) => text.replace(/\{(\w+)\}/g, (_match, key) => values[key]);
  const directions = ["Norden", "Nordosten", "Osten", "Südosten", "Süden", "Südwesten", "Westen", "Nordwesten"];
  const showSun = (report) => {
    sun.hidden = !report;
    if (!report) return;
    const rows = [];
    const timed = [];
    const row = (label, value, warn) => {
      const line = document.createElement("div");
      if (warn) line.className = "warn";
      line.textContent = value == null ? label : `${label}: ${value}`;
      rows.push(line);
      return line;
    };
    // The moments of the day in the order they happen.
    const at = (moment, label, value) => timed.push([Date.parse(moment), label, value || clock(moment)]);
    if (report.sunrise) at(report.sunrise, texts.sunrise);
    if (report.summit) {
      const summit = report.summit;
      const where = fill(texts.sun_at_summit, {
        height: number(summit.sun_height_deg),
        direction: directions[Math.round(summit.sun_direction_deg / 45) % 8],
      });
      const label = fill(texts.summit, { elevation: number(summit.elevation_m) });
      // Below the horizon the direction of the sun says nothing.
      at(summit.time, label, summit.sun_height_deg > 0 ? `${clock(summit.time)} – ${where}` : null);
    }
    at(report.end_time, texts.end);
    if (report.sunset) at(report.sunset, texts.sunset);
    for (const [, label, value] of timed.sort((a, b) => a[0] - b[0])) row(label, value);
    if (report.daylight_left_s != null) {
      const left = report.daylight_left_s;
      if (left >= 0) row(fill(texts.daylight_left, { time: duration(left) }));
      else row(fill(texts.after_sunset, { time: duration(-left) }), null, true);
    }
    if (report.starts_in_dark) row(texts.starts_in_dark, null, true);
    if (report.ends_in_dark) row(texts.ends_in_dark, null, true);
    sun.replaceChildren(...rows);
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
    showSun(result && result.sun);
    if (!series) return;
    note.textContent = fill(texts.duration_note, {
      ascent: number(Number(paceValues.ascent.value)),
      descent: number(Number(paceValues.descent.value)),
      distance: number(Number(paceValues.distance.value), 1),
    });
    // With a start the profile shows the time of day at every point.
    const began = startUtc.value ? Date.parse(startUtc.value) : null;
    const shown =
      began && series.time_s ? { ...series, time: series.time_s.map((seconds) => began + seconds * 1000) } : series;
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
      series: shown,
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
          pace: paceBody(),
          start_time: startUtc.value || null,
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

  // --- Pace for the walking time: built in, own values, or one saved under a name ---
  const saved = () => (pace.value.startsWith("saved:") ? pace.value.slice(6) : null);
  const paceBody = () => {
    if (pace.value !== "custom" && !saved()) return { preset: pace.value };
    return {
      preset: "custom",
      name: paceName.value || null,
      ascent_m_per_h: Number(paceValues.ascent.value),
      descent_m_per_h: Number(paceValues.descent.value),
      distance_km_per_h: Number(paceValues.distance.value),
    };
  };
  const paceChosen = () => {
    const chosen = pace.selectedOptions[0];
    const own = pace.value === "custom";
    // Built-in and saved paces bring their values; only "Individuell" is typed in.
    if (!own) {
      paceValues.ascent.value = chosen.dataset.ascent;
      paceValues.descent.value = chosen.dataset.descent;
      paceValues.distance.value = chosen.dataset.distance;
    }
    for (const input of Object.values(paceValues)) input.readOnly = !own;
    paceName.value = saved() ? chosen.dataset.name : "";
    paceNew.hidden = !own;
    paceStore.hidden = !own;
    paceDelete.hidden = !saved();
  };
  const send = (address, body) =>
    fetch(address, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": form.elements.csrf_token.value },
      body: JSON.stringify(body),
    });
  // A route that uses a saved pace carries its name: show that entry as chosen.
  if (pace.value === "custom" && paceName.value) {
    const known = [...pace.options].find((entry) => entry.dataset.name === paceName.value);
    if (known) pace.value = known.value;
  }
  paceChosen();
  pace.addEventListener("change", () => {
    paceChosen();
    compute();
  });
  for (const input of Object.values(paceValues)) input.addEventListener("change", () => compute());
  paceStore.addEventListener("click", async () => {
    const name = paceNew.value.trim();
    if (!name) {
      say(texts.pace_name_missing, true);
      return;
    }
    let response = null;
    try {
      // A name stands for one pace: saving it again replaces the earlier one.
      const earlier = [...pace.options].find((entry) => entry.dataset.name === name);
      if (earlier) {
        await send(`${data.pacesUrl}/${earlier.value.slice(6)}/delete`, {});
        earlier.remove();
      }
      response = await send(data.pacesUrl, { ...paceBody(), preset: undefined, name });
    } catch (_error) {
      response = null;
    }
    if (!response || !response.ok) {
      say(texts.pace_failed, true);
      return;
    }
    const stored = await response.json();
    const entry = new Option(stored.name, `saved:${stored.id}`);
    entry.dataset.name = stored.name;
    entry.dataset.ascent = Math.round(stored.ascent_m_per_h);
    entry.dataset.descent = Math.round(stored.descent_m_per_h);
    entry.dataset.distance = stored.distance_km_per_h;
    pace.add(entry);
    pace.value = entry.value;
    paceNew.value = "";
    say("");
    paceChosen();
  });
  paceDelete.addEventListener("click", async () => {
    const id = saved();
    if (!id) return;
    try {
      await send(`${data.pacesUrl}/${id}/delete`, {});
    } catch (_error) {
      return;
    }
    // The route keeps the values; only the saved entry is gone.
    pace.selectedOptions[0].remove();
    pace.value = "custom";
    paceChosen();
  });

  // --- Start: local time in the field, UTC for the server ---
  const pad = (value) => String(value).padStart(2, "0");
  if (startUtc.value) {
    const moment = new Date(startUtc.value);
    start.value =
      `${moment.getFullYear()}-${pad(moment.getMonth() + 1)}-${pad(moment.getDate())}` +
      `T${pad(moment.getHours())}:${pad(moment.getMinutes())}`;
  }
  start.addEventListener("change", () => {
    startUtc.value = start.value ? new Date(start.value).toISOString() : "";
    compute();
  });

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
  for (const holder of [list, fields]) {
    holder.addEventListener("keydown", (event) => {
      if (event.key === "Enter") event.preventDefault();
    });
  }
  // For looking at the map from outside, e.g. when checking the page.
  window.hikerMap = map;

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
