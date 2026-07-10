import streamlit as st

from bike_routes.data import load_routes
from bike_routes.views import render_cumulative_miles, render_yearly_miles

routes = load_routes()

st.subheader("Miles added by year")
render_yearly_miles(routes)

st.subheader("Network size")
render_cumulative_miles(routes)

st.markdown(
    "Route length is measured in the [EPSG:2263 coordinate system](https://epsg.io/2263) and converted from feet to miles."
)
