from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from dbridge.logging import get_logger


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


@dataclass
class TableSchema:
    name: str
    schema: str | None
    database: str | None
    columns: list[ColumnDef] = field(default_factory=list)
    primary_keys: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)


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
    def list_databases(self) -> list[str]: ...

    @abstractmethod
    def list_schemas(self, database: str | None = None) -> list[str]: ...

    @abstractmethod
    def list_tables(
        self, database: str | None = None, schema: str | None = None
    ) -> list[str]: ...

    @abstractmethod
    def get_table_schema(self, fqn: str) -> TableSchema: ...

    @abstractmethod
    def dialect_name(self) -> str: ...

    @abstractmethod
    def get_keywords(self) -> list[str]: ...
