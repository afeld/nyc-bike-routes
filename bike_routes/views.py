import pandas as pd
import streamlit as st

from bike_routes.data import load_mayors
from bike_routes.domain import RouteData
from bike_routes.facilities import (
    FACILITY_ORDER,
    FACILITY_STYLE,
    get_facility_label,
    normalize_facility_code,
)


def render_yearly_miles(routes: RouteData) -> None:
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

    st.line_chart(yearly_miles, x="Year", y="Miles added")


def render_cumulative_miles(routes: RouteData) -> None:
    facility_codes = (
        routes.temporal["facilitycl"].fillna("").map(normalize_facility_code)
    )
    unknown_codes = sorted(set(facility_codes) - set(FACILITY_ORDER))
    if unknown_codes:
        unknown_list = ", ".join(code or "(blank)" for code in unknown_codes)
        st.warning(f"Excluding routes with unknown facility types: {unknown_list}")

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

    st.area_chart(
        stacked_miles,
        color=[FACILITY_STYLE[code]["color"] for code in FACILITY_ORDER],
        stack=True,
        x_label="Year",
        y_label="Miles",
    )


def render_mayors(routes: RouteData) -> None:
    mayor_df = load_mayors()

    if mayor_df.empty:
        st.info("No mayor data was returned.")
        return

    mayor_df["miles_installed"] = mayor_df.apply(
        routes.miles_during_administration,
        axis=1,
    )

    st.bar_chart(
        mayor_df,
        x="full_name",
        y="miles_installed",
        horizontal=True,
        height=800,
        x_label="Mayor (most recent first)",
        y_label="Miles installed",
        sort="-start_date",
    )

    st.subheader("Top installers")

    display_df = (
        mayor_df[["full_name", "start_date", "end_date", "miles_installed"]]
        .sort_values("miles_installed", ascending=False)
        .assign(
            # years only
            start_date=mayor_df["start_date"].dt.year,
            end_date=mayor_df["end_date"].dt.year,
        )
        .rename(
            columns={
                "full_name": "Name",
                "start_date": "Term start",
                "end_date": "Term end",
                "miles_installed": "Miles installed",
            }
        )
    )
    st.dataframe(display_df.reset_index(drop=True), hide_index=True)
