"""Builds the site, then loads each page in a headless browser and checks that everything renders."""

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
PROTECTED_COLOR = "#429058"


class QuietHandler(SimpleHTTPRequestHandler):
    # serve /miles from miles.html, like GitHub Pages does
    def send_head(self):
        path = Path(self.translate_path(self.path))
        if not path.exists() and path.with_suffix(".html").exists():
            self.path += ".html"
        return super().send_head()

    def log_message(self, format, *args) -> None:
        pass


class Server(ThreadingHTTPServer):
    # the pages load dozens of modules at once, more than the default backlog of 5 connections
    request_queue_size = 128


@pytest.fixture(scope="session")
def site_url() -> Iterator[str]:
    subprocess.run(["npm", "run", "build"], cwd=REPO_DIR, check=True, capture_output=True)
    handler = partial(QuietHandler, directory=REPO_DIR / "dist")
    server = Server(("127.0.0.1", 0), handler)
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
def map_page(page: Page, site_url: str) -> Page:
    page.goto(site_url)
    expect(page.locator(".leaflet-timeline-control")).to_be_visible()
    return page


def test_map_plays(map_page: Page, errors: list[str]) -> None:
    year = map_page.locator(".leaflet-timeline-control .time-text")
    first_year = year.inner_text()
    expect(year).not_to_have_text(first_year)
    expect(map_page.locator(".leaflet-container path.leaflet-interactive").first).to_be_attached()
    assert errors == []


def test_map_legend_toggles(map_page: Page) -> None:
    protected = map_page.locator(f'.leaflet-container path[stroke="{PROTECTED_COLOR}"]')
    expect(protected.first).to_be_attached()

    checkbox = map_page.get_by_role("checkbox", name="Protected (I)")
    checkbox.uncheck()
    expect(protected).to_have_count(0)
    checkbox.check()
    expect(protected.first).to_be_attached()


def test_miles(page: Page, site_url: str, errors: list[str]) -> None:
    page.goto(f"{site_url}miles")
    charts = page.locator(".card svg[class^=plot]")
    expect(charts).to_have_count(2)
    expect(page.get_by_role("figure").get_by_text("Protected (I)")).to_be_visible()
    assert errors == []


def test_network_size_types_toggle(page: Page, site_url: str) -> None:
    page.goto(f"{site_url}miles")
    areas = page.locator(".card svg[class^=plot]").nth(1).locator("[aria-label=area] path")
    expect(areas).to_have_count(4)

    conventional = page.get_by_role("checkbox", name="Conventional (II)")
    conventional.uncheck()
    expect(areas).to_have_count(3)
    conventional.check()
    expect(areas).to_have_count(4)


def test_mayors(page: Page, site_url: str, errors: list[str]) -> None:
    page.goto(f"{site_url}mayors")
    expect(page.locator(".card svg[class^=plot]")).to_have_count(1)

    rows = page.locator("table tbody tr")
    expect(rows.first).to_be_visible()
    miles = [float(text) for text in rows.locator("td:last-child").all_inner_texts()]
    assert miles == sorted(miles, reverse=True)

    page.get_by_placeholder("Search mayors…").fill("Bloomberg")
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("Michael Bloomberg")

    expect(page.locator("#last-updated")).to_have_text(re.compile(r"^\d{4}-\d{2}-\d{2}$"))
    assert errors == []
