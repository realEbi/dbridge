"""SQL completion for tables, scoped SELECT columns, and dialect keywords."""
from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import sqlglot
import sqlglot.expressions as exp
from sqlglot.optimizer.scope import Scope, traverse_scope

from dbridge.adapters.base import ScopePath, TableEntry, TableRef

# Tokens that indicate the cursor sits after a FROM or JOIN keyword.
_FROM_JOIN_RE = re.compile(
    r"\b(?:FROM|JOIN)\s*\w*$", re.IGNORECASE
)
# The legacy unqualified predicate path; SELECT targets are resolved by scope.
_WHERE_RE = re.compile(
    r"\b(?:WHERE|AND|OR|ON)\s*\w*$", re.IGNORECASE
)
# A potential unquoted qualifier; parsing below confirms this is a column,
# rather than a table, a string literal, or a comment.
_QUALIFIED_COLUMN_RE = re.compile(
    r"(?<![\w.])(?P<qualifier>[^\W\d]\w*)\s*\.\s*(?P<partial>\w*)$"
)
_UNQUALIFIED_COLUMN_RE = re.compile(r"(?<![\w.])(?P<partial>\w*)$")


@dataclass
class CompletionItem:
    label: str
    kind: str           # "table" | "column" | "keyword"
    detail: str = ""
    insert_text: str = ""
    sort_key: str = ""

    def __post_init__(self) -> None:
        if not self.insert_text:
            self.insert_text = self.label
        if not self.sort_key:
            self.sort_key = self.label.lower()

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "kind": self.kind,
            "detail": self.detail,
            "insert_text": self.insert_text,
            "sort_key": self.sort_key,
        }


def _prefix_at(sql: str, position: int | None) -> str:
    """
    Return the text of *sql* that precedes the cursor.

    *position* is a byte offset into the UTF-8 encoding of *sql* (that is what
    editors such as Neovim report). ``None`` means end-of-string. Out-of-range
    and negative offsets are clamped so completion can never raise here.
    """
    if position is None:
        return sql
    try:
        offset = int(position)
    except (TypeError, ValueError):
        return sql
    encoded = sql.encode("utf-8")
    offset = max(0, min(offset, len(encoded)))
    # errors="ignore" drops a partial code point when the offset splits one.
    return encoded[:offset].decode("utf-8", errors="ignore")


@dataclass(frozen=True)
class _TableSource:
    identity: TableRef
    label: str


def _table_source(table: exp.Table, path: ScopePath) -> _TableSource | None:
    """Resolve literal source components while retaining SQL-written detail."""
    parts = table.parts
    if (
        not parts
        or any(not isinstance(part, exp.Identifier) for part in parts)
        or len(parts) - 1 > len(path)
        or (table.catalog and not table.db)
    ):
        return None
    qualifiers = tuple(part.name for part in parts[:-1])
    resolved_path = path[:len(path) - len(qualifiers)] + qualifiers
    return _TableSource(
        TableRef(parts[-1].name, resolved_path),
        ".".join(part.name for part in parts),
    )


def _extract_tables_from_sql(sql: str, path: ScopePath) -> list[_TableSource]:
    """Return physical source identities from the legacy whole-statement path."""
    try:
        tree = sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.IGNORE)
        return [
            source
            for t in tree.find_all(exp.Table)
            if (source := _table_source(t, path)) is not None
        ]
    except Exception:
        return []


def _column_scope(
    sql: str, prefix: str, match: re.Match[str],
) -> tuple[exp.Column, Scope] | None:
    """Find the marked column and the SELECT scope containing it.

    Replacing the unfinished identifier keeps ``p. FROM`` from being parsed as
    the column ``p.FROM``. The unique marker also identifies the cursor's exact
    scope when statements, subqueries, or UNION branches reuse an alias.
    """
    marker = "__dbridge_completion__"
    while marker in sql:
        marker += "_"
    # prefix has already converted the UTF-8 byte offset to a character boundary.
    # Remove the right-hand part too when the cursor is inside an existing name.
    cursor = len(prefix)
    suffix = re.split(r"\W", sql[cursor:], maxsplit=1)[0]
    # An empty target directly before FROM has no identifier suffix to replace.
    # Separate the marker so the clause remains parseable without a second space.
    suffix_length = 0 if not match["partial"] and suffix.upper() == "FROM" else len(suffix)
    repaired = sql[:match.start("partial")] + marker + " " + sql[cursor + suffix_length:]
    for tree in sqlglot.parse(repaired, error_level=sqlglot.ErrorLevel.IGNORE):
        if tree is None:
            continue
        column = next((c for c in tree.find_all(exp.Column) if c.name == marker), None)
        if column is None:
            continue
        select = column.find_ancestor(exp.Select)
        for scope in traverse_scope(tree):
            if scope.expression is not select:
                continue
            return column, scope
    return None


