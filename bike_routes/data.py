import pandas as pd
import streamlit as st

from bike_routes.domain import RouteData
from bike_routes.repositories import MayorSnapshotRepository, RouteSnapshotRepository


@st.cache_data
def load_routes() -> RouteData:
    return RouteSnapshotRepository().load()


@st.cache_data
def load_mayors() -> pd.DataFrame:
    return MayorSnapshotRepository().load()
