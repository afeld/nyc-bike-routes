# NYC Bike Routes

## Setup

1. Install:
   1. Python
   1. [Node.js](https://nodejs.org/)
   1. [uv](https://docs.astral.sh/uv/getting-started/installation/)
1. Install dependencies.

   ```sh
   uv sync
   npm install
   ```

1. Preview the [Observable Framework](https://observablehq.com/framework/) site, which reloads as you edit. A [GitHub Action](.github/workflows/deploy.yml) builds and deploys it to GitHub Pages. The [data loaders](https://observablehq.com/framework/data-loaders) in `src/data/` compute what each chart needs from the snapshot. Framework only reruns a loader when its own file changes, so after changing the data or `bike_routes/`, run `npm run clean` and restart the preview.

   ```sh
   npm run dev
   ```

## Data

The app reads a processed snapshot of the [bike routes](https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data) and [mayors](https://www.wikidata.org/wiki/Q785304) from [`data/`](data/), rather than downloading them from NYC Open Data and Wikidata on startup. A [GitHub Action](.github/workflows/update-data.yml) refreshes it weekly, committing only if it changed. To refresh it yourself, such as after changing how the data is processed:

```sh
uv run --group data python -m bike_routes.update_data
```

## Testing

Build the site and check each page for errors in a headless browser, which you install once:

```sh
uv run playwright install chromium
uv run pytest
```
