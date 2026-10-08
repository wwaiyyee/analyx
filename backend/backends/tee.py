"""Confidential Computing / TEE execution backend P1 stub per §8.5 and §12."""

from typing import Any
from backend.backends.base import ExecutionBackend, QueryResult
from backend.config import settings


class TeeBackend(ExecutionBackend):
    """TEE (Trusted Execution Environment) execution backend stub.

    Gated behind settings.feature_tee. Stubs enclave attestation measurement and remote execution.
    """

    def __init__(self) -> None:
        self.enabled = settings.feature_tee

    def execute_query(
        self,
        sql: str,
        params: list[Any],
        table_map: dict[str, str],
    ) -> QueryResult:
        """Execute query in a confidential enclave."""
        if not self.enabled:
            raise NotImplementedError(
                "TEE confidential execution backend is disabled. Enable with FEATURE_TEE=true."
            )

        # P1 Mock enclave response
        return QueryResult(
            columns=["enclave_status", "measurement_hash"],
            rows=[["mock_enclave_executed", "0" * 64]],
            row_count=1,
        )
