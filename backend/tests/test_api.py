"""Comprehensive integration test suite for Analyx API layer."""

from pathlib import Path
import base58
from fastapi.testclient import TestClient
import nacl.signing
import pytest

from backend.db.session import init_db
from backend.main import app

init_db()
client = TestClient(app)


@pytest.fixture(autouse=True, scope="module")
def setup_db() -> None:
    init_db()


@pytest.fixture
def test_wallet_auth() -> tuple[str, str, str]:
    """Helper fixture to create a valid ed25519 wallet and authenticate, returning (wallet, token, workspace_id)."""
    # 1. Generate ed25519 keypair
    signing_key = nacl.signing.SigningKey.generate()
    pubkey_bytes = signing_key.verify_key.encode()
    wallet_address = base58.b58encode(pubkey_bytes).decode()

    # 2. Get nonce
    nonce_resp = client.post("/api/auth/nonce", json={"wallet": wallet_address})
    assert nonce_resp.status_code == 200
    nonce_data = nonce_resp.json()
    challenge_msg = nonce_data["message"]

    # 3. Sign challenge message
    signed = signing_key.sign(challenge_msg.encode("utf-8"))
    sig_b58 = base58.b58encode(signed.signature).decode()

    # 4. Verify signature and get JWT
    verify_resp = client.post(
        "/api/auth/verify",
        json={
            "wallet": wallet_address,
            "signature": sig_b58,
            "message": challenge_msg,
        },
    )
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    token = verify_data["token"]
    workspace_id = verify_data["workspace_id"]

    return wallet_address, token, workspace_id


def test_health_endpoint() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["backend"] == "local"


def test_auth_replay_protection() -> None:
    signing_key = nacl.signing.SigningKey.generate()
    wallet_address = base58.b58encode(signing_key.verify_key.encode()).decode()

    # Nonce
    nonce_resp = client.post("/api/auth/nonce", json={"wallet": wallet_address})
    assert nonce_resp.status_code == 200
    msg = nonce_resp.json()["message"]

    signed = signing_key.sign(msg.encode("utf-8"))
    sig_b58 = base58.b58encode(signed.signature).decode()

    payload = {
        "wallet": wallet_address,
        "signature": sig_b58,
        "message": msg,
    }

    # First verify succeeds
    r1 = client.post("/api/auth/verify", json=payload)
    assert r1.status_code == 200

    # Replay fails (nonce marked used)
    r2 = client.post("/api/auth/verify", json=payload)
    assert r2.status_code == 401


def test_unauthenticated_protected_route() -> None:
    resp = client.get("/api/datasets")
    assert resp.status_code == 401


def test_dataset_upload_and_dictionary(test_wallet_auth: tuple[str, str, str]) -> None:
    wallet, token, workspace_id = test_wallet_auth
    headers = {"Authorization": f"Bearer {token}"}

    sample_csv = Path("fixtures/sales_sample.csv")
    assert sample_csv.exists()

    with open(sample_csv, "rb") as f:
        resp = client.post(
            "/api/datasets/upload",
            files={"file": ("sales_sample.csv", f, "text/csv")},
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "dataset" in data
    assert "version" in data
    assert "profile" in data
    assert "dictionary_proposal" in data

    dataset_id = data["dataset"]["id"]

    # List datasets
    list_resp = client.get("/api/datasets", headers=headers)
    assert list_resp.status_code == 200
    datasets = list_resp.json()
    assert any(d["id"] == dataset_id for d in datasets)

    # Get dataset details
    get_resp = client.get(f"/api/datasets/{dataset_id}", headers=headers)
    assert get_resp.status_code == 200

    # Get profile
    prof_resp = client.get(f"/api/datasets/{dataset_id}/profile", headers=headers)
    assert prof_resp.status_code == 200
    assert "profile" in prof_resp.json()

    # Get dictionary
    dict_resp = client.get(f"/api/datasets/{dataset_id}/dictionary", headers=headers)
    assert dict_resp.status_code == 200
    entries = dict_resp.json()
    assert len(entries) > 0

    first_col = entries[0]["column_name"]
    # Update dictionary
    put_resp = client.put(
        f"/api/datasets/{dataset_id}/dictionary",
        json={"entries": [{"column_name": first_col, "display_name": "Custom Name"}]},
        headers=headers,
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert any(e["column_name"] == first_col and e["display_name"] == "Custom Name" for e in updated)


def test_session_report_and_attestation_flow(test_wallet_auth: tuple[str, str, str]) -> None:
    wallet, token, workspace_id = test_wallet_auth
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create session
    ses_resp = client.post("/api/sessions", json={"title": "Q3 Treasury Review"}, headers=headers)
    assert ses_resp.status_code == 200
    session_id = ses_resp.json()["id"]

    # 2. Post message (SSE)
    msg_resp = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"text": "Summarize treasury net flow"},
        headers=headers,
    )
    assert msg_resp.status_code == 200
    assert "text/event-stream" in msg_resp.headers["content-type"]
    assert "data:" in msg_resp.text

    # 3. Generate report
    rep_resp = client.post(f"/api/sessions/{session_id}/report", headers=headers)
    assert rep_resp.status_code == 200
    report_data = rep_resp.json()
    report_id = report_data["id"]
    report_md = report_data["markdown_content"]

    # 4. Export report markdown
    exp_resp = client.get(f"/api/reports/{report_id}/export?format=md", headers=headers)
    assert exp_resp.status_code == 200
    assert exp_resp.text == report_md

    # 5. Prepare attestation
    att_resp = client.post(
        f"/api/reports/{report_id}/attestation/prepare",
        json={"signer": wallet, "cluster": "devnet"},
        headers=headers,
    )
    assert att_resp.status_code == 200
    prep_data = att_resp.json()
    bundle = prep_data["bundle"]
    root = prep_data["root"]
    assert "analyx:v1:" in prep_data["memo"]

    # 6. Confirm attestation (with mock signature)
    conf_resp = client.post(
        f"/api/reports/{report_id}/attestation/confirm",
        json={"tx_signature": "mock_solana_tx_sig", "cluster": "devnet"},
        headers=headers,
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["status"] == "confirmed"

    # 7. Public verify endpoint
    # A) Valid verify
    ver_resp = client.post(
        "/api/verify",
        json={
            "bundle": bundle,
            "report_markdown": report_md,
            "tx_signature": "mock_solana_tx_sig",
            "cluster": "devnet",
        },
    )
    assert ver_resp.status_code == 200
    v_data = ver_resp.json()
    assert v_data["status"] == "VERIFIED"

    # B) Tampered report -> MODIFIED
    tampered_resp = client.post(
        "/api/verify",
        json={
            "bundle": bundle,
            "report_markdown": report_md + "\n[TAMPERED CONTENT]",
            "tx_signature": "mock_solana_tx_sig",
            "cluster": "devnet",
        },
    )
    assert tampered_resp.status_code == 200
    assert tampered_resp.json()["status"] == "MODIFIED"
