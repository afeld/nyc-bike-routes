import pandas as pd
import streamlit as st

from bike_routes.domain import RouteData
from bike_routes.repositories import MayorRepository, RouteRepository


@st.cache_data
def load_routes() -> RouteData:
    return RouteRepository().load()


@st.cache_data
def load_mayors(
    earliest: pd.Timestamp, dataset_last_updated: pd.Timestamp | None
) -> pd.DataFrame:
    return MayorRepository().load(earliest, dataset_last_updated)
