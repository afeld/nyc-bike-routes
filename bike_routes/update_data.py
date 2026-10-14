"""Downloads the bike routes from NYC Open Data and the mayors from Wikidata, and saves the processed snapshot that the app reads."""

import json
from pathlib import Path
from textwrap import dedent
from typing import Any

import httpx
import pandas as pd
from geopandas import GeoDataFrame

from bike_routes.repositories import (
    DATA_DIR,
    MAP_DATE_COLUMNS,
    MAP_ROUTES_FILE,
    MAYOR_COLUMNS,
    MAYORS_FILE,
    METADATA_FILE,
    ROUTE_COLUMNS,
    ROUTES_FILE,
    RouteSnapshotRepository,
)

DATA_URL = (
    "https://data.cityofnewyork.us/api/views/mzxg-pwib/rows.geojson?accessType=DOWNLOAD"
)
DATASET_METADATA_URL = "https://data.cityofnewyork.us/api/views/mzxg-pwib.json"
WIKIDATA_URL = "https://query.wikidata.org/sparql"
DATE_COLUMNS = [":created_at", "ret_date", "instdate"]
MAP_SIMPLIFY_TOLERANCE_FEET = 30.0
MAP_COORDINATE_PRECISION_DEGREES = 1e-5


def remove_timezone(series: pd.Series) -> pd.Series:
    if getattr(series.dt, "tz", None) is not None:
        return series.dt.tz_localize(None)
    return series


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
            return pd.DataFrame(columns=MAYOR_COLUMNS)

        mayor_df = mayor_df.rename(columns={"mayorLabel.value": "full_name"})
        mayor_df["start_date"] = pd.to_datetime(
            mayor_df["start_date.value"], errors="coerce", utc=True
        )
        mayor_df["end_date"] = pd.to_datetime(
            mayor_df["end_date.value"], errors="coerce", utc=True
        )
        mayor_df["start_date"] = mayor_df["start_date"].dt.tz_convert(None)
        mayor_df["end_date"] = mayor_df["end_date"].dt.tz_convert(None)
        # Sort so the snapshot doesn't change when the data doesn't.
        return mayor_df[MAYOR_COLUMNS].sort_values(
            ["start_date", "full_name"], ignore_index=True
        )

    def load(
        self, earliest: pd.Timestamp, dataset_last_updated: pd.Timestamp | None
    ) -> pd.DataFrame:
        query = self.build_query(earliest, dataset_last_updated)
        response = httpx.get(
            self.url, params={"query": query}, headers=self.headers, timeout=30.0
        )
        response.raise_for_status()
        return self.normalize_results(response.json())


class RouteRepository:
    def __init__(
        self,
        data_url: str = DATA_URL,
        metadata_url: str = DATASET_METADATA_URL,
    ) -> None:
        self.data_url = data_url
        self.metadata_url = metadata_url

    def fetch_geojson(self, url: str, timeout: float = 20.0) -> dict[str, Any]:
        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def fetch_dataset_last_updated(self, metadata: dict[str, Any]) -> pd.Timestamp:
        metadata_updated_unix = metadata.get("rowsUpdatedAt") or metadata.get(
            "viewLastModified"
        )
        dataset_last_updated = pd.to_datetime(
            metadata_updated_unix,
            unit="s",
            errors="coerce",
            utc=True,
        )
        if pd.notna(dataset_last_updated):
            return dataset_last_updated.tz_convert(None)
        return dataset_last_updated

    def prepare_temporal_routes(self, raw: GeoDataFrame) -> GeoDataFrame:
        temporal = raw.copy()
        for column in DATE_COLUMNS:
            temporal[column] = pd.to_datetime(temporal[column], errors="coerce")

        temporal["instdate"] = remove_timezone(temporal["instdate"])
        temporal["ret_date"] = remove_timezone(temporal["ret_date"])
        return temporal

    def project_routes_with_lengths(self, temporal: GeoDataFrame) -> GeoDataFrame:
        projected = temporal.to_crs(epsg=2263)
        projected["length_miles"] = projected.geometry.length / 5280
        temporal["length_miles"] = projected["length_miles"]
        return projected

    def simplify_routes_for_map(
        self,
        projected: GeoDataFrame,
        tolerance_feet: float = MAP_SIMPLIFY_TOLERANCE_FEET,
    ) -> GeoDataFrame:
        # Combine segments that appear and disappear together, so the map has far fewer features to draw.
        keys = ["instdate", "ret_date", "facilitycl"]
        simplified = projected[keys + ["geometry"]].dissolve(
            by=keys, dropna=False, as_index=False
        )
        # Join adjacent segments into longer lines, which simplify further.
        simplified["geometry"] = simplified.geometry.line_merge()
        # Simplify route coordinates in projected units before converting back to WGS84.
        simplified["geometry"] = simplified.geometry.simplify(
            tolerance=tolerance_feet,
            preserve_topology=True,
        )
        simplified = simplified.to_crs(epsg=4326)
        # Round to 5 decimal places (~1 meter), to shrink the GeoJSON embedded in the map.
        simplified["geometry"] = simplified.geometry.set_precision(
            MAP_COORDINATE_PRECISION_DEGREES
        )
        return simplified

    def save_snapshot(self, data_dir: Path = DATA_DIR) -> None:
        geojson = self.fetch_geojson(self.data_url, timeout=30.0)
        metadata = self.fetch_geojson(self.metadata_url)

        raw = GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")
        # Sort by the row ID so the snapshot doesn't change when the data doesn't.
        raw = raw.sort_values(":id", ignore_index=True)
        temporal = self.prepare_temporal_routes(raw)
        projected = self.project_routes_with_lengths(temporal)
        map_routes = self.simplify_routes_for_map(projected)
        for column in MAP_DATE_COLUMNS:
            map_routes[column] = map_routes[column].dt.strftime("%Y-%m-%d")
        dataset_last_updated = self.fetch_dataset_last_updated(metadata)
        earliest, _ = RouteSnapshotRepository().get_route_date_range(temporal)
        mayors = MayorRepository().load(earliest, dataset_last_updated)

        data_dir.mkdir(exist_ok=True)
        temporal[ROUTE_COLUMNS].to_parquet(data_dir / ROUTES_FILE, index=False)
        (data_dir / MAP_ROUTES_FILE).write_text(map_routes.to_json(drop_id=True))
        mayors.to_csv(data_dir / MAYORS_FILE, index=False, date_format="%Y-%m-%d")
        snapshot_metadata = {
            "dataset_last_updated": (
                dataset_last_updated.isoformat()
                if pd.notna(dataset_last_updated)
                else None
            ),
        }
        (data_dir / METADATA_FILE).write_text(
            json.dumps(snapshot_metadata, indent=2) + "\n"
        )


if __name__ == "__main__":
    RouteRepository().save_snapshot()
