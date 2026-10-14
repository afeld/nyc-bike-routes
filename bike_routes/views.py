import warnings

import pandas as pd

from bike_routes.data import load_mayors
from bike_routes.domain import RouteData
from bike_routes.facilities import (
    FACILITY_ORDER,
    get_facility_label,
    normalize_facility_code,
)


def get_yearly_miles(routes: RouteData) -> pd.DataFrame:
    yearly_miles = (
        routes.temporal.set_index("instdate")
        .resample("YS")["length_miles"]
        .sum()
        .reset_index()
    )
    yearly_miles["year"] = yearly_miles["instdate"].dt.year
    yearly_miles = yearly_miles.rename(
        columns={
            "year": "Year",
            "length_miles": "Miles added",
        }
    )

    return yearly_miles[["Year", "Miles added"]]


def get_cumulative_miles(routes: RouteData) -> pd.DataFrame:
    facility_codes = (
        routes.temporal["facilitycl"].fillna("").map(normalize_facility_code)
    )
    unknown_codes = sorted(set(facility_codes) - set(FACILITY_ORDER))
    if unknown_codes:
        unknown_list = ", ".join(code or "(blank)" for code in unknown_codes)
        warnings.warn(f"Excluding routes with unknown facility types: {unknown_list}")

    year_starts = pd.date_range(routes.earliest, routes.latest, freq="YS")
    stacked_miles = pd.DataFrame(
        {
            year: routes.existing_at(year)
            .groupby(facility_codes)["length_miles"]
            .sum()
            for year in year_starts
        }
    ).T.reindex(columns=FACILITY_ORDER).fillna(0)
    stacked_miles.columns = [get_facility_label(code) for code in FACILITY_ORDER]
    return stacked_miles


def get_mayors(routes: RouteData) -> pd.DataFrame:
    mayor_df = load_mayors()

    mayor_df["miles_installed"] = mayor_df.apply(
        routes.miles_during_administration,
        axis=1,
    )

    return mayor_df
