import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from branca.element import Element
from folium.plugins.timeline import Timeline, TimelineSlider

from bike_routes.data import load_mayors
from bike_routes.domain import RouteData


def render_hero() -> None:
    st.markdown(
        """\
        # NYC bike routes over time

        Explore how the NYC bicycle network has changed over time.
        """
    )


def render_map(routes: RouteData) -> None:
    """Uses the Folium Timeline plugin."""

    timeline_df = routes.temporal[
        ["geometry", "instdate", "ret_date", "facilitycl"]
    ].copy()
    timeline_df = timeline_df.rename(columns={"instdate": "start", "ret_date": "end"})
    timeline_df["end"] = timeline_df["end"].fillna(routes.latest)
    timeline_df["start"] = timeline_df["start"].dt.strftime("%Y-%m-%d")
    timeline_df["end"] = timeline_df["end"].dt.strftime("%Y-%m-%d")

    map_object = folium.Map(
        location=[routes.center_lat, routes.center_lon],
        zoom_start=10,
        tiles="CartoDB positron",
    )

    timeline = Timeline(
        timeline_df,
        # match the colors from the map
        # https://www.nyc.gov/html/dot/html/bicyclists/bikemaps.shtml
        style=folium.JsCode(
            """
            (feature) => {
                const facility = String(feature.properties.facilitycl || "").trim().toUpperCase();
                const colors = {
                    // protected
                    I: "#429058",
                    // conventional
                    II: "#53b5e9",
                    // shared lane or signed route
                    III: "#a864a3",
                    // link
                    L: "#acce67"
                };

                return {
                    color: colors[facility] || "#6b7280",
                    weight: 3,
                    opacity: 0.9
                };
            }
            """
        ),
    ).add_to(map_object)
    TimelineSlider(
        auto_play=True,
        show_ticks=True,
        enable_keyboard_controls=True,
        date_options="MMM D, YYYY",
    ).add_timelines(timeline).add_to(map_object)

    # make the date larger
    map_object.get_root().header.add_child(
        Element(
            """
            <style>
                .leaflet-timeline-control .time-text {
                    font-size: 2rem;
                    font-weight: bold;
                }
            </style>
            """
        )
    )

    st.iframe(map_object.get_root().render(), width="stretch", height=720)


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
    miles = [routes.miles_in_year(start.year) for start in year_starts]

    cumulative_figure = px.line(
        x=year_starts,
        y=miles,
        markers=True,
        labels={
            "x": "Year",
            "y": "Miles",
        },
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
