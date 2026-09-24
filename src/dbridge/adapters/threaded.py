"""Adapter orchestration for blocking drivers with thread-affine connections."""

from abc import abstractmethod
import asyncio
from collections.abc import Callable
from typing import TypeVar

from dbridge.adapters.base import (
    ContainerEntry, DBAdapter, QueryResult, ScopePath, TableEntry, TableRef, TableSchema,
)
from dbridge.adapters.lane import Lane


T = TypeVar("T")


class ThreadBackedAdapter(DBAdapter):
    metadata_lane = "query"

    def __init__(self, config: dict[str, str]) -> None:
        super().__init__(config)
        self._lanes: dict[str, Lane] = {}
        self._disconnect_task: asyncio.Task[None] | None = None

    def _new_lane(self, name: str) -> Lane:
        lane = Lane(
            f"dbridge-{self.adapter_name}-{name}",
            lambda: self._interrupt(name),
            self._is_interruption,
        )
        self._lanes[name] = lane
        return lane

    async def connect(self) -> None:
        self._disconnect_task = None
        try:
            await self._new_lane("query").run(self._connect)
            if self.metadata_lane != "query":
                await self._new_lane(self.metadata_lane).run(self._connect_metadata)
        except BaseException:
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        if self._disconnect_task is None:
            self._disconnect_task = asyncio.create_task(self._close_lanes())
        while True:
            try:
                await asyncio.shield(self._disconnect_task)
                return
            except asyncio.CancelledError:
                if self._disconnect_task.done():
                    return self._disconnect_task.result()

    async def _close_lanes(self) -> None:
        # Close sibling cursors before their parent connection.
        try:
            try:
                if self.metadata_lane != "query" and self.metadata_lane in self._lanes:
                    await self._lanes[self.metadata_lane].run(self._disconnect_metadata)
            finally:
                if "query" in self._lanes:
                    await self._lanes["query"].run(self._disconnect)
        finally:
            try:
                for lane in self._lanes.values():
                    await lane.close()
            finally:
                self._lanes.clear()

    def abandon(self) -> None:
        metadata = self._lanes.get(self.metadata_lane) if self.metadata_lane != "query" else None

        def close_parent() -> None:
            # DuckDB parent.close() invalidates its sibling cursor. Preserve
            # normal close order on the daemon workers too; a stuck sibling may
            # defer parent cleanup, but never holds up the event loop's exit.
            if metadata is not None:
                metadata.thread.join()
            self._disconnect()

        for name, lane in self._lanes.items():
            lane.abandon(close_parent if name == "query" else self._disconnect_metadata)

    async def _run(self, lane: str, call: Callable[[], T]) -> T:
        assert lane in self._lanes, "adapter not connected"
        return await self._lanes[lane].run(call)

    async def execute(self, sql: str) -> QueryResult:
        return await self._run("query", lambda: self._execute(sql))

    async def default_scope(self) -> ScopePath:
        return await self._run(self.metadata_lane, self._default_scope)

    async def list_databases(self) -> list[ContainerEntry]:
        return await self._run(self.metadata_lane, self._list_databases)

    async def list_schemas(self, path: ScopePath) -> list[ContainerEntry]:
        return await self._run(self.metadata_lane, lambda: self._list_schemas(path))

    async def list_tables(self, path: ScopePath) -> list[TableEntry]:
        return await self._run(self.metadata_lane, lambda: self._list_tables(path))

    async def get_table_schema(self, table: TableRef) -> TableSchema:
        return await self._run(self.metadata_lane, lambda: self._get_table_schema(table))

    @abstractmethod
    def _connect(self) -> None: ...

    @abstractmethod
    def _disconnect(self) -> None: ...

    @abstractmethod
    def _interrupt(self, lane: str) -> None: ...

    @abstractmethod
    def _is_interruption(self, error: BaseException) -> bool: ...

    def _connect_metadata(self) -> None:
        """Override when metadata has its own lane."""

    def _disconnect_metadata(self) -> None:
        """Override when metadata has its own lane."""

    @abstractmethod
    def _execute(self, sql: str) -> QueryResult: ...

    @abstractmethod
    def _default_scope(self) -> ScopePath: ...

    @abstractmethod
    def _list_databases(self) -> list[ContainerEntry]: ...

    @abstractmethod
    def _list_schemas(self, path: ScopePath) -> list[ContainerEntry]: ...

    @abstractmethod
    def _list_tables(self, path: ScopePath) -> list[TableEntry]: ...

    @abstractmethod
    def _get_table_schema(self, table: TableRef) -> TableSchema: ...
