"""Downloads the bike routes from NYC Open Data and saves the processed snapshot that the app reads."""

import json
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from geopandas import GeoDataFrame

from bike_routes.repositories import (
    DATA_DIR,
    MAP_DATE_COLUMNS,
    MAP_ROUTES_FILE,
    METADATA_FILE,
    ROUTE_COLUMNS,
    ROUTES_FILE,
)

DATA_URL = (
    "https://data.cityofnewyork.us/api/views/mzxg-pwib/rows.geojson?accessType=DOWNLOAD"
)
DATASET_METADATA_URL = "https://data.cityofnewyork.us/api/views/mzxg-pwib.json"
DATE_COLUMNS = [":created_at", "ret_date", "instdate"]
MAP_SIMPLIFY_TOLERANCE_FEET = 30.0
MAP_COORDINATE_PRECISION_DEGREES = 1e-5


def remove_timezone(series: pd.Series) -> pd.Series:
    if getattr(series.dt, "tz", None) is not None:
        return series.dt.tz_localize(None)
    return series


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

    def get_map_center(self, projected: GeoDataFrame) -> tuple[float, float]:
        projected_centroids = GeoDataFrame(
            geometry=projected.geometry.centroid,
            crs=projected.crs,
        ).to_crs(epsg=4326)
        center = projected_centroids.geometry.union_all().centroid
        return center.y, center.x

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
        center_lat, center_lon = self.get_map_center(projected)

        data_dir.mkdir(exist_ok=True)
        temporal[ROUTE_COLUMNS].to_parquet(data_dir / ROUTES_FILE, index=False)
        (data_dir / MAP_ROUTES_FILE).write_text(map_routes.to_json(drop_id=True))
        snapshot_metadata = {
            "dataset_last_updated": (
                dataset_last_updated.isoformat()
                if pd.notna(dataset_last_updated)
                else None
            ),
            "center_lat": center_lat,
            "center_lon": center_lon,
        }
        (data_dir / METADATA_FILE).write_text(
            json.dumps(snapshot_metadata, indent=2) + "\n"
        )


if __name__ == "__main__":
    RouteRepository().save_snapshot()
