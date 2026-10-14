import pandas as pd

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


def enrich_facility_columns(df: pd.DataFrame) -> pd.DataFrame:
    enriched_df = df.copy()
    enriched_df["facilitycl_code"] = (
        enriched_df["facilitycl"].fillna("").astype(str).str.strip().str.upper()
    )
    enriched_df["facilitycl_name"] = enriched_df["facilitycl_code"].map(
        lambda code: FACILITY_STYLE.get(code, {"name": "Other"})["name"]
    )
    enriched_df["facilitycl_label"] = enriched_df["facilitycl_code"].map(
        lambda code: (
            f"{FACILITY_STYLE[code]['name']} ({code})"
            if code in FACILITY_STYLE
            else f"Other ({code})"
        )
    )
    enriched_df["facilitycl_color"] = enriched_df["facilitycl_code"].map(
        get_facility_color
    )
    return enriched_df
