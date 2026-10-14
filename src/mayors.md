---
title: Mayors
toc: false
---

# Mayoral administrations

This compares route miles that were installed during each administration window. Mayor information from [Wikidata](https://www.wikidata.org/).

```js
const mayors = FileAttachment("data/mayor_miles.json").json();
```

```js
const mostRecentFirst = d3
  .sort(mayors, (mayor) => mayor.start_date)
  .reverse()
  .map((mayor) => mayor.full_name);
```

<div class="card">${resize((width) => Plot.plot({
  width,
  height: mayors.length * 24 + 40,
  marginLeft: 180,
  x: { label: "Miles installed", grid: true },
  y: { label: null, domain: mostRecentFirst },
  marks: [
    Plot.barX(mayors, { x: "miles_installed", y: "full_name", tip: { format: { x: ".1f" } } }),
    Plot.ruleX([0]),
  ],
}))}</div>

## Top installers

```js
const results = view(Inputs.search(mayors, { placeholder: "Search mayors…" }));
```

```js
const year = (date) => date?.slice(0, 4) ?? "";

display(
  Inputs.table(results, {
    columns: ["full_name", "start_date", "end_date", "miles_installed"],
    header: {
      full_name: "Name",
      start_date: "Term start",
      end_date: "Term end",
      miles_installed: "Miles installed",
    },
    format: { start_date: year, end_date: year, miles_installed: (miles) => miles.toFixed(1) },
    sort: "miles_installed",
    reverse: true,
    rows: 30,
    select: false,
  }),
);
```
