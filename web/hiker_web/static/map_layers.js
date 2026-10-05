// The controls of the map: small drop-down fields at its top edge.
//   "Ebenen":      overlays (slope with its angles, snow, avalanche danger, weather), the
//                  day they show, rain radar and clouds with their time
//   "Darstellung": drawn map, winter or aerial image, and what the colours of the paths mean
//   further fields a page adds itself (the planner: "Schwierigkeit")
//   a button that switches between 2D and 3D
// Which choices exist is written in the style of the server (metadata.hiker), so that web
// and app offer the same. A map of raster tiles only has no layer fields.
window.hikerMapLayers = (map, texts, options = {}) => {
  const stored = (key, fallback) => {
    try {
      return window.localStorage.getItem(`hiker-map-${key}`) || fallback;
    } catch (_error) {
      return fallback;
    }
  };
  const remember = (key, value) => {
    try {
      window.localStorage.setItem(`hiker-map-${key}`, value);
    } catch (_error) {
      // Private mode: the choice lasts for this page only.
    }
  };
  const show = (layer, visible) => {
    if (map.getLayer(layer)) map.setLayoutProperty(layer, "visibility", visible ? "visible" : "none");
  };
  const element = (name, className, text) => {
    const node = document.createElement(name);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  };
  const withQuery = (address, query) => (query ? `${address}${address.includes("?") ? "&" : "?"}${query}` : address);

  const bar = element("div", "maplibregl-ctrl map-bar");
  // Clicks in the controls must not set points on the map beneath them.
  for (const name of ["click", "dblclick", "mousedown", "touchstart", "wheel"]) {
    bar.addEventListener(name, (event) => event.stopPropagation());
  }
  const panels = [];
  const dropdown = (title) => {
    const holder = element("div", "map-drop");
    const button = element("button", "map-drop-button", `${title} ▾`);
    button.type = "button";
    button.setAttribute("aria-expanded", "false");
    const panel = element("div", "map-drop-panel");
    panel.hidden = true;
    button.addEventListener("click", () => {
      const open = panel.hidden;
      // One field at a time: opening one closes the others.
      for (const other of panels) {
        other.panel.hidden = true;
        other.button.setAttribute("aria-expanded", "false");
      }
      panel.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
    });
    panels.push({ panel, button });
    holder.append(button, panel);
    bar.append(holder);
    return panel;
  };
  const option = (panel, type, name, value, label, checked, onChange) => {
    const row = element("label", "map-option");
    const input = element("input");
    input.type = type;
    input.name = name;
    input.value = value;
    input.checked = checked;
    input.addEventListener("change", () => onChange(input.checked));
    row.append(input, ` ${label}`);
    panel.append(row);
    return row;
  };
  const note = (panel, text) => {
    if (text) panel.append(element("small", "", text));
  };

  map.once("load", () => {
    const style = map.getStyle();
    const meta = (style.metadata || {}).hiker;
    const original = style.sources;

    if (meta) {
      // --- Ebenen ---
      const layers = dropdown(texts.title);
      let slopeQuery = "";
      let day = "";
      const applySources = () => {
        // The tiles of a source are asked for again with the chosen angles and day.
        const dated = new Set((meta.history || {}).sources || []);
        for (const [name, source] of Object.entries(original)) {
          const query = [name === "slope" ? slopeQuery : "", dated.has(name) && day ? `date=${day}` : ""]
            .filter(Boolean)
            .join("&");
          const live = map.getSource(name);
          if (!live || (name !== "slope" && !dated.has(name))) continue;
          if (source.tiles && live.setTiles) live.setTiles(source.tiles.map((tile) => withQuery(tile, query)));
          if (typeof source.data === "string" && live.setData) live.setData(withQuery(source.data, query));
        }
      };

      let group = null;
      for (const overlay of meta.overlays) {
        // The overlays come in groups: the ground, snow and avalanches, the weather.
        if (overlay.group && overlay.group !== group) {
          group = overlay.group;
          layers.append(element("strong", "map-group", (texts.group || {})[group] || group));
        }
        const on = stored(`overlay-${overlay.id}`, "off") === "on";
        const apply = (visible) => {
          for (const layer of overlay.layers) show(layer, visible);
          remember(`overlay-${overlay.id}`, visible ? "on" : "off");
        };
        const row = option(layers, "checkbox", "", overlay.id, texts.overlay[overlay.id] || overlay.id, on, apply);
        if (overlay.legend) {
          const legend = element("span", "map-legend");
          for (const entry of overlay.legend) {
            const swatch = element("i");
            swatch.style.background = entry.color;
            // Slope classes name their angle, danger levels their number.
            legend.append(swatch, entry.from != null ? `${entry.from}°` : String(entry.level));
          }
          row.append(legend);
        }
        if (overlay.opacity) {
          // How much of the map shines through, e.g. through the aerial image.
          const opacity = overlay.opacity;
          const box = element("div", "map-range");
          const input = element("input");
          input.type = "range";
          input.min = Math.round(opacity.min * 100);
          input.max = 100;
          input.step = 5;
          input.value = stored(`opacity-${overlay.id}`, String(Math.round(opacity.default * 100)));
          input.setAttribute("aria-label", texts.opacity);
          const label = element("span");
          const update = () => {
            label.textContent = `${texts.opacity}: ${input.value} %`;
            remember(`opacity-${overlay.id}`, input.value);
            if (map.getLayer(opacity.layer)) {
              map.setPaintProperty(opacity.layer, "raster-opacity", Number(input.value) / 100);
            }
          };
          input.addEventListener("input", update);
          box.append(input, label);
          layers.append(box);
          update();
        }
        if (overlay.range) {
          // One slider with two handles: from which angle and up to which angle slopes
          // are coloured. Two inputs share one track; only their handles take the pointer.
          const range = overlay.range;
          const box = element("div", "map-range");
          const track = element("div", "map-dual");
          const fill = element("div", "map-dual-fill");
          const top = 90;
          const slider = (key, start) => {
            const input = element("input");
            input.type = "range";
            input.min = range.min;
            input.max = top;
            input.step = range.step;
            input.value = stored(`slope-${key}`, String(start));
            input.setAttribute("aria-label", texts.slope[key]);
            return input;
          };
          const low = slider("low", range.low);
          const high = slider("high", range.high);
          const label = element("span");
          const show = (changed) => {
            // The ends never cross: the one that was moved pushes the other.
            if (Number(low.value) >= Number(high.value)) {
              if (changed === low) high.value = String(Math.min(top, Number(low.value) + range.step));
              else low.value = String(Math.max(range.min, Number(high.value) - range.step));
              if (Number(low.value) >= Number(high.value)) low.value = String(Number(high.value) - range.step);
            }
            const share = (value) => ((Number(value) - range.min) / (top - range.min)) * 100;
            fill.style.left = `${share(low.value)}%`;
            fill.style.right = `${100 - share(high.value)}%`;
            const end = Number(high.value) >= top ? texts.slope.open : `${high.value}°`;
            label.textContent = `${low.value}° – ${end}`;
          };
          const update = (changed) => {
            show(changed);
            remember("slope-low", low.value);
            remember("slope-high", high.value);
            const usual = Number(low.value) === range.low && Number(high.value) >= top;
            slopeQuery = usual ? "" : `low=${low.value}&high=${Math.min(top, Number(high.value))}`;
            applySources();
          };
          for (const input of [low, high]) {
            // While dragging only the picture of the slider follows; the tiles are asked
            // for anew when the handle is let go.
            input.addEventListener("input", () => show(input));
            input.addEventListener("change", () => update(input));
          }
          track.append(fill, low, high);
          box.append(track, label);
          layers.append(box);
          update(null);
        }
        note(layers, (texts.note || {})[overlay.id]);
        apply(on);
      }

      // --- Rain radar and clouds with their time ---
      if (meta.radar) {
        // Radar and clouds belong to the weather, the last group of the overlays.
        if (group !== "weather") layers.append(element("hr"));
        const radar = meta.radar;
        const state = { rain: false, clouds: false, frames: null, index: 0, timer: null };
        const controls = element("div", "map-radar");
        controls.hidden = true;
        const slider = element("input");
        slider.type = "range";
        slider.min = 0;
        slider.step = 1;
        const clock = element("span");
        const play = element("button", "", "▶");
        play.type = "button";
        play.setAttribute("aria-label", texts.radar.play);
        const kinds = {
          rain: { maxzoom: radar.rain_max_zoom, opacity: 0.75 },
          clouds: { maxzoom: radar.clouds_max_zoom, opacity: 0.55 },
        };
        const draw = () => {
          if (!state.frames) return;
          const time = state.frames.times[state.index];
          clock.textContent = new Date(time * 1000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
          for (const kind of ["clouds", "rain"]) {
            const id = `radar-${kind}`;
            // The image of that kind closest before the chosen time.
            const known = state.frames[kind].filter((frame) => frame <= time);
            const frame = known.length ? known[known.length - 1] : null;
            if (!state[kind] || frame == null) {
              if (map.getLayer(id)) show(id, false);
              continue;
            }
            const tiles = [radar[kind].replace("{time}", frame)];
            if (map.getSource(id)) {
              map.getSource(id).setTiles(tiles);
            } else {
              map.addSource(id, {
                type: "raster",
                tiles,
                tileSize: 256,
                maxzoom: kinds[kind].maxzoom,
                attribution: radar.attribution,
              });
              map.addLayer(
                { id, type: "raster", source: id, paint: { "raster-opacity": kinds[kind].opacity, "raster-fade-duration": 0 } },
                map.getLayer("tunnel") ? "tunnel" : undefined,
              );
            }
            show(id, true);
          }
        };
        const load = async () => {
          try {
            const response = await fetch(radar.frames);
            const frames = await response.json();
            const times = [...new Set([...frames.rain, ...frames.clouds])].sort((a, b) => a - b);
            state.frames = { rain: frames.rain, clouds: frames.clouds, times };
            slider.max = Math.max(0, times.length - 1);
            state.index = times.length - 1;
            slider.value = state.index;
          } catch (_error) {
            state.frames = { rain: [], clouds: [], times: [] };
          }
          draw();
        };
        const toggle = (kind) => async (on) => {
          state[kind] = on;
          controls.hidden = !(state.rain || state.clouds);
          if (!state.frames) await load();
          else draw();
          if (controls.hidden && state.timer) play.click();
        };
        option(layers, "checkbox", "", "rain", texts.radar.rain, false, toggle("rain"));
        option(layers, "checkbox", "", "clouds", texts.radar.clouds, false, toggle("clouds"));
        slider.addEventListener("input", () => {
          state.index = Number(slider.value);
          draw();
        });
        play.addEventListener("click", () => {
          if (state.timer) {
            clearInterval(state.timer);
            state.timer = null;
            play.textContent = "▶";
            return;
          }
          play.textContent = "⏸";
          state.timer = setInterval(() => {
            if (!state.frames || !state.frames.times.length) return;
            state.index = (state.index + 1) % state.frames.times.length;
            slider.value = state.index;
            draw();
          }, 700);
        });
        controls.append(play, slider, clock);
        layers.append(controls);
        note(layers, texts.radar.note);
      }

      // --- A day in the past for the layers that have a history ---
      if (meta.history) {
        layers.append(element("hr"));
        const row = element("label", "map-option");
        const input = element("input");
        input.type = "date";
        const today = new Date();
        const iso = (date) => date.toISOString().slice(0, 10);
        input.max = iso(today);
        input.min = iso(new Date(today.getTime() - meta.history.days * 86400000));
        input.addEventListener("change", () => {
          day = input.value && input.value < iso(new Date()) ? input.value : "";
          applySources();
        });
        const reset = element("button", "link", texts.history.today);
        reset.type = "button";
        reset.addEventListener("click", () => {
          input.value = "";
          day = "";
          applySources();
        });
        row.append(`${texts.history.label} `, input, reset);
        layers.append(row);
        note(layers, texts.history.note);
      }

      // --- Darstellung ---
      const looks = dropdown(texts.looks);
      const setBase = (id) => {
        const chosen = meta.bases.find((base) => base.id === id) || meta.bases[0];
        for (const base of meta.bases) {
          for (const layer of base.show) show(layer, base === chosen);
          for (const layer of base.hide) show(layer, true);
        }
        for (const layer of chosen.hide) show(layer, false);
        remember("base", chosen.id);
      };
      const current = stored("base", meta.bases[0].id);
      for (const base of meta.bases) {
        option(looks, "radio", "map-base", base.id, texts.base[base.id] || base.id, base.id === current, () =>
          setBase(base.id),
        );
      }
      setBase(current);
      if (meta.bases.length > 3) note(looks, texts.looksNote);
      if (meta.legend && meta.legend.length) {
        looks.append(element("hr"));
        const legend = element("div", "map-legend paths");
        legend.append(`${texts.paths} `);
        for (const entry of meta.legend) {
          const swatch = element("i");
          swatch.style.background = entry.color;
          // Via ferratas are drawn with cross strokes: the sample shows them too.
          if (entry.pattern === "rungs") swatch.className = "rungs";
          legend.append(swatch, entry.label);
        }
        looks.append(legend);
        note(looks, texts.pathsNote);
      }
    }

    // --- Search for places of the own map ---
    if (meta && texts.search) {
      const search = texts.search;
      const holder = element("div", "map-drop map-search");
      const input = element("input");
      input.type = "search";
      input.placeholder = search.label;
      input.setAttribute("aria-label", search.label);
      input.autocomplete = "off";
      const results = element("div", "map-drop-panel");
      results.hidden = true;
      let asked = 0;
      let timer = null;
      const pin = element("div", "dot-marker search-pin");
      const marker = new maplibregl.Marker({ element: pin });
      const go = (place) => {
        results.hidden = true;
        input.value = place.name;
        marker.setLngLat([place.lon, place.lat]).addTo(map);
        // Towns from further away, a summit or a hut from close by.
        const zoom = ["city", "town"].includes(place.kind) ? 12 : place.kind === "village" ? 13 : 14;
        map.flyTo({ center: [place.lon, place.lat], zoom, speed: 1.6 });
        if (options.onPlace) options.onPlace(place);
      };
      const show = (places) => {
        results.replaceChildren();
        if (!places.length) results.append(element("small", "", search.none));
        for (const place of places) {
          const button = element("button", "map-result");
          button.type = "button";
          const kind = search.kinds[place.kind] || search.kinds.other;
          const height = place.elevation_m != null ? `, ${Math.round(place.elevation_m).toLocaleString("de-DE")} m` : "";
          button.append(element("strong", "", place.name), element("span", "", `${kind}${height}`));
          button.addEventListener("click", () => go(place));
          results.append(button);
        }
        results.hidden = false;
      };
      const ask = async () => {
        const text = input.value.trim();
        const current = ++asked;
        if (text.length < 2) {
          results.hidden = true;
          return;
        }
        const center = map.getCenter();
        const query = `q=${encodeURIComponent(text)}&lat=${center.lat.toFixed(4)}&lon=${center.lng.toFixed(4)}&limit=8`;
        try {
          const response = await fetch(`${search.url}?${query}`);
          const places = response.ok ? await response.json() : [];
          // A newer search is already on its way.
          if (current === asked) show(places);
        } catch (_error) {
          if (current === asked) show([]);
        }
      };
      input.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(ask, 250);
      });
      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          // Enter takes the first result and never sends a form around the map.
          event.preventDefault();
          const first = results.querySelector("button");
          if (first && !results.hidden) first.click();
        } else if (event.key === "Escape") {
          results.hidden = true;
        }
      });
      holder.append(input, results);
      bar.append(holder);
    }

    // --- Fields of the page itself, e.g. the difficulty in the planner ---
    for (const group of options.groups || []) group.build(dropdown(group.title));

    // --- 2D / 3D: the map is lifted by the elevation data and tilted ---
    if (meta && meta.terrain && map.setTerrain) {
      const button = element("button", "map-drop-button map-3d", "3D");
      button.type = "button";
      button.title = texts.terrain;
      let on = false;
      button.addEventListener("click", () => {
        on = !on;
        map.setTerrain(on ? meta.terrain : null);
        map.easeTo({ pitch: on ? 60 : 0, duration: 600 });
        button.textContent = on ? "2D" : "3D";
        button.setAttribute("aria-pressed", String(on));
      });
      bar.append(button);
    }

    if (bar.children.length) map.addControl({ onAdd: () => bar, onRemove: () => bar.remove() }, "top-left");
  });
};
