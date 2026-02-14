"""Unit tests for SQL query validation in the text-to-SQL service."""

import pytest

from src.services.text_to_sql import _validate_sql

pytestmark = pytest.mark.unit


class TestValidateSQL:
    def test_valid_select(self):
        ok, err = _validate_sql("SELECT * FROM users")
        assert ok is True
        assert err == ""

    def test_valid_with_cte(self):
        ok, err = _validate_sql("WITH cte AS (SELECT 1) SELECT * FROM cte")
        assert ok is True

    def test_reject_insert(self):
        ok, err = _validate_sql("INSERT INTO users VALUES (1)")
        assert ok is False
        assert "forbidden" in err.lower() or "Only SELECT" in err

    def test_reject_update(self):
        ok, err = _validate_sql("UPDATE users SET name = 'x'")
        assert ok is False

    def test_reject_delete(self):
        ok, err = _validate_sql("DELETE FROM users")
        assert ok is False

    def test_reject_drop(self):
        ok, err = _validate_sql("DROP TABLE users")
        assert ok is False

    def test_reject_alter(self):
        ok, err = _validate_sql("ALTER TABLE users ADD COLUMN x INT")
        assert ok is False

    def test_reject_truncate(self):
        ok, err = _validate_sql("TRUNCATE users")
        assert ok is False

    def test_reject_empty(self):
        ok, err = _validate_sql("")
        assert ok is False
        assert "Empty" in err

    def test_reject_non_select(self):
        ok, err = _validate_sql("EXPLAIN SELECT 1")
        assert ok is False
        assert "Only SELECT" in err

    def test_select_with_semicolon(self):
        ok, err = _validate_sql("SELECT 1;")
        assert ok is True

    def test_case_insensitive(self):
        ok, err = _validate_sql("select * from users")
        assert ok is True

    def test_reject_grant(self):
        ok, err = _validate_sql("GRANT ALL ON users TO evil")
        assert ok is False
