"""In-process DuckDB execution backend querying Parquet files per §8.5."""

from decimal import Decimal
from typing import Any
import duckdb

from backend.backends.base import ExecutionBackend, QueryResult


def _format_cell(val: Any) -> Any:
    """Format DuckDB query output cells deterministically."""
    if val is None:
        return None
    if isinstance(val, (Decimal, float)):
        # Normalize numeric results without scientific notation or trailing zeros if integer
        d = Decimal(str(val))
        return f"{d:.2f}" if "." in str(val) else str(val)
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return val


class LocalBackend(ExecutionBackend):
    """Local in-process DuckDB analytical query execution backend."""

    def __init__(self) -> None:
        pass

    def execute_query(
        self,
        sql: str,
        params: list[Any],
        table_map: dict[str, str],
    ) -> QueryResult:
        """Run compiled SQL query in a fresh in-process DuckDB connection."""
        conn = duckdb.connect(":memory:")

        try:
            # Register parquet files as temporary views
            for alias, path in table_map.items():
                escaped_path = path.replace("'", "''")
                conn.execute(
                    f"CREATE TEMPORARY VIEW {alias} AS SELECT * FROM read_parquet('{escaped_path}')"
                )

            cursor = conn.execute(sql, params)
            col_names = [desc[0] for desc in cursor.description]
            raw_rows = cursor.fetchall()

            formatted_rows: list[list[Any]] = []
            for row in raw_rows:
                formatted_rows.append([_format_cell(c) for c in row])

            return QueryResult(
                columns=col_names,
                rows=formatted_rows,
                row_count=len(formatted_rows),
            )
        finally:
            conn.close()
