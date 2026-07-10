import folium
import streamlit as st
from branca.element import Element
from folium.plugins.timeline import Timeline, TimelineSlider

from bike_routes.domain import RouteData
from bike_routes.facilities import (
    FACILITY_ORDER,
    FACILITY_STYLE,
    enrich_facility_columns,
)


def get_map_legend_html() -> str:
    items_html = "".join(
        f'<div><span style="color: {FACILITY_STYLE[facility_code]["color"]};">&#9632;</span> '
        f"{FACILITY_STYLE[facility_code]['name']} ({facility_code})</div>"
        for facility_code in FACILITY_ORDER
    )
    return (
        '<div class="legend">'
        '<div style="font-weight: bold; margin-bottom: 0.5rem;">Type</div>'
        f"{items_html}"
        "</div>"
    )


def get_map_style_html() -> str:
    return """\
        <style>
            .legend {
                position: fixed;
                top: 2rem;
                right: 2rem;
                z-index: 9999;
                background: rgba(255, 255, 255, 0.95);
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 0.75rem;
                font-size: 1.4rem;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
                line-height: 1.5rem;

                span {
                    font-size: 2rem;
                }
            }

            .leaflet-timeline-control .time-text {
                font-size: 2rem;
                font-weight: bold;
            }
        </style>
        """


def render_map(routes: RouteData) -> None:
    """Uses the Folium Timeline plugin."""

    timeline_df = routes.temporal[
        ["geometry", "instdate", "ret_date", "facilitycl"]
    ].copy()
    timeline_df = enrich_facility_columns(timeline_df)
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
        style=folium.JsCode(
            """
            (feature) => {
                return {
                    color: feature.properties.facilitycl_color || "#6b7280",
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

    root = map_object.get_root()
    root.html.add_child(Element(get_map_legend_html()))

    # make the date larger
    root.header.add_child(Element(get_map_style_html()))

    st.iframe(map_object.get_root().render(), width="stretch", height=720)
