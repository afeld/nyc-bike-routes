import streamlit as st

from bike_routes.data import load_routes
from bike_routes.views import render_data_preview

routes = load_routes()

st.subheader("Source data preview")
render_data_preview(routes)
