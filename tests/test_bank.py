from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from tellerline.actions import Action
from tellerline.bank.api import create_app
from tellerline.bank.client import BankClient
from tellerline.bank.data import iban, iban_is_valid
from tellerline.banking.responses import respond

TODAY = date(2026, 9, 14)


@pytest.fixture
def app():
    return create_app(":memory:", today=TODAY)


@pytest.fixture
def api(app):
    return TestClient(app)


@pytest.fixture
async def bank(app):
    client = BankClient(
        client=httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://bank")
    )
    yield client
    await client.close()


def test_ibans_are_valid_irish_format():
    value = iban("00010001")
    assert value.startswith("IE") and len(value) == 22
    assert iban_is_valid(value)
    assert not iban_is_valid(value[:-1] + ("2" if value[-1] != "2" else "3"))


def test_verification_needs_matching_number_and_birthday(api):
    ok = api.post(
        "/v1/identity/verify", json={"customer_number": "45127890", "date_of_birth": "1991-03-03"}
    )
    assert ok.json() == {"verified": True, "customer_id": "cus_0001", "first_name": "Aoife"}
    wrong = api.post(
        "/v1/identity/verify", json={"customer_number": "45127890", "date_of_birth": "1991-03-04"}
    )
    assert wrong.json() == {"verified": False}


def test_verification_rejects_malformed_numbers(api):
    response = api.post(
        "/v1/identity/verify", json={"customer_number": "1234", "date_of_birth": "1991-03-03"}
    )
    assert response.status_code == 422


def test_balance_and_transactions(api):
    balance = api.get("/v1/customers/cus_0001/accounts/current/balance").json()
    assert balance["balance_eur"] == 1250.40
    assert balance["available_eur"] == 1180.40
    items = api.get(
        "/v1/customers/cus_0001/accounts/current/transactions", params={"count": 4}
    ).json()
    dates = [t["date"] for t in items["transactions"]]
    assert len(dates) == 4 and dates == sorted(dates, reverse=True)


def test_unknown_customer_and_card_are_404_with_error_codes(api):
    assert api.get("/v1/customers/cus_9999/accounts/current/balance").json()["detail"] == {
        "error": "customer_not_found"
    }
    response = api.post("/v1/customers/cus_0001/cards/9999/freeze", json={"reason": "lost"})
    assert response.status_code == 404
    assert response.json()["detail"] == {"error": "card_not_found"}


def test_dispute_references_are_unique(api):
    body = {"merchant": "StreamFlix", "amount": 49.99, "date": "2026-09-02"}
    first = api.post("/v1/customers/cus_0001/disputes", json=body).json()
    second = api.post("/v1/customers/cus_0001/disputes", json=body).json()
    assert first["case_reference"] != second["case_reference"]


def test_dispute_date_must_be_within_the_last_year(api):
    body = {"merchant": "Aldi", "amount": 10, "date": "2027-01-01"}
    response = api.post("/v1/customers/cus_0001/disputes", json=body)
    assert response.json()["detail"] == {"error": "dispute_date_out_of_range"}


async def test_client_refuses_banking_before_verification(bank):
    with pytest.raises(PermissionError):
        await bank.run(Action("get_balance", {"account": "current"}))


async def test_client_runs_a_verified_call(bank):
    verified = await bank.run(
        Action("verify_identity", {"customer_number": "45127890", "date_of_birth": "1991-03-03"})
    )
    assert verified["verified"] and bank.customer_id == "cus_0001"

    frozen = await bank.run(Action("freeze_card", {"card_last_four": "4217", "reason": "stolen"}))
    assert frozen["status"] == "frozen"

    missing = await bank.run(Action("freeze_card", {"card_last_four": "9999", "reason": "lost"}))
    spoken = respond("freeze_card", {"card_last_four": "9999"}, missing, TODAY)
    assert spoken.startswith(
        "Sorry, I can't find that card. There's no card ending nine nine nine nine"
    )


async def test_other_customers_cards_are_not_reachable(bank):
    await bank.run(
        Action("verify_identity", {"customer_number": "45127890", "date_of_birth": "1991-03-03"})
    )
    # 5561 belongs to Cian Murphy, not Aoife.
    result = await bank.run(Action("freeze_card", {"card_last_four": "5561", "reason": "lost"}))
    assert result == {"error": "card_not_found"}


async def test_handoff_works_before_verification(bank):
    assert (await bank.run(Action("transfer_to_human", {})))["status"] == "queued"


def test_found_cards_can_be_unfrozen_but_stolen_ones_cannot(api):
    base = "/v1/customers/cus_0001/cards"
    api.post(f"{base}/4217/freeze", json={"reason": "temporary"})
    assert api.post(f"{base}/4217/unfreeze").json() == {"status": "active", "changed": True}
    assert api.post(f"{base}/4217/unfreeze").json() == {"status": "active", "changed": False}

    api.post(f"{base}/0093/freeze", json={"reason": "stolen"})
    refused = api.post(f"{base}/0093/unfreeze").json()
    assert refused == {"status": "frozen", "changed": False, "freeze_reason": "stolen"}


def test_card_status_reports_the_freeze_and_the_replacement(api):
    base = "/v1/customers/cus_0001/cards/4217"
    assert api.get(base).json() == {
        "status": "active",
        "freeze_reason": None,
        "replacement_ordered_on": None,
        "replacement_arrives_by": None,
    }
    api.post(f"{base}/freeze", json={"reason": "lost"})
    api.post(f"{base}/replacement")
    status = api.get(base).json()
    assert status["status"] == "frozen" and status["freeze_reason"] == "lost"
    # Ordered Monday 14 September: five working days later is Monday 21 September.
    assert status["replacement_ordered_on"] == "2026-09-14"
    assert status["replacement_arrives_by"] == "2026-09-21"


def test_working_days_skip_the_weekend():
    from tellerline.bank.api import add_working_days

    assert add_working_days(date(2026, 9, 11), 1) == date(2026, 9, 14)  # Friday -> Monday
    assert add_working_days(date(2026, 9, 14), 5) == date(2026, 9, 21)


async def test_client_unfreezes_and_reads_card_status(bank):
    await bank.run(
        Action("verify_identity", {"customer_number": "45127890", "date_of_birth": "1991-03-03"})
    )
    await bank.run(Action("freeze_card", {"card_last_four": "4217", "reason": "temporary"}))
    status = await bank.run(Action("get_card_status", {"card_last_four": "4217"}))
    assert status["status"] == "frozen"
    unfrozen = await bank.run(Action("unfreeze_card", {"card_last_four": "4217"}))
    assert unfrozen == {"status": "active", "changed": True}
