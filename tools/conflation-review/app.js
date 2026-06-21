"use strict";

// ── Constants ────────────────────────────────────────────────────────────────

const DATA_URL =
  "../../cycling_network_conflation/toronto/output_files/combined_with_matches.geojson";

const COLORS = {
  autoMatched: "#3b82f6", // blue
  overrideExcluded: "#ef4444", // red
  overrideIncluded: "#2563eb", // darker blue (dashed)
  selected: "#000000", // black
  unmatched: "#f97316", // orange
  highlighted: "#facc15", // yellow
  municipalGrey: "#aaaaaa",
  osmGrey: "#cccccc",
};

// ── State ────────────────────────────────────────────────────────────────────

let map;
let municipalFeatures = []; // sorted array of GeoJSON features
let osmFeaturesById = {}; // osm_way_id → GeoJSON feature
let currentIndex = 0;
let highlightedOsmId = null;

// ── Utilities ────────────────────────────────────────────────────────────────

function parseIds(str) {
  if (!str) return [];
  return str
    .split(";")
    .map((s) => s.trim())
    .filter(Boolean);
}

function osmLabel(feature) {
  if (!feature) return "unknown";
  const tags = feature.properties.tags || {};
  return tags.name || tags.ref || null;
}

function osmSubLabel(feature) {
  if (!feature) return "";
  const tags = feature.properties.tags || {};
  const parts = [];
  if (tags.highway) parts.push(tags.highway);
  if (tags.cycleway) parts.push(`cycleway=${tags.cycleway}`);
  if (tags.bicycle) parts.push(`bicycle=${tags.bicycle}`);
  return parts.join(", ");
}

function featureBbox(geom) {
  const coords =
    geom.type === "LineString"
      ? geom.coordinates
      : geom.type === "MultiLineString"
        ? geom.coordinates.flat()
        : [];
  if (!coords.length) return null;
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity;
  for (const [x, y] of coords) {
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }
  return [minX, minY, maxX, maxY];
}

function unionBbox(bboxes) {
  const valid = bboxes.filter(Boolean);
  if (!valid.length) return null;
  return [
    Math.min(...valid.map((b) => b[0])),
    Math.min(...valid.map((b) => b[1])),
    Math.max(...valid.map((b) => b[2])),
    Math.max(...valid.map((b) => b[3])),
  ];
}

function isMunicipalUnmatched(f) {
  const p = f.properties;
  return (
    !parseIds(p._conflation_algo_matches).length &&
    !parseIds(p._conflation_override_included).length
  );
}

// ── Map setup ────────────────────────────────────────────────────────────────

function initMap() {
  map = new maplibregl.Map({
    container: "map",
    style: { version: 8, sources: {}, layers: [] },
    center: [-79.38, 43.72],
    zoom: 11,
  });
  return map;
}

function addBasemap() {
  map.addSource("basemap", {
    type: "raster",
    tiles: ["https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"],
    tileSize: 256,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    maxzoom: 19,
  });
  map.addLayer({ id: "basemap", type: "raster", source: "basemap" });
}

