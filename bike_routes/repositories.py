from textwrap import dedent
from typing import Any

import httpx
import pandas as pd
from geopandas import GeoDataFrame

from bike_routes.domain import RouteData, remove_timezone

DATA_URL = (
    "https://data.cityofnewyork.us/api/views/mzxg-pwib/rows.geojson?accessType=DOWNLOAD"
)
DATASET_METADATA_URL = "https://data.cityofnewyork.us/api/views/mzxg-pwib.json"
WIKIDATA_URL = "https://query.wikidata.org/sparql"
DATE_COLUMNS = [":created_at", "ret_date", "instdate"]


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

    def get_route_date_range(
        self, temporal: GeoDataFrame
    ) -> tuple[pd.Timestamp, pd.Timestamp]:
        earliest = pd.concat([temporal["instdate"], temporal["ret_date"]]).min()
        latest = pd.concat([temporal["instdate"], temporal["ret_date"]]).max()
        return earliest, latest

    def get_map_center(self, projected: GeoDataFrame) -> tuple[float, float]:
        projected_centroids = GeoDataFrame(
            geometry=projected.geometry.centroid,
            crs=projected.crs,
        ).to_crs(epsg=4326)
        center = projected_centroids.geometry.union_all().centroid
        return center.y, center.x

    def load(self) -> RouteData:
        geojson = self.fetch_geojson(self.data_url, timeout=30.0)
        metadata = self.fetch_geojson(self.metadata_url)

        raw = GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")
        temporal = self.prepare_temporal_routes(raw)
        projected = self.project_routes_with_lengths(temporal)
        dataset_last_updated = self.fetch_dataset_last_updated(metadata)
        earliest, latest = self.get_route_date_range(temporal)
        center_lat, center_lon = self.get_map_center(projected)

        return RouteData(
            raw=raw,
            temporal=temporal,
            projected=projected,
            center_lat=center_lat,
            center_lon=center_lon,
            earliest=earliest,
            latest=latest,
            dataset_last_updated=dataset_last_updated,
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
            ORDER BY ?start_date
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
