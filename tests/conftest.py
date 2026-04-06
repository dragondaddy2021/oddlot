"""Shared pytest fixtures for oddlot tests."""
import os

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# ── Config from environment ────────────────────────────────────────────────────

def pytest_addoption(parser):
    parser.addoption(
        "--run-appium",
        action="store_true",
        default=False,
        help="Run Appium mobile tests (requires Appium server + Android emulator)",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-appium"):
        skip_appium = pytest.mark.skip(reason="Pass --run-appium to run Appium tests")
        for item in items:
            if "appium" in item.keywords:
                item.add_marker(skip_appium)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def supabase_url():
    url = os.environ.get("SUPABASE_URL", "")
    if not url:
        pytest.skip("SUPABASE_URL not set")
    return url.rstrip("/")


@pytest.fixture(scope="session")
def supabase_anon_key():
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not key:
        pytest.skip("SUPABASE_ANON_KEY not set")
    return key


@pytest.fixture(scope="session")
def base_url():
    return os.environ.get(
        "TEST_BASE_URL", "https://dragondaddy2021.github.io/oddlot"
    ).rstrip("/")


@pytest.fixture(scope="session")
def chrome_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,800")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(10)
    yield driver
    driver.quit()
