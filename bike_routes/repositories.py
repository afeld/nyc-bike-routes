import json
from pathlib import Path
from textwrap import dedent
from typing import Any

import httpx
import pandas as pd

from bike_routes.domain import RouteData

WIKIDATA_URL = "https://query.wikidata.org/sparql"

# Processed snapshot of the routes that the app reads, so it doesn't need to download them from NYC Open Data. Refreshed by `python -m bike_routes.update_data`.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ROUTES_FILE = "routes.parquet"
MAP_ROUTES_FILE = "map_routes.geojson"
METADATA_FILE = "metadata.json"
ROUTE_COLUMNS = ["instdate", "ret_date", "facilitycl", "length_miles"]
MAP_DATE_COLUMNS = ["instdate", "ret_date"]


class RouteSnapshotRepository:
    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir

    def get_route_date_range(
        self, temporal: pd.DataFrame
    ) -> tuple[pd.Timestamp, pd.Timestamp]:
        earliest = pd.concat([temporal["instdate"], temporal["ret_date"]]).min()
        latest = pd.concat([temporal["instdate"], temporal["ret_date"]]).max()
        return earliest, latest

    def load(self) -> RouteData:
        temporal = pd.read_parquet(self.data_dir / ROUTES_FILE)

        map_routes = json.loads((self.data_dir / MAP_ROUTES_FILE).read_text())

        metadata = json.loads((self.data_dir / METADATA_FILE).read_text())
        earliest, latest = self.get_route_date_range(temporal)

        return RouteData(
            temporal=temporal,
            map_routes=map_routes,
            center_lat=metadata["center_lat"],
            center_lon=metadata["center_lon"],
            earliest=earliest,
            latest=latest,
            dataset_last_updated=pd.Timestamp(metadata["dataset_last_updated"]),
        )


class MayorRepository:
    def __init__(self, url: str = WIKIDATA_URL) -> None:
        self.url = url
        self.headers = {
            "Accept": "application/sparql-results+json",
            "User-Agent": "BikeRoutes/0.0 (https://afeld.me/; aidan.feldman@gmail.com)",
        }

    def build_query(
        self, earliest: pd.Timestamp, dataset_last_updated: pd.Timestamp | None
    ) -> str:
        earliest_str = earliest.strftime("%Y-%m-%dT%H:%M:%SZ")
        if pd.notna(dataset_last_updated):
            latest_str = dataset_last_updated.strftime("%Y-%m-%dT%H:%M:%SZ")
            latest_start_filter = f'&& (!BOUND(?start_date) || ?start_date <= "{latest_str}"^^xsd:dateTime)'
        else:
            latest_start_filter = ""

        return dedent(
            f"""
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?mayor ?mayorLabel ?start_date ?end_date WHERE {{
              ?mayor p:P39 ?statement.
              ?statement ps:P39 wd:Q785304.
              ?mayor wdt:P31 wd:Q5.
              OPTIONAL {{ ?statement pq:P580 ?start_date. }}
              OPTIONAL {{ ?statement pq:P582 ?end_date. }}
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
              FILTER (
                (
                  (BOUND(?start_date) && ?start_date >= "{earliest_str}"^^xsd:dateTime)
                  || (BOUND(?end_date) && ?end_date >= "{earliest_str}"^^xsd:dateTime)
                )
                {latest_start_filter}
              )
            }}
            """
        ).strip()

    def normalize_results(self, data: dict[str, Any]) -> pd.DataFrame:
        mayor_df = pd.json_normalize(data["results"]["bindings"])
        if mayor_df.empty:
            return pd.DataFrame(
                columns=["full_name", "start_date", "end_date", "miles_installed"]
            )

        mayor_df = mayor_df.rename(columns={"mayorLabel.value": "full_name"})
        mayor_df["start_date"] = pd.to_datetime(
            mayor_df["start_date.value"], errors="coerce", utc=True
        )
        mayor_df["end_date"] = pd.to_datetime(
            mayor_df["end_date.value"], errors="coerce", utc=True
        )
        mayor_df["start_date"] = mayor_df["start_date"].dt.tz_convert(None)
        mayor_df["end_date"] = mayor_df["end_date"].dt.tz_convert(None)
        return mayor_df

    def load(
        self, earliest: pd.Timestamp, dataset_last_updated: pd.Timestamp | None
    ) -> pd.DataFrame:
        query = self.build_query(earliest, dataset_last_updated)
        response = httpx.get(self.url, params={"query": query}, headers=self.headers)
        response.raise_for_status()
        return self.normalize_results(response.json())
