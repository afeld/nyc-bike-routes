from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"
PAGES = ["app_pages/home.py", "app_pages/miles.py", "app_pages/mayors.py"]


@pytest.mark.parametrize("page", PAGES)
def test_page_runs_without_errors(page: str) -> None:
    app = AppTest.from_file(str(APP_PATH), default_timeout=120)
    app.run()
    if page != PAGES[0]:
        app.switch_page(page).run()

    assert not app.exception
