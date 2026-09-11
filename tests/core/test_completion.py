"""Unit tests for core/completion.py — three contexts with a fake registry."""

from dbridge.core.completion import (
    CompletionItem,
    _extract_tables_from_sql,
    complete,
)

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


# ── CompletionItem defaults ───────────────────────────────────────────────────

def test_completion_item_derives_insert_text_and_sort_key():
    item = CompletionItem(label="Users", kind="table")
    assert item.insert_text == "Users"
    assert item.sort_key == "users"


def test_completion_item_keeps_explicit_insert_text_and_sort_key():
    """__post_init__ must not overwrite values the caller supplied."""
    item = CompletionItem(
        label="Users", kind="table", insert_text="\"Users\"", sort_key="zzz"
    )
    assert item.insert_text == "\"Users\""
    assert item.sort_key == "zzz"


# ── cursor offsets are UTF-8 byte offsets ─────────────────────────────────────

def test_position_is_a_byte_offset_not_a_character_offset():
    """'né' is 3 bytes; the byte offset after it must still classify as FROM."""
    sql = "SELECT * FROM né"
    items = _complete(sql, position=len(sql.encode("utf-8")))
    assert {i["kind"] for i in items} == {"table"}


def test_offset_splitting_a_code_point_does_not_raise():
    """A split code point is dropped rather than raising (errors='ignore')."""
    sql = "SELECT * FROM né"
    # One byte into the two-byte 'é'.
    items = _complete(sql, position=len(sql.encode("utf-8")) - 1)
    assert {i["kind"] for i in items} == {"table"}


def test_negative_position_is_clamped_to_the_start():
    items = _complete("SELECT * FROM users", position=-10)
    assert {i["kind"] for i in items} == {"keyword"}


def test_position_past_the_end_is_clamped():
    items = _complete("SELECT * FROM ", position=9999)
    assert {i["kind"] for i in items} == {"table"}


def test_non_integer_position_falls_back_to_the_whole_string():
    items = _complete("SELECT * FROM ", position="not-a-number")
    assert {i["kind"] for i in items} == {"table"}


def test_none_position_means_end_of_string():
    assert _complete("SELECT * FROM ", position=None) == _complete("SELECT * FROM ")


# ── failures degrade to a usable result instead of raising ────────────────────

def test_unparseable_sql_does_not_propagate():
    """sqlglot raising inside table extraction must be swallowed.

    "SELECT " classifies as a column context, but sqlglot cannot parse it, so no
    table is in scope and the result is empty. Pins current behavior: a bare
    SELECT offers nothing rather than falling back to keywords.
    """
    assert _complete("SELECT ") == []


def test_unparseable_sql_outside_a_known_context_returns_keywords():
    """"SELECT (((" matches neither context regex, so keywords are the fallback."""
    items = _complete("SELECT ((( ")
    assert {i["kind"] for i in items} == {"keyword"}


def test_a_table_whose_columns_cannot_be_read_is_skipped():
    """One failing table must not lose the other tables' columns."""
    def get_columns(table):
        if table == "orders":
            raise RuntimeError("introspection failed")
        return COLUMNS.get(table, [])

    items = complete(
        "SELECT  FROM users JOIN orders ON users.id = orders.user_id",
        list_tables_fn=lambda: TABLES,
        get_columns_fn=get_columns,
        get_keywords_fn=lambda: KEYWORDS,
        position=7,
    )

    labels = [i["label"] for i in items]
    assert "name" in labels
    assert "total" not in labels


def test_failing_list_tables_falls_back_to_keywords():
    """An adapter failure in a FROM position degrades to keywords, not an error."""
    def list_tables():
        raise RuntimeError("adapter down")

    items = complete(
        "SELECT * FROM ",
        list_tables_fn=list_tables,
        get_columns_fn=lambda t: [],
        get_keywords_fn=lambda: KEYWORDS,
    )

    assert {i["kind"] for i in items} == {"keyword"}


def test_table_extraction_swallows_a_parser_error():
    """sqlglot raises on an empty statement; the helper must return [] not raise."""
    assert _extract_tables_from_sql("") == []
    assert _extract_tables_from_sql("   ") == []


def test_table_extraction_finds_tables_in_from_and_join():
    tables = _extract_tables_from_sql(
        "SELECT * FROM users JOIN orders ON users.id = orders.user_id"
    )
    assert set(tables) == {"users", "orders"}
