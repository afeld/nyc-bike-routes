import json
from pathlib import Path

import pandas as pd

from bike_routes.domain import RouteData

# Processed snapshot of the routes and mayors that the app reads, so it doesn't need to download them from NYC Open Data and Wikidata. Refreshed by `python -m bike_routes.update_data`.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ROUTES_FILE = "routes.parquet"
MAP_ROUTES_FILE = "map_routes.geojson"
METADATA_FILE = "metadata.json"
MAYORS_FILE = "mayors.csv"
MAYOR_COLUMNS = ["full_name", "start_date", "end_date"]
ROUTE_COLUMNS = [
    "instdate",
    "ret_date",
    "facilitycl",
    "replaced_facilitycl",
    "length_miles",
    "street",
    "boro",
]
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
            earliest=earliest,
            latest=latest,
            dataset_last_updated=pd.Timestamp(metadata["dataset_last_updated"]),
        )


class MayorSnapshotRepository:
    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir

    def load(self) -> pd.DataFrame:
        return pd.read_csv(
            self.data_dir / MAYORS_FILE, parse_dates=["start_date", "end_date"]
        )
