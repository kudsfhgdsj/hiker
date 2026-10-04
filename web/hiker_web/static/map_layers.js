// The layer control of the map: base map or aerial image, overlays such as slope, and 2D/3D.
// Which choices exist is written in the style of the server (metadata.hiker), so that web
// and app offer the same. A map of raster tiles only has no control.
window.hikerMapLayers = (map, texts) => {
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

  map.once("load", () => {
    const meta = (map.getStyle().metadata || {}).hiker;
    if (!meta) return;
    const panel = document.createElement("div");
    panel.className = "map-layers-panel";
    panel.hidden = true;

    const option = (type, name, value, label, checked, onChange) => {
      const row = document.createElement("label");
      const input = document.createElement("input");
      input.type = type;
      input.name = name;
      input.value = value;
      input.checked = checked;
      input.addEventListener("change", () => onChange(input.checked));
      row.append(input, ` ${label}`);
      panel.append(row);
      return row;
    };

    // --- Base: the drawn map or an aerial image under paths and names ---
    const setBase = (id) => {
      const chosen = meta.bases.find((base) => base.id === id) || meta.bases[0];
      for (const base of meta.bases) {
        for (const layer of base.show) show(layer, base === chosen);
        for (const layer of base.hide) show(layer, true);
      }
      for (const layer of chosen.hide) show(layer, false);
      remember("base", chosen.id);
    };
    if (meta.bases.length > 1) {
      const current = stored("base", meta.bases[0].id);
      for (const base of meta.bases) {
        option("radio", "map-base", base.id, texts.base[base.id] || base.id, base.id === current, () =>
          setBase(base.id),
        );
      }
      setBase(current);
      panel.append(document.createElement("hr"));
    }

    // --- Overlays ---
    for (const overlay of meta.overlays) {
      const on = stored(`overlay-${overlay.id}`, "off") === "on";
      const apply = (visible) => {
        for (const layer of overlay.layers) show(layer, visible);
        remember(`overlay-${overlay.id}`, visible ? "on" : "off");
      };
      const row = option("checkbox", "", overlay.id, texts.overlay[overlay.id] || overlay.id, on, apply);
      if (overlay.legend) {
        const legend = document.createElement("span");
        legend.className = "map-legend";
        for (const entry of overlay.legend) {
          const swatch = document.createElement("i");
          swatch.style.background = entry.color;
          swatch.title = `${texts.from} ${entry.from}°`;
          legend.append(swatch, `${entry.from}°`);
        }
        row.append(legend);
      }
      apply(on);
    }

    // --- 2D / 3D: the map is lifted by the elevation data and tilted ---
    if (meta.terrain && map.setTerrain) {
      const apply = (on) => {
        map.setTerrain(on ? meta.terrain : null);
        map.easeTo({ pitch: on ? 60 : 0, duration: 600 });
      };
      option("checkbox", "", "3d", texts.terrain, false, apply);
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "map-layers-button";
    button.textContent = texts.title;
    button.setAttribute("aria-expanded", "false");
    button.addEventListener("click", () => {
      panel.hidden = !panel.hidden;
      button.setAttribute("aria-expanded", String(!panel.hidden));
    });
    const container = document.createElement("div");
    container.className = "maplibregl-ctrl map-layers";
    container.append(button, panel);
    // Clicks in the control must not set points on the map beneath it.
    for (const name of ["click", "dblclick", "mousedown", "touchstart"]) {
      container.addEventListener(name, (event) => event.stopPropagation());
    }
    map.addControl({ onAdd: () => container, onRemove: () => container.remove() }, "top-left");
  });
};
