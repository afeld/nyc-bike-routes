import streamlit as st

from bike_routes.data import load_mayors
from bike_routes.domain import RouteData


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
