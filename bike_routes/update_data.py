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
# How far apart a retirement and an installation in the same place can be, for the new facility to count as replacing the old one.
REPLACEMENT_WINDOW = pd.Timedelta(days=60)
# How close a retired route needs to be to a new one to count as in the same place, allowing for the lines being drawn on different sides of the street.
REPLACEMENT_DISTANCE_FEET = 50.0
# How much of a new route needs to be in the same place as retired ones, for it to count as replacing them.
REPLACEMENT_MIN_OVERLAP = 0.8
# The data spells street types inconsistently, e.g. "PARK AV" and "PARK AVENUE".
STREET_TYPE_ABBREVIATIONS = {
    "AVENUE": "AV",
    "AVE": "AV",
    "STREET": "ST",
    "BOULEVARD": "BLVD",
    "BL": "BLVD",
    "ROAD": "RD",
    "PARKWAY": "PKWY",
    "PLACE": "PL",
    "DRIVE": "DR",
}


def remove_timezone(series: pd.Series) -> pd.Series:
    if getattr(series.dt, "tz", None) is not None:
        return series.dt.tz_localize(None)
    return series


def normalize_street(street: str | None) -> str:
    words = (street or "").upper().split()
    if words:
        words[-1] = STREET_TYPE_ABBREVIATIONS.get(words[-1], words[-1])
    return " ".join(words)


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
        temporal["street"] = temporal["street"].map(normalize_street)
        temporal["replaced_facilitycl"] = self.find_replaced_facilities(temporal)
        return temporal

    def find_replaced_facilities(self, temporal: pd.DataFrame) -> pd.Series:
        """The facility class that each route replaced, i.e. the one retired from the same place around when the route was installed. Missing for routes that were new.

        This matches on location rather than street segment IDs, since a street is sometimes split into different segments when it's redone."""
        # in feet
        projected = temporal.to_crs(epsg=2263)
        retired = projected.loc[
            projected["ret_date"].notna(), ["ret_date", "facilitycl", "geometry"]
        ]
        retired["geometry"] = retired.buffer(REPLACEMENT_DISTANCE_FEET)
        pairs = (
            projected[["instdate", "geometry"]]
            .reset_index(names="new")
            .sjoin(retired.reset_index(names="old"), predicate="intersects")
        )
        pairs["gap"] = (pairs["instdate"] - pairs["ret_date"]).abs()
        pairs = pairs[
            (pairs["new"] != pairs["old"]) & (pairs["gap"] <= REPLACEMENT_WINDOW)
        ]

        # how much of each new route is covered by the ones retired around then, which may have been split up differently
        retired_nearby = (
            GeoDataFrame(
                {"new": pairs["new"]},
                geometry=retired.geometry.loc[pairs["old"]].values,
                crs=retired.crs,
            )
            .dissolve(by="new")
            .geometry
        )
        new_routes = projected.geometry.loc[retired_nearby.index]
        overlap = new_routes.intersection(retired_nearby).length / new_routes.length
        pairs = pairs[
            pairs["new"].isin(overlap.index[overlap >= REPLACEMENT_MIN_OVERLAP])
        ]

        # if multiple were retired around then, use the closest in time, then the closest in shape
        pairs["distance"] = (
            projected.geometry.loc[pairs["new"]]
            .hausdorff_distance(projected.geometry.loc[pairs["old"]], align=False)
            .values
        )
        replaced = (
            pairs.sort_values(["gap", "distance"])
            .drop_duplicates("new")
            .set_index("new")
        )
        return replaced["facilitycl"].reindex(temporal.index)

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
        # Combine segments of a street that appear and disappear together, so the map has far fewer features to draw. Keep the fields that projects are grouped by, so they can be shown on a map too.
        keys = [
            "instdate",
            "ret_date",
            "facilitycl",
            "replaced_facilitycl",
            "street",
            "boro",
        ]
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
