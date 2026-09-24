"""Unit tests for SQL completion contexts and scope with a fake registry."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from dbridge.adapters.base import TableEntry, TableRef
from dbridge.adapters.duckdb import DuckDBAdapter

from dbridge.core.completion import (
    CompletionItem,
    _extract_tables_from_sql,
    complete,
)

PATH = ("memory", "main")
TABLES = [
    TableEntry(name, f'"memory"."main"."{name}"')
    for name in ("users", "orders", "products")
]
COLUMNS = {
    "users": ["id", "name", "email"],
    "orders": ["id", "user_id", "total"],
    "products": ["id", "sku", "name", "category", "price", "discontinued"],
}
KEYWORDS = ["SELECT", "FROM", "WHERE", "JOIN"]


async def _adapter_columns(adapter, table):
    return [column.name for column in (await adapter.get_table_schema(table)).columns]


async def _complete(sql, position=None):
    return await complete(
        sql,
        list_tables_fn=AsyncMock(side_effect=lambda: TABLES),
        get_columns_fn=AsyncMock(side_effect=lambda t: COLUMNS.get(t.name, [])),
        get_keywords_fn=lambda: KEYWORDS,
        path=PATH,
        position=position,
    )


async def _complete_at_cursor(marked_sql):
    before, after = marked_sql.split("|")
    return await _complete(before + after, position=len(before.encode("utf-8")))


# ── FROM / JOIN context ───────────────────────────────────────────────────────

async def test_from_returns_tables():
    items = await _complete("SELECT * FROM ")
    kinds = {i["kind"] for i in items}
    labels = [i["label"] for i in items]
    assert kinds == {"table"}
    assert "users" in labels
    assert "orders" in labels


async def test_join_returns_tables():
    items = await _complete("SELECT * FROM users JOIN ")
    assert all(i["kind"] == "table" for i in items)
    assert "orders" in [i["label"] for i in items]


async def test_from_with_partial_prefix_returns_tables():
    items = await _complete("SELECT * FROM use")
    assert all(i["kind"] == "table" for i in items)


# ── SELECT / WHERE context ────────────────────────────────────────────────────

async def test_select_returns_columns_of_referenced_tables():
    # Cursor sits right after "SELECT " (byte offset 7), before the FROM clause.
    items = await _complete("SELECT  FROM users", position=7)
    assert {i["kind"] for i in items} == {"column"}
    labels = [i["label"] for i in items]
    assert labels == ["id", "name", "email"]


async def test_position_mid_string_classifies_from_prefix_only():
    sql = "SELECT  FROM users JOIN orders ON users.id = orders.user_id"
    items = await _complete(sql, position=7)
    labels = [i["label"] for i in items]
    assert {i["kind"] for i in items} == {"column"}
    # Both tables are in scope even though they appear after the cursor.
    assert "email" in labels
    assert "total" in labels


async def test_omitted_position_is_end_of_string():
    sql = "SELECT  FROM users"
    assert await _complete(sql) == await _complete(sql, position=len(sql))
    # ... and that is the pre-existing FROM behaviour: tables, not columns.
    assert {i["kind"] for i in await _complete(sql)} == {"table"}


async def test_multiline_select_position_returns_columns():
    items = await _complete("SELECT \nFROM users", position=7)
    assert {i["kind"] for i in items} == {"column"}
    assert "name" in [i["label"] for i in items]


async def test_position_zero_returns_keywords():
    items = await _complete("SELECT * FROM users", position=0)
    assert {i["kind"] for i in items} == {"keyword"}


async def test_out_of_range_position_does_not_raise():
    for pos in (-5, 9999):
        items = await _complete("SELECT * FROM users", position=pos)
        assert isinstance(items, list)


async def test_where_includes_columns_from_scope():
    items = await _complete("SELECT id FROM orders WHERE ")
    labels = [i["label"] for i in items]
    assert "user_id" in labels
    assert "total" in labels


async def test_column_detail_contains_table_prefix():
    items = await _complete("SELECT id FROM users WHERE ")
    detail_map = {i["label"]: i["detail"] for i in items}
    assert detail_map["name"] == "users.name"


# ── Qualified columns ────────────────────────────────────────────────────────

@pytest.mark.parametrize("marked_sql", [
    "SELECT p.|name, p.category FROM products p LIMIT 100",
    "SELECT p.name, p.|category FROM products p LIMIT 100",
])
async def test_reported_product_query_completes_both_qualified_targets(marked_sql):
    items = await _complete_at_cursor(marked_sql)

    assert items == [
        {
            "label": column,
            "kind": "column",
            "detail": f"products.{column}",
            "insert_text": column,
            "sort_key": f"products.{column}",
        }
        for column in COLUMNS["products"]
    ]


@pytest.mark.parametrize("marked_sql", [
    "SELECT p.| FROM products p",
    "SELECT p.| FROM products AS p",
    "SELECT P.| FROM products AS p",
    "SELECT p.| FROM products AS P",
    "SELECT products.| FROM products",
    "SELECT p.name,\n p.| FROM products p",
    "SELECT COALESCE(p.|, '') FROM products p",
    "SELECT * FROM products p JOIN orders o ON p.id = o.id WHERE p.|",
    "SELECT * FROM products p WHERE p.id = 1 AND p.|",
    "SELECT * FROM products p WHERE p.id = 1 OR p.|",
    "SELECT * FROM orders o JOIN products p ON p.|",
    "SELECT * FROM orders o JOIN products p ON o.id = p.|",
])
async def test_qualified_columns_resolve_only_the_named_table(marked_sql):
    items = await _complete_at_cursor(marked_sql)

    assert [item["label"] for item in items] == COLUMNS["products"]
    assert {item["kind"] for item in items} == {"column"}


@pytest.mark.parametrize(("marked_sql", "expected"), [
    ("SELECT p.na| FROM products p", ["name"]),
    ("SELECT p.NA| FROM products p", ["name"]),
    ("SELECT p.na|me FROM products p", ["name"]),
    ("SELECT p.|name FROM products p", COLUMNS["products"]),
    ("SELECT p.unavailable| FROM products p", []),
])
async def test_qualified_column_prefix_filters_without_duplicating_alias(marked_sql, expected):
    items = await _complete_at_cursor(marked_sql)

    assert [item["label"] for item in items] == expected
    assert [item["insert_text"] for item in items] == expected


async def test_qualified_cursor_uses_utf8_byte_offset_in_multiline_sql():
    items = await _complete_at_cursor("SELECT 'café ☕',\n p.|name FROM products p")

    assert [item["label"] for item in items] == COLUMNS["products"]


async def test_qualified_completion_without_position_uses_end_of_sql():
    sql = "SELECT * FROM products p WHERE p."

    assert await _complete(sql) == await _complete(sql, position=len(sql.encode("utf-8")))
    assert [item["label"] for item in await _complete(sql)] == COLUMNS["products"]


@pytest.mark.parametrize(("marked_sql", "table"), [
    (
        "SELECT p.| FROM products p WHERE EXISTS (SELECT p.id FROM orders p)",
        "products",
    ),
    (
        "SELECT p.id FROM products p WHERE EXISTS (SELECT p.| FROM orders p)",
        "orders",
    ),
    (
        "SELECT (SELECT p.id FROM orders p), (SELECT p.| FROM products p)",
        "products",
    ),
    (
        "SELECT p.id FROM orders p UNION SELECT p.| FROM products p",
        "products",
    ),
    (
        "SELECT p.| FROM products p UNION SELECT p.id FROM orders p",
        "products",
    ),
    (
        "SELECT p.id FROM orders p; SELECT p.| FROM products p",
        "products",
    ),
    (
        "SELECT p.| FROM products p; SELECT p.id FROM orders p",
        "products",
    ),
])
async def test_qualified_columns_use_the_cursors_select_scope(marked_sql, table):
    items = await _complete_at_cursor(marked_sql)

    assert [item["label"] for item in items] == COLUMNS[table]
    assert all(item["detail"].startswith(f"{table}.") for item in items)


@pytest.mark.parametrize("marked_sql", [
    "SELECT missing.| FROM products p",
    "SELECT products.| FROM products p",
    "SELECT p.| FROM products p JOIN orders p ON 1 = 1",
    "SELECT p.| FROM products p JOIN orders P ON 1 = 1",
    "SELECT p.| FROM (SELECT * FROM products) p",
    "WITH products AS (SELECT id FROM orders) SELECT p.| FROM products p",
    "WITH p AS (SELECT * FROM products) SELECT p.| FROM orders o",
    "SELECT p.id FROM products p WHERE EXISTS (SELECT p.| FROM orders o)",
    "SELECT (SELECT p.id FROM products p), (SELECT p.| FROM orders o)",
    "SELECT p.| FROM orders o WHERE EXISTS (SELECT p.id FROM products p)",
    "SELECT p.id FROM products p UNION SELECT p.| FROM orders o",
    "SELECT p.id FROM products p; SELECT p.| FROM orders o",
    "SELECT p.| FROM orders o; SELECT p.id FROM products p",
])
async def test_unresolved_qualified_sources_do_not_guess_columns(marked_sql):
    assert await _complete_at_cursor(marked_sql) == []


@pytest.mark.parametrize(("cte_name", "reference"), [
    ("PRODUCTS", "products"),
    ("products", "PRODUCTS"),
])
async def test_cte_name_case_does_not_expose_shadowed_physical_table(cte_name, reference):
    queried_tables = []

    async def get_columns(table):
        queried_tables.append(table)
        return COLUMNS["products"]

    before = f"WITH {cte_name} AS (SELECT user_id FROM orders) SELECT p."
    items = await complete(
        before + f" FROM {reference} p",
        list_tables_fn=AsyncMock(side_effect=lambda: TABLES),
        get_columns_fn=get_columns,
        get_keywords_fn=lambda: KEYWORDS,
        path=PATH,
        position=len(before.encode("utf-8")),
    )

    assert items == []
    assert queried_tables == []


async def test_explicit_schema_reference_is_not_shadowed_by_same_named_cte():
    before = "WITH PRODUCTS AS (SELECT user_id FROM orders) SELECT p."
    items = await complete(
        before + " FROM main.products p",
        list_tables_fn=AsyncMock(side_effect=lambda: TABLES),
        get_columns_fn=AsyncMock(side_effect=lambda table: COLUMNS["products"]
        if table == TableRef("products", PATH) else []),
        get_keywords_fn=lambda: KEYWORDS,
        path=PATH,
        position=len(before.encode("utf-8")),
    )

    assert [item["label"] for item in items] == COLUMNS["products"]


@pytest.mark.parametrize(("source", "identity"), [
    ("first.products", TableRef("products", ("memory", "first"))),
    ("catalog.first.products", TableRef("products", ("catalog", "first"))),
    ('"catalog.with.dot"."first.with.dot"."products.with.dot"',
     TableRef("products.with.dot", ("catalog.with.dot", "first.with.dot"))),
])
async def test_qualified_lookup_preserves_physical_source_schema_and_catalog(source, identity):
    queried_tables = []

    async def get_columns(table):
        queried_tables.append(table)
        if table == identity:
            return ["selected_source_column"]
        return ["unrelated_source_column"]

    items = await complete(
        f"SELECT p. FROM {source} p",
        list_tables_fn=AsyncMock(side_effect=lambda: TABLES),
        get_columns_fn=get_columns,
        get_keywords_fn=lambda: KEYWORDS,
        path=PATH,
        position=len("SELECT p."),
    )

    assert queried_tables == [identity]
    assert [item["label"] for item in items] == ["selected_source_column"]


@pytest.mark.parametrize("marked_sql", [
    "SELECT 'p.|' FROM products p",
    "SELECT 'it''s p.|' FROM products p",
    "SELECT /* p.| */ name FROM products p",
    "SELECT name -- p.|\nFROM products p",
    "SELECT * FROM p.| JOIN products p ON 1 = 1",
])
async def test_dots_outside_column_expressions_do_not_offer_columns(marked_sql):
    items = await _complete_at_cursor(marked_sql)

    assert all(item["kind"] != "column" for item in items)


async def test_qualified_metadata_failure_returns_no_unrelated_suggestions():
    queried_tables = []

    async def get_columns(table):
        queried_tables.append(table)
        raise RuntimeError("introspection unavailable")

    sql = "SELECT * FROM products p JOIN orders o ON o.id = p.id WHERE p."
    items = await complete(
        sql,
        list_tables_fn=AsyncMock(side_effect=lambda: TABLES),
        get_columns_fn=get_columns,
        get_keywords_fn=lambda: KEYWORDS,
        path=PATH,
    )

    assert items == []
    assert queried_tables == [TableRef("products", PATH)]


@pytest.mark.parametrize("marked_sql", [
    "SELECT p.| FROM 'unterminated",
    "SELECT p.| FROM",
    "p.|",
])
async def test_unresolvable_qualified_sql_returns_empty_without_raising(marked_sql):
    assert await _complete_at_cursor(marked_sql) == []


# ── Keyword fallback ──────────────────────────────────────────────────────────

async def test_bare_sql_returns_keywords():
    items = await _complete("")
    kinds = {i["kind"] for i in items}
    assert kinds == {"keyword"}
    labels = [i["label"] for i in items]
    assert "SELECT" in labels


async def test_non_clause_position_returns_keywords():
    items = await _complete("CREATE ")
    assert all(i["kind"] == "keyword" for i in items)


# ── Grace under malformed SQL ─────────────────────────────────────────────────

async def test_malformed_sql_does_not_raise():
    items = await _complete("SELECT *** FROM ;;;")
    # Should return something (keywords) without raising
    assert isinstance(items, list)


async def test_truncated_sql_does_not_raise():
    items = await _complete("SELECT id, name FR")
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

async def test_position_is_a_byte_offset_not_a_character_offset():
    """'né' is 3 bytes; the byte offset after it must still classify as FROM."""
    sql = "SELECT * FROM né"
    items = await _complete(sql, position=len(sql.encode("utf-8")))
    assert {i["kind"] for i in items} == {"table"}


async def test_offset_splitting_a_code_point_does_not_raise():
    """A split code point is dropped rather than raising (errors='ignore')."""
    sql = "SELECT * FROM né"
    # One byte into the two-byte 'é'.
    items = await _complete(sql, position=len(sql.encode("utf-8")) - 1)
    assert {i["kind"] for i in items} == {"table"}


async def test_negative_position_is_clamped_to_the_start():
    items = await _complete("SELECT * FROM users", position=-10)
    assert {i["kind"] for i in items} == {"keyword"}


async def test_position_past_the_end_is_clamped():
    items = await _complete("SELECT * FROM ", position=9999)
    assert {i["kind"] for i in items} == {"table"}


async def test_non_integer_position_falls_back_to_the_whole_string():
    items = await _complete("SELECT * FROM ", position="not-a-number")
    assert {i["kind"] for i in items} == {"table"}


async def test_none_position_means_end_of_string():
    assert await _complete("SELECT * FROM ", position=None) == await _complete("SELECT * FROM ")


# ── failures degrade to a usable result instead of raising ────────────────────

async def test_bare_select_returns_keywords():
    items = await _complete("SELECT ")
    assert [item["label"] for item in items] == KEYWORDS
    assert {item["kind"] for item in items} == {"keyword"}


async def test_unparseable_sql_outside_a_known_context_returns_keywords():
    """"SELECT (((" matches neither context regex, so keywords are the fallback."""
    items = await _complete("SELECT ((( ")
    assert {i["kind"] for i in items} == {"keyword"}


async def test_a_table_whose_columns_cannot_be_read_is_skipped():
    """One failing table must not lose the other tables' columns."""
    async def get_columns(table):
        if table == TableRef("orders", PATH):
            raise RuntimeError("introspection failed")
        return COLUMNS.get(table.name, [])

    items = await complete(
        "SELECT  FROM users JOIN orders ON users.id = orders.user_id",
        list_tables_fn=AsyncMock(side_effect=lambda: TABLES),
        get_columns_fn=get_columns,
        get_keywords_fn=lambda: KEYWORDS,
        path=PATH,
        position=7,
    )

    labels = [i["label"] for i in items]
    assert "name" in labels
    assert "total" not in labels