def _physical_table(
    source: exp.Expression | Scope, scope: Scope, path: ScopePath,
) -> _TableSource | None:
    if not isinstance(source, exp.Table):
        return None
    # sqlglot's source map is case-sensitive; SQLite/DuckDB CTE references are
    # not. A differently cased CTE must not expose a physical table's columns.
    if not source.db and not source.catalog and any(
        name.casefold() == source.name.casefold() for name in scope.cte_sources
    ):
        return None
    # Keep decoded identifier components separate: a literal "sales.products"
    # must never become the table products in the sales namespace on lookup.
    return _table_source(source, path)


def _qualified_table(
    sql: str, prefix: str, match: re.Match[str], path: ScopePath,
) -> _TableSource | None:
    found = _column_scope(sql, prefix, match)
    if found is None:
        return None
    column, scope = found
    sources = [
        source for alias, (_, source) in scope.selected_sources.items()
        if alias.casefold() == column.table.casefold()
    ]
    # Unknown, ambiguous, derived, and CTE sources must not borrow physical
    # columns from another scope. Outer references are deferred.
    return _physical_table(sources[0], scope, path) if len(sources) == 1 else None


def _select_tables(
    sql: str, prefix: str, match: re.Match[str], path: ScopePath,
) -> list[_TableSource]:
    found = _column_scope(sql, prefix, match)
    if found is None:
        return []
    column, scope = found
    if column.table or column.this.args.get("quoted"):
        return []
    # A Column can also occur in WHERE/ORDER BY/etc. Only SELECT projections
    # belong to this path, including columns nested in a target expression.
    if not any(
        column is node
        for target in scope.expression.expressions
        for node in target.walk()
    ):
        return []
    return [
        table for _, source in scope.selected_sources.values()
        if (table := _physical_table(source, scope, path)) is not None
    ]


async def complete(
    sql: str,
    list_tables_fn: Callable[[], Awaitable[list[TableEntry]]],
    get_columns_fn: Callable[[TableRef], Awaitable[list[str]]],
    get_keywords_fn: Callable[[], list[str]],
    path: ScopePath,
    position: int | None = None,
) -> list[dict]:
    """
    Return completion items for *sql* (which may be partial/invalid).

    - alias.column position → columns of its physical table in the current SELECT
    - FROM/JOIN position  → table names
    - SELECT target       → columns of physical tables in the current SELECT
    - WHERE position      → columns using legacy statement-wide extraction
    - otherwise           → dialect keywords

    *position* is an optional byte offset of the cursor into *sql*; ``None``
    means end-of-string. The context is classified from the text *before* the
    cursor, while the **full** statement is parsed for tables in scope — that is
    what lets ``SELECT ␣ FROM users`` offer ``users``' columns.
    """
    prefix = _prefix_at(sql, position)
    qualified = _QUALIFIED_COLUMN_RE.search(prefix)
    if qualified:
        try:
            table = _qualified_table(sql, prefix, qualified, path)
            if table is None:
                return []
            table_label = table.label
            partial = qualified["partial"].casefold()
            return [
                CompletionItem(
                    label=col,
                    kind="column",
                    detail=f"{table_label}.{col}",
                    sort_key=f"{table_label}.{col}".lower(),
                ).to_dict()
                for col in await get_columns_fn(table.identity)
                if col.casefold().startswith(partial)
            ]
        except Exception:
            return []

    try:
        if _FROM_JOIN_RE.search(prefix.rstrip()):
            tables = await list_tables_fn()
            return [
                CompletionItem(
                    label=t.name, kind="table", detail="table", insert_text=t.sql_identifier,
                ).to_dict()
                for t in tables
            ]

        unqualified = _UNQUALIFIED_COLUMN_RE.search(prefix)
        if unqualified:
            in_scope = _select_tables(sql, prefix, unqualified, path)
            if in_scope:
                partial = unqualified["partial"].casefold()
                columns: list[CompletionItem] = []
                for table in in_scope:
                    table_label = table.label
                    try:
                        columns.extend(
                            CompletionItem(
                                label=col, kind="column", detail=f"{table_label}.{col}",
                                sort_key=f"{table_label}.{col}".lower(),
                            )
                            for col in await get_columns_fn(table.identity)
                            if col.casefold().startswith(partial)
                        )
                    except Exception:
                        pass
                return [c.to_dict() for c in columns]

        if _WHERE_RE.search(prefix.rstrip()):
            legacy_tables = _extract_tables_from_sql(sql.rstrip(), path)
            columns = []
            for legacy_table in legacy_tables:
                try:
                    for col in await get_columns_fn(legacy_table.identity):
                        columns.append(
                            CompletionItem(
                                label=col,
                                kind="column",
                                detail=f"{legacy_table.label}.{col}",
                                sort_key=f"{legacy_table.label}.{col}".lower(),
                            )
                        )
                except Exception:
                    pass
            return [c.to_dict() for c in columns]
    except Exception:
        pass

    # Keyword fallback
    keywords = get_keywords_fn()
    return [
        CompletionItem(label=k, kind="keyword", detail="keyword").to_dict()
        for k in keywords
    ]
