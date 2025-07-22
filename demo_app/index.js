import "./thirdparty/maplibre-gl.js";
import "./thirdparty/maplibre-gl-geocoder.min.js";
import { PopUpHandler } from "./assets/js/popuphandler.js";
import { parkingStyleOptions as pso } from "./assets/js/parking_style_options.js";

const PARKING_LAYER = "byQuality";

const map = new maplibregl.Map({
  container: "map",
  style: "https://api.maptiler.com/maps/streets/style.json?key=MlRGiaPF42qIx2cAP9Hn",
  center: [-79.416, 43.714],
  zoom: 10.5,
});

// set up bounding box of Toronto used to narrow down geolocation
class BBox {
  constructor(xmin, xmax, ymin, ymax) {
    this.xmin = xmin;
    this.xmax = xmax;
    this.ymin = ymin;
    this.ymax = ymax;
  }
  getURLParams() {
    return `${this.xmin},${this.ymin},${this.xmax},${this.ymax}`;
  }
}
const torontoBBox = new BBox(-79.6392832, -79.1132193, 43.5796082, 43.8554425);

const geocoderApi = {
  forwardGeocode: async (config) => {
    const features = [];
    try {
      const request = `https://nominatim.openstreetmap.org/search?q=${
        config.query
      }&format=geojson&polygon_geojson=1&addressdetails=1&countrycodes=CA&viewbox=${torontoBBox.getURLParams()}&bounded=1`;
      const response = await fetch(request);
      const geojson = await response.json();
      for (const feature of geojson.features) {
        const center = [
          feature.bbox[0] + (feature.bbox[2] - feature.bbox[0]) / 2,
          feature.bbox[1] + (feature.bbox[3] - feature.bbox[1]) / 2,
        ];
        const point = {
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates: center,
          },
          place_name: feature.properties.display_name,
          properties: feature.properties,
          text: feature.properties.display_name,
          place_type: ["place"],
          center,
        };
        features.push(point);
      }
    } catch (e) {
      console.error(`Failed to forwardGeocode with error: ${e}`);
    }

    return {
      features,
    };
  },
};

map.on("load", () => {
  map.addControl(new maplibregl.NavigationControl(), "top-left");
  map.addControl(new maplibregl.GeolocateControl(), "top-left");
  map.addControl(
    new MaplibreGeocoder(geocoderApi, {
      maplibregl,
    })
  );

  // add in data sources
  const displayData =
    "https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/bicycle_parking/display_files/all_sources.geojson";
  const bikeLaneURL =
    "https://raw.githubusercontent.com/bikespace/parking-map-data/refs/heads/data/bicycle_network/cycling-network-display.geojson";
  const bikeTheftURL = "data/bicycle-thefts.geojson";

  map.addSource("bicycle-parking", {
    type: "geojson",
    data: displayData,
    generateId: true,
  });
  map.addSource("bicycle-lanes", {
    type: "geojson",
    data: bikeLaneURL,
  });
  map.addSource("bicycle-thefts", {
    type: "geojson",
    data: bikeTheftURL,
  });

  // Add a layer showing bike lanes
  // line-dasharray doesn't support data-driven styling, so the dashed and non-dashed lines have to be added as separate layers
  map.addLayer({
    id: "bicycle-lanes",
    type: "line",
    source: "bicycle-lanes",
    filter: [
      "match",
      ["get", "INFRA_HIGHORDER"],
      [
        "Sharrows - Wayfinding",
        "Sharrows - Arterial - Connector",
        "Signed Route (No Pavement Markings)",
        "Sharrows",
      ],
      false,
      true,
    ],
    layout: {
      "line-cap": "round",
    },
    paint: {
      "line-width": 3,
      "line-color": [
        "match",
        ["get", "INFRA_HIGHORDER"],
        ["Cycle Track", "Cycle Track - Contraflow", "Bi-Directional Cycle Track"],
        "hsl(137, 68%, 23%)",
        [
          "Multi-Use Trail - Boulevard",
          "Multi-Use Trail - Entrance",
          "Multi-Use Trail - Existing Connector",
          "Multi-Use Trail - Connector",
          "Multi-Use Trail",
          "Park Road",
        ],
        "#8c5535",
        ["Bike Lane - Buffered", "Bike Lane", "Bike Lane - Contraflow"],
        "hsl(137, 68%, 36%)",
        "#2c3b42",
      ],
    },
  });
  map.addLayer({
    id: "bicycle-routes",
    type: "line",
    source: "bicycle-lanes",
    filter: [
      "match",
      ["get", "INFRA_HIGHORDER"],
      [
        "Sharrows - Wayfinding",
        "Sharrows - Arterial - Connector",
        "Signed Route (No Pavement Markings)",
        "Sharrows",
      ],
      true,
      false,
    ],
    layout: {
      "line-cap": "round",
    },
    paint: {
      "line-width": 3,
      "line-dasharray": [1, 2],
      "line-color": [
        "match",
        ["get", "INFRA_HIGHORDER"],
        [
          "Sharrows - Wayfinding",
          "Sharrows - Arterial - Connector",
          "Signed Route (No Pavement Markings)",
          "Sharrows",
        ],
        "hsl(137, 56%, 62%)",
        "#2c3b42",
      ],
    },
  });

  // Add a layer showing the parking
  map.addLayer({
    id: "bicycle-parking-nodes",
    type: pso[PARKING_LAYER].nodes.type,
    source: "bicycle-parking",
    filter: ["match", ["geometry-type"], ["Point"], true, false],
    paint: pso[PARKING_LAYER].nodes.paint,
  });
  map.addLayer({
    id: "bicycle-parking-ways",
    type: pso[PARKING_LAYER].ways.type,
    source: "bicycle-parking",
    filter: ["match", ["geometry-type"], ["LineString"], true, false],
    paint: pso[PARKING_LAYER].ways.paint,
  });

  const ParkingPopUp = new PopUpHandler(
    map,
    ["bicycle-parking-nodes", "bicycle-parking-ways"],
    document.getElementById("feature-details"),
    document.body,
    "layout-popup"
  );

  map.on("click", (e) => {
    ParkingPopUp.fromPoint(e.point);
  });

  document.getElementById("button-biketheft").addEventListener("click", () => {
    // Add bike theft heatmap
    map.addLayer(
      {
        id: "bicycle-thefts",
        type: "heatmap",
        source: "bicycle-thefts",
        filter: [
          "match",
          ["get", "PREMISES_TYPE"],
          ["Outside", "Transit"],
          true,
          false,
        ],
        paint: {
          "heatmap-radius": {
            base: 2,
            stops: [
              [10, 2],
              [19, 1028],
            ],
          },
          "heatmap-color": [
            "interpolate",
            ["linear"],
            ["heatmap-density"],
            0,
            "rgba(0, 0, 255, 0)",
            0.3,
            "royalblue",
            0.6,
            "cyan",
            0.9,
            "lime",
            0.999,
            "yellow",
            1,
            "red",
          ],
          "heatmap-opacity": 0.5,
        },
      },
      "bicycle-lanes"
    );
  });
});

// zoom indicator for debug
map.on("zoomend", () => {
  document.getElementById("zoom-indicator").textContent =
    "Zoom: " + Math.round(map.getZoom() * 10) / 10;
});