async def test_failing_list_tables_falls_back_to_keywords():
    """An adapter failure in a FROM position degrades to keywords, not an error."""
    async def list_tables():
        raise RuntimeError("adapter down")

    items = await complete(
        "SELECT * FROM ",
        list_tables_fn=list_tables,
        get_columns_fn=AsyncMock(side_effect=lambda t: []),
        get_keywords_fn=lambda: KEYWORDS,
        path=PATH,
    )

    assert {i["kind"] for i in items} == {"keyword"}


def test_table_extraction_swallows_a_parser_error():
    """sqlglot raises on an empty statement; the helper must return [] not raise."""
    assert _extract_tables_from_sql("", PATH) == []
    assert _extract_tables_from_sql("   ", PATH) == []


def test_table_extraction_finds_tables_in_from_and_join():
    tables = _extract_tables_from_sql(
        "SELECT * FROM users JOIN orders ON users.id = orders.user_id", PATH,
    )
    assert {table.identity for table in tables} == {
        TableRef("users", PATH), TableRef("orders", PATH),
    }


# Unqualified SELECT target expressions use the cursor's SELECT scope.

@pytest.mark.parametrize("marked_sql", [
    "SELECT | FROM products",
    "SELECT |FROM products",
    "SELECT id, | FROM products",
    "SELECT id, |FROM products",
    "SELECT id,\n | FROM products",
    "SELECT DISTINCT | FROM products",
    "SELECT COALESCE(|, '') FROM products",
    "SELECT id + | FROM products",
    "SELECT 'café ☕',\n | FROM products",
    "SELECT __dbridge_completion__, | FROM products",
])
async def test_unqualified_select_targets_return_schema_order(marked_sql):
    items = await _complete_at_cursor(marked_sql)
    assert items == [
        {
            "label": column, "kind": "column",
            "detail": f"products.{column}", "insert_text": column,
            "sort_key": f"products.{column}",
        }
        for column in COLUMNS["products"]
    ]


