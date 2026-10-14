import pandas as pd
import streamlit as st

from bike_routes.data import get_mayor
from bike_routes.domain import RouteData
from bike_routes.facilities import (
    get_facility_label,
    normalize_facility_code,
)
from bike_routes.maps.project_map import render_features_map

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
