import json
import re
from pathlib import Path

import pytest

from bike_routes.build_site import build_site


@pytest.fixture(scope="module")
def site_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    site_dir = tmp_path_factory.mktemp("site")
    build_site(site_dir)
    return site_dir


def test_index_has_charts(site_dir: Path) -> None:
    index = (site_dir / "index.html").read_text()
    match = re.search(r"const charts = (.*);", index)
    assert match
    charts = json.loads(match.group(1))
    assert set(charts) == {"yearly-miles", "network-size", "mayors-chart"}
    for chart_id, spec in charts.items():
        assert f'id="{chart_id}"' in index
        assert spec["datasets"], f"{chart_id} has no data"


def test_index_has_top_installers(site_dir: Path) -> None:
    index = (site_dir / "index.html").read_text()
    assert "<th>Miles installed</th>" in index
    assert "Michael Bloomberg" in index


def test_map(site_dir: Path) -> None:
    assert "Timeline" in (site_dir / "map.html").read_text()