@pytest.mark.parametrize(("marked_sql", "expected"), [
    ("SELECT na| FROM products", ["name"]),
    ("SELECT id, NA| FROM products", ["name"]),
    ("SELECT id, na|me FROM products", ["name"]),
    ("SELECT 'café',\n COALESCE(na|me, '') FROM products", ["name"]),
    ("SELECT id, |name FROM products", COLUMNS["products"]),
    ("SELECT id, missing| FROM products", []),
])
async def test_unqualified_select_prefix_matches_case_insensitively(marked_sql, expected):
    items = await _complete_at_cursor(marked_sql)
    assert [item["label"] for item in items] == expected
    assert [item["insert_text"] for item in items] == expected


@pytest.mark.parametrize(("marked_sql", "table"), [
    ("SELECT | FROM products WHERE EXISTS (SELECT id FROM orders)", "products"),
    ("SELECT id FROM products WHERE EXISTS (SELECT | FROM orders)", "orders"),
    ("SELECT (SELECT id FROM orders), (SELECT | FROM products)", "products"),
    ("SELECT | FROM products UNION SELECT id FROM orders", "products"),
    ("SELECT id FROM orders UNION SELECT | FROM products", "products"),
    ("SELECT id FROM orders; SELECT | FROM products", "products"),
    ("SELECT | FROM products; SELECT id FROM orders", "products"),
    ("WITH p AS (SELECT | FROM products) SELECT * FROM p", "products"),
    ("SELECT | FROM products JOIN (SELECT * FROM orders) o ON 1=1", "products"),
])
async def test_unqualified_select_uses_only_current_scope(marked_sql, table):
    items = await _complete_at_cursor(marked_sql)
    assert [item["label"] for item in items] == COLUMNS[table]
    assert all(item["detail"].startswith(table + ".") for item in items)


