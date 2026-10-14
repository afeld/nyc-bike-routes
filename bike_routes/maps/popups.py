from html import escape

from bike_routes.facilities import get_facility_color, get_facility_label


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
