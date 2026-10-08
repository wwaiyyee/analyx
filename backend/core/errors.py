"""Custom domain exceptions for Analyx backend."""

from typing import Any


class AnalyxError(Exception):
    """Base exception for all Analyx application errors."""

    def __init__(
        self,
        message: str,
        code: str = "ANALYX_ERROR",
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize error details for JSON API responses."""
        payload: dict[str, Any] = {
            "error": self.code,
            "message": self.message,
        }
        if self.details:
            payload["details"] = self.details
        return payload


class ValidationError(AnalyxError):
    """Raised when data or model validation fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details,
        )


class FloatNotAllowedError(ValidationError):
    """Raised when a float is encountered in canonical hashing or analysis spec."""

    def __init__(self, message: str = "Floats are not permitted in canonical hashing or specs") -> None:
        super().__init__(message=message, details={"hint": "Use decimal strings or integers"})


class IngestError(AnalyxError):
    """Raised during dataset ingestion or parsing."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="INGEST_ERROR",
            status_code=400,
            details=details,
        )


class EngineError(AnalyxError):
    """Raised during analysis compilation or query execution."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="ENGINE_ERROR",
            status_code=500,
            details=details,
        )


class SufficiencyError(AnalyxError):
    """Raised when data is insufficient to compute requested metrics."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="INSUFFICIENT_DATA",
            status_code=400,
            details=details,
        )


class AttestationError(AnalyxError):
    """Raised when attestation bundle generation or on-chain verification fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="ATTESTATION_ERROR",
            status_code=400,
            details=details,
        )


class AuthError(AnalyxError):
    """Raised when wallet signature verification or token authentication fails."""

    def __init__(self, message: str = "Authentication required", details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="AUTH_ERROR",
            status_code=401,
            details=details,
        )


class NotFoundError(AnalyxError):
    """Raised when an entity is not found."""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            message=f"{resource} '{identifier}' not found",
            code="NOT_FOUND",
            status_code=404,
            details={"resource": resource, "id": identifier},
        )


class BudgetExceededError(AnalyxError):
    """Raised when the agent exceeds its execution step or token budget."""

    def __init__(self, message: str = "Agent execution budget exceeded") -> None:
        super().__init__(
            message=message,
            code="BUDGET_EXCEEDED",
            status_code=429,
        )