@pytest.mark.parametrize("marked_sql", [
    "SELECT |",
    "SELECT id, |",
    "SELECT id FROM products; SELECT |",
    "SELECT (SELECT |) FROM products",
    "SELECT | FROM (SELECT * FROM products) p",
    "WITH p AS (SELECT * FROM products) SELECT | FROM p",
    "WITH PRODUCTS AS (SELECT * FROM orders) SELECT | FROM products",
    "WITH products AS (SELECT * FROM orders) SELECT | FROM PRODUCTS",
    "SELECT id AS na|me FROM products",
    "SELECT id na|me FROM products",
    'SELECT "na|me" FROM products',
    "SELECT 'SELECT |' FROM products",
    "SELECT 'id, |' FROM products",
    "SELECT /* SELECT id, | */ id FROM products",
    "SELECT id -- SELECT |\n FROM products",
    "SELECT ((( |",
])
async def test_unqualified_select_fallback_does_not_introspect_other_sources(marked_sql):
    async def unexpected_lookup(*args):
        pytest.fail("Fallback must not list tables or introspect columns")

    before, after = marked_sql.split("|")
    items = await complete(
        before + after, unexpected_lookup, unexpected_lookup, lambda: KEYWORDS, PATH,
        position=len(before.encode("utf-8")),
    )
    assert [item["label"] for item in items] == KEYWORDS
    assert {item["kind"] for item in items} == {"keyword"}


