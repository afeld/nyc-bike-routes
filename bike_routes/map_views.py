from html import escape
from typing import cast

import folium
import pandas as pd
import streamlit as st
from branca.element import Element, Figure
from folium.plugins import Fullscreen
from folium.plugins.timeline import Timeline, TimelineSlider
from folium.utilities import TypeBounds

from bike_routes.data import get_mayor
from bike_routes.domain import RouteData
from bike_routes.facilities import (
    FACILITY_ORDER,
    get_facility_color,
    get_facility_label,
    normalize_facility_code,
)


def get_layer_name(facility_code: str) -> str:
    """HTML for the layer control, which doubles as the legend."""
    return (
        f'<span class="swatch" style="color: {get_facility_color(facility_code)};">'
        f"&#9632;</span> {get_facility_label(facility_code)}"
    )


def get_popup_html(properties: dict, facility_code: str, mayor: str) -> str:
    """Details about a route, shown when it's clicked."""
    details = {
        "Type": (
            f'<span style="color: {get_facility_color(facility_code)};">&#9632;</span> '
            f"{get_facility_label(facility_code)}"
        ),
        "Installed": properties["instdate"][:4],
        "Mayor": escape(mayor),
    }

    rows = "".join(
        f"<dt>{label}</dt><dd>{value}</dd>" for label, value in details.items()
    )
    return (
        f'<div class="route-popup"><strong>{escape(properties["street"])}</strong>'
        f"<dl>{rows}</dl></div>"
    )


def get_bounds(map_object: folium.Map) -> TypeBounds:
    # the bounds are only missing when the map is empty
    return cast(TypeBounds, map_object.get_bounds())


def get_map_style_html() -> str:
    return """\
        <style>
            .leaflet-control-layers {
                font-size: 1.4rem;
                line-height: 1.5rem;

                .swatch {
                    font-size: 2rem;
                }
            }

            .route-popup {
                strong {
                    display: block;
                    margin-bottom: 0.25rem;
                    font-size: 1.1em;
                }

                dl {
                    display: grid;
                    grid-template-columns: auto auto;
                    gap: 0.1rem 0.75rem;
                    margin: 0;
                }

                dt {
                    color: #6b7280;
                    font-weight: normal;
                }

                dd {
                    margin: 0;
                }
            }

            .leaflet-timeline-control .time-text {
                font-size: 1.5rem;
                font-weight: bold;
            }

            /* they're hard to tap on phones, and the slider does the same thing */
            .leaflet-timeline-control .button-container :is(.prev, .next) {
                display: none;
            }
            /* big enough to tap, overriding the plugin's styles that are added later */
            .leaflet-container .leaflet-control.leaflet-timeline-control .button-container button {
                width: 40px;
                height: 40px;
            }
            /* the plugin draws the icons with borders, which Bootstrap's sizing squashes, e.g. the pause icon's two bars into one */
            .leaflet-timeline-control .button-container button::before,
            .leaflet-timeline-control .button-container button::after {
                box-sizing: content-box;
            }
            /* put the year beside the button rather than under it, so the controls cover less of the map */
            .leaflet-container .leaflet-control.leaflet-timeline-control {
                display: flex;
                align-items: center;
                gap: 0.75rem;

                .sldr-ctrl-container {
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    width: auto;
                }

                input[type="range"] {
                    flex: 1;
                }
            }
        </style>
        """


def render_map(routes: RouteData) -> None:
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
    # keep the base map out of the layer control
    folium.TileLayer("Esri.WorldGrayCanvas", control=False).add_to(map_object)

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
    st.iframe(map_object.get_root().render(), height=500)


def render_features_map(features: list[dict]) -> None:
    """A static map of the given routes, zoomed to fit them."""

    map_object = folium.Map(tiles=None)
    folium.TileLayer("Esri.WorldGrayCanvas").add_to(map_object)
    folium.GeoJson(
        {"type": "FeatureCollection", "features": features},
        style_function=lambda feature: {
            "color": get_facility_color(feature["properties"]["facilitycl"]),
            "weight": 5,
            "opacity": 0.9,
        },
    ).add_to(map_object)
    map_object.fit_bounds(get_bounds(map_object), padding=(20, 20))

    st.iframe(map_object.get_root().render(), height=400)
