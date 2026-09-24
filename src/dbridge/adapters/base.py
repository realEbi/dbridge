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
    adapter_name: str

    def __init__(self, config: dict[str, str]) -> None:
        self.logger = get_logger()
        self.config = config

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def execute(self, sql: str) -> QueryResult: ...

    @abstractmethod
    def scope_levels(self) -> list[ScopeLevel]: ...

    @abstractmethod
    def default_scope(self) -> ScopePath: ...

    @abstractmethod
    def list_databases(self) -> list[ContainerEntry]: ...

    @abstractmethod
    def list_schemas(self, path: ScopePath) -> list[ContainerEntry]: ...

    @abstractmethod
    def list_tables(self, path: ScopePath) -> list[TableEntry]: ...

    @abstractmethod
    def get_table_schema(self, table: TableRef) -> TableSchema: ...

    @abstractmethod
    def dialect_name(self) -> str: ...

    @abstractmethod
    def get_keywords(self) -> list[str]: ...