async def test_unqualified_select_preserves_join_source_order_and_duplicate_details():
    items = await _complete_at_cursor(
        "SELECT id, | FROM orders o JOIN products p ON o.id = p.id"
    )
    assert [item["detail"] for item in items] == [
        f"{table}.{column}"
        for table in ("orders", "products")
        for column in COLUMNS[table]
    ]
    assert [item["label"] for item in items].count("id") == 2


async def test_unqualified_select_preserves_schema_and_catalog_lookup():
    queried = []

    async def get_columns(table):
        queried.append(table)
        return ["name"]

    before = "SELECT id, "
    items = await complete(
        before + " FROM warehouse.retail.products",
        AsyncMock(side_effect=lambda: []), get_columns, lambda: KEYWORDS, PATH, position=len(before),
    )
    assert queried == [TableRef("products", ("warehouse", "retail"))]
    assert items[0]["detail"] == "warehouse.retail.products.name"


async def test_unqualified_select_skips_unavailable_metadata_without_keyword_fallback():
    async def unavailable(table):
        raise RuntimeError("introspection failed")

    assert await complete(
        "SELECT id,  FROM products", AsyncMock(side_effect=lambda: []), unavailable, lambda: KEYWORDS, PATH,
        position=len("SELECT id, "),
    ) == []


