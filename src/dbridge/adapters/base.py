from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from dbridge.logging import get_logger


ScopePath = tuple[str, ...]


@dataclass(frozen=True)
class ScopeLevel:
    name: str
    label: str


@dataclass(frozen=True)
class ContainerEntry:
    name: str
    internal: bool = False


@dataclass(frozen=True)
class TableEntry:
    name: str
    sql_identifier: str


@dataclass
class ColumnDef:
    name: str
    data_type: str
    nullable: bool = True
    default: str | None = None
    comment: str | None = None


@dataclass
class ForeignKey:
    column: str
    referenced_table: str
    referenced_column: str


@dataclass(frozen=True)
class TableRef:
    name: str
    path: ScopePath


@dataclass
class TableSchema:
    name: str
    scope: ScopePath
    columns: list[ColumnDef] = field(default_factory=list)
    primary_keys: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    sql_identifier: str | None = None


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    row_count: int
    execution_time_ms: float
    warnings: list[str] = field(default_factory=list)


class DBAdapter(ABC):
    """Database operations are awaitable; declarations remain synchronous.

    Cancelling an awaited operation must stop that operation without affecting
    other requests and leave the Session usable. Interrupted work propagates
    ``asyncio.CancelledError``; work already completed or not interruptible may
    return its normal result. Native async drivers implement this contract using
    their own cancellation mechanism.
    """
    adapter_name: str

    def __init__(self, config: dict[str, str]) -> None:
        self.logger = get_logger()
        self.config = config

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    def abandon(self) -> None:
        """Release request waiters when bounded process shutdown expires.

        Native async implementations can override this last-resort cleanup hook.
        Thread-backed implementations leave driver cleanup to daemon workers.
        """

    @abstractmethod
    async def execute(self, sql: str, *, row_limit: int | None = None) -> QueryResult:
        """Read at most row_limit rows, or all rows when it is None.

        Reject row limits below 1 before calling the driver.
        """
        ...

    @abstractmethod
    def scope_levels(self) -> list[ScopeLevel]: ...

    @abstractmethod
    async def default_scope(self) -> ScopePath: ...

    @abstractmethod
    async def list_databases(self) -> list[ContainerEntry]: ...

    @abstractmethod
    async def list_schemas(self, path: ScopePath) -> list[ContainerEntry]: ...

    @abstractmethod
    async def list_tables(self, path: ScopePath) -> list[TableEntry]: ...

    @abstractmethod
    async def get_table_schema(self, table: TableRef) -> TableSchema: ...

    @abstractmethod
    def dialect_name(self) -> str: ...

    @abstractmethod
    def get_keywords(self) -> list[str]: ...
