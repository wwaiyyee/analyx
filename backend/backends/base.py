"""ExecutionBackend interface protocol per §8.5."""

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class QueryResult:
    """Standardized tabular query execution result with decimal strings for money."""

    columns: list[str]
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
        }


@runtime_checkable
class ExecutionBackend(Protocol):
    """Protocol for executing compiled SQL queries against dataset tables."""

    def execute_query(
        self,
        sql: str,
        params: list[Any],
        table_map: dict[str, str],
    ) -> QueryResult:
        """Execute parameterized SQL query where table_map maps aliases to Parquet paths."""
        ...
