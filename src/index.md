---
title: Map
toc: false
---

# NYC bike routes over time

```js
import * as Leaflet from "npm:leaflet";
import { FACILITY_TYPES } from "./components/facilities.js";

const routes = FileAttachment("data/map_routes.geojson").json();
```

```js
// Leaflet.timeline is a plugin script that extends the global `L`, so give it a copy of the (read-only) module to extend
const L = { ...Leaflet };
globalThis.L = L;
await import("npm:leaflet.timeline@1.6.0/dist/leaflet.timeline.js");
```

```js
const container = display(document.createElement("div"));
container.className = "card";
container.style = "height: 70vh; min-height: 400px; padding: 0;";

const map = L.map(container);
// fit to all of the routes, leaving room for the timeline slider along the bottom
map.fitBounds(L.geoJSON(routes).getBounds(), {
  paddingTopLeft: [10, 10],
  paddingBottomRight: [10, 80],
});
// routes that haven't been removed are shown through the latest date in the data
const latest = routes.features
  .flatMap((feature) => [feature.properties.instdate, feature.properties.ret_date])
  .filter(Boolean)
  .sort()
  .at(-1);
const basemap = dark ? "World_Dark_Gray_Base" : "World_Light_Gray_Base";
L.tileLayer(
  `https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/${basemap}/MapServer/tile/{z}/{y}/{x}`,
  { attribution: "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ", maxZoom: 16 },
).addTo(map);

// one timeline per type, so the layers control works as a legend that can toggle them
const overlays = {};
const timelines = FACILITY_TYPES.map((type) => {
  const features = routes.features.filter(
    (feature) => feature.properties.facilitycl === type.code && feature.properties.instdate,
  );
  const timeline = L.timeline(
    { type: "FeatureCollection", features },
    {
      getInterval: (feature) => ({
        start: Date.parse(feature.properties.instdate),
        end: Date.parse(feature.properties.ret_date ?? latest),
      }),
      style: { color: type.color, weight: 3, opacity: 0.9 },
    },
  ).addTo(map);
  overlays[`<span class="swatch" style="background: ${type.color}"></span>${type.label}`] =
    timeline;
  return timeline;
});
L.control.layers(null, overlays, { collapsed: false }).addTo(map);

const slider = L.timelineSliderControl({
  showTicks: true,
  enableKeyboardControls: true,
  formatOutput: (date) => new Date(date).getUTCFullYear(),
}).addTo(map);
slider.addTimelines(...timelines);
// rather than the autoPlay option, which starts before the timelines are added (and they pause it) once the page has loaded
slider.play();

invalidation.then(() => {
  slider.pause();
  map.remove();
});
```

<style>
  .leaflet-container {
    font: inherit;
    color: #1f2937;
  }
  .swatch {
    display: inline-block;
    width: 0.9em;
    height: 0.9em;
    margin-right: 0.3em;
    vertical-align: -0.1em;
  }
  /* stretch the timeline slider across the bottom of the map */
  .leaflet-bottom.leaflet-left {
    width: 100%;
  }
  .leaflet-timeline-controls {
    box-sizing: border-box;
    width: calc(100% - 20px);
  }
  .leaflet-timeline-control .time-text {
    font-size: 1.25rem;
    font-weight: bold;
  }
</style>
