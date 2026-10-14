# NYC Bike Routes

A static site: [`index.html`](index.html) loads a snapshot of the data from [`data/`](data/) and draws the map with [Leaflet](https://leafletjs.com/) and the charts with [Vega-Lite](https://vega.github.io/vega-lite/). There's no build step; GitHub Pages serves the repository as-is.

## Viewing locally

Serve the repository with any static file server, such as:

```sh
python -m http.server 8000
```

then go to http://localhost:8000.

## Data

The snapshot combines the [bike routes](https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data) from NYC Open Data and the [mayors](https://www.wikidata.org/wiki/Q785304) from Wikidata, preprocessed into what the map and each chart need. A [GitHub Action](.github/workflows/update-data.yml) refreshes it weekly, committing only if it changed. To refresh it yourself, such as after changing how the data is processed:

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
1. Run:

   ```sh
   uv run python -m bike_routes.update_data
   ```

## Testing

```sh
uv run pytest
```
