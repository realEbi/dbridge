"""Unit tests for core/completion.py — three contexts with a fake registry."""

from dbridge.core.completion import complete

TABLES = ["users", "orders", "products"]
COLUMNS = {
    "users": ["id", "name", "email"],
    "orders": ["id", "user_id", "total"],
}
KEYWORDS = ["SELECT", "FROM", "WHERE", "JOIN"]


def _complete(sql, position=None):
    return complete(
        sql,
        list_tables_fn=lambda: TABLES,
        get_columns_fn=lambda t: COLUMNS.get(t, []),
        get_keywords_fn=lambda: KEYWORDS,
        position=position,
    )


# ── FROM / JOIN context ───────────────────────────────────────────────────────

def test_from_returns_tables():
    items = _complete("SELECT * FROM ")
    kinds = {i["kind"] for i in items}
    labels = [i["label"] for i in items]
    assert kinds == {"table"}
    assert "users" in labels
    assert "orders" in labels


def test_join_returns_tables():
    items = _complete("SELECT * FROM users JOIN ")
    assert all(i["kind"] == "table" for i in items)
    assert "orders" in [i["label"] for i in items]


def test_from_with_partial_prefix_returns_tables():
    items = _complete("SELECT * FROM use")
    assert all(i["kind"] == "table" for i in items)


# ── SELECT / WHERE context ────────────────────────────────────────────────────

def test_select_returns_columns_of_referenced_tables():
    # Cursor sits right after "SELECT " (byte offset 7), before the FROM clause.
    items = _complete("SELECT  FROM users", position=7)
    assert {i["kind"] for i in items} == {"column"}
    labels = [i["label"] for i in items]
    assert labels == ["id", "name", "email"]


def test_position_mid_string_classifies_from_prefix_only():
    sql = "SELECT  FROM users JOIN orders ON users.id = orders.user_id"
    items = _complete(sql, position=7)
    labels = [i["label"] for i in items]
    assert {i["kind"] for i in items} == {"column"}
    # Both tables are in scope even though they appear after the cursor.
    assert "email" in labels
    assert "total" in labels


def test_omitted_position_is_end_of_string():
    sql = "SELECT  FROM users"
    assert _complete(sql) == _complete(sql, position=len(sql))
    # ... and that is the pre-existing FROM behaviour: tables, not columns.
    assert {i["kind"] for i in _complete(sql)} == {"table"}


def test_multiline_select_position_returns_columns():
    items = _complete("SELECT \nFROM users", position=7)
    assert {i["kind"] for i in items} == {"column"}
    assert "name" in [i["label"] for i in items]


def test_position_zero_returns_keywords():
    items = _complete("SELECT * FROM users", position=0)
    assert {i["kind"] for i in items} == {"keyword"}


def test_out_of_range_position_does_not_raise():
    for pos in (-5, 9999):
        items = _complete("SELECT * FROM users", position=pos)
        assert isinstance(items, list)


def test_where_includes_columns_from_scope():
    items = _complete("SELECT id FROM orders WHERE ")
    labels = [i["label"] for i in items]
    assert "user_id" in labels
    assert "total" in labels


def test_column_detail_contains_table_prefix():
    items = _complete("SELECT id FROM users WHERE ")
    detail_map = {i["label"]: i["detail"] for i in items}
    assert detail_map["name"] == "users.name"


# ── Keyword fallback ──────────────────────────────────────────────────────────

def test_bare_sql_returns_keywords():
    items = _complete("")
    kinds = {i["kind"] for i in items}
    assert kinds == {"keyword"}
    labels = [i["label"] for i in items]
    assert "SELECT" in labels


def test_non_clause_position_returns_keywords():
    items = _complete("CREATE ")
    assert all(i["kind"] == "keyword" for i in items)


# ── Grace under malformed SQL ─────────────────────────────────────────────────

def test_malformed_sql_does_not_raise():
    items = _complete("SELECT *** FROM ;;;")
    # Should return something (keywords) without raising
    assert isinstance(items, list)


def test_truncated_sql_does_not_raise():
    items = _complete("SELECT id, name FR")
    assert isinstance(items, list)
