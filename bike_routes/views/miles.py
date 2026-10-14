import altair as alt
import pandas as pd
import streamlit as st

from bike_routes.domain import RouteData
from bike_routes.facilities import (
    FACILITY_ORDER,
    FACILITY_STYLE,
    get_facility_label,
    normalize_facility_code,
)
from bike_routes.views.projects import NEW, get_kind


def render_yearly_miles(routes: RouteData) -> None:
    new_routes = routes.temporal[get_kind(routes.temporal) == NEW]
    yearly_miles = (
        new_routes.set_index("instdate")
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
    st.caption(
        "Excludes routes that replaced existing ones, such as a conventional lane being upgraded to a protected one. See [Projects](projects) for those."
    )


def render_cumulative_miles(routes: RouteData) -> None:
    facility_codes = (
        routes.temporal["facilitycl"].fillna("").map(normalize_facility_code)
    )
    unknown_codes = sorted(set(facility_codes) - set(FACILITY_ORDER))
    if unknown_codes:
        unknown_list = ", ".join(code or "(blank)" for code in unknown_codes)
        st.warning(f"Excluding routes with unknown facility types: {unknown_list}")

    year_starts = pd.date_range(routes.earliest, routes.latest, freq="YS")
    stacked_miles = (
        pd.DataFrame(
            {
                year: routes.existing_at(year)
                .groupby(facility_codes)["length_miles"]
                .sum()
                for year in year_starts
            }
        )
        .T.reindex(columns=FACILITY_ORDER)
        .fillna(0)
    )
    stacked_miles.columns = [get_facility_label(code) for code in FACILITY_ORDER]
    labels = stacked_miles.columns.tolist()

    # clicking a type in the legend hides/shows it, starting with all of them shown
    visible = alt.selection_point(
        fields=["facilitycl"],
        bind="legend",
        toggle="true",
        value=[{"facilitycl": label} for label in labels],
    )
    chart = (
        alt.Chart(
            stacked_miles.rename_axis("year")
            .reset_index()
            .melt(id_vars="year", var_name="facilitycl", value_name="miles")
        )
        .mark_area()
        .encode(
            x=alt.X("year:T", title="Year"),
            y=alt.Y("miles:Q", title="Miles", stack=True),
            color=alt.Color(
                "facilitycl:N",
                title="Type (click to toggle)",
                scale=alt.Scale(
                    domain=labels,
                    range=[FACILITY_STYLE[code]["color"] for code in FACILITY_ORDER],
                ),
                # below rather than beside, so it doesn't squeeze the chart on narrow screens
                legend=alt.Legend(orient="bottom", direction="vertical", labelLimit=0),
            ),
            # stack in the same order as the legend
            order=alt.Order("order:Q"),
            tooltip=[
                alt.Tooltip("year:T", title="Year", format="%Y"),
                alt.Tooltip("facilitycl:N", title="Type"),
                alt.Tooltip("miles:Q", title="Miles", format=",.1f"),
            ],
        )
        .transform_calculate(order=f"indexof({labels!r}, datum.facilitycl)")
        .add_params(visible)
        .transform_filter(visible)
        # fit the width to the page, but make the height the plot's, so the legend below doesn't shrink it
        .properties(
            height=300, autosize=alt.AutoSizeParams(type="fit-x", contains="padding")
        )
    )
    st.altair_chart(chart)
