"""Pieces shared by the maps."""

from typing import cast

import folium
from folium.elements import JSCSSMixin
from folium.map import CustomPane
from folium.template import Template
from folium.utilities import TypeBounds

# OpenFreeMap's minimal style. See https://openfreemap.org/quick_start/.
STYLE_URL = "https://tiles.openfreemap.org/styles/positron"
ATTRIBUTION = (
    '<a href="https://openfreemap.org">OpenFreeMap</a> '
    '© <a href="https://www.openmaptiles.org/">OpenMapTiles</a> '
    'Data from <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
)
# above the routes, so they don't cover the street names, but below popups
LABELS_PANE = "labels"


class Basemap(JSCSSMixin):
    """An OpenStreetMap basemap, drawn in the browser from vector tiles by MapLibre, so it's sharp on high-resolution screens and at half zoom levels. The style is split in two: the labels go in their own pane, above the routes."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
            fetch({{ this.style_url|tojson }})
                .then((response) => response.json())
                .then((style) => {
                    const isLabel = (layer) => layer.type === "symbol";
                    const labelLayers = style.layers.filter(isLabel).map((layer) => ({
                        ...layer,
                        // halos around the text, so it's readable on top of the routes
                        paint: {
                            ...layer.paint,
                            "text-halo-color": "#fff",
                            "text-halo-width": 2,
                        },
                    }));
                    L.maplibreGL({
                        style: { ...style, layers: style.layers.filter((layer) => !isLabel(layer)) },
                        attribution: {{ this.attribution|tojson }},
                    }).addTo({{ this._parent.get_name() }});
                    L.maplibreGL({
                        style: { ...style, layers: labelLayers },
                        pane: {{ this.labels_pane|tojson }},
                    }).addTo({{ this._parent.get_name() }});
                });
        {% endmacro %}
        """
    )

    def __init__(self) -> None:
        super().__init__()
        # MapLibre 5, since 6 is only published as an ES module, which can't be loaded with a plain script tag like Folium's
        self.default_js = [
            (
                "maplibre-gl",
                "https://cdn.jsdelivr.net/npm/maplibre-gl@5.24.0/dist/maplibre-gl.js",
            ),
            (
                "maplibre-gl-leaflet",
                "https://cdn.jsdelivr.net/npm/@maplibre/maplibre-gl-leaflet@0.1.4/leaflet-maplibre-gl.js",
            ),
        ]
        self.default_css = [
            (
                # Folium dedupes scripts and stylesheets by name together
                "maplibre-gl-css",
                "https://cdn.jsdelivr.net/npm/maplibre-gl@5.24.0/dist/maplibre-gl.css",
            ),
        ]
        self.style_url = STYLE_URL
        self.attribution = ATTRIBUTION
        self.labels_pane = LABELS_PANE


def add_basemap(map_object: folium.Map) -> None:
    # let clicks through to the routes below
    CustomPane(LABELS_PANE, z_index=450).add_to(map_object)
    Basemap().add_to(map_object)


def get_bounds(map_object: folium.Map) -> TypeBounds:
    # the bounds are only missing when the map is empty
    return cast(TypeBounds, map_object.get_bounds())
