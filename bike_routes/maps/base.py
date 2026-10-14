"""Pieces shared by the maps."""

from typing import cast

import folium
from branca.element import Element, Figure
from folium.map import CustomPane
from folium.utilities import TypeBounds

# Free key for NYC's map tiles, from https://api-portal.nyc.gov (the "GeoServer Tile Service User" product). It's visible in the page anyway, since it's part of each tile's URL.
NYC_API_KEY = "4e037ecaa17d47c8ac52942761633271"
NYC_TILES_URL = "https://api.nyc.gov/geoserver/gwc/service/tms/1.0.0"
NYC_ATTRIBUTION = '© <a href="https://www.nyc.gov/">City of New York</a>'
# above the routes, so they don't cover the street names, but below popups
LABELS_PANE = "labels"


class Basemap(folium.TileLayer):
    """NYC's own basemap, with parks, streets, and buildings. See https://finder.nyc.gov/nyc-lib/tiles/."""

    def __init__(self) -> None:
        super().__init__(
            tiles=(
                f"{NYC_TILES_URL}/carto%3Abasemap@EPSG%3A900913@jpg/{{z}}/{{x}}/{{y}}.jpg"
                f"?Key={NYC_API_KEY}"
            ),
            attr=NYC_ATTRIBUTION,
            name="Basemap",
            # keep it out of the layer control
            control=False,
            tms=True,
            min_native_zoom=8,
            max_zoom=19,
            max_native_zoom=19,
            # the extent of the tiles
            bounds=[[39.3682, -75.9374], [42.0329, -71.7187]],
            # sharper on high-resolution screens, by using tiles from a zoom level further in
            detect_retina=True,
        )


class Labels(folium.TileLayer):
    """NYC's labels for the basemap, e.g. street and neighborhood names."""

    def __init__(self) -> None:
        super().__init__(
            tiles=(
                f"{NYC_TILES_URL}/carto%3Alabel@EPSG%3A900913@png8/{{z}}/{{x}}/{{y}}.png8"
                f"?Key={NYC_API_KEY}"
            ),
            attr=NYC_ATTRIBUTION,
            name="Labels",
            control=False,
            overlay=True,
            tms=True,
            max_zoom=19,
            max_native_zoom=19,
            # the extent of the tiles
            bounds=[[40.0341, -74.2727], [41.2919, -71.9101]],
            pane=LABELS_PANE,
            # not detect_retina, which would halve the size of the text
        )


def add_basemap(map_object: folium.Map) -> None:
    Basemap().add_to(map_object)
    # let clicks through to the routes below
    CustomPane(LABELS_PANE, z_index=450).add_to(map_object)
    Labels().add_to(map_object)

    # halos around the text, so it's readable on top of the routes
    root = map_object.get_root()
    assert isinstance(root, Figure)
    root.header.add_child(
        Element(
            f"""
            <style>
                .leaflet-{LABELS_PANE}-pane {{
                    filter: drop-shadow(0 0 1px #fff) drop-shadow(0 0 1px #fff) drop-shadow(0 0 1px #fff);
                }}
            </style>
            """
        )
    )


def get_bounds(map_object: folium.Map) -> TypeBounds:
    # the bounds are only missing when the map is empty
    return cast(TypeBounds, map_object.get_bounds())
