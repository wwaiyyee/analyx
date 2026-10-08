"""Unit tests for canonical hashing, JCS, and table hashing."""

import json
from pathlib import Path
import pytest

from backend.core.errors import FloatNotAllowedError
from backend.core.hashing import (
    attestation_root,
    canonical_table_hash,
    hash_obj,
    jcs,
    sha256_hex,
)


def get_fixtures_path() -> Path:
    # Look for fixtures/ relative to repo root
    current = Path(__file__).resolve().parent
    for p in [current.parent.parent / "fixtures", current.parent / "fixtures"]:
        if p.exists():
            return p
    return Path("fixtures")


def test_hashing_vectors() -> None:
    vectors_file = get_fixtures_path() / "test_hashing_vectors.json"
    assert vectors_file.exists(), f"Vectors file missing: {vectors_file}"

    with open(vectors_file, "r", encoding="utf-8") as f:
        vectors = json.load(f)

    assert len(vectors) >= 10, "Must have at least 10 test vectors"

    for vec in vectors:
        name = vec["name"]
        inp = vec["input"]
        reject_float = vec.get("reject_float", False)

        if reject_float:
            with pytest.raises(FloatNotAllowedError):
                jcs(inp)
            with pytest.raises(FloatNotAllowedError):
                hash_obj(inp)
        else:
            canonical_bytes = jcs(inp)
            expected_json = vec["canonical_json"]
            assert (
                canonical_bytes.decode("utf-8") == expected_json
            ), f"Failed canonical JSON for {name}"

            computed_hash = hash_obj(inp)
            assert computed_hash == vec["hash"], f"Failed hash for {name}"


def test_float_rejection_nested() -> None:
    # Directly rejected at top-level, in array, and in deep dict
    with pytest.raises(FloatNotAllowedError):
        jcs(3.14159)

    with pytest.raises(FloatNotAllowedError):
        jcs({"amount": 100.5})

    with pytest.raises(FloatNotAllowedError):
        jcs({"data": [{"nested": [1, 2.0]}]})


def test_canonical_table_hash_order_invariance() -> None:
    # Table hash must be independent of row arrival order
    table_a = [
        {"id": "1", "name": "Alice", "amount": 100, "active": True},
        {"id": "2", "name": "Bob", "amount": 200, "active": False},
        {"id": "3", "name": "Charlie", "amount": 300, "active": True},
    ]

    table_b = [
        {"id": "3", "name": "Charlie", "amount": 300, "active": True},
        {"id": "1", "name": "Alice", "amount": 100, "active": True},
        {"id": "2", "name": "Bob", "amount": 200, "active": False},
    ]

    cols = ["id", "name", "amount", "active"]
    hash_a = canonical_table_hash(table_a, columns=cols)
    hash_b = canonical_table_hash(table_b, columns=cols)

    assert hash_a == hash_b
    assert len(hash_a) == 64


def test_canonical_table_hash_detects_mutation() -> None:
    table = [
        {"id": "1", "name": "Alice", "amount": 100},
        {"id": "2", "name": "Bob", "amount": 200},
    ]
    cols = ["id", "name", "amount"]
    base_hash = canonical_table_hash(table, cols)

    # Change value
    mutated = [
        {"id": "1", "name": "Alice", "amount": 101},
        {"id": "2", "name": "Bob", "amount": 200},
    ]
    assert canonical_table_hash(mutated, cols) != base_hash

    # Change column schema order
    assert canonical_table_hash(table, ["amount", "id", "name"]) != base_hash


def test_attestation_root() -> None:
    bundle = {
        "version": 1,
        "report": {"id": "rp_test", "sha256": "0" * 64},
        "signer": "wallet123",
        "created_at": "2026-10-08T00:00:00Z",
    }

    root1 = attestation_root(bundle)
    assert len(root1) == 64

    # Permuted bundle keys must yield identical root
    bundle_permuted = {
        "signer": "wallet123",
        "created_at": "2026-10-08T00:00:00Z",
        "version": 1,
        "report": {"sha256": "0" * 64, "id": "rp_test"},
    }
    root2 = attestation_root(bundle_permuted)
    assert root1 == root2
