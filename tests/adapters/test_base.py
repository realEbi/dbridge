from dataclasses import asdict
import json
from unittest.mock import AsyncMock

import pytest

from dbridge.adapters.base import ScopeLevel, ScopePath, TableRef, TableSchema
from dbridge.adapters.sqlite import SqliteAdapter


def test_scope_level_has_a_stable_name_and_display_label():
    level = ScopeLevel(name="catalog", label="Catalog")
    assert asdict(level) == {"name": "catalog", "label": "Catalog"}


def test_literal_scope_path_round_trips_through_json():
    path: ScopePath = ('catalog.with"quote', "schema with space", "select")
    schema = TableSchema(name="literal.table", scope=path)
    payload = json.loads(json.dumps(asdict(schema)))
    assert tuple(payload["scope"]) == path
    assert payload["name"] == "literal.table"
    assert "database" not in payload
    assert "schema" not in payload


def test_table_ref_is_a_literal_hashable_cache_key():
    dotted = TableRef(name="orders", path=("catalog.with.dot", "main"))
    separate = TableRef(name="orders", path=("catalog", "with.dot"))
    cache = {dotted: "dotted", separate: "separate"}
    assert cache[TableRef(name="orders", path=("catalog.with.dot", "main"))] == "dotted"
    assert cache[TableRef(name="orders", path=("catalog", "with.dot"))] == "separate"


@pytest.mark.parametrize("row_limit", [0, -1])
async def test_invalid_row_limit_is_rejected_before_submitting_a_lane_job(monkeypatch, row_limit):
    adapter = SqliteAdapter({"uri": ":memory:"})
    run = AsyncMock()
    monkeypatch.setattr(adapter, "_run", run)

    with pytest.raises(ValueError, match="row_limit must be at least 1"):
        await adapter.execute("SELECT 1", row_limit=row_limit)

    run.assert_not_awaited()