function addDataLayers(geojson) {
  map.addSource("data", { type: "geojson", data: geojson });

  // 1. Background grey municipal
  map.addLayer({
    id: "municipal-grey",
    type: "line",
    source: "data",
    filter: ["==", ["get", "_source"], "municipal"],
    paint: { "line-color": COLORS.municipalGrey, "line-width": 1.5 },
  });

  // 2. Background grey OSM
  map.addLayer({
    id: "osm-grey",
    type: "line",
    source: "data",
    filter: ["==", ["get", "_source"], "osm"],
    paint: { "line-color": COLORS.osmGrey, "line-width": 1 },
  });

  // 3. Unmatched municipal — orange, always shown when not selected
  map.addLayer({
    id: "municipal-unmatched",
    type: "line",
    source: "data",
    filter: ["literal", false],
    paint: { "line-color": COLORS.unmatched, "line-width": 2.5 },
  });

  // 4. Auto-matched OSM — blue
  map.addLayer({
    id: "osm-auto-matched",
    type: "line",
    source: "data",
    filter: ["literal", false],
    paint: { "line-color": COLORS.autoMatched, "line-width": 3 },
  });

  // 5. Override-excluded OSM — red solid
  map.addLayer({
    id: "osm-override-excluded",
    type: "line",
    source: "data",
    filter: ["literal", false],
    paint: { "line-color": COLORS.overrideExcluded, "line-width": 3 },
  });

  // 6. Override-included OSM — blue dashed
  map.addLayer({
    id: "osm-override-included",
    type: "line",
    source: "data",
    filter: ["literal", false],
    paint: {
      "line-color": COLORS.overrideIncluded,
      "line-width": 3,
      "line-dasharray": [4, 3],
    },
  });

  // 7. Selected municipal — black, top
  map.addLayer({
    id: "municipal-selected",
    type: "line",
    source: "data",
    filter: ["literal", false],
    paint: { "line-color": COLORS.selected, "line-width": 5, "line-opacity": 0.5 },
  });

  // 8. Highlighted OSM (list click) — yellow halo
  map.addLayer({
    id: "osm-highlighted",
    type: "line",
    source: "data",
    filter: ["literal", false],
    paint: {
      "line-color": COLORS.highlighted,
      "line-width": 7,
      "line-gap-width": 0,
    },
  });
}

// ── Layer updates ────────────────────────────────────────────────────────────

function idsFilter(ids) {
  if (!ids.length) return ["literal", false];
  return ["in", ["get", "osm_way_id"], ["literal", ids]];
}

function unmatchedMunicipalFilter() {
  const unmatched = municipalFeatures
    .filter(isMunicipalUnmatched)
    .map((f) => f.properties.SEGMENT_ID);
  if (!unmatched.length) return ["literal", false];
  return ["in", ["get", "SEGMENT_ID"], ["literal", unmatched]];
}

function updateSelectionLayers() {
  if (!municipalFeatures.length) return;
  const feature = municipalFeatures[currentIndex];
  const p = feature.properties;
  const segId = p.SEGMENT_ID;

  const autoIds = parseIds(p._conflation_algo_matches);
  const excludedIds = parseIds(p._conflation_override_excluded);
  const includedIds = parseIds(p._conflation_override_included);

  map.setFilter("municipal-selected", ["==", ["get", "SEGMENT_ID"], segId]);
  map.setFilter("osm-auto-matched", idsFilter(autoIds));
  map.setFilter("osm-override-excluded", idsFilter(excludedIds));
  map.setFilter("osm-override-included", idsFilter(includedIds));

  // Unmatched municipal: show all unmatched EXCEPT the currently selected one
  const unmatched = municipalFeatures
    .filter((f) => isMunicipalUnmatched(f) && f.properties.SEGMENT_ID !== segId)
    .map((f) => f.properties.SEGMENT_ID);
  map.setFilter(
    "municipal-unmatched",
    unmatched.length
      ? ["in", ["get", "SEGMENT_ID"], ["literal", unmatched]]
      : ["literal", false],
  );

  clearHighlight();
}

function zoomToSelection() {
  const feature = municipalFeatures[currentIndex];
  const p = feature.properties;

  const bboxes = [featureBbox(feature.geometry)];
  const allIds = [
    ...parseIds(p._conflation_algo_matches),
    ...parseIds(p._conflation_override_excluded),
    ...parseIds(p._conflation_override_included),
  ];
  for (const id of allIds) {
    const osm = osmFeaturesById[id];
    if (osm) bboxes.push(featureBbox(osm.geometry));
  }

  const bbox = unionBbox(bboxes);
  if (bbox) {
    map.fitBounds(
      [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[3]],
      ],
      { padding: 80, maxZoom: 18 },
    );
  }
}

function clearHighlight() {
  highlightedOsmId = null;
  map.setFilter("osm-highlighted", ["literal", false]);
  document
    .querySelectorAll(".osm-item.highlighted")
    .forEach((el) => el.classList.remove("highlighted"));
}

