FACILITY_ORDER = ["I", "II", "III", "L"]
# names come from the data dictionary:
# https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data
# colors come from the official map:
# https://www.nyc.gov/html/dot/html/bicyclists/bikemaps.shtml
FACILITY_STYLE = {
    "I": {
        "name": "Protected",
        "color": "#429058",
    },
    "II": {
        "name": "Conventional",
        "color": "#53b5e9",
    },
    "III": {
        "name": "Shared lane / signed route",
        "color": "#a864a3",
    },
    "L": {
        "name": "Link",
        "color": "#acce67",
    },
}
DEFAULT_FACILITY_COLOR = "#6b7280"


def normalize_facility_code(facilitycl: str | None) -> str:
    return (facilitycl or "").strip().upper()


def get_facility_color(facilitycl: str | None) -> str:
    return FACILITY_STYLE.get(
        normalize_facility_code(facilitycl), {"color": DEFAULT_FACILITY_COLOR}
    )["color"]


def get_facility_label(facility_code: str) -> str:
    style = FACILITY_STYLE.get(facility_code, {"name": "Other"})
    return f"{style['name']} ({facility_code})"
