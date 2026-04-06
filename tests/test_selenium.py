"""Selenium end-to-end tests for the oddlot GitHub Pages frontend.

Requires headless Chrome via webdriver-manager (handled in conftest.py).
"""
import time

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


WAIT = 15  # seconds


def wait_for(driver, condition, timeout=WAIT):
    return WebDriverWait(driver, timeout).until(condition)


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_homepage_title(chrome_driver, base_url):
    """Page title should contain 'oddlot' (case-insensitive)."""
    chrome_driver.get(base_url + "/")
    wait_for(chrome_driver, EC.title_contains("ddlot"))
    assert "oddlot" in chrome_driver.title.lower()


def test_disclaimer_banner(chrome_driver, base_url):
    """Amber disclaimer banner must be visible on homepage."""
    chrome_driver.get(base_url + "/")
    banner = wait_for(
        chrome_driver,
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'不構成投資建議')]")),
    )
    assert banner.is_displayed()


def test_stock_cards_displayed(chrome_driver, base_url):
    """At least one stock card should render after data loads."""
    chrome_driver.get(base_url + "/")
    # Wait for skeleton to disappear and real cards to appear
    wait_for(
        chrome_driver,
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'殖利率')]")),
        timeout=20,
    )
    cards = chrome_driver.find_elements(By.XPATH, "//*[contains(@class,'rounded-2xl')]")
    assert len(cards) >= 1, "No stock cards found on homepage"


def test_navbar_links(chrome_driver, base_url):
    """Navbar should contain links for 首頁, 我的最愛, and 選股說明."""
    chrome_driver.get(base_url + "/")
    wait_for(chrome_driver, EC.presence_of_element_located((By.TAG_NAME, "nav")))

    nav = chrome_driver.find_element(By.TAG_NAME, "nav")
    nav_text = nav.text

    assert "首頁" in nav_text, "Missing 首頁 link in navbar"
    assert "我的最愛" in nav_text, "Missing 我的最愛 link in navbar"
    assert "選股說明" in nav_text, "Missing 選股說明 link in navbar"


def test_about_page(chrome_driver, base_url):
    """Clicking 選股說明 should navigate to the about page with 資料來源 text."""
    chrome_driver.get(base_url + "/")
    wait_for(chrome_driver, EC.presence_of_element_located((By.TAG_NAME, "nav")))

    about_link = wait_for(
        chrome_driver,
        EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'選股說明')]")),
    )
    about_link.click()

    wait_for(
        chrome_driver,
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'資料來源')]")),
    )
    assert "資料來源" in chrome_driver.page_source


def test_login_page(chrome_driver, base_url):
    """Login page should show the coming-soon message."""
    chrome_driver.get(base_url + "/login")
    wait_for(
        chrome_driver,
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(),'登入功能即將開放')]")
        ),
    )
    assert "登入功能即將開放" in chrome_driver.page_source


def test_footer_copyright(chrome_driver, base_url):
    """Footer should contain the copyright notice."""
    chrome_driver.get(base_url + "/")
    wait_for(
        chrome_driver,
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(),'Dragon')]")
        ),
    )
    assert "Dragon" in chrome_driver.page_source
    assert "2026" in chrome_driver.page_source
