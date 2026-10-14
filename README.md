# NYC Bike Routes

## Setup

1. Install:
   1. Python
   1. [uv](https://docs.astral.sh/uv/getting-started/installation/)
1. Install dependencies.

   ```sh
   uv sync
   ```

1. Run the Streamlit app.

   ```sh
   uv run streamlit run app.py
   ```

## Data

The app reads a processed snapshot of the [bike routes](https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data) from [`data/`](data/), rather than downloading it from NYC Open Data on startup. A [GitHub Action](.github/workflows/update-data.yml) refreshes it daily, committing only if it changed. To refresh it yourself, such as after changing how the data is processed:

```sh
uv run python -m bike_routes.update_data
```

## Testing

Run each page of the app and check for errors:

```sh
uv run pytest
```
