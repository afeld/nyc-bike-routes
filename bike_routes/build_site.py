"""Renders the snapshot in `data/` into a static site."""

import json
from pathlib import Path

import altair as alt
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from bike_routes.charts import (
    mayors_chart,
    mayors_with_miles,
    network_size_chart,
    top_installers_table,
    yearly_miles_chart,
)
from bike_routes.map_views import build_map
from bike_routes.repositories import MayorSnapshotRepository, RouteSnapshotRepository

SITE_DIR = Path(__file__).resolve().parent.parent / "site"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def build_site(site_dir: Path = SITE_DIR) -> None:
    routes = RouteSnapshotRepository().load()
    mayors = mayors_with_miles(routes, MayorSnapshotRepository().load())

    charts = {
        "yearly-miles": yearly_miles_chart(routes),
        "network-size": network_size_chart(routes),
        "mayors-chart": mayors_chart(mayors),
    }
    # escape "</" so the JSON can't close the <script> tag
    charts_json = json.dumps(
        {chart_id: chart.to_dict() for chart_id, chart in charts.items()}
    ).replace("</", "<\\/")

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape()
    )
    index = env.get_template("index.html").render(
        vega_version=alt.VEGA_VERSION,
        vegalite_version=alt.VEGALITE_VERSION,
        vegaembed_version=alt.VEGAEMBED_VERSION,
        charts=Markup(charts_json),
        top_installers_table=Markup(
            top_installers_table(mayors).to_html(index=False, border=0, na_rep="")
        ),
        last_updated=routes.formatted_last_updated,
    )

    site_dir.mkdir(exist_ok=True)
    (site_dir / "index.html").write_text(index)
    build_map(routes).save(site_dir / "map.html")


if __name__ == "__main__":
    build_site()