function highlightOsm(osmId) {
  highlightedOsmId = osmId;
  map.setFilter("osm-highlighted", ["==", ["get", "osm_way_id"], osmId]);
  const osm = osmFeaturesById[osmId];
  if (osm) {
    const bbox = featureBbox(osm.geometry);
    if (bbox) {
      const current = map.getBounds();
      const inView =
        bbox[0] >= current.getWest() &&
        bbox[2] <= current.getEast() &&
        bbox[1] >= current.getSouth() &&
        bbox[3] <= current.getNorth();
      if (!inView) {
        map.fitBounds(
          [
            [bbox[0], bbox[1]],
            [bbox[2], bbox[3]],
          ],
          { padding: 100, maxZoom: 18 },
        );
      }
    }
  }
  document.querySelectorAll(".osm-item").forEach((el) => {
    el.classList.toggle("highlighted", el.dataset.osmId === osmId);
  });
}

// ── Panel rendering ──────────────────────────────────────────────────────────

function renderPanel() {
  if (!municipalFeatures.length) return;
  const feature = municipalFeatures[currentIndex];
  const p = feature.properties;

  document.getElementById("feature-counter").textContent =
    `Feature ${currentIndex + 1} of ${municipalFeatures.length}`;

  const autoIds = parseIds(p._conflation_algo_matches);
  const excludedIds = parseIds(p._conflation_override_excluded);
  const includedIds = parseIds(p._conflation_override_included);

  const panel = document.getElementById("panel");
  panel.innerHTML = "";

  panel.appendChild(buildLegend());
  panel.appendChild(buildMunicipalSection(p));
  panel.appendChild(
    buildOsmSection("Auto-matched", autoIds, COLORS.autoMatched, false, "auto"),
  );
  panel.appendChild(
    buildOsmSection(
      "Override-excluded",
      excludedIds,
      COLORS.overrideExcluded,
      false,
      "excluded",
    ),
  );
  panel.appendChild(
    buildOsmSection(
      "Override-included",
      includedIds,
      COLORS.overrideIncluded,
      true,
      "included",
    ),
  );
}

function buildLegend() {
  const items = [
    { color: COLORS.selected, label: "Selected municipal", dashed: false },
    { color: COLORS.autoMatched, label: "Auto-matched OSM", dashed: false },
    { color: COLORS.overrideExcluded, label: "Override-excluded OSM", dashed: false },
    { color: COLORS.overrideIncluded, label: "Override-included OSM", dashed: true },
    { color: COLORS.unmatched, label: "Unmatched municipal", dashed: false },
    { color: COLORS.highlighted, label: "Panel-highlighted OSM", dashed: false },
  ];
  const div = document.createElement("div");
  div.id = "legend";
  for (const { color, label, dashed } of items) {
    const item = document.createElement("div");
    item.className = "legend-item";
    const swatch = document.createElement("span");
    swatch.className = `legend-swatch${dashed ? " dashed" : ""}`;
    swatch.style.background = dashed ? "none" : color;
    if (dashed) swatch.style.color = color;
    const text = document.createTextNode(label);
    item.append(swatch, text);
    div.appendChild(item);
  }
  return div;
}

