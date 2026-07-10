import streamlit as st

from bike_routes.data import load_routes
from bike_routes.views import (
    render_cumulative_miles,
    render_data_preview,
    render_hero,
    render_map,
    render_mayors,
    render_summary,
    render_yearly_miles,
)

st.set_page_config(
    page_title="NYC Bike Routes Over Time",
    page_icon="🚲",
    layout="wide",
)


def main() -> None:
    render_hero()

    routes = load_routes()
    render_summary(routes)

    tabs = st.tabs(["Map", "Miles", "Mayors", "Data"])

    with tabs[0]:
        st.subheader("Bike network over time")
        render_map(routes)

    with tabs[1]:
        st.subheader("Miles added by year")
        st.markdown(
            "Route length is measured in the [EPSG:2263 coordinate system](https://epsg.io/2263) and converted from feet to miles."
        )
        render_yearly_miles(routes)

        st.subheader("Network miles by year")
        render_cumulative_miles(routes)

    with tabs[2]:
        st.subheader("Mayoral administrations")
        st.markdown(
            "This compares route miles that were installed during each administration window. Mayor information from [Wikidata](https://www.wikidata.org/)."
        )
        render_mayors(routes)

    with tabs[3]:
        st.subheader("Source data preview")
        render_data_preview(routes)


if __name__ == "__main__":
    main()
