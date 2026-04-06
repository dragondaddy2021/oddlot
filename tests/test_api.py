"""API-level tests using requests.

Tests target:
- GitHub Pages frontend (HTTP reachability)
- Supabase REST API (data presence + RLS enforcement)
"""
from datetime import datetime, timezone, timedelta

import pytest
import requests


# ── Helpers ────────────────────────────────────────────────────────────────────

def _today_tw() -> str:
    """Return today's date in Taiwan time (UTC+8) as YYYY-MM-DD."""
    tz_tw = timezone(timedelta(hours=8))
    return datetime.now(tz=tz_tw).date().isoformat()


def _sb_headers(anon_key: str) -> dict:
    return {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
    }


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_homepage_loads(base_url):
    """GitHub Pages should serve the frontend with HTTP 200."""
    resp = requests.get(base_url + "/", timeout=15)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


def test_supabase_recommendations(supabase_url, supabase_anon_key):
    """Supabase should have today's ai_recommendations row."""
    today = _today_tw()
    url = f"{supabase_url}/rest/v1/ai_recommendations"
    resp = requests.get(
        url,
        headers=_sb_headers(supabase_anon_key),
        params={"date": f"eq.{today}", "select": "date,stocks"},
        timeout=15,
    )
    assert resp.status_code == 200, f"Supabase returned {resp.status_code}: {resp.text}"
    data = resp.json()
    assert len(data) >= 1, f"No recommendations found for {today}"


def test_supabase_rls_anon_can_read(supabase_url, supabase_anon_key):
    """Anon role must be able to SELECT from ai_recommendations (RLS policy check)."""
    url = f"{supabase_url}/rest/v1/ai_recommendations"
    resp = requests.get(
        url,
        headers=_sb_headers(supabase_anon_key),
        params={"select": "date", "limit": "1"},
        timeout=15,
    )
    assert resp.status_code == 200, (
        f"Anon read blocked (status {resp.status_code}). "
        "Run the 'anyone can read recommendations' RLS policy SQL."
    )


def test_supabase_rls_anon_cannot_write(supabase_url, supabase_anon_key):
    """Anon role must NOT be able to INSERT into ai_recommendations."""
    url = f"{supabase_url}/rest/v1/ai_recommendations"
    resp = requests.post(
        url,
        headers={**_sb_headers(supabase_anon_key), "Content-Type": "application/json"},
        json={"date": "2000-01-01", "stocks": [], "reasoning": "rls-test"},
        timeout=15,
    )
    assert resp.status_code in (401, 403), (
        f"Expected 401/403 for anon write, got {resp.status_code}. "
        "RLS may not be configured correctly."
    )


def test_recommendations_data_format(supabase_url, supabase_anon_key):
    """Today's picks should have 10 items, each with required fields."""
    today = _today_tw()
    url = f"{supabase_url}/rest/v1/ai_recommendations"
    resp = requests.get(
        url,
        headers=_sb_headers(supabase_anon_key),
        params={"date": f"eq.{today}", "select": "stocks"},
        timeout=15,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data, f"No row found for {today}"

    picks = data[0].get("stocks", [])
    assert len(picks) == 10, f"Expected 10 picks, got {len(picks)}"

    required_fields = {"symbol", "name", "price", "yield_rate", "pe_ratio", "reason"}
    for i, pick in enumerate(picks):
        missing = required_fields - pick.keys()
        assert not missing, f"Pick #{i} missing fields: {missing} — data: {pick}"
