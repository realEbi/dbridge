import pandas as pd

from dbridge.adapters.capabilities import CapabilityEnums
from dbridge.adapters.interfaces import DBAdapter
from dbridge.config import NO_COLS_FETCH

from .models import INSTALLED_ADAPTERS, DbCatalog

try:
    import snowflake.connector
    from snowflake.connector import DictCursor
    from snowflake.connector.connection import SnowflakeConnection

    INSTALLED_ADAPTERS.append("snowflake")
except ImportError:
    pass


class SnowflakeAdapter(DBAdapter):
    def __init__(self, config: dict[str, str]) -> None:
        super().__init__(config)
        assert (
            snowflake.connector and SnowflakeConnection
        ), "You should `pip install snowflake.connection` to be able to use this module"
        self.adapter_name = "snowflake"
        self.connection: SnowflakeConnection = snowflake.connector.connect(
            **self.config
        )

    def is_single_connection(self) -> bool:
        return False

    def get_capabilities(self) -> list[CapabilityEnums]:
        return [CapabilityEnums.USE_DB, CapabilityEnums.USE_SCHEMA]

    def _fetch_rows_value_key(self, rows, name: str) -> list[str]:
        ind = 0
        for ind, row in enumerate(rows.description):
            if row.name == name:
                break
        return [d[ind] for d in rows.fetchall()]

    def _get_show_names(self, entity: str) -> list[str]:
        query = f"show {entity}"
        rows = self.connection.cursor().execute(query)
        return self._fetch_rows_value_key(rows, "name")

    def show_dbs(self) -> list[str]:
        return self._get_show_names("databases")

    def show_columns(self, table_name: str, dbname=None, schema_name=None) -> list[str]:
        columns = []
        if dbname and schema_name:
            query = f"select column_name as name from {dbname}.INFORMATION_SCHEMA.columns where table_schema='{schema_name.upper()}' and table_name='{table_name.upper()}';"
            rows = self.connection.cursor().execute(query)
            columns = self._fetch_rows_value_key(rows, "name")
        return columns

    def get_all_columns(self, dbname: str, **args) -> list[str]:
        columns = []
        if dbname:
            query = f"select column_name as name, table_name as tbl from {dbname}.INFORMATION_SCHEMA.columns limit {NO_COLS_FETCH};"
            rows = self.connection.cursor().execute(query)
            columns = [
                f"{tbl}.{col}"
                for tbl, col in zip(
                    self._fetch_rows_value_key(rows, "tbl"),
                    self._fetch_rows_value_key(rows, "name"),
                )
            ]
        return columns

    def show_tables_schema_dbs(self) -> list[DbCatalog]:
        dbname = "dbname".upper()
        schema = "schema_name".upper()
        table = "table_name".upper()
        dbs = self._get_show_names("databases")
        tables_schema_dbs = []
        for db in dbs:
            query = f"select TABLE_CATALOG as {dbname}, TABLE_SCHEMA as {schema}, TABLE_NAME as {table} from {db}.information_schema.tables;"
            rows_dict = self.connection.cursor(DictCursor).execute(query)
            tables_schema_dbs.extend(rows_dict)
        df = pd.DataFrame(tables_schema_dbs)
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
        self.logger.info(f"Running query:\n{query}")
        for cur in self.connection.execute_string(query):
            data = cur.fetchmany(limit)
        return self._get_dict_items(data, [desc.name for desc in cur.description])
