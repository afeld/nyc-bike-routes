"""Works out which routes replaced others, e.g. a conventional lane being upgraded to a protected one."""

import pandas as pd
from geopandas import GeoDataFrame, GeoSeries

# How far apart a retirement and an installation in the same place can be, for the new facility to count as replacing the old one.
REPLACEMENT_WINDOW = pd.Timedelta(days=60)
# How close a retired route needs to be to a new one to count as in the same place, allowing for the lines being drawn on different sides of the street.
REPLACEMENT_DISTANCE_FEET = 50.0
# How much of a new route needs to be in the same place as retired ones, for it to count as replacing them.
REPLACEMENT_MIN_OVERLAP = 0.8


def pair_with_retired_routes(
    temporal: pd.DataFrame, routes: GeoSeries, retired_areas: GeoSeries
) -> pd.DataFrame:
    """Each route with the ones retired near it, around when it was installed. Returns the indexes of the `new` and `old` routes, and the `gap` between the installation and retirement."""
    new_positions, old_positions = retired_areas.sindex.query(
        routes, predicate="intersects"
    )
    pairs = pd.DataFrame(
        {
            "new": routes.index[new_positions],
            "old": retired_areas.index[old_positions],
        }
    )
    pairs["gap"] = abs(
        temporal["instdate"].loc[pairs["new"]].to_numpy()
        - temporal["ret_date"].loc[pairs["old"]].to_numpy()
    )
    return pairs[(pairs["new"] != pairs["old"]) & (pairs["gap"] <= REPLACEMENT_WINDOW)]


def get_overlap(
    routes: GeoSeries, retired_areas: GeoSeries, pairs: pd.DataFrame
) -> pd.Series:
    """The fraction of each new route that's covered by the retired ones it's paired with. They're combined, since they may have been split up differently."""
    retired_nearby = (
        GeoDataFrame(pairs[["new"]], geometry=retired_areas.loc[pairs["old"]].values)
        .dissolve(by="new")
        .geometry
    )
    new_routes = GeoSeries(routes.loc[retired_nearby.index])
    return new_routes.intersection(retired_nearby).length / new_routes.length


def choose_closest(routes: GeoSeries, pairs: pd.DataFrame) -> pd.DataFrame:
    """If multiple routes were retired around when a new one was installed, use the closest in time, then the closest in shape."""
    distance = (
        GeoSeries(routes.loc[pairs["new"]])
        .hausdorff_distance(GeoSeries(routes.loc[pairs["old"]]), align=False)
        .to_numpy()
    )
    return (
        pairs.assign(distance=distance)
        .sort_values(["gap", "distance"])
        .drop_duplicates("new")
    )


def find_replaced_facilities(temporal: pd.DataFrame) -> pd.Series:
    """The facility class that each route replaced, i.e. the one retired from the same place around when the route was installed. Missing for routes that were new.

    This matches on location rather than street segment IDs, since a street is sometimes split into different segments when it's redone."""
    # in feet
    routes = temporal.geometry.to_crs(epsg=2263)
    retired_areas = routes[temporal["ret_date"].notna()].buffer(
        REPLACEMENT_DISTANCE_FEET
    )

    pairs = pair_with_retired_routes(temporal, routes, retired_areas)
    overlap = get_overlap(routes, retired_areas, pairs)
    # skip routes that are mostly somewhere new
    pairs = pairs[pairs["new"].map(overlap) >= REPLACEMENT_MIN_OVERLAP]
    replaced = choose_closest(routes, pairs)

    return (
        temporal["facilitycl"]
        .loc[replaced["old"]]
        .set_axis(replaced["new"])
        .reindex(temporal.index)
    )
