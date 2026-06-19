"""Tier-1 SQL completion: FROM/JOIN → tables, SELECT/WHERE → columns, else keywords."""
from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
import sqlglot.expressions as exp

# Tokens that indicate the cursor sits after a FROM or JOIN keyword.
_FROM_JOIN_RE = re.compile(
    r"\b(?:FROM|JOIN)\s*\w*$", re.IGNORECASE
)
# Tokens that indicate the cursor sits in a SELECT or WHERE clause.
_SELECT_WHERE_RE = re.compile(
    r"\b(?:SELECT|WHERE|AND|OR|ON)\s*\w*$", re.IGNORECASE
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


def complete(
    sql: str,
    list_tables_fn,          # () -> list[str]
    get_columns_fn,          # (table: str) -> list[str]
    get_keywords_fn,         # () -> list[str]
) -> list[dict]:
    """
    Return completion items for *sql* (which may be partial/invalid).

    - FROM/JOIN position  → table names
    - SELECT/WHERE position → column names of tables already in scope
    - otherwise           → dialect keywords
    """
    sql_stripped = sql.rstrip()

    try:
        if _FROM_JOIN_RE.search(sql_stripped):
            tables = list_tables_fn()
            return [
                CompletionItem(label=t, kind="table", detail="table").to_dict()
                for t in tables
            ]

        if _SELECT_WHERE_RE.search(sql_stripped):
            in_scope = _extract_tables_from_sql(sql_stripped)
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
