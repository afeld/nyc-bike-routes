"""Renders the site with Quarto, then loads it in a headless browser and checks that everything renders."""

import re
import subprocess
import threading
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

REPO_DIR = Path(__file__).resolve().parent.parent
PAGES = ["index.html", "miles.html", "mayors.html"]
PROTECTED_COLOR = "#429058"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args) -> None:
        pass


@pytest.fixture(scope="session")
def site_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    site_dir = tmp_path_factory.mktemp("site")
    subprocess.run(
        ["quarto", "render", "--output-dir", str(site_dir)],
        cwd=REPO_DIR,
        check=True,
        capture_output=True,
    )

    handler = partial(QuietHandler, directory=site_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()


@pytest.fixture
def errors(page: Page) -> list[str]:
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console",
        lambda message: errors.append(message.text) if message.type == "error" else None,
    )
    return errors


@pytest.mark.parametrize("path", PAGES)
def test_page_loads(page: Page, site_url: str, errors: list[str], path: str) -> None:
    page.goto(site_url + path)
    expect(page.get_by_text(re.compile(r"Dataset updated \d{4}-\d{2}-\d{2}"))).to_be_visible()
    page.wait_for_load_state("networkidle")
    assert errors == []


def visible_charts(page: Page):
    return page.locator(".cell-output-display:visible .vega-embed svg.marks")


def test_charts_switch_with_color_scheme(page: Page, site_url: str) -> None:
    page.goto(site_url + "miles.html")
    expect(visible_charts(page)).to_have_count(2)
    expect(page.locator(".light-content .vega-embed svg.marks").first).to_be_visible()

    page.locator(".quarto-color-scheme-toggle").first.click()
    expect(page.locator("body.quarto-dark")).to_be_attached()
    expect(visible_charts(page)).to_have_count(2)
    expect(page.locator(".dark-content .vega-embed svg.marks").first).to_be_visible()


def test_top_installers(page: Page, site_url: str) -> None:
    page.goto(site_url + "mayors.html")
    expect(visible_charts(page)).to_have_count(1)
    miles = [
        float(miles.replace(",", ""))
        for miles in page.locator("table tbody td:last-child").all_inner_texts()
    ]
    assert miles
    assert miles == sorted(miles, reverse=True)


def test_map_plays(page: Page, site_url: str) -> None:
    page.goto(site_url)
    map_frame = page.frame_locator("iframe").first
    year = map_frame.locator(".leaflet-timeline-control .time-text")
    expect(year).not_to_have_text(year.inner_text())
    routes = map_frame.locator(f'path.leaflet-interactive[stroke="{PROTECTED_COLOR}"]')
    expect(routes.first).to_be_attached()


def test_network_size_legend_toggles(page: Page, site_url: str) -> None:
    page.goto(site_url + "miles.html")
    # the second chart on the page, in the light version that's shown by default
    chart = page.locator(".light-content .vega-embed").nth(1)
    areas = chart.locator(".mark-area path")
    expect(areas).to_have_count(4)

    conventional = chart.locator(".role-legend-label text", has_text="Conventional")
    conventional.click()
    expect(areas).to_have_count(3)
    conventional.click()
    expect(areas).to_have_count(4)
