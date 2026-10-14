from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class RouteData:
    temporal: pd.DataFrame
    # GeoJSON FeatureCollection
    map_routes: dict[str, Any]
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

    def existing_at(self, cutoff: pd.Timestamp) -> pd.DataFrame:
        """Routes that were installed before the cutoff and not yet removed."""
        was_previously_installed = self.temporal["instdate"] < cutoff
        still_exists = self.temporal["ret_date"].isna() | (
            self.temporal["ret_date"] >= cutoff
        )
        return self.temporal.loc[was_previously_installed & still_exists]

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
