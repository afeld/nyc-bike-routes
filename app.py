import streamlit as st

from bike_routes.data import load_routes
from bike_routes.views import render_hero

st.set_page_config(
    page_title="NYC Bike Routes Over Time",
    page_icon="🚲",
    layout="wide",
)


def main() -> None:
    routes = load_routes()
    render_hero(routes)

    page = st.navigation(
        [
            st.Page("app_pages/home.py", title="Map", icon=":material/map:"),
            st.Page("app_pages/miles.py", title="Miles", icon=":material/show_chart:"),
            st.Page(
                "app_pages/mayors.py", title="Mayors", icon=":material/account_balance:"
            ),
            st.Page("app_pages/data.py", title="Data", icon=":material/table_view:"),
        ],
        position="top",
    )
    page.run()

    st.space("medium")
    st.markdown(
        "Created by [Aidan Feldman](https://api.afeld.me).",
        text_alignment="center",
    )


if __name__ == "__main__":
    main()
