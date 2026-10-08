"""Assumption ledger for explicit analytical tracking per §7.4 and §8.3."""

from typing import Literal
from backend.core.ids import generate_id
from backend.engine.models import Assumption

AssumptionSource = Literal["system", "user", "llm"]
AssumptionStatus = Literal["active", "revised", "overridden"]

# Common system assumption templates
ASSUMPTION_STABLECOIN_PARITY = "Treated USDC and USDT as pegged to 1.00 USD"
ASSUMPTION_EXCLUDE_UNPRICED = "Excluded unpriced token transactions from USD financial aggregates"
ASSUMPTION_EXCLUDE_FAILED_TXS = "Excluded transactions with tx_status='failed' from financial metrics"
ASSUMPTION_COMPLETE_MONTH_POLICY = "Excluded partial calendar months from period-over-period comparisons"


class AssumptionLedger:
    """In-memory and session-level ledger managing explicit domain assumptions."""

    def __init__(self) -> None:
        self._assumptions: dict[str, Assumption] = {}

    def add(
        self,
        session_id: str,
        text: str,
        source: AssumptionSource = "system",
        affects_finding_ids: list[str] | None = None,
    ) -> Assumption:
        """Register a new assumption in the ledger."""
        assumption_id = generate_id("as")
        assumption = Assumption(
            id=assumption_id,
            session_id=session_id,
            text=text,
            source=source,
            affects_finding_ids=affects_finding_ids or [],
            status="active",
        )
        self._assumptions[assumption_id] = assumption
        return assumption

    def get(self, assumption_id: str) -> Assumption | None:
        """Fetch an assumption by ID."""
        return self._assumptions.get(assumption_id)

    def list_for_session(
        self,
        session_id: str,
        status: AssumptionStatus | None = None,
    ) -> list[Assumption]:
        """List all assumptions for a session, optionally filtered by status."""
        items = [a for a in self._assumptions.values() if a.session_id == session_id]
        if status is not None:
            items = [a for a in items if a.status == status]
        return items

    def link_finding(self, assumption_id: str, finding_id: str) -> None:
        """Associate an assumption with an affected finding."""
        assumption = self._assumptions.get(assumption_id)
        if assumption and finding_id not in assumption.affects_finding_ids:
            assumption.affects_finding_ids.append(finding_id)

    def override(self, assumption_id: str) -> None:
        """Mark an assumption as overridden by user directive."""
        assumption = self._assumptions.get(assumption_id)
        if assumption:
            assumption.status = "overridden"
