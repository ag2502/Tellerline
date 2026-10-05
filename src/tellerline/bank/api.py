"""HTTP API of the mock bank.

Account endpoints are scoped to a customer id, which the agent only learns from a successful
identity check, so the agent can never read or change another customer's data by asking.

Run it with:
    python -m tellerline.bank --port 8090
"""

import sqlite3
import threading
from datetime import date, timedelta
from functools import wraps
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from tellerline.bank.data import connect, seed

Account = Literal["current", "savings"]
FreezeReason = Literal["lost", "stolen", "suspicious_activity", "temporary"]

REPLACEMENT_WORKING_DAYS = 5
QUEUE_WAIT_MINUTES = 3
# A caller who finds a card can unfreeze it. A card frozen as stolen or for suspicious payments
# may have been copied, so it stays blocked and is replaced instead.
UNFREEZABLE_REASONS = ("lost", "temporary")


class VerifyRequest(BaseModel):
    customer_number: str = Field(pattern=r"^\d{8}$")
    date_of_birth: date


class FreezeRequest(BaseModel):
    reason: FreezeReason = "lost"


class DisputeRequest(BaseModel):
    merchant: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0, le=100_000)
    date: date


class HandoffRequest(BaseModel):
    customer_id: str | None = None
    reason: str | None = Field(default=None, max_length=300)


def _not_found(error: str) -> HTTPException:
    return HTTPException(status_code=404, detail={"error": error})


def add_working_days(start: date, days: int) -> date:
    """The date ``days`` working days (Monday to Friday) after ``start``."""
    current = start
    while days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days -= 1
    return current


class _LockedConnection:
    """The bank's SQLite connection, one request at a time.

    FastAPI runs these endpoints on a thread pool, so with several calls at once two requests
    could use the connection together, and two disputes opened at the same moment could draw the
    same reference. Each endpoint holds the lock for its whole read-modify-write.
    """

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.lock = threading.RLock()

    def execute(self, *args):
        return self.connection.execute(*args)

    def commit(self):
        self.connection.commit()


