"""Spec-to-SQL compiler producing parameterized DuckDB queries per §8.5."""

from datetime import date, datetime
from typing import Any, Tuple

from backend.core.errors import ValidationError
from backend.engine.models import AnalysisSpec, Filter
from backend.semantic.metrics import MetricPackRegistry, default_registry


def _compile_filter(flt: Filter) -> Tuple[str, list[Any]]:
    """Compile a single Filter object into parameterized SQL clause and params."""
    col = flt.column
    op = flt.op
    val = flt.value

    if op == "is_null":
        return f"{col} IS NULL", []
    if op == "not_null":
        return f"{col} IS NOT NULL", []
    if op == "=":
        return f"{col} = ?", [str(val)]
    if op == "!=":
        return f"{col} != ?", [str(val)]
    if op == ">":
        return f"{col} > ?", [str(val)]
    if op == ">=":
        return f"{col} >= ?", [str(val)]
    if op == "<":
        return f"{col} < ?", [str(val)]
    if op == "<=":
        return f"{col} <= ?", [str(val)]
    if op == "in":
        items = list(val) if isinstance(val, (list, tuple, set)) else [val]
        placeholders = ", ".join(["?"] * len(items))
        return f"{col} IN ({placeholders})", [str(x) for x in items]
    if op == "not_in":
        items = list(val) if isinstance(val, (list, tuple, set)) else [val]
        placeholders = ", ".join(["?"] * len(items))
        return f"{col} NOT IN ({placeholders})", [str(x) for x in items]
    if op == "between":
        items = list(val)
        return f"{col} BETWEEN ? AND ?", [str(items[0]), str(items[1])]

    raise ValidationError(f"Unsupported operator '{op}'")


def _format_time_bound(val: date | datetime | str | None, is_end: bool = False) -> str | None:
    """Format date/datetime bound for SQL timestamp comparison."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, date):
        suffix = " 23:59:59" if is_end else " 00:00:00"
        return f"{val.isoformat()}{suffix}"
    s = str(val).strip()
    if len(s) == 10 and is_end:
        return f"{s} 23:59:59"
    return s


def compile_spec(
    spec: AnalysisSpec,
    table_name: str = "t",
    registry: MetricPackRegistry | None = None,
) -> Tuple[str, list[Any]]:
    """Compile AnalysisSpec into a parameterized SQL query string and parameter list."""
    reg = registry or default_registry
    params: list[Any] = []
    where_clauses: list[str] = []

    # 1. Compile filters
    for flt in spec.filters:
        clause, flt_params = _compile_filter(flt)
        where_clauses.append(clause)
        params.extend(flt_params)

    # 2. Check for period-over-period comparison
    is_pop = (
        spec.comparison.kind == "period_over_period"
        and spec.time is not None
        and spec.comparison.baseline is not None
    )

    if is_pop:
        # Dual-window conditional aggregation
        time_col = spec.time.column
        curr_start = _format_time_bound(spec.time.start, is_end=False)
        curr_end = _format_time_bound(spec.time.end, is_end=True)
        base_start = _format_time_bound(spec.comparison.baseline.start, is_end=False)
        base_end = _format_time_bound(spec.comparison.baseline.end, is_end=True)

        # Outer time bounds to restrict overall scan
        min_start = min(s for s in (curr_start, base_start) if s is not None)
        max_end = max(s for s in (curr_end, base_end) if s is not None)

        if min_start:
            where_clauses.append(f"{time_col} >= ?")
            params.append(min_start)
        if max_end:
            where_clauses.append(f"{time_col} <= ?")
            params.append(max_end)

        select_exprs: list[str] = []
        for dim in spec.dimensions:
            select_exprs.append(dim)

        # Window condition expressions
        curr_cond = f"({time_col} >= '{curr_start}' AND {time_col} <= '{curr_end}')"
        base_cond = f"({time_col} >= '{base_start}' AND {time_col} <= '{base_end}')"

        for m_ref in spec.metrics:
            m_def = reg.find_metric(m_ref.name)
            if not m_def or not m_def.sql:
                continue

            # Injected window condition into CASE expressions
            curr_sql = m_def.sql.replace("WHERE ", f"WHERE {curr_cond} AND ")
            if "WHEN " in curr_sql:
                curr_sql = curr_sql.replace("WHEN ", f"WHEN {curr_cond} AND ")
            else:
                curr_sql = f"CASE WHEN {curr_cond} THEN ({m_def.sql}) END"

            base_sql = m_def.sql.replace("WHERE ", f"WHERE {base_cond} AND ")
            if "WHEN " in base_sql:
                base_sql = base_sql.replace("WHEN ", f"WHEN {base_cond} AND ")
            else:
                base_sql = f"CASE WHEN {base_cond} THEN ({m_def.sql}) END"

            select_exprs.append(f"{curr_sql} AS current_{m_ref.name}")
            select_exprs.append(f"{base_sql} AS baseline_{m_ref.name}")

    else:
        # Standard single-window query
        if spec.time:
            time_col = spec.time.column
            t_start = _format_time_bound(spec.time.start, is_end=False)
            t_end = _format_time_bound(spec.time.end, is_end=True)
            if t_start:
                where_clauses.append(f"{time_col} >= ?")
                params.append(t_start)
            if t_end:
                where_clauses.append(f"{time_col} <= ?")
                params.append(t_end)

        select_exprs: list[str] = []
        # Time series grain
        if spec.time and spec.time.grain:
            time_col = spec.time.column
            grain = spec.time.grain.lower()
            select_exprs.append(f"DATE_TRUNC('{grain}', CAST({time_col} AS TIMESTAMP)) AS {time_col}_grain")

        # Dimensions
        for dim in spec.dimensions:
            select_exprs.append(dim)

        # Metrics
        for m_ref in spec.metrics:
            m_def = reg.find_metric(m_ref.name)
            if m_def and m_def.sql:
                select_exprs.append(f"{m_def.sql} AS {m_ref.name}")

    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    select_sql = ", ".join(select_exprs) if select_exprs else "*"

    group_cols: list[str] = []
    if spec.time and spec.time.grain and not is_pop:
        group_cols.append(f"{spec.time.column}_grain")
    group_cols.extend(spec.dimensions)

    group_sql = f" GROUP BY {', '.join(group_cols)}" if group_cols else ""

    # Order by
    order_sql = ""
    if spec.order_by:
        dir_str = "DESC" if spec.descending else "ASC"
        order_sql = f" ORDER BY {spec.order_by} {dir_str}"

    # Limit
    limit_sql = ""
    if spec.limit:
        limit_sql = f" LIMIT {int(spec.limit)}"

    sql = f"SELECT {select_sql} FROM {table_name}{where_sql}{group_sql}{order_sql}{limit_sql}"
    return sql, params