@pytest.fixture
async def catalog_adapter():
    adapter = DuckDBAdapter({"uri": ":memory:"})
    await adapter.connect()
    try:
        for catalog in ("memory", "side", "other"):
            if catalog != "memory":
                await adapter.execute(f"ATTACH ':memory:' AS {catalog}")
            await adapter.execute(f"CREATE TABLE {catalog}.main.shipments (origin VARCHAR)")
            await adapter.execute(f"INSERT INTO {catalog}.main.shipments VALUES ('{catalog}')")
            await adapter.execute(f"CREATE SCHEMA {catalog}.sales")
            await adapter.execute(f"CREATE TABLE {catalog}.sales.products ({catalog}_column INTEGER)")
        yield adapter
    finally:
        await adapter.disconnect()


@pytest.mark.parametrize("catalog", ["memory", "side", "other"])
async def test_table_completion_stays_in_requested_path_and_executes_exact_table(
    catalog_adapter, catalog,
):
    path = (catalog, "main")
    items = await complete(
        "SELECT * FROM ",
        list_tables_fn=lambda: catalog_adapter.list_tables(path),
        get_columns_fn=lambda table: _adapter_columns(catalog_adapter, table),
        get_keywords_fn=catalog_adapter.get_keywords,
        path=path,
    )

    assert [item["label"] for item in items] == ["shipments"]
    assert items[0]["insert_text"] == f'"{catalog}"."main"."shipments"'
    result = await catalog_adapter.execute("SELECT origin FROM " + items[0]["insert_text"])
    assert result.rows == [[catalog]]


