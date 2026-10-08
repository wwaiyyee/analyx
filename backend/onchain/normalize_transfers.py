"""Normalization of Solana parsed JSON transactions into onchain_transfers schema per §7.2 and §8.3."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import pandas as pd

from backend.onchain.source import RawTxBatch

# Stablecoin mint allow-list
STABLECOIN_MINTS: dict[str, str] = {
    # Mainnet USDC
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    # Devnet USDC
    "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU": "USDC",
    # Mainnet USDT
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
}


def _get_account_index(account_keys: list[Any], address: str) -> int | None:
    """Find index of an account in transaction message accountKeys."""
    for idx, key in enumerate(account_keys):
        pubkey = key.get("pubkey") if isinstance(key, dict) else str(key)
        if pubkey == address:
            return idx
    return None


def normalize_raw_batch(batch: RawTxBatch) -> pd.DataFrame:
    """Transform raw transaction JSON records into normalized onchain_transfers table rows."""
    wallet = batch.address
    rows: list[dict[str, Any]] = []

    for tx_obj in batch.transactions:
        slot = tx_obj.get("slot", 0)
        block_time_raw = tx_obj.get("blockTime")
        if block_time_raw:
            block_time = datetime.fromtimestamp(block_time_raw, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        else:
            block_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        tx_inner = tx_obj.get("transaction", {})
        signatures = tx_inner.get("signatures", [])
        sig = signatures[0] if signatures else "unknown_sig"

        msg = tx_inner.get("message", {})
        account_keys = msg.get("accountKeys", [])
        wallet_idx = _get_account_index(account_keys, wallet)

        meta = tx_obj.get("meta", {})
        err = meta.get("err")
        is_failed = err is not None
        fee = meta.get("fee", 5000) if wallet_idx == 0 else 0

        # Handle failed transaction
        if is_failed:
            rows.append({
                "tx_signature": sig,
                "slot": slot,
                "block_time": block_time,
                "wallet": wallet,
                "counterparty": None,
                "counterparty_confidence": "none",
                "direction": "out",
                "token_mint": "SOL",
                "token_symbol": "SOL",
                "decimals": 9,
                "amount_raw": "0",
                "amount": "0.00",
                "price_usd": None,
                "amount_usd": None,
                "fee_lamports": fee,
                "tx_status": "failed",
                "source": batch.source,
            })
            continue

        # 1. SPL Token Balances Delta
        pre_tokens = meta.get("preTokenBalances", [])
        post_tokens = meta.get("postTokenBalances", [])

        # Map balances by (owner, mint) -> raw amount int
        pre_map: dict[tuple[str, str], int] = {}
        post_map: dict[tuple[str, str], int] = {}
        decimals_map: dict[str, int] = {}

        for t in pre_tokens:
            owner = t.get("owner")
            mint = t.get("mint")
            if owner and mint:
                amt = int(t.get("uiTokenAmount", {}).get("amount", "0"))
                pre_map[(owner, mint)] = amt
                decimals_map[mint] = t.get("uiTokenAmount", {}).get("decimals", 6)

        for t in post_tokens:
            owner = t.get("owner")
            mint = t.get("mint")
            if owner and mint:
                amt = int(t.get("uiTokenAmount", {}).get("amount", "0"))
                post_map[(owner, mint)] = amt
                decimals_map[mint] = t.get("uiTokenAmount", {}).get("decimals", 6)

        all_mints = {mint for (_, mint) in list(pre_map.keys()) + list(post_map.keys())}

        for mint in all_mints:
            w_pre = pre_map.get((wallet, mint), 0)
            w_post = post_map.get((wallet, mint), 0)
            delta = w_post - w_pre

            if delta == 0:
                continue

            decimals = decimals_map.get(mint, 6)
            direction = "in" if delta > 0 else "out"
            abs_delta = abs(delta)
            amount_dec = Decimal(abs_delta) / (Decimal(10) ** decimals)
            amount_str = f"{amount_dec:.{decimals}f}".rstrip("0").rstrip(".")

            # Find counterparties with opposite sign delta
            opposite_sign = -1 if delta > 0 else 1
            candidates: list[tuple[str, int]] = []
            all_owners = {o for (o, m) in list(pre_map.keys()) + list(post_map.keys()) if m == mint and o != wallet}

            for o in all_owners:
                o_delta = post_map.get((o, mint), 0) - pre_map.get((o, mint), 0)
                if (opposite_sign > 0 and o_delta > 0) or (opposite_sign < 0 and o_delta < 0):
                    candidates.append((o, abs(o_delta)))

            counterparty: str | None = None
            confidence = "none"

            if len(candidates) == 1:
                counterparty = candidates[0][0]
                confidence = "high"
            elif len(candidates) > 1:
                candidates.sort(key=lambda c: c[1], reverse=True)
                counterparty = candidates[0][0]
                confidence = "low"

            token_symbol = STABLECOIN_MINTS.get(mint)
            price_usd = "1.00" if token_symbol in ("USDC", "USDT") else None
            amount_usd = f"{amount_dec:.2f}" if price_usd else None

            rows.append({
                "tx_signature": sig,
                "slot": slot,
                "block_time": block_time,
                "wallet": wallet,
                "counterparty": counterparty,
                "counterparty_confidence": confidence,
                "direction": direction,
                "token_mint": mint,
                "token_symbol": token_symbol,
                "decimals": decimals,
                "amount_raw": str(abs_delta),
                "amount": amount_str,
                "price_usd": price_usd,
                "amount_usd": amount_usd,
                "fee_lamports": fee,
                "tx_status": "success",
                "source": batch.source,
            })

        # 2. Native SOL Transfer
        if wallet_idx is not None:
            pre_lamports = meta.get("preBalances", [])
            post_lamports = meta.get("postBalances", [])
            if wallet_idx < len(pre_lamports) and wallet_idx < len(post_lamports):
                raw_sol_delta = post_lamports[wallet_idx] - pre_lamports[wallet_idx]
                # If wallet is fee payer (idx 0), add back fee to isolate transfer delta
                transfer_lamports = raw_sol_delta + fee if wallet_idx == 0 else raw_sol_delta

                if transfer_lamports != 0:
                    sol_dir = "in" if transfer_lamports > 0 else "out"
                    abs_lamports = abs(transfer_lamports)
                    sol_amount = Decimal(abs_lamports) / Decimal(1_000_000_000)

                    # Look for counterparty in account keys with opposite delta
                    cp_sol: str | None = None
                    cp_conf = "none"
                    other_candidates: list[tuple[str, int]] = []
                    for i, k in enumerate(account_keys):
                        if i == wallet_idx:
                            continue
                        if i < len(pre_lamports) and i < len(post_lamports):
                            d = post_lamports[i] - pre_lamports[i]
                            if (transfer_lamports < 0 and d > 0) or (transfer_lamports > 0 and d < 0):
                                pub = k.get("pubkey") if isinstance(k, dict) else str(k)
                                other_candidates.append((pub, abs(d)))

                    if len(other_candidates) == 1:
                        cp_sol = other_candidates[0][0]
                        cp_conf = "high"
                    elif len(other_candidates) > 1:
                        other_candidates.sort(key=lambda c: c[1], reverse=True)
                        cp_sol = other_candidates[0][0]
                        cp_conf = "low"

                    rows.append({
                        "tx_signature": sig,
                        "slot": slot,
                        "block_time": block_time,
                        "wallet": wallet,
                        "counterparty": cp_sol,
                        "counterparty_confidence": cp_conf,
                        "direction": sol_dir,
                        "token_mint": "SOL",
                        "token_symbol": "SOL",
                        "decimals": 9,
                        "amount_raw": str(abs_lamports),
                        "amount": f"{sol_amount:.9f}".rstrip("0").rstrip("."),
                        "price_usd": None,
                        "amount_usd": None,
                        "fee_lamports": fee,
                        "tx_status": "success",
                        "source": batch.source,
                    })

    cols = [
        "tx_signature",
        "slot",
        "block_time",
        "wallet",
        "counterparty",
        "counterparty_confidence",
        "direction",
        "token_mint",
        "token_symbol",
        "decimals",
        "amount_raw",
        "amount",
        "price_usd",
        "amount_usd",
        "fee_lamports",
        "tx_status",
        "source",
    ]
    if not rows:
        return pd.DataFrame(columns=cols)

    return pd.DataFrame(rows)[cols]
