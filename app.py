from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent

import folium
import httpx
import pandas as pd
import plotly.express as px
import streamlit as st
from folium.plugins.timeline import Timeline, TimelineSlider
from geopandas import GeoDataFrame

DATA_URL = (
    "https://data.cityofnewyork.us/api/views/mzxg-pwib/rows.geojson?accessType=DOWNLOAD"
)
DATASET_METADATA_URL = "https://data.cityofnewyork.us/api/views/mzxg-pwib.json"
WIKIDATA_URL = "https://query.wikidata.org/sparql"
DATE_COLUMNS = [":created_at", "ret_date", "instdate"]


@dataclass
class RouteData:
    raw: GeoDataFrame
    temporal: GeoDataFrame
    projected: GeoDataFrame
    center_lat: float
    center_lon: float
    earliest: pd.Timestamp
    latest: pd.Timestamp
    dataset_last_updated: pd.Timestamp


st.set_page_config(
    page_title="NYC Bike Routes Over Time",
    page_icon="🚲",
    layout="wide",
)


def remove_timezone(series: pd.Series) -> pd.Series:
    if getattr(series.dt, "tz", None) is not None:
        return series.dt.tz_localize(None)
    return series


@st.cache_data
def load_routes() -> RouteData:
    response = httpx.get(DATA_URL, timeout=30.0)
    response.raise_for_status()
    geojson = response.json()

    metadata_response = httpx.get(DATASET_METADATA_URL, timeout=20.0)
    metadata_response.raise_for_status()
    metadata = metadata_response.json()

    raw = GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")

    temporal = raw.copy()
    for column in DATE_COLUMNS:
        temporal[column] = pd.to_datetime(temporal[column], errors="coerce")

    projected = temporal.to_crs(epsg=2263)
    projected["length_miles"] = projected.geometry.length / 5280
    temporal["length_miles"] = projected["length_miles"]

    temporal["instdate"] = remove_timezone(temporal["instdate"])
    temporal["ret_date"] = remove_timezone(temporal["ret_date"])

    metadata_updated_unix = metadata.get("rowsUpdatedAt") or metadata.get(
        "viewLastModified"
    )
    dataset_last_updated = pd.to_datetime(
        metadata_updated_unix,
        unit="s",
        errors="coerce",
        utc=True,
    )
    if pd.notna(dataset_last_updated):
        dataset_last_updated = dataset_last_updated.tz_convert(None)

    earliest = pd.concat([temporal["instdate"], temporal["ret_date"]]).min()
    latest = pd.concat([temporal["instdate"], temporal["ret_date"]]).max()

    projected_centroids = GeoDataFrame(
        geometry=projected.geometry.centroid,
        crs=projected.crs,
    ).to_crs(epsg=4326)
    center = projected_centroids.geometry.union_all().centroid

    return RouteData(
        raw=raw,
        temporal=temporal,
        projected=projected,
        center_lat=center.y,
        center_lon=center.x,
        earliest=earliest,
        latest=latest,
        dataset_last_updated=dataset_last_updated,
    )


@st.cache_data
def load_mayors(earliest: pd.Timestamp) -> pd.DataFrame:
    earliest_str = earliest.strftime("%Y-%m-%dT%H:%M:%SZ")
    query = dedent(
        f"""
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

        SELECT ?mayor ?mayorLabel ?start_date ?end_date WHERE {{
          ?mayor p:P39 ?statement.
          ?statement ps:P39 wd:Q785304.
          ?mayor wdt:P31 wd:Q5.
          OPTIONAL {{ ?statement pq:P580 ?start_date. }}
          OPTIONAL {{ ?statement pq:P582 ?end_date. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
          FILTER (
            (BOUND(?start_date) && ?start_date >= "{earliest_str}"^^xsd:dateTime)
            || (BOUND(?end_date) && ?end_date >= "{earliest_str}"^^xsd:dateTime)
          )
        }}
        ORDER BY ?start_date
        """
    ).strip()

    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "BikeRoutes/0.0 (https://afeld.me/; aidan.feldman@gmail.com)",
    }

    response = httpx.get(
        WIKIDATA_URL, params={"query": query}, headers=headers, timeout=20.0
    )
    response.raise_for_status()
    data = response.json()

    mayor_df = pd.json_normalize(data["results"]["bindings"])
    if mayor_df.empty:
        return pd.DataFrame(
            columns=["full_name", "start_date", "end_date", "miles_installed"]
        )

    mayor_df = mayor_df.rename(columns={"mayorLabel.value": "full_name"})
    mayor_df["start_date"] = pd.to_datetime(
        mayor_df["start_date.value"], errors="coerce", utc=True
    )
    mayor_df["end_date"] = pd.to_datetime(
        mayor_df["end_date.value"], errors="coerce", utc=True
    )
    mayor_df["start_date"] = mayor_df["start_date"].dt.tz_convert(None)
    mayor_df["end_date"] = mayor_df["end_date"].dt.tz_convert(None)
    return mayor_df


