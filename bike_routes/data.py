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


def get_mayor(dates: pd.Series) -> pd.Series:
    """Who was mayor on each date."""
    mayors = load_mayors().sort_values("start_date")
    return pd.cut(
        dates,
        bins=[*mayors["start_date"], pd.Timestamp.max],
        right=False,
        labels=mayors["full_name"].tolist(),
    )
