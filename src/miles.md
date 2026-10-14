---
title: Miles
toc: false
---

# Miles

```js
import { FACILITY_TYPES } from "./components/facilities.js";

const yearlyMiles = FileAttachment("data/yearly_miles.json").json();
// one column per type, keyed by its label
const cumulativeMiles = FileAttachment("data/cumulative_miles.json").json();
```

## Miles added by year

<div class="card">${resize((width) => Plot.plot({
  width,
  height: 350,
  x: { label: "Year", tickFormat: "d" },
  y: { label: "Miles added", grid: true },
  marks: [
    Plot.ruleY([0]),
    Plot.lineY(yearlyMiles, { x: "Year", y: "Miles added", marker: true, tip: { format: { x: "d", y: ".1f" } } }),
  ],
}))}</div>

## Network size

Miles of each type of route at the start of each year.

```js
const types = FACILITY_TYPES.map((type) => type.label);
const visibleTypes = view(Inputs.checkbox(types, { label: "Show", value: types }));
```

<div class="card">${resize((width) => Plot.plot({
  width,
  height: 350,
  x: { label: "Year" },
  y: { label: "Miles", grid: true },
  color: {
    legend: true,
    domain: FACILITY_TYPES.map((type) => type.label),
    range: FACILITY_TYPES.map((type) => type.color),
  },
  marks: [
    Plot.areaY(
      cumulativeMiles.flatMap((row) =>
        visibleTypes.map((type) => ({ year: new Date(row.year), type, miles: row[type] })),
      ),
      {
        x: "year",
        y: "miles",
        fill: "type",
        order: types,
        tip: { format: { x: "%Y", y: ".1f" } },
      },
    ),
    Plot.ruleY([0]),
  ],
}))}</div>
