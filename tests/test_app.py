"""Loads index.html in a headless browser and checks that everything renders."""

import re
import threading
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

REPO_DIR = Path(__file__).resolve().parent.parent
PROTECTED_COLOR = "#429058"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args) -> None:
        pass


@pytest.fixture(scope="module")
def site_url() -> Iterator[str]:
    handler = partial(QuietHandler, directory=REPO_DIR)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
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


@pytest.fixture
def loaded_page(page: Page, site_url: str, errors: list[str]) -> Page:
    page.goto(site_url)
    expect(page.locator("#top-installers tr").first).to_be_visible()
    return page


def test_no_errors(loaded_page: Page, errors: list[str]) -> None:
    for chart_id in ["yearly-miles", "network-size", "mayors-chart"]:
        expect(loaded_page.locator(f"#{chart_id} > .marks")).to_be_visible()
    assert errors == []


def test_last_updated(loaded_page: Page) -> None:
    expect(loaded_page.locator("#last-updated")).to_have_text(
        re.compile(r"^\d{4}-\d{2}-\d{2}$")
    )


def test_top_installers(loaded_page: Page) -> None:
    rows = loaded_page.locator("#top-installers tr")
    expect(rows.first.locator("td").first).not_to_be_empty()
    miles = [
        float(miles.replace(",", ""))
        for miles in rows.locator("td:last-child").all_inner_texts()
    ]
    assert miles == sorted(miles, reverse=True)


def test_map_plays(loaded_page: Page) -> None:
    year = loaded_page.locator(".leaflet-timeline-control .time-text")
    first_year = year.inner_text()
    expect(year).not_to_have_text(first_year)
    expect(loaded_page.locator("#map path.leaflet-interactive").first).to_be_attached()


def test_map_legend_toggles(loaded_page: Page) -> None:
    routes = loaded_page.locator("#map path.leaflet-interactive")
    protected = routes.and_(loaded_page.locator(f'[stroke="{PROTECTED_COLOR}"]'))
    expect(protected.first).to_be_attached()

    checkbox = loaded_page.get_by_role("checkbox", name="Protected (I)")
    checkbox.uncheck()
    expect(protected).to_have_count(0)
    checkbox.check()
    expect(protected.first).to_be_attached()


def test_network_size_legend_toggles(loaded_page: Page) -> None:
    chart = loaded_page.locator("#network-size")
    areas = chart.locator(".mark-area path")
    expect(areas).to_have_count(4)

    conventional = chart.locator(".role-legend-label text", has_text="Conventional")
    conventional.click()
    expect(areas).to_have_count(3)
    conventional.click()
    expect(areas).to_have_count(4)
