"""Pieces shared by the maps."""

from typing import cast

import folium
from folium.elements import JSCSSMixin
from folium.template import Template
from folium.utilities import TypeBounds


class Basemap(JSCSSMixin):
    """An OpenStreetMap basemap, drawn in the browser from vector tiles, so it's sharp on high-resolution screens. The tiles are read straight from a PMTiles archive of the whole planet, which only downloads the parts that are shown."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
            protomapsL.leafletLayer({
                url: "https://data.source.coop/protomaps/openstreetmap/v4.pmtiles",
                flavor: "white",
                lang: "en",
                attribution: '<a href="https://protomaps.com">Protomaps</a> © <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>',
            }).addTo({{ this._parent.get_name() }});
        {% endmacro %}
        """
    )

    def __init__(self) -> None:
        super().__init__()
        self.default_js = [
            (
                "protomaps-leaflet",
                "https://cdn.jsdelivr.net/npm/protomaps-leaflet@5.1.0/dist/protomaps-leaflet.js",
            )
        ]


def get_bounds(map_object: folium.Map) -> TypeBounds:
    # the bounds are only missing when the map is empty
    return cast(TypeBounds, map_object.get_bounds())
