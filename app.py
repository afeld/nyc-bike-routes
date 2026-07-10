from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import Any

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

    @property
    def total_routes(self) -> int:
        return len(self.temporal)

    @property
    def total_miles(self) -> float:
        return self.temporal["length_miles"].sum()

    @property
    def first_year(self) -> int:
        return int(self.earliest.year)

    @property
    def latest_year(self) -> int:
        return int(self.latest.year)

    @property
    def formatted_last_updated(self) -> str:
        if pd.isna(self.dataset_last_updated):
            return "Unknown"
        return self.dataset_last_updated.strftime("%Y-%m-%d")

    def miles_in_year(self, year: int) -> float:
        cutoff = pd.Timestamp(year=year, month=1, day=1)
        was_previously_installed = self.temporal["instdate"] < cutoff
        still_exists = self.temporal["ret_date"].isna() | (
            self.temporal["ret_date"] >= cutoff
        )
        return self.temporal.loc[
            was_previously_installed & still_exists, "length_miles"
        ].sum()

    def miles_during_administration(self, row: pd.Series) -> float:
        start = row["start_date"]
        end = row["end_date"]

        if pd.isna(start):
            return 0.0

        if pd.isna(end):
            mask = self.temporal["instdate"] >= start
        else:
            mask = (self.temporal["instdate"] >= start) & (
                self.temporal["instdate"] <= end
            )

        return self.temporal.loc[mask, "length_miles"].sum()


class RouteRepository:
    def __init__(
        self,
        data_url: str = DATA_URL,
        metadata_url: str = DATASET_METADATA_URL,
    ) -> None:
        self.data_url = data_url
        self.metadata_url = metadata_url

    def fetch_geojson(self, url: str, timeout: float = 20.0) -> dict[str, Any]:
        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def fetch_dataset_last_updated(self, metadata: dict[str, Any]) -> pd.Timestamp:
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
            return dataset_last_updated.tz_convert(None)
        return dataset_last_updated

    def prepare_temporal_routes(self, raw: GeoDataFrame) -> GeoDataFrame:
        temporal = raw.copy()
        for column in DATE_COLUMNS:
            temporal[column] = pd.to_datetime(temporal[column], errors="coerce")

        temporal["instdate"] = remove_timezone(temporal["instdate"])
        temporal["ret_date"] = remove_timezone(temporal["ret_date"])
        return temporal

    def project_routes_with_lengths(self, temporal: GeoDataFrame) -> GeoDataFrame:
        projected = temporal.to_crs(epsg=2263)
        projected["length_miles"] = projected.geometry.length / 5280
        temporal["length_miles"] = projected["length_miles"]
        return projected

    def get_route_date_range(
        self, temporal: GeoDataFrame
    ) -> tuple[pd.Timestamp, pd.Timestamp]:
        earliest = pd.concat([temporal["instdate"], temporal["ret_date"]]).min()
        latest = pd.concat([temporal["instdate"], temporal["ret_date"]]).max()
        return earliest, latest

    def get_map_center(self, projected: GeoDataFrame) -> tuple[float, float]:
        projected_centroids = GeoDataFrame(
            geometry=projected.geometry.centroid,
            crs=projected.crs,
        ).to_crs(epsg=4326)
        center = projected_centroids.geometry.union_all().centroid
        return center.y, center.x

    def load(self) -> RouteData:
        geojson = self.fetch_geojson(self.data_url, timeout=30.0)
        metadata = self.fetch_geojson(self.metadata_url)

        raw = GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")
        temporal = self.prepare_temporal_routes(raw)
        projected = self.project_routes_with_lengths(temporal)
        dataset_last_updated = self.fetch_dataset_last_updated(metadata)
        earliest, latest = self.get_route_date_range(temporal)
        center_lat, center_lon = self.get_map_center(projected)

        return RouteData(
            raw=raw,
            temporal=temporal,
            projected=projected,
            center_lat=center_lat,
            center_lon=center_lon,
            earliest=earliest,
            latest=latest,
            dataset_last_updated=dataset_last_updated,
        )


class MayorRepository:
    def __init__(self, url: str = WIKIDATA_URL) -> None:
        self.url = url
        self.headers = {
            "Accept": "application/sparql-results+json",
            "User-Agent": "BikeRoutes/0.0 (https://afeld.me/; aidan.feldman@gmail.com)",
        }

    def build_query(
        self, earliest: pd.Timestamp, dataset_last_updated: pd.Timestamp | None
    ) -> str:
        earliest_str = earliest.strftime("%Y-%m-%dT%H:%M:%SZ")
        if pd.notna(dataset_last_updated):
            latest_str = dataset_last_updated.strftime("%Y-%m-%dT%H:%M:%SZ")
            latest_start_filter = f'&& (!BOUND(?start_date) || ?start_date <= "{latest_str}"^^xsd:dateTime)'
        else:
            latest_start_filter = ""

        return dedent(
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
                (
                  (BOUND(?start_date) && ?start_date >= "{earliest_str}"^^xsd:dateTime)
                  || (BOUND(?end_date) && ?end_date >= "{earliest_str}"^^xsd:dateTime)
                )
                {latest_start_filter}
              )
            }}
            ORDER BY ?start_date
            """
        ).strip()

    def normalize_results(self, data: dict[str, Any]) -> pd.DataFrame:
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

    def load(
        self, earliest: pd.Timestamp, dataset_last_updated: pd.Timestamp | None
    ) -> pd.DataFrame:
        query = self.build_query(earliest, dataset_last_updated)
        response = httpx.get(self.url, params={"query": query}, headers=self.headers)
        response.raise_for_status()
        return self.normalize_results(response.json())


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
    return RouteRepository().load()


@st.cache_data
def load_mayors(
    earliest: pd.Timestamp, dataset_last_updated: pd.Timestamp | None
) -> pd.DataFrame:
    return MayorRepository().load(earliest, dataset_last_updated)


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


def main() -> None:
    render_hero()

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
