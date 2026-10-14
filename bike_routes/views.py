import altair as alt
import pandas as pd
from IPython.display import display

from bike_routes.data import load_mayors
from bike_routes.domain import RouteData
from bike_routes.facilities import (
    FACILITY_ORDER,
    FACILITY_STYLE,
    get_facility_label,
    normalize_facility_code,
)


def display_light_and_dark(chart: alt.Chart) -> None:
    """Outputs a light and a dark version of the chart, for a Quarto cell with `renderings: [light, dark]` to switch between."""

    chart = chart.properties(width="container")
    display(chart)
    with alt.theme.enable("dark"):
        display(chart.configure(background="transparent"))


def render_yearly_miles(routes: RouteData) -> None:
    yearly_miles = (
        routes.temporal.set_index("instdate")
        .resample("YS")["length_miles"]
        .sum()
        .reset_index()
    )
    yearly_miles["year"] = yearly_miles["instdate"].dt.year
    yearly_miles = yearly_miles.rename(
        columns={
            "year": "Year",
            "length_miles": "Miles added",
        }
    )

    display_light_and_dark(
        alt.Chart(yearly_miles)
        .mark_line(point=True)
        .encode(
            x=alt.X("Year:Q", axis=alt.Axis(format="d")),
            y="Miles added:Q",
            tooltip=[alt.Tooltip("Year:Q", format="d"), "Miles added:Q"],
        )
    )


def render_cumulative_miles(routes: RouteData) -> None:
    facility_codes = (
        routes.temporal["facilitycl"].fillna("").map(normalize_facility_code)
    )
    unknown_codes = sorted(set(facility_codes) - set(FACILITY_ORDER))
    # in the chart's title rather than separate output, which would throw off the cell's light/dark renderings
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
    chart = (
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
        # fit the width to the page, but make the height the plot's, so the legend below doesn't shrink it
        .properties(
            height=300, autosize=alt.AutoSizeParams(type="fit-x", contains="padding")
        )
    )
    display_light_and_dark(chart)


def _load_mayors_with_miles(routes: RouteData) -> pd.DataFrame:
    mayor_df = load_mayors()
    mayor_df["miles_installed"] = mayor_df.apply(
        routes.miles_during_administration,
        axis=1,
    )
    return mayor_df


def render_mayors(routes: RouteData) -> None:
    mayor_df = _load_mayors_with_miles(routes)

    if mayor_df.empty:
        print("No mayor data was returned.")
        return

    display_light_and_dark(
        alt.Chart(mayor_df[["full_name", "miles_installed"]])
        .mark_bar()
        .encode(
            x=alt.X("miles_installed:Q", title="Miles installed"),
            y=alt.Y(
                "full_name:N",
                title="Mayor (most recent first)",
                sort=mayor_df.sort_values("start_date", ascending=False)[
                    "full_name"
                ].tolist(),
            ),
            tooltip=[
                alt.Tooltip("full_name:N", title="Mayor"),
                alt.Tooltip("miles_installed:Q", title="Miles installed", format=",.1f"),
            ],
        )
        .properties(height=800)
    )


def render_top_installers(routes: RouteData) -> None:
    mayor_df = _load_mayors_with_miles(routes)
    columns = ["full_name", "start_date", "end_date", "miles_installed"]

    display(
        mayor_df.sort_values("miles_installed", ascending=False)[columns]
        .style.hide(axis="index")
        .format(
            {"start_date": "{:%Y}", "end_date": "{:%Y}", "miles_installed": "{:.1f}"},
            na_rep="",
        )
        .relabel_index(
            ["Name", "Term start", "Term end", "Miles installed"], axis="columns"
        )
        .set_table_attributes('class="table table-sm"')
    )