function buildMunicipalSection(p) {
  const section = document.createElement("div");
  section.className = "section";

  const header = document.createElement("div");
  header.className = "section-header";
  header.innerHTML = `<span>Municipal feature</span>`;
  section.appendChild(header);

  const body = document.createElement("div");
  body.className = "section-body";

  const primary = [
    "SEGMENT_ID",
    "INFRA_HIGHORDER",
    "INFRA_LOWORDER",
    "STREET_NAME",
    "FROM_STREET",
    "TO_STREET",
  ];
  const skip = [
    "_source",
    "_conflation_algo_matches",
    "_conflation_override_excluded",
    "_conflation_override_included",
  ];

  const grid = document.createElement("div");
  grid.className = "prop-grid";
  for (const key of primary) {
    if (p[key] == null) continue;
    const k = document.createElement("div");
    k.className = "prop-key";
    k.textContent = key;
    const v = document.createElement("div");
    v.className = "prop-val";
    v.textContent = p[key];
    grid.append(k, v);
  }
  body.appendChild(grid);

  const details = document.createElement("details");
  details.className = "all-props";
  const summary = document.createElement("summary");
  summary.textContent = "Show all properties";
  details.appendChild(summary);
  const allGrid = document.createElement("div");
  allGrid.className = "prop-grid";
  for (const [key, val] of Object.entries(p)) {
    if (primary.includes(key) || skip.includes(key)) continue;
    const k = document.createElement("div");
    k.className = "prop-key";
    k.textContent = key;
    const v = document.createElement("div");
    v.className = "prop-val";
    v.textContent =
      val == null ? "—" : typeof val === "object" ? JSON.stringify(val) : String(val);
    allGrid.append(k, v);
  }
  details.appendChild(allGrid);
  body.appendChild(details);
  section.appendChild(body);
  return section;
}

function buildOsmSection(title, ids, color, dashed, type) {
  const section = document.createElement("div");
  section.className = "section";

  const header = document.createElement("div");
  header.className = "section-header";
  const dot = document.createElement("span");
  dot.style.cssText = `display:inline-block;width:10px;height:10px;border-radius:50%;background:${color};margin-right:6px;flex-shrink:0;`;
  const titleEl = document.createElement("span");
  titleEl.textContent = title;
  const badge = document.createElement("span");
  badge.className = "badge";
  badge.textContent = ids.length;
  header.append(dot, titleEl);
  header.appendChild(badge);
  section.appendChild(header);

  const body = document.createElement("div");
  body.className = "section-body";
  header.addEventListener("click", () => body.classList.toggle("hidden"));

  if (!ids.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "None";
    body.appendChild(empty);
  } else {
    const ul = document.createElement("ul");
    ul.className = "osm-list";
    for (const osmId of ids) {
      ul.appendChild(buildOsmItem(osmId, color, dashed));
    }
    body.appendChild(ul);
  }
  section.appendChild(body);
  return section;
}

function buildOsmItem(osmId, color, dashed) {
  const osm = osmFeaturesById[osmId];
  const tags = osm ? osm.properties.tags || {} : {};
  const name = osmLabel(osm);
  const subLabel = osmSubLabel(osm);

  const li = document.createElement("li");
  li.className = "osm-item";
  li.dataset.osmId = osmId;

  const details = document.createElement("details");
  details.className = "osm-detail";

  const summary = document.createElement("summary");

  const dot = document.createElement("span");
  dot.className = "osm-color-dot";
  dot.style.background = color;
  if (dashed) dot.style.outline = `2px dashed ${color}`;

  const idSpan = document.createElement("span");
  idSpan.className = "osm-id";
  idSpan.textContent = osmId;

  const nameSpan = document.createElement("span");
  nameSpan.className = "osm-name";
  nameSpan.textContent = name || "(unnamed)";

  const tagsSpan = document.createElement("span");
  tagsSpan.className = "osm-tags";
  tagsSpan.textContent = subLabel;

  summary.append(dot, idSpan, nameSpan, tagsSpan);
  details.appendChild(summary);

  if (osm) {
    const detailBody = document.createElement("div");
    detailBody.className = "osm-detail-body";
    const grid = document.createElement("div");
    grid.className = "prop-grid";
    for (const [k, v] of Object.entries(tags)) {
      const kEl = document.createElement("div");
      kEl.className = "prop-key";
      kEl.textContent = k;
      const vEl = document.createElement("div");
      vEl.className = "prop-val";
      vEl.textContent = String(v);
      grid.append(kEl, vEl);
    }
    detailBody.appendChild(grid);
    details.appendChild(detailBody);
  }

  li.appendChild(details);

  li.addEventListener("click", (e) => {
    if (highlightedOsmId === osmId) {
      clearHighlight();
    } else {
      highlightOsm(osmId);
    }
  });

  return li;
}

