"""Solana JSON-RPC transaction client implementing pagination, throttling, and offline fallback."""

import asyncio
import json
from pathlib import Path
from typing import Any
import httpx

from backend.config import settings
from backend.onchain.source import OnchainSource, RawTxBatch

FIXTURE_PATH = Path("fixtures/onchain_sample_txs.json")


class RpcSource(OnchainSource):
    """Fetches transactions from Solana JSON-RPC or falls back to offline fixtures."""

    def __init__(
        self,
        rpc_url: str | None = None,
        offline_mode: bool | None = None,
        rate_limit_delay_seconds: float = 0.05,
    ) -> None:
        self.rpc_url = rpc_url or settings.solana_rpc_url
        self.offline_mode = offline_mode if offline_mode is not None else settings.onchain_offline_mode
        self.delay = rate_limit_delay_seconds

    def _load_offline_fixture(self, address: str, cluster: str) -> RawTxBatch:
        """Load bundled fixture transactions for deterministic offline testing."""
        path = FIXTURE_PATH
        if not path.exists():
            path = Path(__file__).resolve().parent.parent.parent / "fixtures" / "onchain_sample_txs.json"

        with open(path, "r", encoding="utf-8") as f:
            txs = json.load(f)

        slots = [t.get("slot") for t in txs if t.get("slot") is not None]
        from_slot = min(slots) if slots else 0
        to_slot = max(slots) if slots else 0

        return RawTxBatch(
            address=address,
            cluster=cluster,
            transactions=txs,
            from_slot=from_slot,
            to_slot=to_slot,
            complete_history=True,
            source="fixture",
        )

    async def _rpc_call(self, client: httpx.AsyncClient, method: str, params: list[Any]) -> Any:
        """Execute single JSON-RPC call with exponential backoff on 429."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }

        retries = 3
        backoff = 0.5
        for attempt in range(retries):
            try:
                resp = await client.post(self.rpc_url, json=payload, timeout=20.0)
                if resp.status_code == 429:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    raise RuntimeError(f"RPC Error: {data['error']}")
                return data.get("result")
            except (httpx.HTTPError, RuntimeError) as e:
                if attempt == retries - 1:
                    raise e
                await asyncio.sleep(backoff)
                backoff *= 2

    async def fetch(
        self,
        address: str,
        cluster: str = "devnet",
        max_signatures: int = 1000,
    ) -> RawTxBatch:
        """Fetch transactions via RPC or return offline fixture if offline_mode is enabled."""
        if self.offline_mode:
            return self._load_offline_fixture(address, cluster)

        try:
            async with httpx.AsyncClient() as client:
                # 1. Paginate getSignaturesForAddress
                all_sigs: list[dict[str, Any]] = []
                before: str | None = None
                complete_history = False

                while len(all_sigs) < max_signatures:
                    limit = min(100, max_signatures - len(all_sigs))
                    params: list[Any] = [address, {"limit": limit}]
                    if before:
                        params[1]["before"] = before

                    batch = await self._rpc_call(client, "getSignaturesForAddress", params)
                    if not batch:
                        complete_history = True
                        break

                    all_sigs.extend(batch)
                    before = batch[-1]["signature"]
                    if len(batch) < limit:
                        complete_history = True
                        break

                # 2. Fetch full parsed transaction for each signature
                txs: list[dict[str, Any]] = []
                for sig_info in all_sigs:
                    sig = sig_info["signature"]
                    tx_data = await self._rpc_call(
                        client,
                        "getTransaction",
                        [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
                    )
                    if tx_data:
                        txs.append(tx_data)
                    if self.delay > 0:
                        await asyncio.sleep(self.delay)

                slots = [t.get("slot") for t in txs if t.get("slot") is not None]
                return RawTxBatch(
                    address=address,
                    cluster=cluster,
                    transactions=txs,
                    from_slot=min(slots) if slots else None,
                    to_slot=max(slots) if slots else None,
                    complete_history=complete_history,
                    source="rpc",
                )
        except Exception:
            # Fall back to offline fixture on failure
            return self._load_offline_fixture(address, cluster)
