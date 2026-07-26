import pandas as pd
import streamlit as st

from bike_routes.data import load_mayors
from bike_routes.domain import RouteData
from bike_routes.facilities import (
    FACILITY_ORDER,
    enrich_facility_columns,
)


def render_hero() -> None:
    st.markdown(
        """\
        # NYC bike routes over time

        Explore how the NYC bicycle network has changed over time.
        """
    )


def render_yearly_miles(routes: RouteData) -> None:
    yearly_miles = (
        routes.temporal.set_index("instdate")
        .resample("YS")["length_miles"]
        .sum()
        .reset_index()
    )
    yearly_miles["year"] = yearly_miles["instdate"].dt.year

    st.line_chart(
        yearly_miles,
        x="year",
        y="length_miles",
        x_label="Year",
        y_label="Miles added",
    )


def _miles_by_facility_at_cutoff(
    temporal_df: pd.DataFrame,
    cutoff: pd.Timestamp,
) -> pd.DataFrame:
    was_previously_installed = temporal_df["instdate"] < cutoff
    still_exists = temporal_df["ret_date"].isna() | (temporal_df["ret_date"] >= cutoff)

    return (
        temporal_df.loc[was_previously_installed & still_exists]
        .groupby(["facilitycl_code", "facilitycl_label", "facilitycl_color"])[
            ["length_miles"]
        ]
        .sum()
        .reset_index()
        .rename(columns={"facilitycl_label": "facilitycl", "length_miles": "miles"})
    )


def _build_cumulative_miles(routes: RouteData) -> pd.DataFrame:
    year_starts = pd.date_range(routes.earliest, routes.latest, freq="YS")
    temporal_df = enrich_facility_columns(routes.temporal)

    cumulative_frames = []
    for start in year_starts:
        cutoff = pd.Timestamp(year=start.year, month=1, day=1)
        miles_by_facility = _miles_by_facility_at_cutoff(temporal_df, cutoff).assign(
            year=start
        )
        cumulative_frames.append(miles_by_facility)

    if not cumulative_frames:
        return pd.DataFrame(
            columns=[
                "year",
                "facilitycl",
                "facilitycl_code",
                "facilitycl_color",
                "miles",
            ]
        )

    return pd.concat(cumulative_frames, ignore_index=True)[
        ["year", "facilitycl", "facilitycl_code", "facilitycl_color", "miles"]
    ]


def _ordered_facility_classes(cumulative_df: pd.DataFrame) -> list[str]:
    facility_order_lookup = {
        facility_code: i for i, facility_code in enumerate(FACILITY_ORDER)
    }
    unique_facility_classes = cumulative_df[
        ["facilitycl", "facilitycl_code"]
    ].drop_duplicates()
    return unique_facility_classes.sort_values(
        by=["facilitycl_code", "facilitycl"],
        key=lambda series: series.map(facility_order_lookup).fillna(
            len(FACILITY_ORDER)
        ),
    )["facilitycl"].tolist()


def render_cumulative_miles(routes: RouteData) -> None:
    cumulative_df = _build_cumulative_miles(routes)

    if cumulative_df.empty:
        st.info("No route data is available to display network size.")
        return

    ordered_facility_classes = _ordered_facility_classes(cumulative_df)

    facility_colors = (
        cumulative_df[["facilitycl", "facilitycl_color"]]
        .dropna(subset=["facilitycl_color"])
        .drop_duplicates(subset=["facilitycl"])
        .set_index("facilitycl")["facilitycl_color"]
        .to_dict()
    )
    stacked_miles = (
        cumulative_df.pivot_table(
            index="year",
            columns="facilitycl",
            values="miles",
            aggfunc="sum",
        )
        .reindex(columns=ordered_facility_classes)
        .fillna(0)
    )
    chart_colors = [
        facility_colors.get(facility, "gray") for facility in ordered_facility_classes
    ]

    st.area_chart(
        stacked_miles,
        y=ordered_facility_classes,
        color=chart_colors,
        stack=True,
        x_label="Year",
        y_label="Miles",
    )


def render_mayors(routes: RouteData) -> None:
    try:
        mayor_df = load_mayors(routes.earliest, routes.dataset_last_updated)
    except Exception as exc:  # pragma: no cover - external network dependency
        st.warning(f"Could not load mayor data: {exc}")
        return

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
                "miles_installed": "Miles of bike routes installed",
            }
        )
    )
    st.dataframe(display_df.reset_index(drop=True), width="stretch", hide_index=True)
