import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from folium.plugins.timeline import Timeline, TimelineSlider

from bike_routes.data import load_mayors
from bike_routes.domain import RouteData


def render_hero() -> None:
    st.markdown(
        """\
        # NYC bike routes over time

        Explore how the NYC bicycle network changed over time. Uses [Bike Routes from NYC Open Data](https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data).
        """
    )


def render_summary(routes: RouteData) -> None:
    summary_cols = st.columns(5)
    summary_cols[0].metric("Route segments", f"{routes.total_routes:,}")
    summary_cols[1].metric("Total miles", f"{routes.total_miles:,.1f}")
    summary_cols[2].metric("First record", f"{routes.first_year}")
    summary_cols[3].metric("Latest record", f"{routes.latest_year}")
    summary_cols[4].metric("Dataset updated", routes.formatted_last_updated)


def render_map(routes: RouteData) -> None:
    """Uses the Folium Timeline plugin."""

    timeline_df = routes.temporal.loc[:, ["geometry", "instdate", "ret_date"]].copy()
    timeline_df = timeline_df.rename(columns={"instdate": "start", "ret_date": "end"})
    timeline_df["end"] = timeline_df["end"].fillna(routes.latest)
    timeline_df["start"] = timeline_df["start"].dt.strftime("%Y-%m-%d")
    timeline_df["end"] = timeline_df["end"].dt.strftime("%Y-%m-%d")

    map_object = folium.Map(
        location=[routes.center_lat, routes.center_lon],
        zoom_start=10,
        tiles="CartoDB positron",
    )

    timeline = Timeline(timeline_df).add_to(map_object)  # type: ignore[arg-type]
    TimelineSlider(
        auto_play=False,
        show_ticks=True,
        enable_keyboard_controls=True,
        date_options="MMM D, YYYY",
    ).add_timelines(timeline).add_to(map_object)

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
        labels={"year": "Year", "length_miles": "Miles added"},
    )
    figure.update_layout(margin=dict(l=20, r=20, t=60, b=20))
    st.plotly_chart(figure, width="stretch")


def render_cumulative_miles(routes: RouteData) -> None:
    year_starts = pd.date_range(routes.earliest, routes.latest, freq="YS")
    miles = [routes.miles_in_year(start.year) for start in year_starts]

    cumulative_figure = px.line(
        x=year_starts,
        y=miles,
        markers=True,
        labels={"x": "Year", "y": "Cumulative miles of bike routes"},
    )
    cumulative_figure.update_layout(margin=dict(l=20, r=20, t=60, b=20))
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
    display_df = mayor_df[
        ["full_name", "start_date", "end_date", "miles_installed"]
    ].sort_values("miles_installed", ascending=False)

    chart_figure = px.bar(
        mayor_df,
        x="full_name",
        y="miles_installed",
        labels={"full_name": "Mayor", "miles_installed": "Miles installed"},
    )
    chart_figure.update_layout(margin=dict(l=20, r=20, t=60, b=20), xaxis_tickangle=-35)
    st.plotly_chart(chart_figure, width="stretch")
    st.dataframe(display_df.reset_index(drop=True), width="stretch", hide_index=True)


def render_data_preview(routes: RouteData) -> None:
    st.dataframe(
        routes.temporal,
        width="stretch",
        hide_index=True,
    )