@pytest.mark.parametrize("name", ["order details", "select", 'quoted"name', "literal.dot"])
async def test_table_completion_preserves_adapter_identifier_for_literal_names(catalog_adapter, name):
    path = ("side", "main")
    quoted_name = '"' + name.replace('"', '""') + '"'
    await catalog_adapter.execute(f"CREATE TABLE side.main.{quoted_name} (value INTEGER)")
    await catalog_adapter.execute(f"INSERT INTO side.main.{quoted_name} VALUES (42)")
    items = await complete(
        "SELECT * FROM ",
        lambda: catalog_adapter.list_tables(path), AsyncMock(side_effect=lambda table: []),
        catalog_adapter.get_keywords, path,
    )

    item = next(item for item in items if item["label"] == name)
    assert item["insert_text"] == f'"side"."main".{quoted_name}'
    assert (await catalog_adapter.execute("SELECT * FROM " + item["insert_text"])).rows == [[42]]


@pytest.mark.parametrize(("source", "catalog"), [
    ("sales.products", "side"),
    ("other.sales.products", "other"),
])
@pytest.mark.parametrize("marked_sql", [
    "SELECT p.| FROM {source} p",
    "SELECT | FROM {source} p",
    "SELECT * FROM {source} WHERE |",
])
async def test_column_sources_resolve_from_request_path_and_keep_written_detail(
    catalog_adapter, source, catalog, marked_sql,
):
    before, after = marked_sql.format(source=source).split("|")
    items = await complete(
        before + after,
        list_tables_fn=AsyncMock(side_effect=lambda: []),
        get_columns_fn=lambda table: _adapter_columns(catalog_adapter, table),
        get_keywords_fn=catalog_adapter.get_keywords,
        path=("side", "main"), position=len(before.encode("utf-8")),
    )

    assert [item["label"] for item in items] == [f"{catalog}_column"]
    assert items[0]["insert_text"] == f"{catalog}_column"
    assert items[0]["detail"] == f"{source}.{catalog}_column"


@pytest.mark.parametrize(("source", "path"), [
    ("catalog.main.products", ("main",)),
    ("extra.catalog.main.products", ("catalog", "main")),
    ("catalog..products", ("catalog", "main")),
])
async def test_source_with_unsupported_qualification_does_not_select_another_table(source, path):
    async def unexpected_lookup(table):
        pytest.fail("Unsupported qualification must not resolve a different table")

    before = "SELECT p."
    assert await complete(
        before + f" FROM {source} p", AsyncMock(side_effect=lambda: []), unexpected_lookup, lambda: KEYWORDS,
        path, position=len(before),
    ) == []


@pytest.mark.parametrize("sql,position", [
    ("SELECT * FROM ", None),
    ("SELECT p. FROM products p", len("SELECT p.")),
    ("SELECT  FROM products", len("SELECT ")),
])
async def test_cancellation_during_metadata_lookup_propagates(sql, position):
    lookup = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await complete(sql, lookup, lookup, lambda: KEYWORDS, PATH, position=position)
    lookup.assert_awaited_once()
