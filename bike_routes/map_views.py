import folium
import streamlit as st
from branca.element import Element
from folium.plugins.timeline import Timeline, TimelineSlider

from bike_routes.domain import RouteData
from bike_routes.facilities import (
    DEFAULT_FACILITY_COLOR,
    FACILITY_ORDER,
    FACILITY_STYLE,
    get_facility_color,
    normalize_facility_code,
)


def get_layer_name(facility_code: str) -> str:
    """HTML for the layer control, which doubles as the legend."""
    style = FACILITY_STYLE.get(facility_code)
    color = style["color"] if style else DEFAULT_FACILITY_COLOR
    name = style["name"] if style else "Other"
    return (
        f'<span class="swatch" style="color: {color};">&#9632;</span> '
        f"{name} ({facility_code})"
    )


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

            .leaflet-timeline-control .time-text {
                font-size: 1.5rem;
                font-weight: bold;
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
    for feature in routes.map_routes["features"]:
        facility_code = normalize_facility_code(feature["properties"]["facilitycl"])
        features_by_facility.setdefault(facility_code, []).append(
            {
                "type": "Feature",
                "geometry": feature["geometry"],
                "properties": {
                    "start": feature["properties"]["instdate"],
                    "end": feature["properties"]["ret_date"] or latest,
                    "facilitycl_color": get_facility_color(facility_code),
                },
            }
        )

    map_object = folium.Map(
        location=[routes.center_lat, routes.center_lon],
        zoom_start=10,
        tiles=None,
    )
    # keep the base map out of the layer control
    folium.TileLayer("Esri.WorldGrayCanvas", control=False).add_to(map_object)

    folium.plugins.Fullscreen(
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

    folium.LayerControl(position="topright", collapsed=False).add_to(map_object)

    root = map_object.get_root()

    # make the date larger
    root.header.add_child(Element(get_map_style_html()))

    st.iframe(map_object.get_root().render(), height=500)
