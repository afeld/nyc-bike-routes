import folium
import streamlit as st

from bike_routes.facilities import get_facility_color
from bike_routes.maps.base import (
    MIN_ZOOM,
    add_basemap,
    get_bounds,
    remove_unused_assets,
)


def render_features_map(features: list[dict]) -> None:
    """A static map of the given routes, zoomed to fit them."""

    map_object = folium.Map(tiles=None, minZoom=MIN_ZOOM)
    remove_unused_assets(map_object)
    add_basemap(map_object)
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
