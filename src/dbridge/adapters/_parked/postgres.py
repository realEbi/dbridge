import pandas as pd

from dbridge.adapters.capabilities import CapabilityEnums
from dbridge.adapters.interfaces import DBAdapter

from .models import INSTALLED_ADAPTERS, DbCatalog

try:
    import psycopg2

    INSTALLED_ADAPTERS.append("postgres")
except ImportError:
    pass


class PostgresAdapter(DBAdapter):
    def __init__(self, config: dict[str, str]) -> None:
        super().__init__(config)
        self.adapter_name = "postgres"
        self.connection = psycopg2.connect(**self.config)

    def is_single_connection(self) -> bool:
        return False

    def get_capabilities(self) -> list[CapabilityEnums]:
        return [CapabilityEnums.USE_DB, CapabilityEnums.USE_SCHEMA]

    def show_columns(self, table_name: str, *args, **kwargs) -> list[str]:
        query = f"SELECT COLUMN_NAME as col FROM information_schema.columns where TABLE_NAME='{table_name}'"
        columns = self.run_query(query)
        return [d["col"] for d in columns]

    def get_all_columns(self, dbname: str, **args) -> list[str]:
        query = "SELECT COLUMN_NAME as col, TABLE_NAME as tbl FROM information_schema.columns limit 1000"
        columns = self.run_query(query)
        return [d["tbl"] + "." + d["col"] for d in columns]

    def show_tables_schema_dbs(self) -> list[DbCatalog]:
        dbname = "dbname"
        schema = "schema_name"
        table = "tbl_name"
        query = f"select table_catalog as {dbname}, table_schema as {schema}, table_name as {table} from information_schema.tables"
        df = pd.DataFrame(self.run_query(query, 500))
        result = (
            df.groupby(dbname, group_keys=True)[[dbname, schema, table]]
            .apply(
                lambda group: {
                    "name": group.name,
                    "schemas": group.groupby(schema)[table]
                    .apply(list)
                    .reset_index()
                    .apply(
                        lambda x: {
                            "name": x[schema],
                            "tables": x[table],
                        },
                        axis=1,
                    )
                    .tolist(),
                }
            )
            .tolist()
        )
        return [DbCatalog.model_validate(r) for r in result]

    def run_query(self, query: str, limit=100) -> list[dict]:
        with self.connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchmany(limit)
            return self._get_dict_items(rows, [d.name for d in cursor.description])
