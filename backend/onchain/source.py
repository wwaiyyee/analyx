"""OnchainSource protocol and raw transaction batch data models per §8.3."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable


@dataclass
class RawTxBatch:
    """Raw batch of fetched Solana transactions and pagination bounds."""

    address: str
    cluster: str
    transactions: list[dict[str, Any]] = field(default_factory=list)
    from_slot: int | None = None
    to_slot: int | None = None
    complete_history: bool = False
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "rpc"  # "rpc" or "fixture"


@runtime_checkable
class OnchainSource(Protocol):
    """Protocol for fetching on-chain Solana transactions."""

    async def fetch(
        self,
        address: str,
        cluster: str = "devnet",
        max_signatures: int = 1000,
    ) -> RawTxBatch:
        """Fetch raw transaction records for an address up to max_signatures."""
        ...