def create_app(db_path: Path | str = ":memory:", today: date | None = None) -> FastAPI:
    today = today or date.today()
    db = _LockedConnection(connect(db_path))
    seed(db.connection, today)
    app = FastAPI(title="Tellerline mock bank", version="1.0")

    def locked(endpoint):
        @wraps(endpoint)
        def run(*args, **kwargs):
            with db.lock:
                return endpoint(*args, **kwargs)

        return run

    def customer_or_404(customer_id: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if row is None:
            raise _not_found("customer_not_found")
        return row

    def account_or_404(customer_id: str, kind: Account) -> sqlite3.Row:
        customer_or_404(customer_id)
        row = db.execute(
            "SELECT * FROM accounts WHERE customer_id = ? AND kind = ?", (customer_id, kind)
        ).fetchone()
        if row is None:
            raise _not_found("account_not_found")
        return row

    def card_or_404(customer_id: str, last_four: str) -> sqlite3.Row:
        customer_or_404(customer_id)
        row = db.execute(
            "SELECT * FROM cards WHERE customer_id = ? AND last_four = ?", (customer_id, last_four)
        ).fetchone()
        if row is None:
            raise _not_found("card_not_found")
        return row

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/v1/identity/verify")
    @locked
    def verify(request: VerifyRequest) -> dict:
        row = db.execute(
            "SELECT id, first_name FROM customers WHERE customer_number = ? AND date_of_birth = ?",
            (request.customer_number, request.date_of_birth.isoformat()),
        ).fetchone()
        if row is None:
            return {"verified": False}
        return {"verified": True, "customer_id": row["id"], "first_name": row["first_name"]}

    @app.get("/v1/customers/{customer_id}/accounts/{kind}/balance")
    @locked
    def balance(customer_id: str, kind: Account) -> dict:
        account = account_or_404(customer_id, kind)
        return {
            "account": kind,
            "balance_eur": account["balance_cents"] / 100,
            "available_eur": account["available_cents"] / 100,
        }

    @app.get("/v1/customers/{customer_id}/accounts/{kind}/transactions")
    @locked
    def transactions(customer_id: str, kind: Account, count: int = 3) -> dict:
        account = account_or_404(customer_id, kind)
        rows = db.execute(
            "SELECT posted_on, merchant, amount_cents FROM transactions WHERE account_id = ? "
            "ORDER BY posted_on DESC, id DESC LIMIT ?",
            (account["id"], max(1, min(count, 10))),
        ).fetchall()
        return {
            "account": kind,
            "transactions": [
                {
                    "date": r["posted_on"],
                    "merchant": r["merchant"],
                    "amount_eur": r["amount_cents"] / 100,
                }
                for r in rows
            ],
        }

    @app.post("/v1/customers/{customer_id}/cards/{last_four}/freeze")
    @locked
    def freeze(customer_id: str, last_four: str, request: FreezeRequest) -> dict:
        card = card_or_404(customer_id, last_four)
        db.execute(
            "UPDATE cards SET status = 'frozen', freeze_reason = ? WHERE id = ?",
            (request.reason, card["id"]),
        )
        db.commit()
        return {"status": "frozen", "reason": request.reason}

    @app.post("/v1/customers/{customer_id}/cards/{last_four}/unfreeze")
    @locked
    def unfreeze(customer_id: str, last_four: str) -> dict:
        card = card_or_404(customer_id, last_four)
        if card["status"] != "frozen":
            return {"status": card["status"], "changed": False}
        if card["freeze_reason"] not in UNFREEZABLE_REASONS:
            return {"status": "frozen", "changed": False, "freeze_reason": card["freeze_reason"]}
        db.execute(
            "UPDATE cards SET status = 'active', freeze_reason = NULL WHERE id = ?", (card["id"],)
        )
        db.commit()
        return {"status": "active", "changed": True}

    @app.get("/v1/customers/{customer_id}/cards/{last_four}")
    @locked
    def card_status(customer_id: str, last_four: str) -> dict:
        card = card_or_404(customer_id, last_four)
        ordered = card["replacement_ordered_on"]
        arrives = (
            add_working_days(date.fromisoformat(ordered), REPLACEMENT_WORKING_DAYS).isoformat()
            if ordered
            else None
        )
        return {
            "status": card["status"],
            "freeze_reason": card["freeze_reason"],
            "replacement_ordered_on": ordered,
            "replacement_arrives_by": arrives,
        }

    @app.post("/v1/customers/{customer_id}/cards/{last_four}/replacement")
    @locked
    def replacement(customer_id: str, last_four: str) -> dict:
        card = card_or_404(customer_id, last_four)
        db.execute(
            "UPDATE cards SET replacement_ordered_on = ? WHERE id = ?",
            (today.isoformat(), card["id"]),
        )
        db.commit()
        return {"status": "ordered", "arrives_in_working_days": REPLACEMENT_WORKING_DAYS}

    @app.post("/v1/customers/{customer_id}/disputes")
    @locked
    def dispute(customer_id: str, request: DisputeRequest) -> dict:
        customer_or_404(customer_id)
        if request.date > today or request.date < today - timedelta(days=365):
            raise HTTPException(status_code=422, detail={"error": "dispute_date_out_of_range"})
        count = db.execute("SELECT COUNT(*) FROM disputes").fetchone()[0]
        reference = f"DSP-{20417 + count}"
        db.execute(
            "INSERT INTO disputes (reference, customer_id, merchant, amount_cents, "
            "transaction_date, opened_on) VALUES (?, ?, ?, ?, ?, ?)",
            (
                reference,
                customer_id,
                request.merchant,
                round(request.amount * 100),
                request.date.isoformat(),
                today.isoformat(),
            ),
        )
        db.commit()
        return {"status": "opened", "case_reference": reference}

    @app.post("/v1/handoffs")
    @locked
    def handoff(request: HandoffRequest) -> dict:
        if request.customer_id is not None:
            customer_or_404(request.customer_id)
        db.execute(
            "INSERT INTO handoffs (customer_id, reason, created_on) VALUES (?, ?, ?)",
            (request.customer_id, request.reason, today.isoformat()),
        )
        db.commit()
        return {"status": "queued", "estimated_wait_minutes": QUEUE_WAIT_MINUTES}

    return app
