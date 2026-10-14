import altair as alt
import pandas as pd
import streamlit as st

from bike_routes.data import get_mayor, load_mayors
from bike_routes.domain import RouteData
from bike_routes.facilities import (
    FACILITY_ORDER,
    FACILITY_STYLE,
    get_facility_label,
    normalize_facility_code,
)
from bike_routes.map_views import render_features_map

NEW = "New"
REPLACED = "Replaced existing"
# codes from the data dictionary:
# https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data
BOROUGHS = {
    "1": "Manhattan",
    "2": "Bronx",
    "3": "Brooklyn",
    "4": "Queens",
    "5": "Staten Island",
}


def get_kind(temporal: pd.DataFrame) -> pd.Series:
    return temporal["replaced_facilitycl"].isna().map({True: NEW, False: REPLACED})


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


def render_projects(routes: RouteData) -> None:
    temporal = routes.temporal
    projects = (
        temporal.assign(
            year=temporal["instdate"].dt.year,
            mayor=get_mayor(temporal["instdate"]),
            kind=get_kind(temporal),
            facility=temporal["facilitycl"].map(normalize_facility_code),
            replaced=temporal["replaced_facilitycl"].map(
                normalize_facility_code, na_action="ignore"
            ),
        )
        .groupby(
            ["year", "street", "boro", "kind", "facility", "replaced"], dropna=False
        )
        .agg(
            length_miles=("length_miles", "sum"),
            # in order, in case the mayor changed partway through the year
            mayor=("mayor", lambda mayors: " / ".join(mayors.unique().sort_values())),
        )
        .reset_index()
    )
    projects["boro"] = projects["boro"].map(BOROUGHS)
    projects["facility"] = projects["facility"].map(get_facility_label)
    projects["replaced"] = (
        projects["replaced"].map(get_facility_label, na_action="ignore").fillna("")
    )

    year_col, kind_col = st.columns(2)
    years = sorted(projects["year"].dropna().unique(), reverse=True)
    year = year_col.selectbox(
        "Year", years, index=None, placeholder="All years", format_func=str
    )
    kinds = kind_col.pills(
        "Show", [NEW, REPLACED], selection_mode="multi", default=[NEW, REPLACED]
    )

    if year is not None:
        projects = projects[projects["year"] == year]
    projects = projects[projects["kind"].isin(kinds)]

    projects = projects.sort_values("length_miles", ascending=False)
    event = st.dataframe(
        projects,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_order=[
            "year",
            "mayor",
            "street",
            "boro",
            "facility",
            "replaced",
            "length_miles",
        ],
        column_config={
            "year": st.column_config.NumberColumn("Year", format="%d"),
            "mayor": "Mayor",
            "street": "Street",
            "boro": "Borough",
            "facility": "Type",
            "replaced": "Replaced",
            "length_miles": st.column_config.NumberColumn("Miles", format="%.2f"),
        },
    )

    if event.selection.rows:
        project = projects.iloc[event.selection.rows[0]]
        render_features_map(get_project_features(routes, project))
    else:
        st.caption("Select a row to see it on a map.")


def get_project_features(routes: RouteData, project: pd.Series) -> list[dict]:
    """The map routes that make up a row of the projects table."""

    def is_in_project(properties: dict) -> bool:
        replaced = properties["replaced_facilitycl"]
        return (
            properties["instdate"][:4] == str(project["year"])
            and properties["street"] == project["street"]
            and BOROUGHS.get(properties["boro"]) == project["boro"]
            and get_facility_label(normalize_facility_code(properties["facilitycl"]))
            == project["facility"]
            and (
                get_facility_label(normalize_facility_code(replaced))
                if replaced
                else ""
            )
            == project["replaced"]
        )

    return [
        feature
        for feature in routes.map_routes["features"]
        if feature["properties"]["instdate"] and is_in_project(feature["properties"])
    ]


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


def render_mayors(routes: RouteData) -> None:
    mayor_df = load_mayors()

    if mayor_df.empty:
        st.info("No mayor data was returned.")
        return

    mayor_df["miles_installed"] = mayor_df.apply(
        routes.miles_during_administration,
        axis=1,
    )
    # the current mayor's term runs through the latest data
    years_in_office = (
        mayor_df["end_date"].fillna(routes.latest) - mayor_df["start_date"]
    ).dt.days / 365.25
    # a mayor who served less than a day installed nothing, which would otherwise be 0 / 0
    mayor_df["miles_per_year"] = (mayor_df["miles_installed"] / years_in_office).fillna(
        0
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

    st.dataframe(
        mayor_df.sort_values("miles_installed", ascending=False),
        hide_index=True,
        column_order=[
            "full_name",
            "start_date",
            "end_date",
            "miles_installed",
            "miles_per_year",
        ],
        column_config={
            "full_name": "Name",
            "start_date": st.column_config.DateColumn("Term start", format="YYYY"),
            "end_date": st.column_config.DateColumn("Term end", format="YYYY"),
            "miles_installed": "Miles installed",
            "miles_per_year": st.column_config.NumberColumn(
                "Miles per year in office", format="%.1f"
            ),
        },
    )
