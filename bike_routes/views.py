import pandas as pd
import plotly.express as px
import streamlit as st

from bike_routes.data import load_mayors
from bike_routes.domain import RouteData
from bike_routes.facilities import (
    FACILITY_ORDER,
    FACILITY_STYLE,
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

    figure = px.line(
        yearly_miles,
        x="year",
        y="length_miles",
        markers=True,
        labels={
            "year": "Year",
            "length_miles": "Miles added",
        },
    )
    st.plotly_chart(figure, width="stretch")


def render_cumulative_miles(routes: RouteData) -> None:
    year_starts = pd.date_range(routes.earliest, routes.latest, freq="YS")
    temporal_df = enrich_facility_columns(routes.temporal)
    records = []
    for start in year_starts:
        cutoff = pd.Timestamp(year=start.year, month=1, day=1)
        was_previously_installed = temporal_df["instdate"] < cutoff
        still_exists = temporal_df["ret_date"].isna() | (
            temporal_df["ret_date"] >= cutoff
        )
        miles_by_facility = (
            temporal_df.loc[was_previously_installed & still_exists]
            .groupby(["facilitycl_code", "facilitycl_label", "facilitycl_color"])[
                ["length_miles"]
            ]
            .sum()
            .reset_index()
        )

        for row in miles_by_facility.itertuples(index=False):
            records.append(
                {
                    "year": start,
                    "facilitycl": row.facilitycl_label,
                    "facilitycl_code": row.facilitycl_code,
                    "facilitycl_color": row.facilitycl_color,
                    "miles": row.length_miles,
                }
            )

    cumulative_df = pd.DataFrame.from_records(records)
    facility_category_order = [
        f"{FACILITY_STYLE[facility_code]['name']} ({facility_code})"
        for facility_code in FACILITY_ORDER
    ]
    other_labels = sorted(
        label
        for label in cumulative_df["facilitycl"].unique()
        if label not in facility_category_order
    )
    color_discrete_map = {
        row["facilitycl"]: row["facilitycl_color"]
        for _, row in cumulative_df[["facilitycl", "facilitycl_color"]]
        .drop_duplicates()
        .iterrows()
    }

    cumulative_figure = px.area(
        cumulative_df,
        x="year",
        y="miles",
        color="facilitycl",
        category_orders={"facilitycl": facility_category_order + other_labels},
        labels={
            "year": "Year",
            "miles": "Miles",
            "facilitycl": "Facility class",
        },
        color_discrete_map=color_discrete_map,
    )

    st.plotly_chart(cumulative_figure, width="stretch")


def render_mayors(routes: RouteData) -> None:
    try:
        mayor_df = load_mayors(routes.earliest, routes.dataset_last_updated)
    except Exception as exc:  # pragma: no cover - external network dependency
        st.warning(f"Could not load mayor data from Wikidata: {exc}")
        return

    if mayor_df.empty:
        st.info("No mayor data was returned from Wikidata.")
        return

    mayor_df["miles_installed"] = mayor_df.apply(
        routes.miles_during_administration,
        axis=1,
    )

    chart_figure = px.bar(
        mayor_df,
        x="full_name",
        y="miles_installed",
        labels={
            "full_name": "Mayor (chronological order)",
            "miles_installed": "Miles installed",
        },
    )
    chart_figure.update_layout(xaxis_tickangle=-35)
    st.plotly_chart(chart_figure, width="stretch")

    st.subheader("Top installers")

    display_df = (
        mayor_df[["full_name", "start_date", "end_date", "miles_installed"]]
        .sort_values("miles_installed", ascending=False)
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


def render_data_preview(routes: RouteData) -> None:
    st.dataframe(
        routes.temporal,
        width="stretch",
        hide_index=True,
    )
