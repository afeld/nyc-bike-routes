from dataclasses import dataclass

import pandas as pd
from geopandas import GeoDataFrame


def remove_timezone(series: pd.Series) -> pd.Series:
    if getattr(series.dt, "tz", None) is not None:
        return series.dt.tz_localize(None)
    return series


@dataclass
class RouteData:
    raw: GeoDataFrame
    temporal: GeoDataFrame
    projected: GeoDataFrame
    center_lat: float
    center_lon: float
    earliest: pd.Timestamp
    latest: pd.Timestamp
    dataset_last_updated: pd.Timestamp

    @property
    def total_routes(self) -> int:
        return len(self.temporal)

    @property
    def total_miles(self) -> float:
        return self.temporal["length_miles"].sum()

    @property
    def first_year(self) -> int:
        return int(self.earliest.year)

    @property
    def latest_year(self) -> int:
        return int(self.latest.year)

    @property
    def formatted_last_updated(self) -> str:
        if pd.isna(self.dataset_last_updated):
            return "Unknown"
        return self.dataset_last_updated.strftime("%Y-%m-%d")

    def miles_in_year(self, year: int) -> float:
        cutoff = pd.Timestamp(year=year, month=1, day=1)
        was_previously_installed = self.temporal["instdate"] < cutoff
        still_exists = self.temporal["ret_date"].isna() | (
            self.temporal["ret_date"] >= cutoff
        )
        return self.temporal.loc[
            was_previously_installed & still_exists, "length_miles"
        ].sum()

    def miles_during_administration(self, row: pd.Series) -> float:
        start = row["start_date"]
        end = row["end_date"]

        if pd.isna(start):
            return 0.0

        if pd.isna(end):
            mask = self.temporal["instdate"] >= start
        else:
            mask = (self.temporal["instdate"] >= start) & (
                self.temporal["instdate"] <= end
            )

        return self.temporal.loc[mask, "length_miles"].sum()
