"""Pieces shared by the maps."""

from typing import cast

import folium
from folium.utilities import TypeBounds

# Free key for NYC's map tiles, from https://api-portal.nyc.gov (the "GeoServer Tile Service User" product). It's visible in the page anyway, since it's part of each tile's URL.
NYC_API_KEY = "4e037ecaa17d47c8ac52942761633271"


class Basemap(folium.TileLayer):
    """NYC's own basemap, with parks, streets, and buildings. See https://finder.nyc.gov/nyc-lib/tiles/."""

    def __init__(self) -> None:
        super().__init__(
            tiles=(
                "https://api.nyc.gov/geoserver/gwc/service/tms/1.0.0/carto%3Abasemap@EPSG%3A900913@jpg/{z}/{x}/{y}.jpg"
                f"?Key={NYC_API_KEY}"
            ),
            attr='© <a href="https://www.nyc.gov/">City of New York</a>',
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


def get_bounds(map_object: folium.Map) -> TypeBounds:
    # the bounds are only missing when the map is empty
    return cast(TypeBounds, map_object.get_bounds())
