"""Input sanitization, CSV formula injection defense, and file size guards per §14."""

import io
import os
import zipfile
from typing import Any

from backend.core.errors import ValidationError

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_UNCOMPRESSED_XLSX_BYTES = 200 * 1024 * 1024  # 200 MB
MAX_COMPRESSION_RATIO = 100

ALLOWED_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls"}
FORMULA_CHARS = ("=", "+", "-", "@", "\t", "\r")


def validate_file_upload(filename: str, content: bytes) -> None:
    """Validate file extension, size, and guard against zip bombs."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"File extension '{ext}' not allowed. Allowed: {ALLOWED_EXTENSIONS}")

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            f"File size ({len(content):,} bytes) exceeds 50MB maximum limit."
        )

    # Zip-bomb check for XLSX archives
    if ext in (".xlsx", ".xls"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > MAX_UNCOMPRESSED_XLSX_BYTES:
                    raise ValidationError(
                        f"Decompressed XLSX size ({total_uncompressed:,} bytes) exceeds limit (zip-bomb guard)."
                    )
                ratio = total_uncompressed / max(len(content), 1)
                if ratio > MAX_COMPRESSION_RATIO:
                    raise ValidationError(
                        f"Suspicious XLSX compression ratio ({ratio:.1f}:1) exceeds limit (zip-bomb guard)."
                    )
        except zipfile.BadZipFile:
            if ext == ".xlsx":
                raise ValidationError("Invalid XLSX file format (not a valid zip container).")


def sanitize_csv_cell(value: Any) -> Any:
    """Disarm potential CSV formula injection (DDE) attacks while preserving valid numbers."""
    if not isinstance(value, str):
        return value

    s = value.strip()
    if not s:
        return value

    # If starts with formula character
    if s[0] in FORMULA_CHARS:
        # Allow ordinary negative numbers (e.g. -123.45)
        if s[0] == "-":
            try:
                float(s)
                return value
            except ValueError:
                pass
        # Prepend single quote to neutralize formula execution in Excel/Sheets
        return f"'{s}"

    return value
