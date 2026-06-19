from operator import mul

import pandas as pd

from dbridge.adapters.capabilities import CapabilityEnums
from dbridge.adapters.interfaces import DBAdapter

from .models import INSTALLED_ADAPTERS, DbCatalog

try:
    import mysql.connector

    INSTALLED_ADAPTERS.append("mysql")
except ImportError:
    pass


class MySqlAdapter(DBAdapter):
    def __init__(self, config: dict[str, str]) -> None:
        super().__init__(config)
        self.adapter_name = "mysql"
        self.connection = mysql.connector.connect(**self.config)

    def is_single_connection(self) -> bool:
        return False

    def get_capabilities(self) -> list[CapabilityEnums]:
        return [CapabilityEnums.USE_DB]

    def show_dbs(self) -> list[str]:
        query = (
            "select distinct TABLE_SCHEMA as database from information_schema.tables"
        )
        dbs = self.run_query(query)
        return [
            db
            for d in dbs
            if (db := d["database"])
            not in ["information_schema", "mysql", "performance_schema", "sys"]
        ]

    def show_tables(self, *args, **kwargs) -> list[str]:
        query = 'SELECT TABLE_NAME as tbl FROM information_schema.tables where TABLE_SCHEMA not in ("sys", "mysql", "inforrmation_schema", "performance_schema")'
        tables = self.run_query(query, 500)
        return [d["tbl"] for d in tables]

    def show_columns(self, table_name: str, *args, **kwargs) -> list[str]:
        query = f'SELECT COLUMN_NAME as col FROM information_schema.columns where TABLE_NAME="{table_name}"'
        columns = self.run_query(query)
        return [d["col"] for d in columns]

    def get_all_columns(self, dbname: str, **args) -> list[str]:
        query = "SELECT COLUMN_NAME as col, TABLE_NAME as tbl FROM information_schema.columns limit 1000"
        columns = self.run_query(query)
        return [d["tbl"] + "." + d["col"] for d in columns]

    def show_tables_schema_dbs(self) -> list[DbCatalog]:
        dbname = "dbname"
        schema = "cschema"
        table = "ctable"
        query = f'SELECT TABLE_CATALOG as {schema}, TABLE_SCHEMA as {dbname}, TABLE_NAME as {table} FROM information_schema.tables where TABLE_SCHEMA not in ("sys", "mysql", "information_schema", "performance_schema")'
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
        with self.connection.cursor(buffered=True) as cursor:
            results = cursor.execute(query, multi=True)
            data = []
            for rows in results:
                if rows.with_rows:
                    data = rows.fetchmany(limit)
            return self._get_dict_items(data, [desc[0] for desc in rows.description])
