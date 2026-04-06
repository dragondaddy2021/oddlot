"""Appium mobile tests for oddlot.

Requires:
  - Appium server running on localhost:4723
  - Android emulator or physical device connected
  - Pass --run-appium flag to pytest to enable

Run:
  pytest tests/test_appium.py -v --run-appium
"""
import pytest


# All tests in this file are skipped unless --run-appium is passed (see conftest.py)
pytestmark = pytest.mark.appium


@pytest.fixture(scope="module")
def appium_driver(base_url):
    """Create an Appium driver targeting Android Chrome."""
    try:
        from appium import webdriver as appium_webdriver
        from appium.options.android import UiAutomator2Options
    except ImportError:
        pytest.skip("appium-python-client not installed")

    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.browser_name = "Chrome"
    options.no_reset = True

    try:
        driver = appium_webdriver.Remote("http://localhost:4723", options=options)
    except Exception as exc:
        pytest.skip(f"Appium server not reachable: {exc}")

    driver.implicitly_wait(15)
    yield driver
    driver.quit()


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_mobile_homepage_loads(appium_driver, base_url):
    """Mobile browser should load the homepage successfully."""
    appium_driver.get(base_url + "/")
    assert "oddlot" in appium_driver.title.lower(), (
        f"Unexpected title: {appium_driver.title}"
    )


def test_mobile_disclaimer_visible(appium_driver, base_url):
    """Disclaimer banner should be visible on mobile viewport."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    appium_driver.get(base_url + "/")
    WebDriverWait(appium_driver, 15).until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(),'不構成投資建議')]")
        )
    )
    assert "不構成投資建議" in appium_driver.page_source


def test_mobile_stock_cards(appium_driver, base_url):
    """Stock cards should render and be scrollable on mobile."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    appium_driver.get(base_url + "/")
    WebDriverWait(appium_driver, 20).until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(),'殖利率')]")
        )
    )
    cards = appium_driver.find_elements(By.XPATH, "//*[contains(@class,'rounded-2xl')]")
    assert len(cards) >= 1, "No stock cards visible on mobile"
