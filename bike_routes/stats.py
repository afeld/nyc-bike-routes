"""Aggregates the routes into the data behind each chart."""

import pandas as pd

# Columns of the routes DataFrame: instdate, ret_date, facilitycl, length_miles


def get_date_range(routes: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    dates = pd.concat([routes["instdate"], routes["ret_date"]])
    return dates.min(), dates.max()


def yearly_miles(routes: pd.DataFrame) -> pd.DataFrame:
    yearly = routes.set_index("instdate").resample("YS")["length_miles"].sum()
    return pd.DataFrame({"year": yearly.index.year, "miles": yearly.to_numpy()})


def network_size(routes: pd.DataFrame) -> pd.DataFrame:
    """Miles of each type of route that existed at the start of each year."""

    earliest, latest = get_date_range(routes)
    frames = []
    for cutoff in pd.date_range(earliest, latest, freq="YS"):
        was_previously_installed = routes["instdate"] < cutoff
        still_exists = routes["ret_date"].isna() | (routes["ret_date"] >= cutoff)
        frames.append(
            routes.loc[was_previously_installed & still_exists]
            .groupby("facilitycl", as_index=False)["length_miles"]
            .sum()
            .assign(year=cutoff.year)
        )

    if not frames:
        return pd.DataFrame(columns=["year", "type", "miles"])
    return pd.concat(frames, ignore_index=True).rename(
        columns={"facilitycl": "type", "length_miles": "miles"}
    )[["year", "type", "miles"]]


def miles_during_administration(routes: pd.DataFrame, mayor: pd.Series) -> float:
    start = mayor["start_date"]
    end = mayor["end_date"]

    if pd.isna(start):
        return 0.0

    mask = routes["instdate"] >= start
    if pd.notna(end):
        mask &= routes["instdate"] <= end

    return routes.loc[mask, "length_miles"].sum()


def mayors_with_miles(routes: pd.DataFrame, mayors: pd.DataFrame) -> pd.DataFrame:
    miles = [
        miles_during_administration(routes, mayor) for _, mayor in mayors.iterrows()
    ]
    return mayors.assign(miles=pd.Series(miles, index=mayors.index, dtype=float))
