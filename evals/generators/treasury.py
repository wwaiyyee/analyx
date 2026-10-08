"""Planted-truth treasury dataset generator for evaluation suites per §13."""

from datetime import datetime, timedelta, timezone
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
    nov_start = datetime(2024, 11, 1, 0, 0, 0, tzinfo=timezone.utc)
    nov_end = datetime(2024, 11, 30, 23, 59, 59, tzinfo=timezone.utc)

    oct_start = datetime(2024, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    oct_end = datetime(2024, 10, 31, 23, 59, 59, tzinfo=timezone.utc)

    # 1. Plant October baseline: Outflow = 1,000,000, Inflow = 1,800,000
    rows.append({
        "tx_signature": "oct_inflow_tx_001",
        "block_time": datetime(2024, 10, 5, 12, 0, tzinfo=timezone.utc).isoformat(),
        "source": "Staking_Pool_Rewards",
        "destination": "Treasury_Vault",
        "amount_usd": 1800000.0,
        "token": "USDC",
        "direction": "inflow",
        "category": "yield",
        "status": "success",
    })
    rows.append({
        "tx_signature": "oct_outflow_tx_001",
        "block_time": datetime(2024, 10, 10, 14, 0, tzinfo=timezone.utc).isoformat(),
        "source": "Treasury_Vault",
        "destination": "General_Payroll",
        "amount_usd": 1000000.0,
        "token": "USDC",
        "direction": "outflow",
        "category": "operations",
        "status": "success",
    })

    # 2. Plant November exact ground truth:
    # Nov Inflow: exactly 2,500,000.00
    rows.append({
        "tx_signature": "nov_inflow_seed_01",
        "block_time": datetime(2024, 11, 2, 10, 0, tzinfo=timezone.utc).isoformat(),
        "source": "Grant_Foundation",
        "destination": "Treasury_Vault",
        "amount_usd": 1500000.0,
        "token": "USDC",
        "direction": "inflow",
        "category": "grant",
        "status": "success",
    })
    rows.append({
        "tx_signature": "nov_inflow_seed_02",
        "block_time": datetime(2024, 11, 20, 11, 30, tzinfo=timezone.utc).isoformat(),
        "source": "Ecosystem_Rewards",
        "destination": "Treasury_Vault",
        "amount_usd": 1000000.0,
        "token": "USDC",
        "direction": "inflow",
        "category": "yield",
        "status": "success",
    })

    # Nov Outflows: exactly 1,200,000.00
    # Top counterparty: Vendor_Alpha_SecOps (500,000.00)
    rows.append({
        "tx_signature": "nov_outflow_top_vendor",
        "block_time": datetime(2024, 11, 14, 16, 45, tzinfo=timezone.utc).isoformat(),
        "source": "Treasury_Vault",
        "destination": "Vendor_Alpha_SecOps",
        "amount_usd": 500000.0,
        "token": "USDC",
        "direction": "outflow",
        "category": "security_audit",
        "status": "success",
    })

    # Secondary counterparties totaling 700,000.00
    rows.append({
        "tx_signature": "nov_outflow_payroll",
        "block_time": datetime(2024, 11, 15, 12, 0, tzinfo=timezone.utc).isoformat(),
        "source": "Treasury_Vault",
        "destination": "Core_Contributors",
        "amount_usd": 400000.0,
        "token": "USDC",
        "direction": "outflow",
        "category": "payroll",
        "status": "success",
    })
    rows.append({
        "tx_signature": "nov_outflow_infra",
        "block_time": datetime(2024, 11, 18, 9, 15, tzinfo=timezone.utc).isoformat(),
        "source": "Treasury_Vault",
        "destination": "RPC_Infra_Cluster",
        "amount_usd": 200000.0,
        "token": "USDC",
        "direction": "outflow",
        "category": "infrastructure",
        "status": "success",
    })
    rows.append({
        "tx_signature": "nov_outflow_marketing",
        "block_time": datetime(2024, 11, 25, 15, 0, tzinfo=timezone.utc).isoformat(),
        "source": "Treasury_Vault",
        "destination": "Global_Hackathon_Prize",
        "amount_usd": 100000.0,
        "token": "USDC",
        "direction": "outflow",
        "category": "marketing",
        "status": "success",
    })

    # 3. Add background transactions (earlier months & partial current month)
    earlier_start = datetime(2024, 6, 1, tzinfo=timezone.utc)
    for i in range(num_rows - len(rows)):
        # Random date in June-September or December (partial month)
        is_dec = random.random() < 0.2
        if is_dec:
            # December partial month (1st to 14th)
            day = random.randint(1, 14)
            dt = datetime(2024, 12, day, random.randint(0, 23), random.randint(0, 59), tzinfo=timezone.utc)
        else:
            # Summer months
            month = random.randint(6, 9)
            day = random.randint(1, 28)
            dt = datetime(2024, month, day, random.randint(0, 23), random.randint(0, 59), tzinfo=timezone.utc)

        direction = "inflow" if random.random() < 0.4 else "outflow"
        rows.append({
            "tx_signature": f"tx_bg_{i:04d}",
            "block_time": dt.isoformat(),
            "source": f"Account_{random.randint(1, 50)}",
            "destination": f"Account_{random.randint(1, 50)}",
            "amount_usd": round(random.uniform(500.0, 50000.0), 2),
            "token": "USDC" if random.random() < 0.8 else "SOL",
            "direction": direction,
            "category": "operations",
            "status": "success",
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
