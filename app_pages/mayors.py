import streamlit as st

from bike_routes.data import load_routes
from bike_routes.views import render_mayors

st.subheader("Mayoral administrations")
st.markdown(
    "This compares route miles that were installed during each administration window. Mayor information from [Wikidata](https://www.wikidata.org/)."
)
routes = load_routes()
render_mayors(routes)
