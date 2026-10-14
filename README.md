# NYC Bike Routes

## Setup

1. Install:
   1. Python
   1. [uv](https://docs.astral.sh/uv/getting-started/installation/)
1. Install dependencies.

   ```sh
   uv sync
   ```

1. Serve the site, which GitHub Pages serves as-is, then go to http://localhost:8000.

   ```sh
   uv run python -m http.server 8000
   ```

## Data

The app reads a processed snapshot of the [bike routes](https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data) and [mayors](https://www.wikidata.org/wiki/Q785304) from [`data/`](data/), rather than downloading them from NYC Open Data and Wikidata on startup. A [GitHub Action](.github/workflows/update-data.yml) refreshes it weekly, committing only if it changed. To refresh it yourself, such as after changing how the data is processed:

```sh
uv run --group data python -m bike_routes.update_data
```

## Testing

Load the site and check it for errors in a headless browser, which you install once:

```sh
uv run playwright install chromium
uv run pytest
```
