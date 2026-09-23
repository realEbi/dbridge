"""SQL completion for tables, scoped qualified columns, and dialect keywords."""
from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
import sqlglot.expressions as exp
from sqlglot.optimizer.scope import traverse_scope

# Tokens that indicate the cursor sits after a FROM or JOIN keyword.
_FROM_JOIN_RE = re.compile(
    r"\b(?:FROM|JOIN)\s*\w*$", re.IGNORECASE
)
# Tokens that indicate the cursor sits in a SELECT or WHERE clause.
_SELECT_WHERE_RE = re.compile(
    r"\b(?:SELECT|WHERE|AND|OR|ON)\s*\w*$", re.IGNORECASE
)
# A potential unquoted qualifier; parsing below confirms this is a column,
# rather than a table, a string literal, or a comment.
_QUALIFIED_COLUMN_RE = re.compile(
    r"(?<![\w.])(?P<qualifier>[^\W\d]\w*)\s*\.\s*(?P<partial>\w*)$"
)


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


def _extract_tables_from_sql(sql: str) -> list[str]:
    """Return table names referenced in FROM/JOIN clauses using sqlglot."""
    try:
        tree = sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.IGNORE)
        return [
            t.name
            for t in tree.find_all(exp.Table)
            if t.name
        ]
    except Exception:
        return []


def _qualified_table(sql: str, prefix: str, match: re.Match[str]) -> str | None:
    """Resolve the column at the cursor to a physical source in its SELECT.

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
    repaired = sql[:match.start("partial")] + marker + sql[cursor + len(suffix):]
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
            sources = [
                source for alias, (_, source) in scope.selected_sources.items()
                if alias.casefold() == column.table.casefold()
            ]
            if len(sources) == 1 and isinstance(sources[0], exp.Table):
                source = sources[0]
                # sqlglot's source map is case-sensitive; SQLite/DuckDB CTE
                # references are not. Do not mistake a differently cased CTE
                # reference for a physical table of the same name.
                if not source.db and not source.catalog and any(
                    name.casefold() == source.name.casefold()
                    for name in scope.cte_sources
                ):
                    return None
                return ".".join(part.name for part in source.parts)
            # Unknown, ambiguous, derived, and CTE sources must not borrow
            # physical columns from another scope. Outer references are deferred.
            return None
    return None


def complete(
    sql: str,
    list_tables_fn,          # () -> list[str]
    get_columns_fn,          # (table: str) -> list[str]
    get_keywords_fn,         # () -> list[str]
    position: int | None = None,
) -> list[dict]:
    """
    Return completion items for *sql* (which may be partial/invalid).

    - alias.column position → columns of its physical table in the current SELECT
    - FROM/JOIN position  → table names
    - SELECT/WHERE position → column names of tables already in scope
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
            table = _qualified_table(sql, prefix, qualified)
            if table is None:
                return []
            partial = qualified["partial"].casefold()
            return [
                CompletionItem(
                    label=col,
                    kind="column",
                    detail=f"{table}.{col}",
                    sort_key=f"{table}.{col}".lower(),
                ).to_dict()
                for col in get_columns_fn(table)
                if col.casefold().startswith(partial)
            ]
        except Exception:
            return []

    prefix = prefix.rstrip()

    try:
        if _FROM_JOIN_RE.search(prefix):
            tables = list_tables_fn()
            return [
                CompletionItem(label=t, kind="table", detail="table").to_dict()
                for t in tables
            ]

        if _SELECT_WHERE_RE.search(prefix):
            in_scope = _extract_tables_from_sql(sql.rstrip())
            columns: list[CompletionItem] = []
            for table in in_scope:
                try:
                    for col in get_columns_fn(table):
                        columns.append(
                            CompletionItem(
                                label=col,
                                kind="column",
                                detail=f"{table}.{col}",
                                sort_key=f"{table}.{col}".lower(),
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