// ── Navigation ───────────────────────────────────────────────────────────────

function selectFeature(index) {
  currentIndex =
    ((index % municipalFeatures.length) + municipalFeatures.length) %
    municipalFeatures.length;
  updateSelectionLayers();
  zoomToSelection();
  renderPanel();
}

function setupNav() {
  document
    .getElementById("btn-prev")
    .addEventListener("click", () => selectFeature(currentIndex - 1));
  document
    .getElementById("btn-next")
    .addEventListener("click", () => selectFeature(currentIndex + 1));

  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT") return;
    if (e.key === "ArrowLeft" || e.key === "ArrowUp") selectFeature(currentIndex - 1);
    if (e.key === "ArrowRight" || e.key === "ArrowDown")
      selectFeature(currentIndex + 1);
  });

  const searchInput = document.getElementById("search-input");
  searchInput.addEventListener("input", () => {
    const q = searchInput.value.trim().toLowerCase();
    if (!q) return;
    const idx = municipalFeatures.findIndex((f) =>
      String(f.properties.SEGMENT_ID).toLowerCase().includes(q),
    );
    if (idx >= 0) selectFeature(idx);
  });
}

function setupFilters() {
  const toggleGroup = (group, show) => {
    const layers =
      group === "municipal"
        ? ["municipal-grey", "municipal-unmatched", "municipal-selected"]
        : [
            "osm-grey",
            "osm-auto-matched",
            "osm-override-excluded",
            "osm-override-included",
            "osm-highlighted",
          ];
    const vis = show ? "visible" : "none";
    for (const id of layers) map.setLayoutProperty(id, "visibility", vis);
  };

  document
    .getElementById("filter-municipal")
    .addEventListener("change", (e) => toggleGroup("municipal", e.target.checked));
  document
    .getElementById("filter-osm")
    .addEventListener("change", (e) => toggleGroup("osm", e.target.checked));
}

// ── Bootstrap ────────────────────────────────────────────────────────────────

async function loadData() {
  const overlay = document.getElementById("loading-overlay");
  const msg = document.getElementById("loading-msg");
  const progress = document.getElementById("loading-progress");

  msg.textContent = "Downloading data…";

  const response = await fetch(DATA_URL);
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.url}`);

  const total = parseInt(response.headers.get("content-length") || "0", 10);
  const reader = response.body.getReader();
  const chunks = [];
  let received = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.length;
    if (total > 0) progress.value = received / total;
    else progress.removeAttribute("value");
  }

  msg.textContent = "Parsing…";
  await new Promise((r) => setTimeout(r, 0));

  const blob = new Blob(chunks);
  const text = await blob.text();
  const geojson = JSON.parse(text);

  return geojson;
}

async function main() {
  initMap();

  await new Promise((resolve) => map.on("load", resolve));

  addBasemap();

  let geojson;
  try {
    geojson = await loadData();
  } catch (err) {
    document.getElementById("loading-msg").textContent = `Error: ${err.message}`;
    document.getElementById("loading-progress").style.display = "none";
    return;
  }

  // Partition features
  for (const feature of geojson.features) {
    if (feature.properties._source === "municipal") {
      municipalFeatures.push(feature);
    } else if (feature.properties._source === "osm") {
      osmFeaturesById[feature.properties.osm_way_id] = feature;
    }
  }

  municipalFeatures.sort((a, b) =>
    String(a.properties.SEGMENT_ID).localeCompare(
      String(b.properties.SEGMENT_ID),
      undefined,
      { numeric: true },
    ),
  );

  addDataLayers(geojson);
  setupNav();
  setupFilters();

  document.getElementById("loading-overlay").style.display = "none";

  selectFeature(0);
}

main().catch((err) => {
  console.error(err);
  document.getElementById("loading-msg").textContent = `Fatal error: ${err.message}`;
});
