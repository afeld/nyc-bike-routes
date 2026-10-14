import pandas as pd

from bike_routes.domain import RouteData
from bike_routes.repositories import MayorSnapshotRepository, RouteSnapshotRepository


def load_routes() -> RouteData:
    return RouteSnapshotRepository().load()


def load_mayors() -> pd.DataFrame:
    return MayorSnapshotRepository().load()
