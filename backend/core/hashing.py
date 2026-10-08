"""Canonical hashing and RFC 8785 JSON Canonicalization Scheme (JCS).

Per §11.2 and §8.1:
- sha256_hex(bytes | str): standard lowercase SHA-256
- jcs(obj): RFC 8785 canonical JSON bytes. Floats are strictly rejected.
- hash_obj(obj): sha256_hex(jcs(obj))
- canonical_table_hash(table): deterministic hash of normalized table data
- attestation_root(bundle): sha256_hex(b"analyx:v1:attestation\\n" + jcs(bundle))
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any

from backend.core.errors import FloatNotAllowedError


def sha256_hex(data: bytes | str) -> str:
    """Compute standard SHA-256 hash returned as lowercase hex string."""
    if isinstance(data, str):
        payload = data.encode("utf-8")
    elif isinstance(data, (bytes, bytearray)):
        payload = bytes(data)
    else:
        raise TypeError(f"Expected bytes or str, got {type(data).__name__}")
    return hashlib.sha256(payload).hexdigest().lower()


def _escape_jcs_string(s: str) -> str:
    """Escape string according to RFC 8785 §3.2.2.2."""
    out: list[str] = ['"']
    for char in s:
        cp = ord(char)
        if char == '"':
            out.append('\\"')
        elif char == "\\":
            out.append("\\\\")
        elif char == "\b":
            out.append("\\b")
        elif char == "\f":
            out.append("\\f")
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "\t":
            out.append("\\t")
        elif cp < 0x20:
            out.append(f"\\u{cp:04x}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _jcs_serialize(obj: Any) -> str:
    """Recursively serialize object to canonical JSON string per RFC 8785.

    Strictly rejects IEEE 754 floats to prevent cross-platform representation drift.
    """
    if obj is None:
        return "null"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, float):
        raise FloatNotAllowedError(
            f"Floats are not permitted in canonical hashing ({obj}). Use integers or decimal strings."
        )
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, str):
        return _escape_jcs_string(obj)
    if isinstance(obj, Decimal):
        # Format decimal deterministically as string or integer if exact
        return _escape_jcs_string(str(obj))
    if isinstance(obj, (datetime, date)):
        if isinstance(obj, datetime):
            if obj.tzinfo is None:
                utc_dt = obj.replace(tzinfo=timezone.utc)
            else:
                utc_dt = obj.astimezone(timezone.utc)
            return _escape_jcs_string(utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
        return _escape_jcs_string(obj.strftime("%Y-%m-%d"))
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(_jcs_serialize(x) for x in obj) + "]"
    if isinstance(obj, dict):
        # Keys must be sorted by UTF-16 code units (RFC 8785 §3.2.3)
        sorted_keys = sorted(obj.keys(), key=lambda k: str(k).encode("utf-16-be"))
        return "{" + ",".join(
            _escape_jcs_string(str(k)) + ":" + _jcs_serialize(obj[k]) for k in sorted_keys
        ) + "}"
    if hasattr(obj, "model_dump"):
        # Pydantic v2 support
        return _jcs_serialize(obj.model_dump(mode="json"))
    if hasattr(obj, "to_dict"):
        return _jcs_serialize(obj.to_dict())

    raise TypeError(f"Type {type(obj).__name__} is not JSON serializable in canonical form")


def jcs(obj: Any) -> bytes:
    """Encode an object into RFC 8785 canonical JSON UTF-8 bytes."""
    return _jcs_serialize(obj).encode("utf-8")


def hash_obj(obj: Any) -> str:
    """Compute lowercase hex SHA-256 of the RFC 8785 canonical JSON bytes."""
    return sha256_hex(jcs(obj))


def _format_cell_value(val: Any) -> str:
    """Format single cell value deterministically for canonical table hash."""
    if val is None:
        return "<NULL>"
    # Check for pandas/numpy NA or NaN
    val_str = str(val)
    if val_str in ("<NA>", "NaN", "nan", "None", "NaT"):
        return "<NULL>"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, Decimal)):
        return str(val)
    if isinstance(val, float):
        # In tabular data, if float is present, normalize without scientific notation
        # or trailing zeros after decimal point
        d = Decimal(str(val))
        return f"{d:f}".rstrip("0").rstrip(".") if "." in f"{d:f}" else f"{d:f}"
    if isinstance(val, datetime):
        if val.tzinfo is None:
            utc_dt = val.replace(tzinfo=timezone.utc)
        else:
            utc_dt = val.astimezone(timezone.utc)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    return str(val).strip()


def canonical_table_hash(table: Any, columns: list[str] | None = None) -> str:
    """Compute deterministic canonical table hash per §8.1.

    Rules:
    - Columns in schema order
    - Rows sorted by all columns
    - Each value formatted deterministically (UTF-8, ISO-8601 UTC dates, <NULL> for null)
    - Joined with \\n and hashed with SHA-256
    """
    col_names: list[str] = []
    rows_data: list[list[str]] = []

    # Handle pandas DataFrame
    if hasattr(table, "columns") and hasattr(table, "to_dict"):
        col_names = list(columns) if columns else list(table.columns)
        for _, row in table.iterrows():
            formatted_row = [_format_cell_value(row.get(col)) for col in col_names]
            rows_data.append(formatted_row)
    elif isinstance(table, list):
        if not table:
            col_names = list(columns) if columns else []
        elif isinstance(table[0], dict):
            col_names = list(columns) if columns else sorted(table[0].keys())
            for row in table:
                formatted_row = [_format_cell_value(row.get(col)) for col in col_names]
                rows_data.append(formatted_row)
        elif isinstance(table[0], (list, tuple)):
            col_names = list(columns) if columns else [f"col_{i}" for i in range(len(table[0]))]
            for row in table:
                formatted_row = [_format_cell_value(val) for val in row]
                rows_data.append(formatted_row)
    else:
        raise TypeError(f"Unsupported table type: {type(table).__name__}")

    # Sort rows by all columns deterministically
    rows_data.sort(key=lambda r: tuple(r))

    lines: list[str] = ["\t".join(col_names)]
    for r in rows_data:
        lines.append("\t".join(r))

    payload = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().lower()


def attestation_root(bundle: dict[str, Any]) -> str:
    """Compute attestation root per §11.2: sha256_hex(b"analyx:v1:attestation\\n" + jcs(bundle))."""
    prefix = b"analyx:v1:attestation\n"
    canonical_bytes = jcs(bundle)
    return sha256_hex(prefix + canonical_bytes)
