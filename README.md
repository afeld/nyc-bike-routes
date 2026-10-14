# NYC Bike Routes

A static site built with [Quarto](https://quarto.org/) from a snapshot of the data, and deployed to GitHub Pages by a [GitHub Action](.github/workflows/deploy.yml). Each page ([`index.qmd`](index.qmd), [`miles.qmd`](miles.qmd), [`mayors.qmd`](mayors.qmd)) is Markdown with Python cells that output the [folium](https://python-visualization.github.io/folium/) map and [Altair](https://altair-viz.github.io/) charts.

## Setup

1. Install:
   1. Python
   1. [uv](https://docs.astral.sh/uv/getting-started/installation/)
1. Install dependencies, which include Quarto.

   ```sh
   uv sync
   ```

1. Preview the site, which re-renders as you edit.

   ```sh
   uv run quarto preview
   ```

## Data

The site is built from a processed snapshot of the [bike routes](https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data) and [mayors](https://www.wikidata.org/wiki/Q785304) in [`data/`](data/). A [GitHub Action](.github/workflows/update-data.yml) refreshes it weekly, committing only if it changed, after which the site is redeployed. To refresh it yourself, such as after changing how the data is processed:

```sh
uv run --group data python -m bike_routes.update_data
```

## Testing

The tests render the site and load each page in a headless browser. Install the browser once:

```sh
uv run playwright install chromium
```

then run:

```sh
uv run pytest
```
