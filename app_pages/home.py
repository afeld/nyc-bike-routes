import streamlit as st

from bike_routes.data import load_routes
from bike_routes.views import render_map, render_summary

routes = load_routes()

render_summary(routes)

st.subheader("Bike network over time")
render_map(routes)
