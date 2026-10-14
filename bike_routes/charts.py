import altair as alt
import pandas as pd
from IPython.display import display

from bike_routes.domain import RouteData
from bike_routes.facilities import (
    FACILITY_ORDER,
    FACILITY_STYLE,
    get_facility_label,
    normalize_facility_code,
)


def yearly_miles_chart(routes: RouteData) -> alt.Chart:
    yearly_miles = (
        routes.temporal.set_index("instdate")
        .resample("YS")["length_miles"]
        .sum()
        .reset_index()
    )
    yearly_miles["year"] = yearly_miles["instdate"].dt.year

    return (
        alt.Chart(yearly_miles[["year", "length_miles"]])
        .mark_line(point=True)
        .encode(
            x=alt.X("year:Q", title="Year", axis=alt.Axis(format="d")),
            y=alt.Y("length_miles:Q", title="Miles added"),
            tooltip=[
                alt.Tooltip("year:Q", title="Year", format="d"),
                alt.Tooltip("length_miles:Q", title="Miles added", format=",.1f"),
            ],
        )
        .properties(width="container", height=350)
    )


def network_size_chart(routes: RouteData) -> alt.Chart:
    facility_codes = (
        routes.temporal["facilitycl"].fillna("").map(normalize_facility_code)
    )
    unknown_codes = sorted(set(facility_codes) - set(FACILITY_ORDER))
    title = ""
    if unknown_codes:
        unknown_list = ", ".join(code or "(blank)" for code in unknown_codes)
        title = f"Excluding routes with unknown facility types: {unknown_list}"

    year_starts = pd.date_range(routes.earliest, routes.latest, freq="YS")
    stacked_miles = pd.DataFrame(
        {
            year: routes.existing_at(year)
            .groupby(facility_codes)["length_miles"]
            .sum()
            for year in year_starts
        }
    ).T.reindex(columns=FACILITY_ORDER).fillna(0)
    stacked_miles.columns = [get_facility_label(code) for code in FACILITY_ORDER]
    labels = stacked_miles.columns.tolist()
    # clicking a type in the legend hides/shows it, starting with all of them shown
    visible = alt.selection_point(
        fields=["facilitycl"],
        bind="legend",
        toggle="true",
        value=[{"facilitycl": label} for label in labels],
    )

    return (
        alt.Chart(
            stacked_miles.rename_axis("year")
            .reset_index()
            .melt(id_vars="year", var_name="facilitycl", value_name="miles"),
            title=title,
        )
        .mark_area()
        .encode(
            x=alt.X("year:T", title="Year"),
            y=alt.Y("miles:Q", title="Miles", stack=True),
            color=alt.Color(
                "facilitycl:N",
                title="Type (click to toggle)",
                scale=alt.Scale(
                    domain=labels,
                    range=[FACILITY_STYLE[code]["color"] for code in FACILITY_ORDER],
                ),
                # below rather than beside, so it doesn't squeeze the chart on narrow screens
                legend=alt.Legend(orient="bottom", direction="vertical", labelLimit=0),
            ),
            # stack in the same order as the legend
            order=alt.Order("order:Q"),
            tooltip=[
                alt.Tooltip("year:T", title="Year", format="%Y"),
                alt.Tooltip("facilitycl:N", title="Type"),
                alt.Tooltip("miles:Q", title="Miles", format=",.1f"),
            ],
        )
        .transform_calculate(order=f"indexof({labels!r}, datum.facilitycl)")
        .add_params(visible)
        .transform_filter(visible)
        .properties(width="container", height=350)
    )


def mayors_with_miles(routes: RouteData, mayors: pd.DataFrame) -> pd.DataFrame:
    return mayors.assign(
        miles_installed=mayors.apply(routes.miles_during_administration, axis=1)
        if not mayors.empty
        else pd.Series(dtype=float)
    )


def mayors_chart(mayors: pd.DataFrame) -> alt.Chart:
    most_recent_first = mayors.sort_values("start_date", ascending=False)[
        "full_name"
    ].tolist()
    return (
        alt.Chart(mayors[["full_name", "miles_installed"]])
        .mark_bar()
        .encode(
            x=alt.X("miles_installed:Q", title="Miles installed"),
            y=alt.Y(
                "full_name:N",
                title="Mayor (most recent first)",
                sort=most_recent_first,
            ),
            tooltip=[
                alt.Tooltip("full_name:N", title="Mayor"),
                alt.Tooltip("miles_installed:Q", title="Miles installed", format=",.1f"),
            ],
        )
        .properties(width="container", height=800)
    )


def _years(dates: pd.Series) -> pd.Series:
    """Blank where unknown, such as the end of the current mayor's term."""
    return dates.dt.year.astype("Int64").astype("string").fillna("")


def top_installers_table(mayors: pd.DataFrame) -> pd.DataFrame:
    return (
        mayors[["full_name", "start_date", "end_date", "miles_installed"]]
        .sort_values("miles_installed", ascending=False)
        .assign(
            # years only
            start_date=_years(mayors["start_date"]),
            end_date=_years(mayors["end_date"]),
            miles_installed=mayors["miles_installed"].round(1),
        )
        .rename(
            columns={
                "full_name": "Name",
                "start_date": "Term start",
                "end_date": "Term end",
                "miles_installed": "Miles installed",
            }
        )
    )


def display_light_and_dark(chart: alt.Chart) -> None:
    """Outputs a light and a dark version of the chart, for a Quarto cell with `renderings: [light, dark]` to switch between."""

    display(chart)
    with alt.theme.enable("dark"):
        display(chart.configure(background="transparent"))