def miles_in_year(routes: GeoDataFrame, year: int) -> float:
    cutoff = pd.Timestamp(year=year, month=1, day=1)
    was_previously_installed = routes["instdate"] < cutoff
    still_exists = routes["ret_date"].isna() | (routes["ret_date"] >= cutoff)
    return routes.loc[was_previously_installed & still_exists, "length_miles"].sum()


def miles_during_administration(routes: GeoDataFrame, row: pd.Series) -> float:
    start = row["start_date"]
    end = row["end_date"]

    if pd.isna(start):
        return 0.0

    if pd.isna(end):
        mask = routes["instdate"] >= start
    else:
        mask = (routes["instdate"] >= start) & (routes["instdate"] <= end)

    return routes.loc[mask, "length_miles"].sum()


def render_hero() -> None:
    st.markdown(
        """\
        # NYC bike routes over time

        Explore how the NYC bicycle network changed over time. Uses [Bike Routes from NYC Open Data](https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data).
        """
    )


def render_summary(routes: RouteData) -> None:
    total_routes = len(routes.temporal)
    total_miles = routes.temporal["length_miles"].sum()
    first_year = int(routes.earliest.year)
    latest_year = int(routes.latest.year)
    if pd.isna(routes.dataset_last_updated):
        last_updated = "Unknown"
    else:
        last_updated = routes.dataset_last_updated.strftime("%Y-%m-%d")

    summary_cols = st.columns(5)
    summary_cols[0].metric("Route segments", f"{total_routes:,}")
    summary_cols[1].metric("Total miles", f"{total_miles:,.1f}")
    summary_cols[2].metric("First record", f"{first_year}")
    summary_cols[3].metric("Latest record", f"{latest_year}")
    summary_cols[4].metric("Dataset updated", last_updated)


def render_map(routes: RouteData) -> None:
    """Uses the [Folium Timeline plugin](https://python-visualization.github.io/folium/latest/user_guide/plugins/timeline.html)."""

    # Timeline needs every feature to have an `end`` date, so open-ended segments use the latest recorded date.
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
    miles = [miles_in_year(routes.temporal, start.year) for start in year_starts]

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
        mayor_df = load_mayors(routes.earliest)
    except Exception as exc:  # pragma: no cover - external network dependency
        st.warning(f"Could not load mayor data from Wikidata: {exc}")
        return

    if mayor_df.empty:
        st.info("No mayor data was returned from Wikidata.")
        return

    mayor_df["miles_installed"] = mayor_df.apply(
        lambda row: miles_during_administration(routes.temporal, row),
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


def main() -> None:
    render_hero()

    with st.spinner("Loading bike route data..."):
        routes = load_routes()

    render_summary(routes)

    tabs = st.tabs(["Map", "Miles", "Mayors", "Data"])

    with tabs[0]:
        st.subheader("Bike network over time")
        render_map(routes)

    with tabs[1]:
        st.subheader("Miles added by year")
        st.markdown(
            "Route length is measured in the [EPSG:2263 coordinate system](https://epsg.io/2263) and converted from feet to miles."
        )
        render_yearly_miles(routes)

        st.subheader("Network miles by year")
        render_cumulative_miles(routes)

    with tabs[2]:
        st.subheader("Mayoral administrations")
        st.markdown(
            "This compares route miles that were installed during each administration window. Mayor information from [Wikidata](https://www.wikidata.org/)."
        )
        render_mayors(routes)

    with tabs[3]:
        st.subheader("Source data preview")
        render_data_preview(routes)


if __name__ == "__main__":
    main()
