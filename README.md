# NYC Bike Routes

## Setup

1. Install:
   1. Python
   1. [uv](https://docs.astral.sh/uv/getting-started/installation/)
1. Install dependencies.

   ```sh
   uv sync
   ```

1. Preview the [Quarto](https://quarto.org/) site, which re-renders as you edit. A [GitHub Action](.github/workflows/deploy.yml) deploys it to GitHub Pages.

   ```sh
   uv run quarto preview
   ```

## Data

The app reads a processed snapshot of the [bike routes](https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data) and [mayors](https://www.wikidata.org/wiki/Q785304) from [`data/`](data/), rather than downloading them from NYC Open Data and Wikidata on startup. A [GitHub Action](.github/workflows/update-data.yml) refreshes it weekly, committing only if it changed. To refresh it yourself, such as after changing how the data is processed:

```sh
uv run --group data python -m bike_routes.update_data
```

## Testing

Render the site and check each page for errors in a headless browser, which you install once:

```sh
uv run playwright install chromium
uv run pytest
```
