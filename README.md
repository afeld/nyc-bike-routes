# NYC Bike Routes

A static site, built from a snapshot of the data and deployed to GitHub Pages by a [GitHub Action](.github/workflows/deploy.yml).

## Setup

1. Install:
   1. Python
   1. [uv](https://docs.astral.sh/uv/getting-started/installation/)
1. Install dependencies.

   ```sh
   uv sync
   ```

1. Build the site into `site/`.

   ```sh
   uv run python -m bike_routes.build_site
   ```

1. View it at http://localhost:8000.

   ```sh
   uv run python -m http.server 8000 --directory site
   ```

## Data

The site is built from a processed snapshot of the [bike routes](https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data) and [mayors](https://www.wikidata.org/wiki/Q785304) in [`data/`](data/). A [GitHub Action](.github/workflows/update-data.yml) refreshes it weekly, committing only if it changed, after which the site is redeployed. To refresh it yourself, such as after changing how the data is processed:

```sh
uv run --group data python -m bike_routes.update_data
```

## Testing

Build the site and check its contents:

```sh
uv run pytest
```
