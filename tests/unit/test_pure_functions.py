"""Unit tests for pure helper functions in the services layer."""

from datetime import date, timedelta

import pytest

from src.services.purchase import (
    _normalize_store_name,
    _parse_date,
    _resolve_date_range,
)

pytestmark = pytest.mark.unit


# -- _normalize_store_name --


class TestNormalizeStoreName:
    def test_basic(self):
        assert _normalize_store_name("Mercadona") == "mercadona"

    def test_with_apostrophe(self):
        assert _normalize_store_name("Trader Joe's") == "trader joes"

    def test_with_curly_apostrophe(self):
        assert _normalize_store_name("Trader Joe\u2019s") == "trader joes"

    def test_with_spaces(self):
        assert _normalize_store_name("  Lidl  ") == "lidl"


# -- _parse_date --


class TestParseDate:
    def test_valid_iso(self):
        assert _parse_date("2026-02-11") == date(2026, 2, 11)

    def test_none_returns_today(self):
        assert _parse_date(None) == date.today()


# -- _resolve_date_range --


class TestResolveDateRange:
    def test_today(self):
        today = date.today()
        assert _resolve_date_range("today", None, None) == (today, today)

    def test_this_week(self):
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        start, end = _resolve_date_range("this_week", None, None)
        assert start == monday
        assert end == today

    def test_this_month(self):
        today = date.today()
        start, end = _resolve_date_range("this_month", None, None)
        assert start == today.replace(day=1)
        assert end == today

    def test_last_month(self):
        today = date.today()
        first_of_this = today.replace(day=1)
        last_of_prev = first_of_this - timedelta(days=1)
        start, end = _resolve_date_range("last_month", None, None)
        assert start == last_of_prev.replace(day=1)
        assert end == last_of_prev

    def test_this_year(self):
        today = date.today()
        start, end = _resolve_date_range("this_year", None, None)
        assert start == today.replace(month=1, day=1)
        assert end == today

    def test_custom_dates_override_period(self):
        start, end = _resolve_date_range("this_month", "2026-01-01", "2026-01-31")
        assert start == date(2026, 1, 1)
        assert end == date(2026, 1, 31)

    def test_none_defaults(self):
        assert _resolve_date_range(None, None, None) == (None, None)
