import streamlit as st

from bike_routes.data import load_routes

st.set_page_config(
    page_title="NYC Bike Routes Over Time",
    page_icon="🚲",
    layout="wide",
)
# leave less space above the map on phones
st.html(
    """
    <style>
        @media (max-width: 640px) {
            [data-testid="stMainBlockContainer"] {
                padding-top: 4rem;
            }
            [data-testid="stMainBlockContainer"] [data-testid="stHeading"] h1 {
                font-size: 1.75rem;
            }
        }
    </style>
    """
)


def main() -> None:
    routes = load_routes()
    st.title("NYC bike routes over time")

    page = st.navigation(
        [
            st.Page("app_pages/home.py", title="Map", icon=":material/map:"),
            st.Page("app_pages/miles.py", title="Miles", icon=":material/show_chart:"),
            st.Page(
                "app_pages/projects.py",
                title="Projects",
                icon=":material/construction:",
            ),
            st.Page(
                "app_pages/mayors.py", title="Mayors", icon=":material/account_balance:"
            ),
        ],
        position="top",
    )
    page.run()

    st.space("medium")
    st.markdown(
        f"""\
        Uses [Bike Routes from NYC Open Data](https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data). Route length is measured in the [EPSG:2263 coordinate system](https://epsg.io/2263) and converted from feet to miles. Dataset updated {routes.formatted_last_updated}.

        [General NYC bike map info.](https://www.nyc.gov/html/dot/html/bicyclists/bikemaps.shtml) App created by [Aidan Feldman](https://api.afeld.me).
        """,
        text_alignment="center",
    )


if __name__ == "__main__":
    main()
