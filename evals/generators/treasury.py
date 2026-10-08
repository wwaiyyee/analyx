"""Planted-truth treasury dataset generator for evaluation suites per §13."""

from datetime import datetime, timezone
import random
from typing import Any, Tuple
import pandas as pd


def generate_planted_treasury(
    num_rows: int = 1200,
    seed: int = 42,
    reference_date: datetime = datetime(2024, 12, 15, tzinfo=timezone.utc),
) -> Tuple[pd.DataFrame, dict[str, Any]]:
    """Generate a realistic treasury dataset with known planted ground truth metrics.

    Ground truth invariants:
    - Reference date: 2024-12-15 (Mid-month)
    - Last complete month: November 2024 (2024-11-01 to 2024-11-30)
    - Prior complete month: October 2024 (2024-10-01 to 2024-10-31)
    - Planted Outflow in Nov 2024: exactly 1,200,000.00 USD
    - Planted Inflow in Nov 2024: exactly 2,500,000.00 USD
    - Net Flow in Nov 2024: +1,300,000.00 USD
    - Top counterparty: 'Vendor_Alpha_SecOps' with exactly 500,000.00 USD outflow in Nov 2024
    - Outflow spike on 2024-11-14
    """
    random.seed(seed)

    rows = []

    # 1. Plant October baseline: Outflow = 1,000,000, Inflow = 1,800,000
    rows.append({
        "tx_signature": "oct_inflow_tx_001",
        "block_time": "2024-10-05T12:00:00Z",
        "counterparty": "Staking_Pool_Rewards",
        "amount_usd": 1800000.0,
        "token_symbol": "USDC",
        "direction": "in",
        "tx_status": "success",
    })
    rows.append({
        "tx_signature": "oct_outflow_tx_001",
        "block_time": "2024-10-10T14:00:00Z",
        "counterparty": "General_Payroll",
        "amount_usd": 1000000.0,
        "token_symbol": "USDC",
        "direction": "out",
        "tx_status": "success",
    })

    # 2. Plant November exact ground truth:
    # Nov Inflow: exactly 2,500,000.00
    rows.append({
        "tx_signature": "nov_inflow_seed_01",
        "block_time": "2024-11-02T10:00:00Z",
        "counterparty": "Grant_Foundation",
        "amount_usd": 1500000.0,
        "token_symbol": "USDC",
        "direction": "in",
        "tx_status": "success",
    })
    rows.append({
        "tx_signature": "nov_inflow_seed_02",
        "block_time": "2024-11-20T11:30:00Z",
        "counterparty": "Ecosystem_Rewards",
        "amount_usd": 1000000.0,
        "token_symbol": "USDC",
        "direction": "in",
        "tx_status": "success",
    })

    # Nov Outflows: exactly 1,200,000.00
    # Top counterparty: Vendor_Alpha_SecOps (500,000.00)
    rows.append({
        "tx_signature": "nov_outflow_top_vendor",
        "block_time": "2024-11-14T16:45:00Z",
        "counterparty": "Vendor_Alpha_SecOps",
        "amount_usd": 500000.0,
        "token_symbol": "USDC",
        "direction": "out",
        "tx_status": "success",
    })

    # Secondary counterparties totaling 700,000.00
    rows.append({
        "tx_signature": "nov_outflow_payroll",
        "block_time": "2024-11-15T12:00:00Z",
        "counterparty": "Core_Contributors",
        "amount_usd": 400000.0,
        "token_symbol": "USDC",
        "direction": "out",
        "tx_status": "success",
    })
    rows.append({
        "tx_signature": "nov_outflow_infra",
        "block_time": "2024-11-18T09:15:00Z",
        "counterparty": "RPC_Infra_Cluster",
        "amount_usd": 200000.0,
        "token_symbol": "USDC",
        "direction": "out",
        "tx_status": "success",
    })
    rows.append({
        "tx_signature": "nov_outflow_marketing",
        "block_time": "2024-11-25T15:00:00Z",
        "counterparty": "Global_Hackathon_Prize",
        "amount_usd": 100000.0,
        "token_symbol": "USDC",
        "direction": "out",
        "tx_status": "success",
    })

    # 3. Add background transactions (earlier months & partial current month)
    for i in range(num_rows - len(rows)):
        is_dec = random.random() < 0.2
        if is_dec:
            day = random.randint(1, 14)
            dt_str = f"2024-12-{day:02d}T{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00Z"
        else:
            month = random.randint(6, 9)
            day = random.randint(1, 28)
            dt_str = f"2024-{month:02d}-{day:02d}T{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00Z"

        direction = "in" if random.random() < 0.4 else "out"
        rows.append({
            "tx_signature": f"tx_bg_{i:04d}",
            "block_time": dt_str,
            "counterparty": f"Account_{random.randint(1, 50)}",
            "amount_usd": round(random.uniform(500.0, 50000.0), 2),
            "token_symbol": "USDC" if random.random() < 0.8 else "SOL",
            "direction": direction,
            "tx_status": "success",
        })

    df = pd.DataFrame(rows)

    ground_truth = {
        "last_complete_month": "2024-11",
        "nov_outflow_usd": 1200000.0,
        "nov_inflow_usd": 2500000.0,
        "nov_net_flow_usd": 1300000.0,
        "top_counterparty_nov": "Vendor_Alpha_SecOps",
        "top_counterparty_nov_amount": 500000.0,
        "oct_outflow_usd": 1000000.0,
        "mom_outflow_change_pct": 20.0,  # +20% (1.2M vs 1.0M)
        "spike_date": "2024-11-14",
    }

    return df, ground_truth
