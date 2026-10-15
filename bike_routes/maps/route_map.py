from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from branca.element import Element, Figure
from folium.plugins import Fullscreen
from folium.plugins.timeline import Timeline, TimelineSlider

from bike_routes.data import get_mayor
from bike_routes.domain import RouteData
from bike_routes.facilities import (
    FACILITY_ORDER,
    get_facility_color,
    get_facility_label,
    normalize_facility_code,
)
from bike_routes.maps.base import add_basemap, get_bounds, remove_unused_assets
from bike_routes.maps.popups import get_popup_html

STYLE_PATH = Path(__file__).with_name("route_map.css")


def get_layer_name(facility_code: str) -> str:
    """HTML for the layer control, which doubles as the legend."""
    return (
        f'<span class="swatch" style="color: {get_facility_color(facility_code)};">'
        f"&#9632;</span> {get_facility_label(facility_code)}"
    )


def get_map_style_html() -> str:
    return f"<style>{STYLE_PATH.read_text()}</style>"


# the same for every visitor, so only build it once. Hashing all of the routes is almost as slow as building the map, so key on when they were updated.
@st.cache_data(hash_funcs={RouteData: lambda routes: routes.dataset_last_updated})
def get_map_html(routes: RouteData) -> str:
    """Uses the Folium Timeline plugin."""

    latest = routes.latest.strftime("%Y-%m-%d")
    # one layer per facility type, so they can be toggled
    features_by_facility: dict[str, list[dict]] = {
        facility_code: [] for facility_code in FACILITY_ORDER
    }
    features = routes.map_routes["features"]
    mayors = get_mayor(
        pd.to_datetime(
            pd.Series([feature["properties"]["instdate"] for feature in features])
        )
    )
    for feature, mayor in zip(features, mayors):
        facility_code = normalize_facility_code(feature["properties"]["facilitycl"])
        features_by_facility.setdefault(facility_code, []).append(
            {
                "type": "Feature",
                "geometry": feature["geometry"],
                "properties": {
                    "start": feature["properties"]["instdate"],
                    "end": feature["properties"]["ret_date"] or latest,
                    "facilitycl_color": get_facility_color(facility_code),
                    "popup": get_popup_html(
                        feature["properties"], facility_code, mayor
                    ),
                },
            }
        )

    # allow half zoom levels, so the routes fill narrow screens rather than being zoomed out by a whole level
    map_object = folium.Map(tiles=None, zoom_snap=0.5)
    remove_unused_assets(map_object)
    add_basemap(map_object)

    Fullscreen(
        position="topleft",
        title="Expand me",
        title_cancel="Exit me",
        force_separate_button=True,
    ).add_to(map_object)

    timelines = []
    for facility_code, features in features_by_facility.items():
        if not features:
            continue
        timeline = Timeline(
            {"type": "FeatureCollection", "features": features},
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
            on_each_feature=folium.JsCode(
                "(feature, layer) => layer.bindPopup(feature.properties.popup)"
            ),
        )
        # Timeline overrides the name in its constructor, so set it afterwards
        timeline.layer_name = get_layer_name(facility_code)
        timeline.add_to(map_object)
        timelines.append(timeline)

    TimelineSlider(
        auto_play=True,
        show_ticks=True,
        enable_keyboard_controls=True,
        date_options="YYYY",
    ).add_timelines(*timelines).add_to(map_object)

    map_object.fit_bounds(get_bounds(map_object))

    folium.LayerControl(position="topright", collapsed=False).add_to(map_object)

    root = map_object.get_root()
    assert isinstance(root, Figure)

    # make the date larger
    root.header.add_child(Element(get_map_style_html()))

    return root.render()


def render_map(routes: RouteData) -> None:
    # fill the rest of the screen on phones
    st.html(
        """
        <style>
            @media (max-width: 640px) {
                [data-testid="stElementContainer"]:has(> [data-testid="stIFrame"]) {
                    flex-basis: calc(100svh - 9rem);
                    height: calc(100svh - 9rem);
                }
            }
        </style>
        """
    )
    st.iframe(get_map_html(routes), height=500)
