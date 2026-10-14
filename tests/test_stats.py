import pandas as pd
import pytest

from bike_routes.stats import mayors_with_miles, network_size, yearly_miles


@pytest.fixture
def routes() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "instdate": pd.to_datetime(["2000-06-01", "2001-03-01", "2002-09-01"]),
            "ret_date": pd.to_datetime([None, "2002-06-01", None]),
            "facilitycl": ["I", "II", "I"],
            "length_miles": [1.0, 2.0, 4.0],
        }
    )


def test_yearly_miles(routes: pd.DataFrame) -> None:
    assert yearly_miles(routes).to_dict("records") == [
        {"year": 2000, "miles": 1.0},
        {"year": 2001, "miles": 2.0},
        {"year": 2002, "miles": 4.0},
    ]


def test_network_size(routes: pd.DataFrame) -> None:
    assert network_size(routes).to_dict("records") == [
        {"year": 2001, "type": "I", "miles": 1.0},
        {"year": 2002, "type": "I", "miles": 1.0},
        {"year": 2002, "type": "II", "miles": 2.0},
    ]


def test_mayors_with_miles(routes: pd.DataFrame) -> None:
    mayors = pd.DataFrame(
        {
            "full_name": ["Earlier", "Current", "Unknown"],
            "start_date": pd.to_datetime(["1990-01-01", "2001-01-01", None]),
            "end_date": pd.to_datetime(["2000-12-31", None, None]),
        }
    )
    assert mayors_with_miles(routes, mayors)["miles"].tolist() == [1.0, 6.0, 0.0]
